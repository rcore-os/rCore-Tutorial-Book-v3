引言
=========================================

本章导读
-----------------------------------------

上一章的 达科塔盗龙”操作系统和慈母龙操作系统已经具备了传统操作系统中的内在重要因素，如进程、文件、地址空间、进程间通信、线程并发执行、支持线程安全访问共享资源的同步互斥机制等，应用程序也能通过操作系统输入输出字符，读写在磁盘上的数据。不过与我们常见的操作系统（如Linux,Windows等）比起来，好像感知与交互的I/O能力还比较弱。

终于到了I/O设备管理这一章了。人靠衣裳马靠鞍，如果操作系统不能把计算机的外设功能给发挥出来，那应用程序感知外在环境的能力和展示内在计算的能力都会大打折扣。比如基于中断和DMA机制的高性能I/O处理，图形化显示，键盘与鼠标输入等，这些操作系统新技能将在本章展现出来。所以本章要完成的操作系统的核心目标是： **让应用能便捷地访问外设** 。

.. _term-dma-concept:

.. note::

   DMA机制

   DMA（Direct Memory Access）是一种用于在计算机系统中传输I/O数据的技术。它允许I/O设备通过DMA控制器直接将设备中的I/O数据读入内存或把内存中的数据写入I/O设备，而整个数据传输过程无需处理器的介入。这意味着处理器可以在DMA传输期间执行其他任务，从而提高系统的性能和效率。I/O设备通过DMA控制器访问的内存称为DMA内存。


以往操作系统对设备的访问
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

其实在第一章就非常简单介绍了QEMU模拟的RISC-V 64计算机中存在的外设：UART、时钟、virtio-net/block/console/gpu等。并且LibOS模式的操作系统就已通过RustSBI间接地接触过串口设备了，即通过RustSBI提供的一个SBI调用 ``SBI_CONSOLE_PUTCHAR`` 来完成字符输出功能的。

在第三章，为了能实现抢占式调度，引入了时钟这个外设，结合硬件中断机制，并通过SBI调用 ``SBI_SET_TIMER`` 来帮助操作系统在固定时间间隔内获得控制权。而到了第五章，我们通过另外一个SBI调用 ``SBI_CONSOLE_GETCHAR`` 来获得输入的字符能力。这时的操作系统就拥有了与使用者进行简单字符交互的能力了。

后来在第六章又引入了另外一个外设virtio-block设备，即一个虚拟的磁盘设备。还通过这个存储设备完成了对数据的持久存储，并在其上实现了管理存储设备上持久性数据的文件系统。对virtio-block设备的I/O访问没有通过RustSBI来完成，而是直接调用了 ``virtio_drivers`` crate中的 ``virtio-blk`` 设备驱动程序来实现。但我们并没有深入分析这个设备驱动程序的具体实现。

可以说在操作系统中，I/O设备管理无处不在，且与I/O设备相关的操作系统代码--设备驱动程序在整个操作系统中的代码量比例是最高的（Linux/Windows等都达到了75%以上），也是出错概率最大的地方。虽然前面章节的操作系统已经涉及了很多I/O设备访问的相关处理，但我们并没有对I/O设备进行比较全面的分析和讲解。这主要是由于各种I/O设备差异性比较大，操作系统很难像进程/地址空间/文件那样，对各种I/O设备建立一个一致通用的抽象和对应的解决方案。

但I/O设备非常重要，由于各种I/O(输入输出)设备的存在才使得计算机的强大功能得以展现在大众面前，事实上对于各种I/O设备的高效管理是计算机系统操作系统能够在大众中普及的重要因素。比如对于手机而言，大众关注的不是CPU有多快，内存有多大，而是关注显示是否流畅，触摸是否敏捷这些外设带来的人机交互体验。而这些体验在很大程度上取决于操作系统对外设的管理与访问效率。

另外，对I/O设备的管理体现了操作系统最底层的设计机制，如中断，并发，异步，缓冲，同步互斥等。这对上层的进程，地址空间，文件等有着深刻的影响。所以在设计和实现了进程，地址空间，文件这些经典的操作系统抽象概念后，我们需要再重新思考一下，具备多种I/O设备管理能力的操作系统应该如何设计，特别是是否能给I/O设备也建立一个操作系统抽象。如果同学带着这些问题来思考和实践，将会对操作系统有更全面的体会。

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

裸机设备驱动程序
~~~~~~~~~~~~~~~~~~

获取代码：

.. code-block:: console

   $ git clone https://github.com/rcore-os/virtio-drivers.git
   $ cd virtio-drivers
   $ cd examples/riscv

在 qemu 模拟器上运行：

.. code-block:: console

   $ make qemu
   ... #可以看到测试用例发现并初始化和操作各个虚拟化设备的情况
   [ INFO] Detected virtio MMIO device with vendor id 0x554D4551, device type Block, version Modern
   [ INFO] Detected virtio MMIO device with vendor id 0x554D4551, device type GPU, version Modern
   [ INFO] Detected virtio MMIO device with vendor id 0x554D4551, device type Input, version Modern
   [ INFO] Detected virtio MMIO device with vendor id 0x554D4551, device type Network, version Modern
   ...

.. image:: virtio-test-example2.png
   :align: center
   :scale: 30 %
   :name: virtio-test-example2

在这个测例中，可以看到对块设备（virtio-blk）、网络设备（virtio-net）、键盘鼠标类设备（virtio-input）、显示设备（virtio-gpu）的识别、初始化和初步的操作。

侏罗猎龙操作系统
~~~~~~~~~~~~~~~~~~~~~~~~~~~~


.. code-block:: console

   $ git clone https://github.com/rcore-os/rCore-Tutorial-v3.git
   $ cd rCore-Tutorial-v3
   $ git checkout ch9

在 qemu 模拟器上运行：

.. code-block:: console

   $ cd os
   $ make run GUI=on
   >> gui_snake     #在OS启动后的shell界面中执行gui——snake游戏应用

在这个应用中，可以看到 ``gui_snake`` 图形应用通过操作系统提供的UART串口驱动和 ``virtio-gui`` 显示驱动提供的服务来实现的一个贪吃蛇交互式小游戏。下面是该应用的演示图：其中红色为贪吃蛇，黄色方块为食物。玩家可以使用wasd（分别表示上左下右）控制贪吃蛇的行进方向。由于控制是基于和前面章节一样的命令行标准输入实现的，在游玩的时候需要让焦点位于 user shell 命令行界面，才能成功将控制传递给应用程序。应用画面可以在另一个图形显示窗口看到。

.. image:: ../../os-lectures/lec13/figs/gui-snake.png
   :align: center
   :scale: 30 %
   :name: gui-snake


本章代码树
-----------------------------------------

进一步增加了多种设备驱动程序的侏罗盗龙操作系统 -- DeviceOS的总体结构如下图所示：

.. image:: ../../os-lectures/lec13/figs/device-os-detail.png
   :align: center
   :scale: 20 %
   :name: device-os-detail
   :alt: 侏罗盗龙操作系统 -- DeviceOS总体结构


我们先分析一下图的上下两部分。从上图的左上角可以看到为应用程序增加了GUI相关的新系统调用。应用程序可以通过 ``sys_framebuffer`` 和 ``sys_framebuffer_flush`` 来显示图形界面，通过 ``sys_event_get`` 和 ``sys_key_pressed`` 来接收来自串口/键盘/鼠标的输入事件。这其实就形成了基本的GUI应用支持框架。在上图的中上部，添加了三个GUI应用的图形显示，从左到右分别是： ``gui_simple`` 、 ``gui_snake`` 和 ``gui_rect`` 。

在上图的最下面展示的硬件组成中，可以看到由Qemu模拟器仿真的 ``Virt Machine`` ，它包含了我们要管理的各种硬件组件，包括在前面章节中重点涉及的 ``CPU`` 和 ``Main Memory`` ，还包括新引入的外设，  ``ns16500`` UART串口外设、 ``virtio-gpu`` 图形显示外设、 ``virtio-input`` 键盘鼠标外设、 ``vritio-blk`` 硬盘存储设备。为了与这些硬件交互，系统软件还需了解有关这些外设的硬件参数模型，如各个外设的控制寄存器的内存起始地址和范围等，这就是Qemu模拟器中的 ``Virt Machine`` 硬件参数模型。硬件参数的具体内容可以在Qemu源码 ``qemu/include/hw/riscv/virt.h`` 和  ``qemu/hw/riscv/virt.c`` 中找到。

.. code-block:: C
   :linenos:

   // qemu/hw/riscv/virt.c
   static const MemMapEntry virt_memmap[] = {
      [VIRT_PLIC] =        {  0xc000000, VIRT_PLIC_SIZE(VIRT_CPUS_MAX * 2) },
      [VIRT_UART0] =       { 0x10000000,         0x100 },
      [VIRT_VIRTIO] =      { 0x10001000,        0x1000 },
      [VIRT_DRAM] =        { 0x80000000,           0x0 },
      ...
   };
   // qemu/include/hw/riscv/virt.h
   enum {
      UART0_IRQ = 10,
      VIRTIO_IRQ = 1, /* 1 to 8 */
      ...
   };


在上面的代码片段中，可以看到 UART 串口外设的控制寄存器的MMIO内存起始地址和空间大小为： ``{ 0x10000000,         0x100 }`` ，而其它 ``virtio`` 外设的控制寄存器的MMIO内存起始地址和空间大小为 ``{ 0x10001000,        0x1000 }`` 。当操作系统知道这些外设的控制寄存器的MMIO内存地址后，就可以通过读写这些寄存器来访问和管理这些外设了。

同时，我们也看到了各种外设的中断号，如串口中断号 ``UART0_IRQ`` 为10， 而``virtio`` 外设的中断号有8个，编号为 1~8。而对各种外设的中断的管理、检测发送给CPU等事务都在一个特殊的设备中完成，即 ``PLIC`` 平台级中断控制器（Platform Level InterruptController），它的控制寄存器内存起始地址和空间大小为 ``{ 0xc000000, VIRT_PLIC_SIZE(VIRT_CPUS_MAX * 2) }`` ，它的空间大小与CPU个数相关。

现在看看上图中部的操作系统，蓝边橙底方块的部分是主要增加的内容，包括了外设驱动和与外设相关的中断处理。 根据与各种外设的连线可以看到两类驱动：外设驱动和平台驱动。
 
 - ``virtio-GPU Drv``：图形显示驱动
 - ``ns16550a Drv``：串口驱动
 - ``virtio-input Drv``：键盘鼠标驱动
 - ``virtio-Block Drv``：块设备驱动
 - ``PLIC drv``：平台级中断控制器驱动
 - ``Virt Machine Conf``：``virt`` 计算机系统配置信息（可以理解为平台级配置驱动）

在与外设相关的中断处理方面，主要增加了对外设中断的处理，并被功能扩展的 ``异常控制流管理`` 内核模块进行统一管理。 ``异常控制流管理`` 内核模块主要的扩展包括两方面，一方面是支持在内核态响应各种中断，这样就能在内核态中处理外设的中断事件。为此需要扩展在内核态下的中断上下文保存/恢复操作，并根据外设中断号来调用相应外设驱动中的外设中断处理函数。

另一方面是提供了 ``UPIntrFreeCell<T>`` 接口，代替了之前的 ``UPSafeCell<T>`` 。在Device OS 中把 ``UPSafeCell<T>`` 改为 ``UPIntrFreeCell<T>`` 。这是因为在第九章前，系统设置在S-Mode中屏蔽中断，所以在 S-Mode中运行的内核代码不会被各种外设中断打断，这样在单处理器的前提下，采用 ``UPSafeCell`` 来实现对可写数据的独占访问支持是够用的。但在第九章中，系统配置改为在S-Mode中使能中断，所以内核代码在内核执行过程中会被中断打断，无法实现可靠的独占访问。本章引入了新的 ``UPIntrFreeCell`` 机制，使得在通过 ``UPIntrFreeCell`` 对可写数据进行独占访问前，先屏蔽中断；而对可写数据独占访问结束后，再使能中断。从而确保线程对可写数据的独占访问时，不会被中断打断或引入可能的线程切换，而避免了竞态条件的产生。


在内核层，为了支持Qemu模拟的 ``Virt`` 计算机中不同外设，增加了3个外设级设备驱动程序，分别是 ``virtio-gpu`` 显示驱动、 ``virtio-input`` 输入驱动和 ``ns16650`` 串口设备驱动，改进了 ``virtio-blk`` 块设备驱动，以支持高效的中断响应。而各种外设需要计算机中的支持。这4个外设级设备驱动程序需要计算机平台级的配置与管理，所以还增加了 ``Virt Machine Conf`` 和 ``PLIC`` 两个平台级设备驱动程序。在独立于操作系统的软件库中，增加了 ``virtio-drivers`` 库，实现了各种 ``virtio`` 外设的裸机设备驱动的主要功能。这样在实现操作系统中的设备驱动程序时，就可以直接封装 ``virtio`` 裸机设备驱动中的功能，简化了设备驱动程序的编写难度。

本章的代码主要包括两部分内容。一部分是virtio-drivers仓库中的驱动代码和裸机示例代码：

.. code-block::
   :linenos:

   ├── examples
   │   └── riscv
   │       └── src
   │           ├── main.rs （各种virtio设备的测试用例）
   │           └── virtio_impl.rs (用于I/O数据的物理内存空间管理的简单实现)
   └── src
      ├── blk.rs (virtio-blk 驱动)
      ├── gpu.rs (virtio-gpu 驱动)
      ├── hal.rs (用于I/O数据的物理内存空间管理接口)
      ├── header.rs (VirtIOHeader: MMIO设备寄存器接口)
      ├── input.rs (virtio-input 驱动)
      ├── net.rs (virtio-net 驱动)
      └── queue.rs (virtqueues: 批量I/O数据传输的机制) 

另外一部分是侏罗猎龙操作系统 -- Device OS 代码： 

.. code-block:: console
   :linenos:
      
   ├── ...
   ├── easy-fs
   │   └── src
   │       ├── ...
   │       └── block_dev.rs (BlockDevice trait中增加handle_irq接口)
   ├── os
   │   └── src
   │       ├── ...
   │       ├── main.rs（扩展blk/gpu/input等外设初始化调用）   W
   │       ├── config.rs （修改KERNEL_HEAP_SIZE和MEMORY_END，扩展可用内存空间）   
   │       ├── boards
   │       │   └── qemu.rs (扩展blk/gpu/input等外设地址设定/初始化/中断处理等操作)
   │       ├── drivers
   │       │   ├── block
   │       │   │   └── virtio_blk.rs（增加非阻塞读写块/中断响应等I/O操作）
   │       │   ├── bus
   │       │   │   └── virtio.rs（增加virtio-drivers需要的Hal trait接口）
   │       │   ├── chardev
   │       │   │   └── ns16550a.rs（增加s-mode下的串口驱动）
   │       │   ├── gpu
   │       │   │   └── mod.rs（增加基于virtio-gpu基本驱动的OS驱动）
   │       │   ├── input
   │       │   │   └── mod.rs（增加基于virtio-input基本驱动的OS驱动）
   │       │   └── plic.rs（增加RISC-V的PLIC中断控制器驱动）
   │       ├── fs
   │       │   └── stdio.rs（改用s-mode下的串口驱动进行输入输出字符）
   │       ├── mm
   │       │   └── memory_set.rs（扩展Linear内存映射方式，用于显示内存存映射）
   │       ├── sync
   │       │   ├── condvar.rs（扩展条件变量的wait方式，用于外设驱动）
   │       │   └── up.rs（扩展 UPIntrFreeCell<T> 支持内核态屏蔽中断的独占访问）
   │       ├── syscall
   │       │   ├── gui.rs（增加图形显示相关的系统调用）
   │       │   └── input.rs（增加键盘/鼠标/串口相关事件的系统调用）
   │       └── trap
   │           ├── mod.rs（扩展在用户态和内核态响应外设中断）
   │           └── trap.S（扩展内核态响应中断的保存与恢复寄存器操作）
   └── user
      └── src
         ├── bin
         │   ├── gui_rect.rs (显示不同大小正方形)
         │   ├── gui_simple.rs（彩色显示屏幕）
         │   ├── gui_snake.rs（用'a'/'s'/'d'/'w'控制的贪吃蛇图形游戏）
         │   ├── gui_uart.rs (用串口输入字符来控制显示正方形)
         │   ├── huge_write_mt.rs（写磁盘文件性能测试例子）
         │   ├── inputdev_event.rs（接收键盘鼠标输入事件）
         │   ├── random_num.rs（产生随机数）
         │   └── ...
         ├── file.rs（文件系统相关的调用）
         ├── io.rs（图形显示与交互相关的系统调用）
         ├── sync.rs（同步互斥相关的系统调用）
         ├── syscall.rs（扩展图形显示与交互的系统调用号和系统调用接口）
         └── task.rs（进程线程相关的系统调用）

本章代码导读
-----------------------------------------------------

设计设备驱动程序的总体思路
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

这里简要介绍一下在内核中添加设备驱动的大致开发过程。本章涉及的代码主要与设备驱动相关，需要了解硬件，还需要了解如何与操作系统内核的其他部分进行对接，包括其他内核模块可以给驱动提供的内核服务，如内存分配等，以及需要驱动提供的支持功能，如外设中断响应等。在Rust软件工程开发中，推荐代码重用的Crate设计。所以在实际开发中，可以先在没有操作系统的裸机环境下（no-std）实现具备基本功能的裸机设备驱动 Crate，再实现一个最小执行环境（类似我们在第一章完成的 ``三叶虫操作系统 -- LibOS`` ），并在此最小执行环境中测试裸机设备驱动 Crate的基本功能能正常运行。然后再在操作系统内核中设计实现设备驱动程序。操作系统中的设备驱动程序可以通过一层封装来使用裸机设备驱动 Crate 的各种功能，并对接操作系统的而其他内核模块。这样，操作系统中的设备驱动的开发和测试相对会简化不少。

设计设备驱动程序前，需要了解应用程序或操作系统中的其他子系统需要设备驱动程序完成哪些功能，再根据所需提供的功能完成如下基本操作：

- 1. 设备扫描/发现
- 2. 设备初始化
- 3. 准备发给设备的命令
- 4. 通知设备
- 5. 接收设备通知
- 6.（可选）卸载设备驱动时回收设备驱动资源

对于设计实现裸机设备驱动，首先需要大致了解对应设备的硬件规范。在本章中，主要有两类设备，一类是实际的物理设备 -- UART（QEMU模拟了这种NS16550a UART芯片规范）；另外一类是虚拟设备（如各种Virtio设备）。

然后需要了解外设是如何与CPU连接的。首先是CPU访问外设的方式，在RISC-V环境中，把外设相关的控制寄存器映射为某特定的内存区域（即MMIO映射方式），然后CPU通过读写这些特殊区域来访问外设（即PIO访问方式）。外设可以通过DMA来读写主机内存中的数据，并可通过中断来通知CPU。外设并不直接连接CPU，这就需要了解RISC-V中的平台级中断控制器（Platform-Level Interrupt Controller，PLIC），它管理并收集各种外设中断信息，并传递给CPU。


裸机设备驱动程序
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

对于裸机设备驱动程序对外设的具体管理过程，大致会有发现外设、初始化外设和I/O读写与控制等操作。理解这些操作和对应的关键数据结构，就大致理解外设驱动要完成的功能包含哪些内容。每个设备驱动的关键数据结构和处理过程有共性部分和特定的部分。同学们可以从 ``virtio-drivers`` crate 中的  ``examples/riscv/src/main.rs`` 和 ``src\blk.rs`` 有关virtio设备的功能测试例子来分析。以 ``virtio-blk`` 存储设备为例，可以看到需要完成的工作包括：

1. 设备扫描/发现：首先是访问 ``OpenSBI`` (这里没有用RustSBI，用的是QEMU内置的SBI实现)提供的设备树信息，了解QEMU硬件中存在的各种外设，根据外设ID来找到 ``virtio-blk`` 存储设备。

.. mermaid::

   graph LR

   A["init_dt(device_tree_paddr)"] --> B["walk_dt_node(&dt.root)"] --> C["virtio_probe(node)"] --> D["virtio_probe(dt)"] --> F["virtio_blk(header)"]

2. 设备初始化：找到 ``virtio-blk`` 外设后，就进行外设的初始化，如果学习了 virtio规范（需要关注的是 virtqueue、virtio-mmio device， virtio-blk device的描述内容），那就可以看出代码实现的初始化过程和virtio规范中的virtio设备初始化步骤基本上是一致的，但也有与具体设备相关的特定初始化内容，比如分配 I/O buffer等。

.. mermaid::

   graph LR

   A["VirtIOBlk::<HalImpl>::new(header)"] --> B["header.begin_init(...)"]
   A --> C[read configuration space]
   A --> D["VirtQueue::new(...)"]
   A --> E["header.finish_init()"]

3. 准备发给设备的命令：初始化完毕后，设备驱动在收到上层内核发出的读写扇区/磁盘块的请求后，就能通过 ``virtqueue`` 传输通道发出 ``virtio-blk`` 设备能接收的I/O命令和I/O buffer的区域信息。
4. 通知设备： 驱动程序通过 `kick` 机制（即写virtio设备中特定的通知控制寄存器）来通知设备有新请求。

.. mermaid::

   graph LR

   A[read_block] --> E[建立I/O命令] --> F[加入到到virtqueue队列中] --> G[通过写寄存器通知设备]
   B[read_block_nb] --> E
   C[write_block] --> E
   D[write_block_nb] --> E

5.  接收设备通知： ``virtio-blk`` 设备收到信息后，会通过DMA操作完成磁盘数据的读写，然后通过中断或其他方式让设备驱动知道命令完成或命令执行失败。由于中断处理例程的完整操作与操作系统内核相关性较大，所以在裸机设备驱动中，没有实现这部分的完整功能，而只是提供了表示收到中断的操作。

操作系统设备驱动程序
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

由于有了裸机设备驱动程序的实现，对于操作系统设备程序，可以直接访问裸机设备驱动程序的各种功能。这样操作系统设备驱动程序的复杂性和代码量大大降低，整个代码量不到100行。不过还需解决如下一些关键问题：

- 发现具体计算机（如 ``virt machine`` ）中的设备（即与设备交互的设备控制寄存器的MMIO内存地址）；
- 与其它操作系统内核模块（如文件系统、同步互斥、进程管理等）的对接；
- 封装裸机设备驱动程序，提供操作系统层面的I/O设备访问能力（初始化、读写、控制等操作）。

另外，操作系统还需满足裸机设备驱动程序对操作系统的需求，并能对各种外设进行统一的管理，这主要集中在硬件平台级的支持。主要的服务能力包括:

- 在硬件平台层面发现具体计算机（如 ``virt machine`` ）中的各种外设的能力；
- 在硬件平台层面的外设中断总控能力，即在外设中断产生后，能分析出具体是哪个外设产生的中断，并进行相应的处理；
- 给裸机设备驱动程序提供操作系统级别的服务能力，以 ``virtio-drivers`` 为例，OS需要提供 ``HAL`` Trait的具体实现，即驱动进行I/O操作所需的内存动态分配。

以面向 ``virtio-blk`` 外设的操作系统驱动为例，我们可以看看上述过程的具体实现。在硬件平台的总体支持方面，为简化操作，通过对Qemu的分析，在操作系统中直接给出  ``virt machine`` 中各个外设的控制寄存器地址（代码位置: ``os/src/boards/qemu.rs`` ）。为了完成外设中断总控，操作系统提供了 ``PLIC`` 驱动，支持对 ``virt machine`` 中各种外设的中断响应（代码位置: ``os/src/drivers/plic.rs`` ）。

在具体设备驱动实现上，首先是发现设备，操作系统建立了表示virtio_blk设备驱动的全局变量 ``BLOCK_DEVICE`` （代码位置: ``os/src/drivers/block/mod.rs`` ）。为简化发现设备的过程，操作系统直接指定了virtio_blk设备在 ``virt machine`` 中的设备控制寄存器地址 ``VIRTIO0``。

然后是驱动程序初始化、读写块和中断处理的实现（代码位置: ``os/src/drivers/block/virtio_blk.rs`` ）。在操作系统的第一次访问 ``BLOCK_DEVICE`` 时，会执行 ``VirtIOBlock::new()`` 方法，通过调用virtio_blk裸机设备驱动库中的功能，完成了块设备驱动的初始化工作，并初始化条件变量，用于后续块读写过程中与进程的交互（即让等待I/O访问结果的进程先挂起）。

块设备驱动的服务对象是文件系统，它们之间需要有一个交互的接口，这就是在 ``easy-fs`` 文件系统模块定义的 ``BlockDevice`` trait：

.. code-block:: Rust
   :linenos:

   pub trait BlockDevice: Send + Sync + Any {
      fn read_block(&self, block_id: usize, buf: &mut [u8]);
      fn write_block(&self, block_id: usize, buf: &[u8]);
      fn handle_irq(&self);
   }

操作系统块设备驱动程序通过调用裸机块设备驱动程序库，可以很简洁地实现上述功能。在具体实现上，在调用了裸机块设备驱动程序库的读写块方法后，通过条件变量让等待I/O访问结果的进程先挂起）。在中断处理的方法中，在得到I/O读写块完成的中断信息后，通过条件变量唤醒等待的挂起进程。

至此，就分析完毕操作系统设备驱动程序的所有功能了。接下来，我们就可以深入分析到I/O设备管理的级别概念、抽象描述和侏罗猎龙操作系统的具体实现。

.. [#juravenator] 侏罗猎龙是一种小型恐龙，生活在1亿5千万年前的侏罗纪，它有独特的鳞片状的皮肤感觉器官，具有类似鳄鱼的触觉、冷热以及pH等综合感知能力，可能对狩猎有很大帮助。