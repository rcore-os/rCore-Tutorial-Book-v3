引言
=========================================

本章导读
-----------------------------------------

终于到了I/O设备管理这一章了。其实早在第一章的时候，就非常简单介绍了QEMU模拟的RISC-V 64计算机中存在的外设：UART、时钟、virtio-net/block/console/gpu等。并且在第一章，我们就已经间接的通过RustSBI接触过串口设备了。但我们写的OS是通过RustSBI提供的一个SBI调用 ``SBI_CONSOLE_PUTCHAR`` 来完成字符输出功能的。在第三章，为了能实现抢占式调度，引入了时钟这个外设，帮助操作系统能在固定时间间隔内获得控制权。而到了第五章，我们通过另外一个SBI调用 ``SBI_CONSOLE_GETCHAR`` 来获得输入的字符能力。这时的操作系统就拥有了与使用者进行最基本交互的能力了。后来在第七章又引入了另外一个外设virtio-block设备，即一个虚拟的磁盘设备。还通过这个存储设备完成了对数据的持久存储，并在其上实现了方便用户访问持久性数据的文件系统。可以说在操作系统中，I/O设备管理无处不在，且I/O设备的操作系统相关代码在整个操作系统中的比例是最高的（Linux/Windows等都达到了75%以上），当然也是出错概率最大的地方。

虽然前面的操作系统已经涉及了很多I/O设备访问的相关处理，但我们并没有对I/O设备进行比较全面的分析和讲解。这主要是由于各种I/O设备差异性比较大，操作系统很难象进程/地址空间/文件那样，对各种I/O设备建立一个通用和一致的抽象和对应的解决方案。但I/O设备非常重要，各种I/O(输入输出)设备的存在才使得计算机的强大功能能够展现在大众面前。所以能够管理I/O设备的操作系统是让计算机系统在大众中普及的重要因素，比如对于手机而言，大众关注的不是CPU有多快，内存有多大，而是关注显示是否流畅，触摸是否敏捷这些外设带来的人机交互体验。而这些体验在很大程度上取决与操作系统对外设管理的效率。

另外，对I/O设备的管理体现了操作系统最底层机理，如中断，并发，异步，缓冲，同步互斥等。这对上层的进程，地址空间，文件等有着深刻的影响。所以在分析了进程，地址空间，文件这些经典的操作系统抽象概念的设计实现后，再重新思考一下I/O设备管理的操作系统设计思路，会对操作系统有更全面的体会。

.. note::

   如果翻看UNIX诞生的历史，你会发现一个有趣的故事。Ken Tompson在退出Mulitics开发后，还是想做操作系统。他首先做的就是给PDP-7计算机的磁盘驱动器写了一个包含磁盘调度算法的磁盘驱动程序和来提高计算机的磁盘I/O读写速度。为了测试磁盘访问性能，Ken Tompson花了三周时间写了一个操作系统，这就是Unix的诞生。

本章的目标是深入理解I/O设备管理，并将站在I/O设备管理的角度来分析I/O设备的特征，操作系统与I/O设备的交互方式。接着会进一步通过串口，时钟，键盘鼠标，磁盘，图形显示等各种外设的具体实现来展现操作系统是如何管理I/O设备的，并展现设备驱动与操作系统内核其它重要部分的交互。


实践体验
-----------------------------------------

获取本章代码：

.. code-block:: console

   $ git clone https://github.com/rcore-os/rCore-Tutorial-v3.git
   $ cd rCore-Tutorial-v3
   $ git checkout ch8

在 qemu 模拟器上运行本章代码：

.. code-block:: console

   $ cd os
   $ make run



本章代码树
-----------------------------------------

.. code-block::
   :linenos:
   :emphasize-lines: 50

   ./os/src
   Rust        32 Files    2893 Lines
   Assembly     3 Files      88 Lines
   ./easyfs/src
   Rust         7 Files     908 Lines
   ├── bootloader
   │   ├── rustsbi-k210.bin
   │   └── rustsbi-qemu.bin
   ├── Dockerfile
   ├── easy-fs(新增：从内核中独立出来的一个简单的文件系统 EasyFileSystem 的实现)
   │   ├── Cargo.toml
   │   └── src
   │       ├── bitmap.rs(位图抽象)
   │       ├── block_cache.rs(块缓存层，将块设备中的部分块缓存在内存中)
   │       ├── block_dev.rs(声明块设备抽象接口 BlockDevice，需要库的使用者提供其实现)
   │       ├── efs.rs(实现整个 EasyFileSystem 的磁盘布局)
   │       ├── layout.rs(一些保存在磁盘上的数据结构的内存布局)
   │       ├── lib.rs
   │       └── vfs.rs(提供虚拟文件系统的核心抽象，即索引节点 Inode)
   ├── easy-fs-fuse(新增：将当前 OS 上的应用可执行文件按照 easy-fs 的格式进行打包)
   │   ├── Cargo.toml
   │   └── src
   │       └── main.rs
   ├── LICENSE
   ├── Makefile
   ├── os
   │   ├── build.rs
   │   ├── Cargo.toml(修改：新增 Qemu 和 K210 两个平台的块设备驱动依赖 crate)
   │   ├── Makefile(修改：新增文件系统的构建流程)
   │   └── src
   │       ├── config.rs(修改：新增访问块设备所需的一些 MMIO 配置)
   │       ├── console.rs
   │       ├── drivers(修改：新增 Qemu 和 K210 两个平台的块设备驱动)
   │       │   ├── block
   │       │   │   ├── mod.rs(将不同平台上的块设备全局实例化为 BLOCK_DEVICE 提供给其他模块使用)
   │       │   │   ├── sdcard.rs(K210 平台上的 microSD 块设备, Qemu不会用)
   │       │   │   └── virtio_blk.rs(Qemu 平台的 virtio-blk 块设备)
   │       │   └── mod.rs
   │       ├── entry.asm
   │       ├── fs(修改：在文件系统中新增常规文件的支持)
   │       │   ├── inode.rs(新增：将 easy-fs 提供的 Inode 抽象封装为内核看到的 OSInode
   │       │   │            并实现 fs 子模块的 File Trait)
   │       │   ├── mod.rs
   │       │   ├── pipe.rs
   │       │   └── stdio.rs
   │       ├── lang_items.rs
   │       ├── link_app.S
   │       ├── linker-k210.ld
   │       ├── linker-qemu.ld
   │       ├── loader.rs(移除：应用加载器 loader 子模块，本章开始从文件系统中加载应用)
   │       ├── main.rs
   │       ├── mm
   │       │   ├── address.rs
   │       │   ├── frame_allocator.rs
   │       │   ├── heap_allocator.rs
   │       │   ├── memory_set.rs(修改：在创建地址空间的时候插入 MMIO 虚拟页面)
   │       │   ├── mod.rs
   │       │   └── page_table.rs
   │       ├── sbi.rs
   │       ├── syscall
   │       │   ├── fs.rs(修改：新增 sys_open/sys_dup)
   │       │   ├── mod.rs
   │       │   └── process.rs(修改：sys_exec 改为从文件系统中加载 ELF，并支持命令行参数)
   │       ├── task
   │       │   ├── context.rs
   │       │   ├── manager.rs
   │       │   ├── mod.rs(修改初始进程 INITPROC 的初始化)
   │       │   ├── pid.rs
   │       │   ├── processor.rs
   │       │   ├── switch.rs
   │       │   ├── switch.S
   │       │   └── task.rs
   │       ├── timer.rs
   │       └── trap
   │           ├── context.rs
   │           ├── mod.rs
   │           └── trap.S
   ├── README.md
   ├── rust-toolchain
   ├── tools
   │   ├── kflash.py
   │   ├── LICENSE
   │   ├── package.json
   │   ├── README.rst
   │   └── setup.py
   └── user
      ├── Cargo.lock
      ├── Cargo.toml
      ├── Makefile
      └── src
         ├── bin
         │   ├── cat.rs(新增)
         │   ├── cmdline_args.rs(新增)
         │   ├── exit.rs
         │   ├── fantastic_text.rs
         │   ├── filetest_simple.rs(新增：简单文件系统测例)
         │   ├── forktest2.rs
         │   ├── forktest.rs
         │   ├── forktest_simple.rs
         │   ├── forktree.rs
         │   ├── hello_world.rs
         │   ├── initproc.rs
         │   ├── matrix.rs
         │   ├── pipe_large_test.rs
         │   ├── pipetest.rs
         │   ├── run_pipe_test.rs
         │   ├── sleep.rs
         │   ├── sleep_simple.rs
         │   ├── stack_overflow.rs
         │   ├── user_shell.rs(修改：支持命令行参数解析和输入/输出重定向)
         │   ├── usertests.rs
         │   └── yield.rs
         ├── console.rs
         ├── lang_items.rs
         ├── lib.rs(修改：支持命令行参数解析)
         ├── linker.ld
         └── syscall.rs(修改：新增 sys_open 和 sys_dup)


本章代码导读
-----------------------------------------------------          

