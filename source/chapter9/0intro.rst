引言
=========================================

本章导读
-----------------------------------------

进化的 “达科塔盗龙” 操作系统已经具备了传统操作系统中的内在重要因素，如进程、文件、地址空间、进程间通信、线程并发执行等，应用程序也能通过操作系统输入输出字符，读写在磁盘上的数据。不过与我们常见的操作系统（如Linux,Windows等）比起来，好像感知与交互的I/O能力还比较弱。

终于到了I/O设备管理这一章了。人靠衣裳马靠鞍，如果操作系统不能把计算机的外设功能给发挥出来，那应用程序感知外在环境的能力和展示内在计算的能力都会大打折扣。比如基于中断机制的高效I/O处理，图形化的显示，这些操作系统新技能将在本章展现出来。所以本章要完成的操作系统的核心目标是： **让应用能便捷地访问外设** 。


其实在第一章就非常简单介绍了QEMU模拟的RISC-V 64计算机中存在的外设：UART、时钟、virtio-net/block/console/gpu等。并且LibOS模式的操作系统就已通过RustSBI间接地接触过串口设备了，即通过RustSBI提供的一个SBI调用 ``SBI_CONSOLE_PUTCHAR`` 来完成字符输出功能的。

在第三章，为了能实现抢占式调度，引入了时钟这个外设，结合硬件中断机制，并通过SBI调用 ``SBI_SET_TIMER`` 来帮助操作系统在固定时间间隔内获得控制权。而到了第五章，我们通过另外一个SBI调用 ``SBI_CONSOLE_GETCHAR`` 来获得输入的字符能力。这时的操作系统就拥有了与使用者进行简单字符交互的能力了。

后来在第六章又引入了另外一个外设virtio-block设备，即一个虚拟的磁盘设备。还通过这个存储设备完成了对数据的持久存储，并在其上实现了管理存储设备上持久性数据的文件系统。对virtio-block设备的I/O访问没有通过RustSBI来完成，而是直接调用了 ``virtio_drivers`` crate中的 ``virtio-blk`` 设备驱动程序来实现。但我们并没有深入分析这个设备驱动程序的具体实现。

可以说在操作系统中，I/O设备管理无处不在，且与I/O设备相关的操作系统代码--设备驱动程序在整个操作系统中的代码量比例是最高的（Linux/Windows等都达到了75%以上），也是出错概率最大的地方。虽然前面章节的操作系统已经涉及了很多I/O设备访问的相关处理，但我们并没有对I/O设备进行比较全面的分析和讲解。这主要是由于各种I/O设备差异性比较大，操作系统很难像进程/地址空间/文件那样，对各种I/O设备建立一个一致通用的抽象和对应的解决方案。

但I/O设备非常重要，由于各种I/O(输入输出)设备的存在才使得计算机的强大功能得以展现在大众面前，事实上对于各种I/O设备的高效管理是计算机系统操作系统能够在大众中普及的重要因素。比如对于手机而言，大众关注的不是CPU有多快，内存有多大，而是关注显示是否流畅，触摸是否敏捷这些外设带来的人机交互体验。而这些体验在很大程度上取决于操作系统对外设的管理与访问效率。

另外，对I/O设备的管理体现了操作系统最底层的设计机制，如中断，并发，异步，缓冲，同步互斥等。这对上层的进程，地址空间，文件等有着深刻的影响。所以在设计和实现了进程，地址空间，文件这些经典的操作系统抽象概念后，我们需要再重新思考一下，具备I/O设备管理能力的操作系统应该如何设计，特别是是否能给I/O设备也建立一个操作系统抽象。如果同学带着这些问题来思考和实践，将会对操作系统有更全面的体会。

.. note::

   **UNIX诞生是从磁盘驱动程序开始的** 

   回顾UNIX诞生的历史，你会发现一个有趣的故事：贝尔实验室的Ken Tompson在退出Mulitics操作系统开发后，还是想做继续操作系统方面的探索。他先是给一台闲置的PDP-7计算机的磁盘驱动器写了一个包含磁盘调度算法的磁盘驱动程序，希望提高磁盘I/O读写速度。为了测试磁盘访问性能，Ken Tompson花了三周时间写了一个操作系统，这就是Unix的诞生。这说明是磁盘驱动程序促使了UNIX的诞生。


.. chyyuu 可以介绍包括各种外设的 PC OS??? 
   https://blog.ysndr.de/posts/essays/2021-12-12-rust-for-iot/
   https://english.stackexchange.com/questions/56183/origin-of-the-term-driver-in-computer-science
   https://en.wikipedia.org/wiki/MS-DOS
   https://en.wikipedia.org/wiki/Microsoft_Windows
   https://en.wikipedia.org/wiki/MacOS
   https://en.wikipedia.org/wiki/IOS_version_history
   https://en.wikipedia.org/wiki/Android_(operating_system)
   https://en.wikipedia.org/wiki/History_of_the_graphical_user_interface

.. note::

   设备驱动程序是操作系统的一部分？

   我们都知道计算机是由CPU、内存和I/O设备组成的。即使是图灵创造的图灵机这一理论模型，也有其必须存在的I/O设备：笔和纸。1946年出现的远古计算机ENIAC，都具有读卡器和打卡器来读入和输出穿孔卡片中的数据。当然，这些外设不需要额外编写软件，直接通过硬件电路就可以完成I/O操作了。但后续磁带和磁盘等外设的出现，使得需要通过软件来管理越来越复杂的外设功能了，这样设备驱动程序（Device Driver）就出现了，它甚至出现在操作系统之前，以子程序库的形式存在，以便于应用程序来访问硬件。

   随着计算机外部设备越来越多，越来越复杂，设备驱动程序在操作系统中的代码比重也越来越大。甚至某些操作系统的名称直接加入了外设名，如微软在 1981 年至 1995 年间主导了个人计算机市场的DOS操作系统的全称是“Disk Operating System”。1973 年，施乐 PARC 开发了Alto个人电脑，它是第一台具有图形用户界面(GUI) 的计算机，直接影响了苹果公司和微软公司设计的带图形界面的操作系统。微软后续开发的操作系统名称“Windows”也直接体现了图形显示设备（显卡）能够展示的抽象概念，显卡驱动和基于显卡驱动的图形界面子系统在Windows操作系统中始终处于非常重要的位置。

   目前评价操作系统被产业界接受的程度有一个公认的量化指标，该操作系统的设备驱动程序支持的外设种类和数量。量越大说明它在市场上的接受度就越高。正是由于操作系统能够访问和管理各种外设，才给了应用程序丰富多彩的功能。



本章的目标是深入理解I/O设备管理，并将站在I/O设备管理的角度来分析I/O设备的特征，操作系统与I/O设备的交互方式。接着会进一步通过串口，磁盘，图形显示等各种外设的具体实现来展现操作系统是如何管理I/O设备的，并展现设备驱动与操作系统内核其它重要部分的交互, 通过扩展操作系统的I/O能力，形成具有灵活感知和捕猎能力的侏罗猎龙 [#juravenator]_ 操作系统。


实践体验
-----------------------------------------

获取本章代码：

.. code-block:: console

   $ git clone https://github.com/rcore-os/virtio-drivers.git
   $ cd virtio-drivers
   $ cd examples/riscv

在 qemu 模拟器上运行本章代码：

.. code-block:: console

   $ make run

.. image:: virtio-test-example.png
   :align: center
   :name: virtio-test-example

本章代码树
-----------------------------------------

.. code-block::
   :linenos:

   virtio-drivers crate
   ########################
   ./os/src
   Rust         8 Files    1150 Lines
   ./examples/riscv/src
   Rust         2 Files     138 Lines
   
   .
   ├── Cargo.lock
   ├── Cargo.toml
   ├── examples
   │   └── riscv
   │       ├── Cargo.toml
   │       ├── linker32.ld
   │       ├── linker64.ld
   │       ├── Makefile
   │       ├── rust-toolchain
   │       └── src
   │           ├── main.rs （各种virtio设备的测试用例）
   │           └── virtio_impl.rs (用于I/O数据的物理内存空间管理的简单实现)
   ├── LICENSE
   ├── README.md
   └── src
      ├── blk.rs (virtio-blk 驱动)
      ├── gpu.rs (virtio-gpu 驱动)
      ├── hal.rs (用于I/O数据的物理内存空间管理接口)
      ├── header.rs (VirtIOHeader: MMIO Device Register Interface)
      ├── input.rs (virtio-input 驱动)
      ├── lib.rs
      ├── net.rs (virtio-net 驱动)
      └── queue.rs (virtqueues: 批量I/O数据传输的机制) 

   4 directories, 20 files


本章代码导读
-----------------------------------------------------          

本章涉及的代码主要与设备驱动相关，需要了解硬件，需要阅读和运行测试相关代码。这里简要介绍一下在内核中添加设备驱动的大致开发过程。对于设计实现设备驱动，首先需要大致了解对应设备的硬件规范。在本章中，主要有两类设备，一类是实际的物理设备 -- UART（QEMU模拟了这种NS16550A UART芯片规范）；另外一类是虚拟设备（如各种Virtio设备）。

然后需要了解外设是如何与CPU连接的。首先是CPU访问外设的方式，在RISC-V环境中，把外设相关的控制寄存器映射为某特定的内存区域（即MMIO映射方式），然后CPU通过读写这些特殊区域来访问外设（即PIO访问方式）。外设可以通过DMA来读写主机内存中的数据，并可通过中断来通知CPU。外设并不直接连接CPU，这就需要了解RISC-V中的平台级中断控制器（Platform-Level Interrupt Controller，PLIC），它管理并收集各种外设中断信息，并传递给CPU。

对于设备驱动程序对外设的具体管理过程，大致会有初始化外设和I/O读写与控制操作。理解这些操作和对应的关键数据结构，就大致理解外设驱动要完成的功能包含哪些内容。每个设备驱动的关键数据结构和处理过程有共性部分和特定的部分。建议从 ``virtio-drivers`` crate 中的  ``examples/riscv/src/main.rs`` 这个virtio设备的功能测试例子入手来分析。

以 ``virtio-blk`` 存储设备为例，可以看到，首先是访问 ``OpenSBI`` (这里没有用RustSBI，用的是QEMU内置的SBI实现)提供的设备树信息，了解QEMU硬件中存在的各种外设，根据外设ID来找到 ``virtio-blk`` 存储设备；找到后，就进行外设的初始化，如果学习了 virtio规范（需要关注的是 virtqueue、virtio-mmio device， virtio-blk device的描述内容），那就可以看出代码实现的初始化过程和virtio规范中的virtio设备初始化步骤基本上是一致的，但也有与具体设备相关的特定初始化内容，比如分配 I/O buffer等。初始化完毕后，设备驱动在收到上层内核发出的读写扇区/磁盘块的请求后，就能通过 ``virtqueue`` 传输通道发出 ``virtio-blk`` 设备能接收的I/O命令和I/O buffer的区域信息； ``virtio-blk`` 设备收到信息后，会通过DMA操作完成磁盘数据的读写，然后通过中断或其他方式让设备驱动知道命令完成或命令执行失败。而 ``virtio-gpu`` 设备驱动程序的设计实现与 ``virtio-blk`` 设备驱动程序类似。

注：目前还没有提供相关的系统调用来方便应用程序访问virtio-gpu外设。



.. [#juravenator] 侏罗猎龙是一种小型恐龙，生活在1亿5千万年前的侏罗纪，它有独特的鳞片状的皮肤感觉器官，具有类似鳄鱼的触觉、冷热以及pH等综合感知能力，可能对狩猎有很大帮助。