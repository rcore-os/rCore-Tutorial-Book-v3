引言
=========================================

本章导读
-----------------------------------------

在第六章中，我们为进程引入了文件的抽象，使得进程能够通过一个统一的接口来读写内核管理的多种不同的 I/O 资源。作为例子，我们实现了匿名管道，并通过它进行了简单的父子进程间的单向通信。其实文件的最早起源于我们需要把数据持久保存在 **持久存储设备** 上的需求。

大家不要被 **持久存储设备** 这个词给吓住了，这就是指计算机远古时代的卡片、纸带、磁芯、磁鼓，和现在还在使用的磁带、磁盘、硬盘，还有近期逐渐普及的U盘、闪存、固态硬盘 (SSD, Solid-State Drive)等存储设备。我们可以把这些设备叫做 **外存** 。在此之前我们仅使用一种存储，也就是内存（或称 RAM）。相比内存，持久存储设备的读写速度较慢，容量较大，但内存掉电后信息会丢失，外存在掉电之后并不会丢失数据。因此，将需要持久保存的数据从内存写入到外存，或是从外存读入到内存是应用和操作系统必不可少的一种需求。


.. note::

   文件系统在UNIX操作系统有着特殊的地位，根据史料《UNIX: A History and a Memoir》记载，1969年，Ken Thompson（Unix的作者）在贝尔实验室比较闲，写了PDP-7计算机的磁盘调度算法来提高磁盘的吞吐量。为了测试这个算法，他本来想写一个批量读写数据的测试程序。但写着写着，他在某一时刻发现，这个测试程序再扩展一下，就是一个文件系统了，再再扩展一下，就是一个操作系统了。他的自觉告诉他，他离实现一个操作系统仅有 **三周之遥** 。一周：写代码编辑器；一周：写汇编器；一周写shell程序，在写这些程序的同时，需要添加操作系统的功能（如 exec等系统调用）以支持这些应用。结果三周后，为测试磁盘调度算法性能的UNIX雏形诞生了。


本章我们将实现一个简单的文件系统 -- easyfs，能够对 **持久存储设备** (Persistent Storage) 这种 I/O 资源进行管理。对于应用访问持久存储设备的需求，内核需要新增两种文件：常规文件和目录文件，它们均以文件系统所维护的 **磁盘文件** 形式被组织并保存在持久存储设备上。

同时，由于我们进一步完善了对 **文件** 这一抽象概念的实现，我们可以更容易建立 ” **一切皆文件** “ (Everything is a file) 的UNIX的重要设计哲学。我们可扩展与应用程序执行相关的 ``exec`` 系统调用，加入对程序运行参数的支持，并进一步改进了对shell程序自身的实现，加入对重定向符号 ``>`` 、 ``<`` 的识别和处理。这样我们也可以像UNIX中的shell程序一样，基于文件机制实现灵活的I/O重定位和管道操作，更加灵活地把应用程序组合在一起实现复杂功能。

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

内核初始化完成之后就会进入shell程序，在这里我们运行一下本章的测例 ``filetest_simple`` ：

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

此外，在本章我们为shell程序支持了输入/输出重定向功能，可以将一个应用的输出保存到一个指定的文件。例如，下面的命令可以将 ``yield`` 应用的输出保存在文件 ``fileb`` 当中，并在应用执行完毕之后确认它的输出：

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

本章涉及的代码量相对较多，且与进程执行相关的管理还有直接的关系。其实我们是参考经典的UNIX基于索引的文件系统，设计了一个简化的有一级目录并支持创建/打开/读写/关闭文件一系列操作的文件系统。这里简要介绍一下在内核中添加文件系统的大致开发过程。

第一步是能够写出与文件访问相关的应用。这里是参考了Linux的创建/打开/读写/关闭文件的系统调用接口，力图实现一个 :ref:`简化版的文件系统模型 <fs-simplification>` 。在用户态我们只需要遵从相关系统调用的接口约定，在用户库里完成对应的封装即可。这一过程我们在前面的章节中已经重复过多次，读者应当对其比较熟悉。其中最为关键的是系统调用可以参考 :ref:`sys_open 语义介绍 <sys-open>` ，此外我们还给出了 :ref:`测例代码解读 <filetest-simple>` 。

第二步就是要实现 easyfs 文件系统了。由于 Rust 语言的特点，我们可以在用户态实现 easyfs 文件系统，并在用户态完成文件系统功能的基本测试并基本验证其实现正确性之后，就可以放心的将该模块嵌入到操作系统内核中。当然，有了文件系统的具体实现，还需要对上一章的操作系统内核进行扩展，实现与 easyfs 文件系统对接的接口，这样才可以让操作系统拥有一个简单可用的文件系统。从而，内核可以支持允许文件读写功能的更复杂的应用，在命令行参数机制的加持下，可以进一步提升整个系统的灵活性，让应用的开发和调试变得更为轻松。

easyfs 文件系统的整体架构自下而上可分为五层。它的最底层就是对块设备的访问操作接口。在 ``easy-fs/src/block_dev.rs`` 中，可以看到 ``BlockDevice`` trait 代表了一个抽象块设备，该 trait 仅需求两个函数 ``read_block`` 和 ``write_block`` ，分别代表将数据从块设备读到内存中的缓冲区中，或者将数据从内存中的缓冲区写回到块设备中，数据需要以块为单位进行读写。easy-fs 库的使用者需要负责为它们看到的实际的块设备具体实现 ``BlockDevice`` trait 并提供给 easy-fs 库的上层，这样的话 easy-fs 库的最底层就与一个具体的执行环境对接起来了。至于为什么块设备层位于 easy-fs 的最底层，是因为文件系统仅仅是在块设备上存储的结构稍微复杂一点的数据，但无论它的操作变换如何复杂，从块设备的角度终究可以被分解成若干次块读写。

尽管在最底层我们就已经有了块读写的能力，但从编程方便性和性能的角度，仅有块读写这么基础的底层接口是不足以实现如此复杂的文件系统的，虽然它已经被我们大幅简化过了。比如，将一个块的内容读到内存的缓冲区，对缓冲区进行修改，并尚未写回的时候，如果由于编程上的不小心再次将该块的内容读到另一个缓冲区，而不是使用已有的缓冲区，这将会造成不一致问题。此外还有可能增加很多不必要的块读写次数，大幅降低文件系统的性能。因此，通过程序自动而非程序员手动对块的缓冲区进行统一管理也就势在必行了，该机制被我们抽象为 easy-fs 自底向上的第二层，即块缓存层。在 ``easy-fs/src/block_cache.rs`` 中， ``BlockCache`` 代表一个被我们管理起来的块的缓冲区，它带有缓冲区本体以及块的编号等信息。当它被创建的时候，将触发一次 ``read_block`` 将数据从块设备读到它的缓冲区中。接下来只要它驻留在内存中，便可保证对于同一个块的所有操作都会直接在它的缓冲区中进行而无需额外的 ``read_block`` 。块缓存管理器 ``BlockManager`` 在内存中管理有限个 ``BlockCache`` 并实现了类似 FIFO 的缓存替换算法，当一个块缓存被换出的时候视情况可能调用 ``write_block`` 将缓冲区数据写回块设备。总之，块缓存层对上提供 ``get_block_cache`` 接口来屏蔽掉相关细节，从而可以透明的读写一个块。

有了块缓存，我们就可以在内存中方便地处理easyfs文件系统在磁盘上的各种数据了，这就是第三层文件系统的磁盘数据结构。easyfs文件系统中的所有需要持久保存的数据都会放到磁盘上，这包括了管理这个文件系统的 **超级块 (Super Block)**，管理空闲磁盘块的 **索引节点位图区** 和  **数据块位图区** ，以及管理文件的 **索引节点区** 和 放置文件数据的 **数据块区** 组成。

easyfs文件系统中管理这些磁盘数据的控制逻辑主要集中在 **磁盘块管理器** 中，这是文件系统的第四层。对于文件系统管理而言，其核心是 ``EasyFileSystem`` 数据结构及其关键成员函数：
 
 - EasyFileSystem.create：创建文件系统
 - EasyFileSystem.open：打开文件系统
 - EasyFileSystem.alloc_inode：分配inode （dealloc_inode未实现，所以还不能删除文件）
 - EasyFileSystem.alloc_data：分配数据块
 - EasyFileSystem.dealloc_data：回收数据块

对于单个文件的管理和读写的控制逻辑主要是 **索引节点** 来完成，这是文件系统的第五层，其核心是 ``Inode`` 数据结构及其关键成员函数：

 - Inode.new：在磁盘上的文件系统中创建一个inode
 - Inode.find：根据文件名查找对应的磁盘上的inode
 - Inode.create：在根目录下创建一个文件
 - Inode.read_at：根据inode找到文件数据所在的磁盘数据块，并读到内存中
 - Inode.write_at：根据inode找到文件数据所在的磁盘数据块，把内存中数据写入到磁盘数据块中

上述五层就构成了easyfs文件系统的整个内容。我们可以把easyfs文件系统看成是一个库，被应用程序调用。而 ``easy-fs-fuse`` 这个应用就通过调用easyfs文件系统库中各种函数，并用Linux上的文件模拟了一个块设备，就可以在这个模拟的块设备上创建了一个easyfs文件系统。

第三步，我们需要把easyfs文件系统加入到我们的操作系统内核中。这还需要做两件事情，第一件是在Qemu模拟的 ``virtio`` 块设备上实现块设备驱动程序 ``os/src/drivers/block/virtio_blk.rs`` 。由于我们可以直接使用 ``virtio-drivers`` crate中的块设备驱动，所以只要提供这个块设备驱动所需要的内存申请与释放以及虚实地址转换的4个函数就可以了。而我们之前操作系统中的虚存管理实现中，以及有这些函数，导致块设备驱动程序很简单，具体实现细节都被 ``virtio-drivers`` crate封装好了。

第二件事情是把文件访问相关的系统调用与easyfs文件系统连接起来。在easfs文件系统中是没有进程的概念的。而进程是程序运行过程中访问资源的管理实体，这就要对 ``easy-fs`` crate 提供的 ``Inode`` 结构进一步封装，形成 ``OSInode`` 结构，以表示进程中一个打开的常规文件。对于应用程序而言，它理解的磁盘数据是常规的文件和目录，不是 ``OSInode`` 这样相对复杂的结构。其实常规文件对应的 OSInode 是文件在操作系统内核中的内部表示，因此需要为它实现 File Trait 从而能够可以将它放入到进程文件描述符表中，并通过 sys_read/write 系统调用进行读写。这样就建立了文件与 ``OSInode`` 的对应关系，并通过上面描述的三个步骤完成了包含文件系统的操作系统内核，并能给应用提供基于文件的系统调用服务。

完成包含文件系统的操作系统内核后，我们在shell程序和内核中支持命令行参数的解析和传递，这样可以让应用根据灵活地通过命令行参数来动态地表示要操作的文件。这需要扩展对应的系统调用 ``sys_exec`` ,主要的改动就是在创建新进程时，把命令行参数压入用户栈中，这样应用程序在执行时就可以从用户栈中获取到命令行的参数值了。

在上一章，我们提到了把标准输出设备在文件描述符表中的文件描述符的值规定为 1 ，用 Stdin 表示；把标准输入设备在文件描述符表中的文件描述符的值规定为 0，用 stdout 表示 。另外，还有一条文件描述符相关的重要规则：即进程打开一个文件的时候，内核总是会将文件分配到该进程文件描述符表中编号 最小的 空闲位置。利用这些约定，只实现新的系统调用 ``sys_dup`` 完成对文件描述符的复制，就可以巧妙地实现标准 I/O 重定向功能了。

具体思路是，在某应用进程执行之前，父进程（比如 user_shell进程）要对子应用进程的文件描述符表进行某种替换。以输出为例，父进程在创建子进程前，提前打开一个常规文件 A，然后 ``fork`` 子进程，在子进程的最初执行中，通过 ``sys_close`` 关闭 Stdout 文件描述符，用 ``sys_dup`` 复制常规文件 A 的文件描述符，这样 Stdout 文件描述符实际上指向的就是常规文件A了，这时再通过 ``sys_close`` 关闭常规文件 A 的文件描述符。至此，常规文件 A 替换掉了应用文件描述符表位置 1 处的标准输出文件，这就完成了所谓的 **重定向** ，即完成了执行新应用前的准备工作。

接下来是子进程调用 ``sys_exec`` 系统调用，创建并开始执行新子应用进程。在重定向之后，新的子应用进程认为自己输出到 fd=1 的标准输出文件，但实际上是输出到父进程（比如 user_shell进程）指定的文件A中。文件这一抽象概念透明化了文件、I/O设备之间的差异，因为在进程看来无论是标准输出还是常规文件都是一种文件，可以通过同样的接口来读写。这就是文件的强大之处。