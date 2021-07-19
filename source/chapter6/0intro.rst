引言
=========================================

本章导读
-----------------------------------------

在上一章中，我们引入了非常重要的进程的概念，以及与进程管理相关的 ``fork`` 、 ``exec`` 等创建新进程相关的系统调用。虽然操作系统提供新进程的动态创建和执行的服务有了很大的改进，但截止到目前为止，进程在输入和输出方面，还有不少限制。特别是进程能够进行交互的 I/O 资源还非常有限，只能接受用户在键盘上的输入，并将字符输出到屏幕上。我们一般将它们分别称为 **标准** 输入和 **标准** 输出。而且进程之间缺少信息交换的能力，这样就限制了通过进程间的合作一起完成一个大事情的能力。

其实在 **UNIX** 的早期发展历史中，也碰到了同样的问题，每个程序专注在完成一件事情上，但缺少把多个程序联合在一起完成复杂功能的机制。直到1975年UNIX v6中引入了让人眼前一亮的创新机制-- **I/O重定向** 与 **管道（pipe）** 。基于这两种机制，操作系统在不用改变应用程序的情况下，可以将一个程序的输出重新定向到另外一个程序的输入中，这样程序之间就可以进行任意的连接，并组合出各种灵活的复杂功能。

本章我们也会引入新操作系统概念 -- 管道，并进行实现（下一章将实现I/O重定向）。除了键盘和屏幕这样的 **标准** 输入和 **标准** 输出之外，管道其实也可以看成是一种特殊的输入和输出，而后面一章讲解的 **文件系统** 中的对持久化存储数据的抽象 **文件(file)** 也是一种存储设备的输入和输出。所以，我们可以把这三种输入输出都统一在 **文件(file)**  这个抽象之中。这也体现了在 Unix 操作系统中， ” **一切皆文件** “ (Everything is a file) 重要设计哲学。

在本章中提前引入 **文件** 这个概念，但本章不会详细讲解，只是先以最简单直白的方式对 **文件** 这个抽象进行简化的设计与实现。站在本章的操作系统的角度来看， **文件** 成为了一种需要操作系统管理的I/O资源。 

为了让应用能够基于 **文件** 这个抽象接口进行I/O操作，我们就需要对 **进程** 这个概念进行扩展，让它能够管理 **文件** 这种资源。具体而言，就是要对进程控制块进行一定的扩展。为了统一表示 **标准** 输入和 **标准** 输出和管道，我们将在每个进程控制块中增加一个 **文件描述符表** ，在表中保存着多个 **文件** 记录信息。每个文件描述符是一个非负的索引值，即对应文件记录信息的条目在文件描述符表中的索引，可方便进程表示当前使用的 **标准** 输入、 **标准** 输出和管道（当然在下一章还可以表示磁盘上的一块数据）。用户进程访问文件将很简单，它只需通过文件描述符，就可以对 **文件** 进行读写，从而完成接收键盘输入，向屏幕输出，以及两个进程之间进行数据传输的操作。

简而言之，本章我们首先将标准输入/标准输出的访问改造为基于文件描述符，然后同样基于文件描述符实现一种父子进程之间的通信机制——管道，从而实现灵活的进程间通信，并基于管道支持进程组合来实现复杂功能。

实践体验
-----------------------------------------

获取本章代码：

.. code-block:: console

   $ git clone https://github.com/rcore-os/rCore-Tutorial-v3.git
   $ cd rCore-Tutorial-v3
   $ git checkout ch6

在 qemu 模拟器上运行本章代码：

.. code-block:: console

   $ cd os
   $ make run

将 Maix 系列开发板连接到 PC，并在上面运行本章代码：

.. code-block:: console

   $ cd os
   $ make run BOARD=k210

进入shell程序后，可以运行管道机制的简单测例 ``pipetest`` 和比较复杂的测例 ``pipe_large_test`` 。 ``pipetest`` 需要保证父进程通过管道传输给子进程的字符串不会发生变化；而 ``pipe_large_test`` 中，父进程将一个长随机字符串传给子进程，随后父子进程同时计算该字符串的某种 Hash 值（逐字节求和），子进程会将计算后的 Hash 值传回父进程，而父进程接受到之后，需要验证两个 Hash 值相同，才算通过测试。

运行两个测例的输出可能如下：

.. code-block::

    >> pipetest
    Read OK, child process exited!
    pipetest passed!
    Shell: Process 2 exited with code 0
    >> pipe_large_test
    sum = 369114(parent)
    sum = 369114(child)
    Child process exited!
    pipe_large_test passed!
    Shell: Process 2 exited with code 0
    >> 



本章代码树
-----------------------------------------

.. code-block::

    ./os/src
    Rust        28 Files    2061 Lines
    Assembly     3 Files      88 Lines

    ├── bootloader
    │   ├── rustsbi-k210.bin
    │   └── rustsbi-qemu.bin
    ├── LICENSE
    ├── os
    │   ├── build.rs
    │   ├── Cargo.lock
    │   ├── Cargo.toml
    │   ├── Makefile
    │   └── src
    │       ├── config.rs
    │       ├── console.rs
    │       ├── entry.asm
    │       ├── fs(新增：文件系统子模块 fs)
    │       │   ├── mod.rs(包含已经打开且可以被进程读写的文件的抽象 File Trait)
    │       │   ├── pipe.rs(实现了 File Trait 的第一个分支——可用来进程间通信的管道)
    │       │   └── stdio.rs(实现了 File Trait 的第二个分支——标准输入/输出)
    │       ├── lang_items.rs
    │       ├── link_app.S
    │       ├── linker-k210.ld
    │       ├── linker-qemu.ld
    │       ├── loader.rs
    │       ├── main.rs
    │       ├── mm
    │       │   ├── address.rs
    │       │   ├── frame_allocator.rs
    │       │   ├── heap_allocator.rs
    │       │   ├── memory_set.rs
    │       │   ├── mod.rs
    │       │   └── page_table.rs(新增：应用地址空间的缓冲区抽象 UserBuffer 及其迭代器实现)
    │       ├── sbi.rs
    │       ├── syscall
    │       │   ├── fs.rs(修改：调整 sys_read/write 的实现，新增 sys_close/pipe)
    │       │   ├── mod.rs(修改：调整 syscall 分发)
    │       │   └── process.rs
    │       ├── task
    │       │   ├── context.rs
    │       │   ├── manager.rs
    │       │   ├── mod.rs
    │       │   ├── pid.rs
    │       │   ├── processor.rs
    │       │   ├── switch.rs
    │       │   ├── switch.S
    │       │   └── task.rs(修改：在任务控制块中加入文件描述符表相关机制)
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
            │   ├── exit.rs
            │   ├── fantastic_text.rs
            │   ├── forktest2.rs
            │   ├── forktest.rs
            │   ├── forktest_simple.rs
            │   ├── forktree.rs
            │   ├── hello_world.rs
            │   ├── initproc.rs
            │   ├── matrix.rs
            │   ├── pipe_large_test.rs(新增)
            │   ├── pipetest.rs(新增)
            │   ├── run_pipe_test.rs(新增)
            │   ├── sleep.rs
            │   ├── sleep_simple.rs
            │   ├── stack_overflow.rs
            │   ├── user_shell.rs
            │   ├── usertests.rs
            │   └── yield.rs
            ├── console.rs
            ├── lang_items.rs
            ├── lib.rs(新增两个系统调用：sys_close/sys_pipe)
            ├── linker.ld
            └── syscall.rs(新增两个系统调用：sys_close/sys_pipe)



本章代码导读
-----------------------------------------------------             

在本章第一节 :doc:`/chapter6/1file-descriptor` 中，我们引入了文件的概念，用它来代表进程可以读写的多种被内核管理的硬件/软件资源。进程必须通过系统调用打开一个文件，将文件加入到自身的文件描述符表中，才能通过文件描述符（也就是某个特定文件在自身文件描述符表中的下标）来读写该文件。

文件的抽象 Trait ``File`` 声明在 ``os/src/fs/mod.rs`` 中，它提供了 ``read/write`` 两个接口，可以将数据写入应用缓冲区抽象 ``UserBuffer`` ，或者从应用缓冲区读取数据。应用缓冲区抽象类型 ``UserBuffer`` 来自 ``os/src/mm/page_table.rs`` 中，它将 ``translated_byte_buffer`` 得到的 ``Vec<&'static mut [u8]>`` 进一步包装，不仅保留了原有的分段读写能力，还可以将其转化为一个迭代器逐字节进行读写，这在读写一些流式设备的时候特别有用。

在进程控制块 ``TaskControlBlock`` 中需要加入文件描述符表字段 ``fd_table`` ，可以看到它是一个向量，里面保存了若干实现了 ``File`` Trait 的文件，由于采用动态分发，文件的类型可能各不相同。 ``os/src/syscall/fs.rs`` 的 ``sys_read/write`` 两个读写文件的系统调用需要访问当前进程的文件描述符表，用应用传入内核的文件描述符来索引对应的已打开文件，并调用 ``File`` Trait 的 ``read/write`` 接口； ``sys_close`` 这可以关闭一个文件。调用 ``TaskControlBlock`` 的 ``alloc_fd`` 方法可以在文件描述符表中分配一个文件描述符。进程控制块的其他操作也需要考虑到新增的文件描述符表字段的影响，如 ``TaskControlBlock::new`` 的时候需要对 ``fd_table`` 进行初始化， ``TaskControlBlock::fork`` 中则需要将父进程的 ``fd_table`` 复制一份给子进程。

到本章为止我们支持两种文件：标准输入输出和管道。不同于前面章节，我们将标准输入输出分别抽象成 ``Stdin`` 和 ``Stdout`` 两个类型，并为他们实现 ``File`` Trait 。在 ``TaskControlBlock::new`` 创建初始进程的时候，就默认打开了标准输入输出，并分别绑定到文件描述符 0 和 1 上面。

管道 ``Pipe`` 是另一种文件，它可以用于父子进程间的单向进程间通信。我们也需要为它实现 ``File`` Trait 。 ``os/src/syscall/fs.rs`` 中的系统调用 ``sys_pipe`` 可以用来打开一个管道并返回读端/写端两个文件的文件描述符。管道的具体实现在 ``os/src/fs/pipe.rs`` 中，本章第二节 :doc:`/chapter6/2pipe` 中给出了详细的讲解。管道机制的测试用例可以参考 ``user/src/bin`` 目录下的 ``pipetest.rs`` 和 ``pipe_large_test.rs`` 两个文件。