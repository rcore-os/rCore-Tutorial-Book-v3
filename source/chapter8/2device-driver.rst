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

在我们的具体实现中，与上述的一般中断处理过程不太一样。首先操作系统通过自定义的 ``SBI_DEVICE_HANDLER`` SBI调用，告知RustSBI在收到外部中断后，要跳转到到的操作系统中处理外部中断的函数 ``device_trap_handler`` 。这样，在外部中断产生后，先由RustSBI在M Mode下接收的，并转到S Mode，交由 ``device_trap_handler`` 内核函数进一步处理。接下来就是 PLIC识别出是串口中断号 ``10`` 后，最终交由 ``uart::InBuffer`` 结构的 ``peinding`` 函数处理。

.. code-block:: Rust

   let c = Uart::new().get().unwrap();
   self.buffer[self.write_idx] = c;
   self.write_idx = (self.write_idx + 1) % 128;

这个 ``uart::InBuffer`` 结构实际上是一个环形队列，新的输入数据会覆盖队列中旧的输入数据。 

对进程管理的改进
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

在目前的操作系统实现中，当一个进程通过 ``sys_read`` 系统调用来获取串口字符时，并没有用上中断机制。但一个进程读不到字符的时候，将会被操作系统调度到就绪队列的尾部，等待下一次执行的时刻。这其实就是一种变相的轮询方式来获取串口的输入字符。这里其实是可以对进程管理做的一个改进，来避免进程通过轮询的方式检查串口字符输入。

如果一个进程通过系统调用想获取串口输入，但此时串口还没有输入的字符，那么就设置一个进程等待串口输入的等待队列，然后把当前进程设置等待状态，并挂在这个等待队列上，把CPU让给其它就绪进程执行。当产生串口输入中断后，操作系统将查找等待串口输入的等待队列上的进程，把它唤醒并加入到就绪队列中。这样但这个进程再次执行时，就可以获取到串口数据了。


I/O设备抽象
-----------------------------------------

上面描述的串口设备是一种真实存在的I/O设备，有着各种各样的硬件细节需要了解。我们也知道各种I/O设备的种类繁多，差异性很大，使得操作系统难以建立I/O设备抽象，写出了的设备驱动程序也是千差万别，能难象操作系统的其他组成部分那样，把各种I/O设备进行抽象，形成一套统一的接口和功能语义。



基于文件的I/O设备抽象
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

计算机专家为此进行了诸多的探索，希望能给I/O设备提供一个统一的抽象。首先是把本来专门针对存储类I/O设备的文件进行扩展，认为所有的I/O设备都是文件，这就是传统UNIX中常见的设备文件。所有的I/O设备按照文件的方式进行处理。你可以在Linux下执行如下命令，看到各种各样的设备文件：

.. code-block:: Shell

   $ ls /dev
   i2c-0 gpiochip0 nvme0 tty0 rtc0 ...


这些设备按照文件的访问接口（即 ``open/close/read/write`` ）来进行处理。但由于各种设备的功能繁多，仅仅靠 ``read/write`` 这样的方式很难有效地与设备交互。于是UNIX的后续设计者提出了一个非常特别的系统调用 ``ioctl`` ，即 ``input/output control`` 的含义。它是一个专用于设备输入输出操作的系统调用,该调用传入一个跟设备有关的请求码，系统调用的功能完全取决于设备驱动程序对请求码的解读和处理。比如，CD-ROM驱动程序可以弹出光驱，于是操作系统就可以设定一个ioctl的请求码来对应这种操作。当应用程序发出带有CD-ROM设备文件描述符和 **弹出光驱** 请求码这两个参数的 ``ioctl`` 系统调用请求后，操作系统中的CD-ROM驱动程序会识别出这个请求码，并进行弹出光驱的I/O操作。

``ioctl`` 这名字第一次出现在Unix第七版中，他在很多类unix系统（比如Linux、Mac OSX等）都有提供，不过不同系统的请求码对应的设备有所不同。Microsoft Windows在Win32 API里提供了相似的函数，叫做DeviceIoControl。

表面上看，基于设备文件的设备管理得到了大部分通用操作系统的支持，且这种 ``ioctl`` 系统调用很灵活，但它的问题是太灵活了，请求码的定义无规律可循，文件的接口太面向用户应用，并没有挖掘出操作系统在进行I/O设备处理过程中的共性特征。所以文件这个抽象还不足覆盖到操作系统对设备进行管理的整个执行过程中。


基于流的I/O设备抽象
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

在UNIX操作系统的发展的过程中，出现了网络等更加复杂的设备，也随之出现了 ``流 stream`` 这样的面向I/O设备管理的抽象。Dennis M. Ritchie在1984年写了一个技术报告“A Stream Input-Output System”，详细介绍了基于流的I/O设备的抽象设计。现在看起来，是希望把UNIX中的管道（pipe）机制拓展到内核的设备驱动中。

流是用户进程和设备或伪设备之间的全双工连接。它由几个线性连接的处理模块（module）组成，类似于一个shell程序中的管道（pipe），只是数据双向流动。流中的模块通过向邻居模块传递消息来进行通信。除了一些用于流量控制的常规变量，模块不需要访问其邻居模块的其他数据。此外，一个模块只为每个邻居提供一个入口点，即一个接受消息的例程。

.. image:: stream.png
   :align: center
   :name: stream

在最接近进程的流的末端是一组例程，它们为操作系统的其余部分提供接口。用户进程的写操作请求和输入/输出控制请求被转换成发送到流的消息，而读请求将从流中获取数据并将其传递给用户进程。流的另一端是设备驱动程序模块。对字符或网络传输而言，从用户进程以流的方式传递数据将被发送到设备；设备检测到的字符、网络包和状态转换被合成为消息，并被发送到流向用户进程的流中。整个过程会经过多个中间模块，这些模块会以各种方式处理或过滤消息。

在具体实现上，当设备打开时，流中的两个末端管理的内核模块自动连接；中间模块是根据用户程序的请求动态附加的。为了能够方便动态地插入不同的流处理模块，这些中间模块的读写接口被设定为相同。

每个流处理模块由一对队列（queue）组成，每个方向一个队列。队列不仅包括数据队列本身，还包括两个例程和一些状态信息。一个是put例程，它由邻居模块调用以将消息放入数据队列中。另一个是服务（service）例程，被安排在有工作要做的时候执行。状态信息包括指向下游下一个队列的指针、各种标志以及指向队列实例化所需的附加状态信息的指针。


.. image:: stream-queue.png
   :align: center
   :name: stream-queue

虽然基于流的I/O设备抽象看起来很不错，但并没有在其它操作系统中推广开来。其中的一个原因是UNIX在当时还是一个曲高和寡的高端软件系统，运行在高端的工作站和服务器上，支持的外设有限。而Windows这样的操作系统与Intel的x86形成了wintel联盟，在个人计算机市场被广泛使用，并带动了而多媒体，GUI等相关外设的广泛发展，Windows操作系统并没有采用流的I/O设备抽象，而是针对每类设备定义了一套Device Driver API接口，提交给外设厂商，让外设厂商写好相关的驱动程序，并加入到Windows操作系统中。这种相对实用的做法虽然让各种外设得到了Windows操作系统的支持，但也埋下了容易包含bug的隐患。


基于virtio的I/O设备抽象
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

对于操作系统如何有效管理I/O设备的相关探索还在继续，但环境已经有所变化。随着互联网和云计算的兴起，在数据中心的物理服务器上通过虚拟机技术（Virtual Machine Monitor， Hypervisor等），运行多个虚拟机（Virtual Machine），并在虚拟机中运行guest操作系统的模式成为一种主流。但当时存在多种虚拟机技术，如Xen、VMware、KVM等，要支持虚拟化x86、Power等不同的处理器和各种具体的外设，并都要求让以Linux为代表的guest OS能在其上高效的运行。这对于虚拟机和操作系统来说，实在是太繁琐和困难了。

IBM资深工程师 Rusty Russell 在开发Lguest（Linux 内核中的的一个hypervisor（一种高效的虚拟计算机的系统软件）)时，深感写模拟计算机中的高效虚拟I/O设备的困难，且编写I/O设备的驱动程序繁杂且很难形成一种统一的表示。于是他经过仔细琢磨，提出了一组通用的I/O设备的抽象和规范 -- virtio。虚拟机（VMM或Hypervisor）提供virtio设备的实现，virtio设备有着统一的virtio接口，guest操作系统只要能够实现这些通用的接口，就可以管理和控制各种virtio设备。而虚拟机与guest操作系统的virtio设备驱动程序间的通道是基于共享内存的异步访问方式来实现的，效率很高。虚拟机会进一步把相关的virtio设备的I/O操作转换成物理机上的物理外设的I/O操作。这就完成了整个I/O处理过程。

由于virtio设备的设计，使得虚拟机不用模拟真实的外设，从而可以设计一种统一和高效的I/O操作规范来让guest操作系统处理各种I/O操作。这种I/O操作规范其实就形成了基于virtio的I/O设备抽象，并逐渐形成了事实的上的虚拟I/O设备的标准。

.. image:: virtio-simple-arch.png
   :align: center
   :name: virtio-simple-arch

本章将进一步分析virtio规范，设计针对多种virtio设备的设备驱动程序，从而对设备驱动程序和操作系统其他部分的关系有一个更全面的了解。

.. note::

  Rusty Russell工程师在2008年在“ACM SIGOPS Operating Systems Review”期刊上发表了一篇论文“virtio: towards a de-facto standard for virtual I/O devices”，提出了给虚拟环境（Virtual Machine）中的操作系统提供一套统一的设备抽象，这样操作系统针对每类设备只需写一种驱动程序就可以了，这极大降低了系统虚拟机（Virtual Machine Monitor）和Hypervisor，以及运行在它们提供的虚拟环境中的操作系统的开发成本，且可以显著提高I/O的执行效率。目前virtio已经有相应的规范，最新的virtio spec版本是v1.1。


virtio设备和virtio设备驱动程序
----------------------------------------


virtio设备是虚拟外设，存在于QEMU模拟的RISC-V 64 virt 计算机中，而我们要在操作系统中实现的virtio设备驱动程序，以能够管理和控制这些virtio虚拟设备。每一类virtio设备都有自己的virtio接口，virtio接口包括了数据结构的定义和API的定义。这些定义中，很多在结构上都是一致的，只是在有个设备描述的具体内容上，会根据设备的类型特征设定具体的内容。

virtio架构
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

总体上看，virtio 可以分为四层，包括前端 guest 中各种驱动程序模块，后端 Hypervisor （实现在Qemu上）上的处理程序模块，中间用于前后端通信的 virtio 层和 virtio-ring 层，virtio 这一层实现的是虚拟队列接口，算是前后端通信的桥梁，而 virtio-ring 则是该桥梁的具体实现，它实现了两个环形缓冲区，分别用于保存前端驱动程序和后端处理程序执行的信息。

.. image:: virtio-arch.png
   :align: center
   :name: virtio-arch


- 设备状态字段（Device status field）
- 特征位（Feature bits）
- 设备配置空间（Device Configuration space）
- 一个或多个virtqueues

在virtio设备上进行批量数据传输的机制被称为virtqueue，每个virtio设备可以拥有零个或多个virtqueue，每个virtqueue由三部分组成：

- Descriptor Table
- Available Ring
- Used Ring

Descriptor Table用来描述virtio设备驱动程序与virtio设备进行数据交互的缓冲区，由 ``Queue Size`` 个Descriptor（描述符）组成。Descriptor中包括表示数据buffer的物理地址 -- addr字段，数据buffer的长度 -- len字段，可以链接到 ``next Descriptor`` 的next指针并形成描述符链。

Available Ring中的每个条目是一个是描述符链的头部。它仅由virtio设备驱动程序写入，并由virtio设备读出。virtio设备获取Descriptor后，Descriptor对应的缓冲区具有可读写属性，可读的缓冲区用于Driver发送数据，可写的缓冲区用于接收数据。

Used Ring中的每个条目也一个是描述符链的头部。这个描述符是Device完成相应I/O处理后，将Available Ring中的Descriptor移入到Used Ring中来，并通过轮询或中断机制来通知virtio设备驱动程序I/O完成，并让virtio设备驱动程序回收这个描述符。


vring机制
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

每个virtio设备可以拥有零个或多个virtqueue，每个virtqueue就是一个保存和传输I/O数据的抽象数据结构queue，可承载大量I/O数据，而virtqueue由vring（一种环形队列）来实现。


.. image:: vring.png
   :align: center
   :name: vring




当virtio设备驱动程序想要向virtio设备发送数据时，它会填充Descriptor Table中的一项或几项链接在一起，形成描述符链，并将描述符索引写入Available Ring中，然后它通知virtio设备（向queue notify寄存器写入队列index）。当virtio设备收到通知，并完成I/O操作后，virtio设备将描述符索引写入Used Ring中并发送中断，让操作系统进行进一步处理并回收描述符。


virtio 设备操作
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~


**设备的初始化**

1. 重启设备状态，状态位写入 0
2. 设置状态为 ACKNOWLEDGE，guest(driver)端当前已经识别到了设备
3. 设置状态为 Driver，guest 知道如何驱动当前设备
4. 设备特定的安装和配置：特征位的协商，virtqueue 的安装，可选的 MSI-X 的安装，读写设备专属的配置空间等
5. 设置状态为 Driver_OK 或者 Failed（如果中途出现错误）
6. 当前设备初始化完毕，可以进行配置和使用

**设备的安装和配置**

设备操作包括两个部分：driver提供 buffers 给设备，处理 device使用过的 buffers。

**初始化 virtqueue**

该部分代码的实现具体为：

1.选择 virtqueue 的索引，写入 Queue Select 寄存器
2.读取 queue size 寄存器获得 virtqueue 的可用数目
3.分配并清零连续物理内存用于存放 virtqueue。把内存地址除以 4096 写入 Queue Address 寄存器



**Guest 向设备提供 buffer**

1.把 buffer 添加到 description table 中,填充 addr,len,flags
2.更新 available ring head
3.更新 available ring 中的 index
4.通知 device，通过写入 virtqueue index 到 Queue Notify 寄存器

**Device 使用 buffer 并填充 used ring**

device 端使用 buffer 后填充 used ring 的过程如下：

1.从描述符表格（descriptor table）中找到 available ring 中添加的 buffers，映射内存
2.从分散-聚集的 buffer 读取数据
3.取消内存映射,更新 ring[idx]中的 id 和 len 字段
4.更新 vring_used 中的 idx
5.如果设置了使能中断，产生中断并通知操作系统描述符已经使用

**中断处理**

？？？？





现在，我们将为每个部分提供更多详细信息，以及设备和驱动程序如何开始使用它们进行通信。

virtio字符设备
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~


virtio块设备
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~


virtio显示设备
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~