设备驱动设计与实现
=========================================

本节导读
-----------------------------------------

QEMU中的外设
-----------------------------------------
首先，我们需要了解OS管理的计算机硬件系统-- ``QEMU riscv-64 virt machine`` 。这表示了一台虚拟的RISC-V 64计算机，CPU的个数是可以通过参数 ``-cpu num`` 配置的，内存也是可通过参数 ``-m numM/G`` 来配置。这是标配信息，还有很多外设信息，QEMU 可以把它模拟的机器细节信息全都导出到dtb格式的二进制文件中，并可通过 ``dtc`` Device Tree Compiler工具转成可理解的文本文件。如想详细了解这个文件的格式说明可以参考  `Devicetree Specification <https://buildmedia.readthedocs.org/media/pdf/devicetree-specification/latest/devicetree-specification.pdf>`_ 。

.. code-block:: console

   $ qemu-system-riscv64 -machine virt -machine dumpdtb=riscv64-virt.dtb -bios default

   qemu-system-riscv64: info: dtb dumped to riscv64-virt.dtb. Exiting.

   $ dtc -I dtb -O dts -o riscv64-virt.dts riscv64-virt.dtb

   $ less riscv64-virt.dts
   #就可以看到QEMU RV64 virt计算机的详细硬件（包括各种外设）细节，包括CPU，内存，串口，时钟和各种virtio设备的信息。

平台级中断控制器
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

在RISC-V中，与外设连接的I/O控制器的一个重要组成是平台级中断控制器（Platform-Level Interrupt Controller，PLIC），它汇聚了各种外设的中断信号，并连接到CPU的外部中断引脚上。通过RISC-V的 ``mie`` 寄存器中的 ``meie`` 位，可以控制这个引脚是否接收外部中断信号。当然，通过RISC-V中M Mode的中断委托机制，也可以在RISC-V的S Mode下，通过 ``sie`` 寄存器中的 ``seie`` 位，对中断信号是否接收进行控制。

CPU可以通过MMIO方式来对PLIC进行管理，下面是一下与PLIC相关的寄存器：

.. code-block:: console

    寄存器	        地址    	功能描述
    Priority   0x0c00_0000	 设置特定中断源的优先级
    Pending	   0x0c00_1000   包含已触发（正在处理）的中断列表
    Enable	   0x0c00_2000	 启用/禁用某些中断源
    Threshold  0x0c20_0000	 设置中断能够触发的阈值
    Claim      0x0c20_0004	 按优先级顺序返回下一个中断
    Complete   0x0c20_0004	 写操作表示完成对特定中断的处理

在QEMU ``qemu/include/hw/riscv/virt.h`` 的源码中，可以看到

.. code-block:: C

    enum {
        UART0_IRQ = 10,
        RTC_IRQ = 11,
        VIRTIO_IRQ = 1, /* 1 to 8 */
        VIRTIO_COUNT = 8,
        PCIE_IRQ = 0x20, /* 32 to 35 */
        VIRTIO_NDEV = 0x35 /* Arbitrary maximum number of interrupts */
    };


可以看到串口UART0的中断号是10，virtio设备的中断号是1~8。通过 ``dtc`` Device Tree Compiler工具生成的文本文件，我们也可以发现上述中断信号信息，以及基于MMIO的外设寄存器信息。在后续的设备驱动中，这些信息我们可以用到。


操作系统如要响应外设的中断，需要做两方面的初始化工作。首先是完成第三章讲解的中断初始化过程，并需要把 ``sie`` 寄存器中的 ``seie`` 位设置为1，让CPU能够接收通过PLIC传来的外部设备中断信号。然后还需要通过MMIO方式对PLIC的寄存器进行初始设置，才能让外设产生的中断传到CPU处。其主要操作包括：

- 设置外设中断的优先级
- 设置外设中断的阈值，优先级小于等于阈值的中断会被屏蔽
- 激活外设中断，即把 ``Enable`` 寄存器的外设中断编号为索引的位设置为1

但外设产生中断后，CPU并不知道具体是哪个设备传来的中断，这可以通过读PLIC的 ``Claim`` 寄存器来了解。 ``Claim`` 寄存器会返回PLIC接收到的优先级最高的中断；如果没有外设中断产生，读 ``Claim`` 寄存器会返回 0。

操作系统在收到中断并完成中断处理后，还需通过PLIC中断处理完毕，即CPU需要在PLIC的 ``Complete`` 寄存器中写入对应中断号为索引的位，告知PLIC自己已经处理完毕。

上述操作的具体实现，可以参考 ``plic.rs`` 中的代码。

串口设备
------------------------------------

串口（Universal Asynchronous Receiver-Transmitter，简称UART）是一种在嵌入式系统中常用的用于传输、接收系列数据的外部设备。串行数据传输是逐位（bit）顺序发送数据的过程。

我们在第一章其实就接触了串口，但当时是通过RustSBI来帮OS完成对串口的访问，即OS只需发出两种SBI调用请求就可以输出和获取字符了。但这种便捷性是有代价的。比如OS在调用获取字符的SBI调用请求后，RustSBI如果没收到串口字符，会返回 ``-1`` ，这样OS只能采用类似轮询的方式来继续查询。到第七章为止的串口驱动不支持中断是导致在多进程情况下，系统效率低下的主要原因之一。大家也不要遗憾，我们的第一阶段的目标是 **Just do it** ，先把OS做出来，在第二阶段再逐步优化改进。

接下来，我们就需要开始尝试脱离RustSBI的帮助，在操作系统中完成支持中断机制的串口驱动。

通过查找 ``dtc`` 工具生成的 ``riscv64-virt.dts`` 文件，我们可以看到串口设备相关的MMIO模式的寄存器信息和中断相关信息。


.. code-block:: shell
   
   ...
   chosen {
     bootargs = [00];
     stdout-path = "/uart@10000000";
   };

   uart@10000000 {
     interrupts = <0x0a>;
     interrupt-parent = <0x02>;
     clock-frequency = <0x384000>;
     reg = <0x00 0x10000000 0x00 0x100>;
     compatible = "ns16550a";
   };


``chosen`` 节点的内容表明字符输出会通过串口设备打印出来。``uart@10000000`` 节点表明串口设备中寄存器的MMIO起始地址为 ``0x10000000`` ，范围在 ``0x00~0x100`` 区间内，中断号为 ``0x0a`` 。 ``clock-frequency`` 表示时钟频率，其值为0x38400 ，即3.6864 MHz。 ``compatible =“ ns16550a” `` 表示串口的硬件规范兼容NS16550A。

在如下情况下，串口会产生中断：

- 有新的输入数据进入串口的接收缓存
- 串口完成了缓存中数据的发送
- 串口发送出现错误

这里我们仅关注有输入数据时串口产生的中断。

了解QEMU模拟的兼容NS16550A硬件规范是写驱动程序的准备工作。在 UART 中，可访问的 I/O寄存器一共有8个。访问I/O寄存器的方法把串口寄存器的MMIO其实地址加上偏移量，就是各个寄存器的MMIO地址了。

串口设备初始化
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~


第一步是对串口进行初始化设置：

.. code-block:: Rust

    let ptr = UART_ADDR as *mut u8;
    // 偏移 3 指出每次传输的位数为 8 位，即一个字节
    ptr.add(3).write_volatile(8);
    // 使能 FIFO缓冲队列
    ptr.add(2).write_volatile(1);
    // 使能中断
    ptr.add(1).write_volatile(1);
    // 设置输入产生的中断频率
    let divisor : u16 = 592;
    let divisor_least: u8 = (divisor & 0xff).try_into().unwrap();
    let divisor_most:  u8 = (divisor >> 8).try_into().unwrap();
    let lcr = ptr.add(3).read_volatile();
    ptr.add(3).write_volatile(lcr | 1 << 7);
    
    ptr.add(0).write_volatile(divisor_least);
    ptr.add(1).write_volatile(divisor_most);
    ptr.add(3).write_volatile(lcr);


上述代码完成的主要工作包括：
1. 设置每次传输的位数为 8 位，即一个 ASCII 码的大小
2. 激活先进先出队列
3. 使能中断，这意味着我们的输入可以通过中断进行通知
4. 设置输入产生的中断频率


串口设备输入输出操作
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

先看串口输出，由于不设置和处理输出后产生中断的情况，使得整个输出操作比较简单。即向偏移量为 ``0`` 的串口控制寄存器的MMIO地址写8位字符即可。

.. code-block:: Rust

   let ptr = UART_ADDR as *mut u8;
   ptr.add(0).write_volatile(c);

但对于串口输入的处理，由于要考虑中断，相对就要复杂一些。对于操作系统的一般处理过程是，首先是能接收中断，即在 ``trap_handler`` 中通过访问 ``scause`` 寄存器，能够识别出有外部中断产生。然后再进一步通过读PLIC的 ``Claim`` 寄存器来了解是否是收到了串口发来的输入中断。如果确定是，就通过对串口寄存器的偏移量为 ``0`` 的串口控制寄存器的MMIO地址进行读一个字节的操作，从而获得通过串口输入的字符。

在我们的具体实现中，与上述的一般中断处理过程不太一样。首先操作系统通过自定义的 ``SBI_DEVICE_HANDLER`` SBI调用，告知RustSBI在收到外部中断后，要跳转到到的操作系统中处理外部中断的函数 ``device_trap_handler`` 。这样，在外部中断产生后，先由RustSBI在M Mode下接收的，并转到S Mode，交由 ``device_trap_handler`` 内核函数进一步处理。


对进程管理的改进
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

这里可以对进程管理做的一个改进是，如果一个进程通过系统调用想获取串口输入，但此时串口还没有输入的字符，那么这个进程就可以进入等待状态。


virtio设备
-----------------------------------------


virtio字符设备
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~


virtio块设备
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~


virtio显示设备
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~