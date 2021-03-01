引言
=========================================

本章导读
-----------------------------------------

在第六章中，我们为进程引入了文件的抽象，使得进程能够通过一个统一的接口来读写内核管理的多种不同的 I/O 资源。作为例子，我们实现了匿名管道，并通过它进行了简单的父子进程间的单向通信。

本章我们对一种非常重要的外设—— **持久存储设备** (Persistent Storage) 进行管理。在此之前我们仅使用一种存储，也就是内存（或称 RAM）。相比内存，持久存储设备的读写速度较慢，容量较大，且掉电之后并不会丢失数据。如果没有持久存储设备的话，我们在内核上的任何活动记录全部只能保存在内存上，一旦掉电这些数据将会全部丢失。因此，将需要持久保存的数据从内存写入到持久存储设备，或是从持久存储读入到内存是应用必不可少的一种需求。常见的持久存储设备有硬盘、磁盘以及固态硬盘 (SSD, Solid-State Drive) 等。

对于应用访问持久存储设备的需求，内核需要新增两种文件：标准文件和目录，它们均以文件系统的形式被组织并保存在持久存储设备上。

实践体验
-----------------------------------------

获取本章代码：

.. code-block:: console

   $ git clone https://github.com/rcore-os/rCore-Tutorial-v3.git
   $ cd rCore-Tutorial-v3
   $ git checkout ch7

在 qemu 模拟器上运行本章代码：

.. code-block:: console

   $ cd os
   $ make run

若要在 k210 平台上运行，首先需要将 microSD 通过读卡器插入 PC ，然后将打包应用 ELF 的文件系统镜像烧写到 microSD 中：

.. code-block:: console

   $ cd os
   $ make sdcard
   Are you sure write to /dev/sdb ? [y/N]
   y
   16+0 records in
   16+0 records out
   16777216 bytes (17 MB, 16 MiB) copied, 1.76044 s, 9.5 MB/s
   8192+0 records in
   8192+0 records out
   4194304 bytes (4.2 MB, 4.0 MiB) copied, 3.44472 s, 1.2 MB/s

途中需要输入 ``y`` 确认将文件系统烧写到默认的 microSD 所在位置 ``/dev/sdb`` 中。这个位置可以在 ``os/Makefile`` 中的 ``SDCARD`` 处进行修改，在烧写之前请确认它被正确配置为 microSD 的实际位置，否则可能会造成数据损失。

烧写之后，将 microSD 插入到 Maix 系列开发板并连接到 PC，然后在开发板上运行本章代码：

.. code-block:: console

   $ cd os
   $ make run BOARD=k210

内核初始化完成之后就会进入用户终端，在这里我们运行一下本章的测例 ``filetest_simple`` ：

.. code-block::

    >> filetest_simple
    file_test passed!
    Shell: Process 2 exited with code 0
    >> 

它会将 ``Hello, world!`` 输出到另一个文件 ``filea`` ，并读取里面的内容确认输出正确。我们也可以通过命令行工具 ``cat`` 来更直观的查看 ``filea`` 中的内容：

.. code-block::

   >> cat filea
   Hello, world!
   Shell: Process 2 exited with code 0
   >> 

此外，在本章我们为用户终端支持了输入/输出重定向功能，可以将一个应用的输出保存到一个指定的文件。例如，下面的命令可以将 ``yield`` 应用的输出保存在文件 ``fileb`` 当中，并在应用执行完毕之后确认它的输出：

.. code-block::

   >> yield > fileb
   Shell: Process 2 exited with code 0
   >> cat fileb
   Hello, I am process 2.
   Back in process 2, iteration 0.
   Back in process 2, iteration 1.
   Back in process 2, iteration 2.
   Back in process 2, iteration 3.
   Back in process 2, iteration 4.
   yield pass.

   Shell: Process 2 exited with code 0
   >> 

本章代码树
-----------------------------------------

.. code-block::
   :linenos:
   :emphasize-lines: 45

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
   │       │   │   ├── sdcard.rs(K210 平台上的 microSD 块设备)
   │       │   │   └── virtio_blk.rs(Qemu 平台的 virtio-blk 块设备)
   │       │   └── mod.rs
   │       ├── entry.asm
   │       ├── fs(修改：在文件系统中新增普通文件的支持)
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