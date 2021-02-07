引言
===========================================

本章导读
-------------------------------------------

在正式开始这一章的介绍之前，我们很高兴告诉读者：在前面的章节中基本涵盖了一个功能相对完善的内核抽象所需的所有硬件机制，而从本章开始我们所做的主要是一些软件上的工作，这会略微轻松一些。

在前面的章节中，随着应用的需求逐渐变得复杂，作为其执行环境的内核也需要在硬件提供的相关机制的支持之下努力为应用提供更多强大、易用且安全的抽象。让我们先来简单回顾一下：

- 第一章《RV64 裸机应用》中，由于我们从始至终只需运行一个应用，这时我们的内核看起来只是一个 **函数库** ，它会对应用的执行环境进行初始化，包括设置函数调用栈的位置使得应用能够正确使用内存。此外，它还将 SBI 接口函数进行了封装使得应用更容易使用这些功能。
- 第二章《批处理系统》中，我们需要自动加载并执行一个固定序列内的多个应用，当一个应用出错或者正常退出之后则切换到下一个。为了让这个流程能够稳定进行而不至于被某个应用的错误所破坏，内核需要借助硬件提供的 **特权级机制** 将应用代码放在 U 特权级执行，并对它的行为进行限制。一旦应用出现错误或者请求一些只有内核才能提供的服务时，控制权会移交给内核并对该 **Trap** 进行处理。
- 第三章《多道程序与分时多任务》中，出于一些对于总体性能或者交互性的要求，从 CPU 的角度看，它在执行一个应用一段时间之后，会暂停这个应用并切换出去，等到之后切换回来的时候再继续执行。其核心机制就是 **任务切换** 。对于每个应用来说，它会认为自己始终独占一个 CPU ，不过这只是内核对 CPU 资源的恰当抽象给它带来的一种幻象。
- 第四章《地址空间》中，我们利用一种经典的抽象—— **地址空间** 来代替先前对于物理内存的直接访问。这样做使得每个应用独占一个访存空间并与其他应用隔离起来，并由内核和硬件机制保证不同应用的数据被实际存放在物理内存上的位置也不相交。于是开发者在开发应用的时候无需顾及其他应用，整个系统的安全性也得到了一定保证。

事实上，由于我们还没有充分发掘这些抽象的能力，应用的开发和使用仍然比较受限。这尤其体现在交互能力上。目前为止，所有的应用都是在内核初始化阶段被一并加载到内存中的，之后也无法对应用进行动态增删，从用户的角度来看这和第二章的批处理系统似乎并没有什么不同。

.. _term-terminal:
.. _term-command-line:

于是，本章我们会开发一个用户 **终端** (Terminal) 或称 **命令行** (Command Line) 作为用户界面，它就和我们今天常用的 OS 中的没有什么不同：只需在其中输入命令即可启动或杀死应用，或者监控系统的运行状况。这自然是现代 OS 中不可缺少的一部分，大大增加了系统的可交互性。

为了方便开发，我们需要在已有抽象的基础上引入一个新的抽象：进程，还需要实现若干基于进程的功能强大的系统调用。

实践体验
-------------------------------------------

获取本章代码：

.. code-block:: console

   $ git clone https://github.com/rcore-os/rCore-Tutorial-v3.git
   $ cd rCore-Tutorial-v3
   $ git checkout ch5

在 qemu 模拟器上运行本章代码：

.. code-block:: console

   $ cd os
   $ make run

将 Maix 系列开发版连接到 PC，并在上面运行本章代码：

.. code-block:: console

   $ cd os
   $ make run BOARD=k210

待内核初始化完毕之后，将在屏幕上打印可用的应用列表并进入用户终端（以 K210 平台为例）：

.. code-block::

    [rustsbi] Platform: K210
    [rustsbi] misa: RV64ACDFIMSU
    [rustsbi] mideleg: 0x22
    [rustsbi] medeleg: 0x1ab
    [rustsbi] Kernel entry: 0x80020000
    [kernel] Hello, world!
    last 800 Physical Frames.
    .text [0x80020000, 0x8002e000)
    .rodata [0x8002e000, 0x80032000)
    .data [0x80032000, 0x800cf000)
    .bss [0x800cf000, 0x802e0000)
    mapping .text section
    mapping .rodata section
    mapping .data section
    mapping .bss section
    mapping physical memory
    remap_test passed!
    after initproc!
    /**** APPS ****
    exit
    fantastic_text
    forktest
    forktest2
    forktest_simple
    forktree
    hello_world
    initproc
    matrix
    sleep
    sleep_simple
    stack_overflow
    user_shell
    usertests
    yield
    **************/
    Rust user shell
    >> 

只需输入应用的名称并回车即可在系统中执行该应用。如果输入错误的话可以使用退格键 (Backspace) 。以应用 ``exit`` 为例：

.. code-block::

    >> exit
    I am the parent. Forking the child...
    I am the child.
    I am parent, fork a child pid 3
    I am the parent, waiting now..
    waitpid 3 ok.
    exit pass.
    Shell: Process 2 exited with code 0
    >> 

当应用执行完毕后，将继续回到用户终端的命令输入模式。