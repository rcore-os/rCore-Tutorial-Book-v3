引言
=========================================

本章导读
-----------------------------------------

在上一章中，我们引入了非常重要的进程的概念。截止到目前为止，进程能够进行交互的 I/O 资源还非常有限。它只能接受用户在键盘上的输入，并将字符输出到屏幕上。我们一般将它们分别称为标准输入和标准输出。

本章我们会引入操作系统中的另一个概念——文件描述符。每个进程都在它自己的文件描述符表中保存着多个文件描述符，而进程通过每个文件描述符均可对一个它已经请求内核打开的 I/O 资源（也即文件）进行读写。文件描述符可以描述包括标准输入/标准输出在内的多种不同的 I/O 资源。

本章我们首先将标准输入/标准输出的访问改造为基于文件描述符，然后同样基于文件描述符实现一种父子进程之间的通信机制——管道。

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

进入用户终端后，可以运行管道机制的简单测例 ``pipetest`` 和比较复杂的测例 ``pipe_large_test`` 。 ``pipetest`` 需要保证父进程通过管道传输给子进程的字符串不会发生变化；而 ``pipe_large_test`` 中，父进程将一个长随机字符串传给子进程，随后父子进程同时计算该字符串的某种 Hash 值（逐字节求和），子进程会将计算后的 Hash 值传回父进程，而父进程接受到之后，需要验证两个 Hash 值相同，才算通过测试。

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
