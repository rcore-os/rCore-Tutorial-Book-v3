外设平台与串口驱动程序
=========================================

本节导读
-----------------------------------------

本节首先讲述了驱动程序要完成的主要功能，包括初始化设备，接收用户进程的I/O请求并给设备发出I
/O命令，响应设备发出的通知，完成用户进程的I/O请求。然后介绍了计算机硬件系统中除了CPU/内存之外的其他重要的外设和相关I/O控制器，以及如何通过编程来获取外设相关信息。最后介绍了一个具体的物理设备串口的驱动程序的设计与实现。

驱动程序概述
----------------------------------------

从操作系统架构上看，驱动程序与I/O设备靠的更近，离应用程序更远，这使得驱动程序需要站在协助所有进程的全局角度来处理各种I/O操作。这也就意味着在驱动程序的设计实现中，尽量不要与单个进程建立直接的联系，而是在全局角度对I/O设备进行统一处理。

上面只是介绍了CPU和I/O设备之间的交互手段。如果从操作系统角度来看，我们还需要对特定设备编写驱动程序。它一般需要完成如下一些功能：

1. 设备初始化，即完成对设备的初始配置，分配I/O操作所需的内存，设置好中断处理例程
2. 如果设备会产生中断，需要有处理这个设备中断的中断处理例程（Interrupt Handler）
3. 根据操作系统上层模块（如文件系统）的要求（如读磁盘数据），给I/O设备发出命令
4. 与操作系统上层模块进行交互，完成上层模块的要求（如上传读出的磁盘数据）

从驱动程序I/O操作的执行模式上看，主要有两种模式的I/O操作：异步和同步。同步模式下的处理逻辑类似函数调用，从应用程序发出I/O请求，通过同步的系统调用传递到操作系统内核中，操作系统内核的各个层级进行相应处理，并最终把相关的I/O操作命令转给了驱动程序。一般情况下，驱动程序完成相应的I/O操作会比较慢（相对于CPU而言），所以操作系统会让代表应用程序的进程进入等待状态，进行进程切换。但相应的I/O操作执行完毕后（操作系统通过轮询或中断方式感知），操作系统会在合适的时机唤醒等待的进程，从而进程能够继续执行。

异步I/O操作是一个效率更高的执行模式，即应用程序发出I/O请求后，并不会等待此I/O操作完成，而是继续处理应用程序的其它任务（这个任务切换会通过运行时库或操作系统来完成）。调用异步I/O操作的应用程序需要通过某种方式（比如某种异步通知机制）来确定I/O操作何时完成。这部分可以通过协程技术来实现，但目前我们不会就此展开讨论。

编写驱动程序代码需要注意规避三方面的潜在风险的技术准备措施：

1. 了解硬件规范：从而能够正确地与硬件交互，并能处理访问硬件出错的情况；
2. 了解操作系统，由于驱动程序与它所管理的设备会同时执行，也可能与操作系统其他模块并行/并发访问相关共享资源，所以需要考虑同步互斥的问题（后续会深入讲解操作系统同步互斥机制），并考虑到申请资源失败后的处理；
3. 理解驱动程序执行中所在的可能的上下文环境：如果是在进行中断处理（如在执行 ``trap_handler`` 函数），那是在中断上下文中执行；如果是在代表进程的内核线程中执行后续的I/O操作（如收发TCP包），那是在内核线程上下文执行。这样才能写出正确的驱动程序。


硬件系统架构
-----------------------------------------

设备树
~~~~~~~~~~~~~~~~~~~~~~~

首先，我们需要了解OS管理的计算机硬件系统-- ``QEMU riscv-64 virt machine`` 。这表示了一台虚拟的RISC-V 64计算机，CPU的个数是可以通过参数 ``-cpu num`` 配置的，内存也是可通过参数 ``-m numM/G`` 来配置。这是标配信息。这台虚拟计算机还有很多外设信息，每个设备在物理上连接到了父设备上最后再通过总线等连接起来构成一整个设备树。QEMU 可以把它模拟的机器细节信息全都导出到dtb格式的二进制文件中，并可通过 ``dtc`` （Device Tree Compiler）工具转成可理解的文本文件。如想详细了解这个文件的格式说明可以参考  `Devicetree Specification <https://buildmedia.readthedocs.org/media/pdf/devicetree-specification/latest/devicetree-specification.pdf>`_ 。

.. code-block:: console

   $ qemu-system-riscv64 -machine virt -machine dumpdtb=riscv64-virt.dtb -bios default

   qemu-system-riscv64: info: dtb dumped to riscv64-virt.dtb. Exiting.

   $ dtc -I dtb -O dts -o riscv64-virt.dts riscv64-virt.dtb

   $ less riscv64-virt.dts
   #就可以看到QEMU RV64 virt计算机的详细硬件（包括各种外设）细节，包括CPU，内存，串口，时钟和各种virtio设备的信息。
   

一个典型的设备树如下图所示：

.. image:: device-tree.png
   :align: center
   :name: device-tree



**[info] 设备节点属性**

设备树的每个节点上都描述了对应设备的信息，如支持的协议是什么类型等等。而操作系统就是通过这些节点上的信息来实现对设备的识别的。具体而言，一个设备节点上会有几个标准属性，这里简要介绍我们需要用到的几个：

  - compatible：该属性指的是该设备的编程模型，一般格式为 "manufacturer,model"，分别指一个出厂标签和具体模型。如 "virtio,mmio" 指的是这个设备通过 virtio 协议、MMIO（内存映射 I/O）方式来驱动
  - model：指的是设备生产商给设备的型号
  - reg：当一些很长的信息或者数据无法用其他标准属性来定义时，可以用 reg 段来自定义存储一些信息
      
传递设备树信息
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

操作系统在启动后需要了解计算机系统中所有接入的设备，这就要有一个读取全部已接入设备信息的能力，而设备信息放在哪里，又是谁帮我们来做的呢？在 RISC-V 中，这个一般是由 bootloader，即 OpenSBI or RustSBI 固件完成的。它来完成对于包括物理内存在内的各外设的探测，将探测结果以 **设备树二进制对象（DTB，Device Tree Blob）** 的格式保存在物理内存中的某个地方。然后bootloader会启动操作系统，即把放置DTB的物理地址将放在 ``a1`` 寄存器中，而将会把 HART ID （**HART，Hardware Thread，硬件线程，可以理解为执行的 CPU 核**）放在 ``a0`` 寄存器上，然后跳转到操作系统的入口地址处继续执行。例如，我们可以查看 ``virtio_drivers`` crate中的在裸机环境下使用驱动程序的例子。我们只需要给 `rust_main` 函数增加两个参数（即 ``a0`` 和 ``a1`` 寄存器中的值 ）即可：

.. code-block:: Rust

   //virtio_drivers/examples/riscv/src/main.rs
   #[no_mangle]
   extern "C" fn main(_hartid: usize, device_tree_paddr: usize) {
      ...
      init_dt(device_tree_paddr);
      ...
   }

这样测试用例就获得了bootloader传来的放置DTB的物理地址。

解析设备树信息
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

对于解析设备树中的各种属性，我们不需要自己来实现这件事情，可以直接调用 `rCore 中 device_tree 库 <https://github.com/rcore-os/device_tree-rs">`_ ，然后遍历树上节点即可：

.. code-block:: Rust

   // 遍历设备树并初始化设备
   fn init_dt(dtb: usize) {
      info!("device tree @ {:#x}", dtb);
      // 整个设备树的 Headers（用于验证和读取）
      #[repr(C)]
      struct DtbHeader {
         be_magic: u32,
         be_size: u32,
      }
      let header = unsafe { &*(dtb as *const DtbHeader) };
      // from_be 是大小端序的转换（from big endian）
      let magic = u32::from_be(header.be_magic);
      const DEVICE_TREE_MAGIC: u32 = 0xd00dfeed;
      // 验证 Device Tree Magic Number
      assert_eq!(magic, DEVICE_TREE_MAGIC);
      let size = u32::from_be(header.be_size);
      // 拷贝dtb数据
      let dtb_data = unsafe { core::slice::from_raw_parts(dtb as *const u8, size as usize) };
      // 加载dtb数据
      let dt = DeviceTree::load(dtb_data).expect("failed to parse device tree");
      // 遍历dtb数据
      walk_dt_node(&dt.root);
   }

起始时有一步是验证 Magic Number，这是为了保证系统可靠性，验证这段内存是否存放了设备树信息。在遍历过程中，一旦发现了一个支持 "virtio,mmio" 的设备（其实就是 QEMU 模拟的各种virtio设备），就进入下一步加载驱动的逻辑。具体遍历设备树节点的实现如下：

.. code-block:: Rust

   fn walk_dt_node(dt: &Node) {
      if let Ok(compatible) = dt.prop_str("compatible") {
         if compatible == "virtio,mmio" {
            //确定是virtio设备
            virtio_probe(dt);
         }
      }
      for child in dt.children.iter() {
         walk_dt_node(child);
      }
   }

这是一个递归的过程，其中 `virtio_probe` 是分析具体virtio设备的函数，一旦找到这样的设备，就可以启动virtio设备初始化过程了。


.. code-block:: Rust

   fn virtio_probe(node: &Node) {
      if let Some(reg) = node.prop_raw("reg") {
         let paddr = reg.as_slice().read_be_u64(0).unwrap();
         ...
         let header = unsafe { &mut *(paddr as *mut VirtIOHeader) };
         ...
         match header.device_type() {
               DeviceType::Block => virtio_blk(header),
               ...
               t => warn!("Unrecognized virtio device: {:?}", t),
         }
      }
   }

`virtio_probe` 函数会进一步查找virtio设备节点中的`reg` 属性，从而可以找到virtio设备的具体类型（如 `DeviceType::Block` 块设备类型）等参数。这样我们就可以对具体的virtio设备进行初始化和进行具体I/O操作了。

平台级中断控制器
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

如果要让操作系统处理外设中断，就需要对中断控制器进行初始化设置。在RISC-V中，与外设连接的I/O控制器的一个重要组成是平台级中断控制器（Platform-Level Interrupt Controller，PLIC），它汇聚了各种外设的中断信号，并连接到CPU的外部中断引脚上。通过RISC-V的 ``mie`` 寄存器中的 ``meie`` 位，可以控制这个引脚是否接收外部中断信号。当然，通过RISC-V中M Mode的中断委托机制，也可以在RISC-V的S Mode下，通过 ``sie`` 寄存器中的 ``seie`` 位，对中断信号是否接收进行控制。

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


可以看到串口UART0的中断号是10，virtio设备的中断号是1~8。通过 ``dtc`` （Device Tree Compiler）工具生成的文本文件，我们也可以发现上述中断信号信息，以及基于MMIO的外设寄存器信息。在后续的驱动程序中，这些信息我们可以用到。


操作系统如要响应外设的中断，需要做两方面的初始化工作。首先是完成第三章讲解的中断初始化过程，并需要把 ``sie`` 寄存器中的 ``seie`` 位设置为1，让CPU能够接收通过PLIC传来的外部设备中断信号。然后还需要通过MMIO方式对PLIC的寄存器进行初始设置，才能让外设产生的中断传到CPU处。其主要操作包括：

- 设置外设中断的优先级
- 设置外设中断的阈值，优先级小于等于阈值的中断会被屏蔽
- 激活外设中断，即把 ``Enable`` 寄存器的外设中断编号为索引的位设置为1

但外设产生中断后，CPU并不知道具体是哪个设备传来的中断，这可以通过读PLIC的 ``Claim`` 寄存器来了解。 ``Claim`` 寄存器会返回PLIC接收到的优先级最高的中断；如果没有外设中断产生，读 ``Claim`` 寄存器会返回 0。

操作系统在收到中断并完成中断处理后，还需通过PLIC中断处理完毕，即CPU需要在PLIC的 ``Complete`` 寄存器中写入对应中断号为索引的位，告知PLIC自己已经处理完毕。

上述操作的具体实现，可以参考 ``plic.rs`` 中的代码。


串口驱动程序
------------------------------------

完成上述前期准备工作后，我们就可以开始设计实现驱动程序了。
首先我们要管理是物理上存在的串口设备。
串口（Universal Asynchronous Receiver-Transmitter，简称UART）是一种在嵌入式系统中常用的用于传输、接收系列数据的外部设备。串行数据传输是逐位（bit）顺序发送数据的过程。

我们在第一章其实就接触了串口，但当时是通过RustSBI来帮OS完成对串口的访问，即OS只需发出两种SBI调用请求就可以输出和获取字符了。但这种便捷性是有代价的。比如OS在调用获取字符的SBI调用请求后，RustSBI如果没收到串口字符，会返回 ``-1`` ，这样OS只能采用类似轮询的方式来继续查询。到第七章为止的串口驱动不支持中断是导致在多进程情况下，系统效率低下的主要原因之一。大家也不要遗憾，我们的第一阶段的目标是 **Just do it** ，先把OS做出来，在第二阶段再逐步优化改进。

接下来，我们就需要开始尝试脱离RustSBI的帮助，在操作系统中完成支持中断机制的串口驱动。

通过查找 ``dtc`` （Device Tree Compiler）工具生成的 ``riscv64-virt.dts`` 文件，我们可以看到串口设备相关的MMIO模式的寄存器信息和中断相关信息。


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


``chosen`` 节点的内容表明字符输出会通过串口设备打印出来。``uart@10000000`` 节点表明串口设备中寄存器的MMIO起始地址为 ``0x10000000`` ，范围在 ``0x00~0x100`` 区间内，中断号为 ``0x0a`` 。 ``clock-frequency`` 表示时钟频率，其值为0x38400 ，即3.6864 MHz。 ``compatible = "ns16550a"`` 表示串口的硬件规范兼容NS16550A。

在如下情况下，串口会产生中断：

- 有新的输入数据进入串口的接收缓存
- 串口完成了缓存中数据的发送
- 串口发送出现错误

这里我们仅关注有输入数据时串口产生的中断。

了解QEMU模拟的兼容NS16550A硬件规范是写驱动程序的准备工作。在 UART 中，可访问的 I/O寄存器一共有8个。访问I/O寄存器的方法把串口寄存器的MMIO起始地址加上偏移量，就是各个寄存器的MMIO地址了。

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

在我们的具体实现中，与上述的一般中断处理过程不太一样。首先操作系统通过自定义的 ``SBI_DEVICE_HANDLER`` SBI调用，告知RustSBI在收到外部中断后，要跳转到的操作系统中处理外部中断的函数 ``device_trap_handler`` 。这样，在外部中断产生后，先由RustSBI在M Mode下接收的，并转到S Mode，交由 ``device_trap_handler`` 内核函数进一步处理。接下来就是 PLIC识别出是串口中断号 ``10`` 后，最终交由 ``uart::InBuffer`` 结构的 ``peinding`` 函数处理。

.. code-block:: Rust

   let c = Uart::new().get().unwrap();
   self.buffer[self.write_idx] = c;
   self.write_idx = (self.write_idx + 1) % 128;

这个 ``uart::InBuffer`` 结构实际上是一个环形队列，新的输入数据会覆盖队列中旧的输入数据。 

对进程管理的改进
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

在目前的操作系统实现中，当一个进程通过 ``sys_read`` 系统调用来获取串口字符时，并没有用上中断机制。但一个进程读不到字符的时候，将会被操作系统调度到就绪队列的尾部，等待下一次执行的时刻。这其实就是一种变相的轮询方式来获取串口的输入字符。这里其实是可以对进程管理做的一个改进，来避免进程通过轮询的方式检查串口字符输入。

如果一个进程通过系统调用想获取串口输入，但此时串口还没有输入的字符，那么就设置一个进程等待串口输入的等待队列，然后把当前进程设置等待状态，并挂在这个等待队列上，把CPU让给其它就绪进程执行。当产生串口输入中断后，操作系统将查找等待串口输入的等待队列上的进程，把它唤醒并加入到就绪队列中。这样但这个进程再次执行时，就可以获取到串口数据了。