引言
=========================================

本章导读
-----------------------------------------



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

