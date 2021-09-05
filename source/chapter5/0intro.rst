引言
===========================================

本章导读
-------------------------------------------

在正式开始这一章的介绍之前，我们很高兴告诉读者：在前面的章节中基本涵盖了一个功能相对完善的内核抽象所需的所有硬件机制，而从本章开始我们所做的主要是一些软件上的工作，这会略微轻松一些。

在前面的章节中，随着应用的需求逐渐变得复杂，作为其执行环境的内核也需要在硬件提供的相关机制的支持之下努力为应用提供更多强大、易用且安全的抽象。让我们先来简单回顾一下：

- 第一章《RV64 裸机应用》中，由于我们从始至终只需运行一个应用，这时我们的内核看起来只是一个 **函数库** ，它会对应用的执行环境进行初始化，包括设置函数调用栈的位置使得应用能够正确使用内存。此外，它还将 SBI 接口函数进行了封装使得应用更容易使用这些功能。
- 第二章《批处理系统》中，我们需要自动加载并执行一个固定序列内的多个应用，当一个应用出错或者正常退出之后则切换到下一个。为了让这个流程能够稳定进行而不至于被某个应用的错误所破坏，内核需要借助硬件提供的 **特权级机制** 将应用代码放在 U 特权级执行，并对它的行为进行限制。一旦应用出现错误或者请求一些只有内核才能提供的服务时，控制权会移交给内核并对该 **Trap** 进行处理。
- 第三章《多道程序与分时多任务》中，出于一些对于总体性能或者交互性的要求，从 CPU 的角度看，它在执行一个应用一段时间之后，会暂停这个应用并切换出去，等到之后切换回来的时候再继续执行。其核心机制就是 **任务切换** 。对于每个应用来说，它会认为自己始终独占一个 CPU ，不过这只是内核对 CPU 资源的恰当抽象给它带来的一种幻象。
- 第四章《地址空间》中，我们利用一种经典的抽象—— **地址空间** 来代替先前对于物理内存的直接访问。这样做使得每个应用独占一个访存空间并与其他应用隔离起来，并由内核和硬件机制保证不同应用的数据（应用间的共享数据除外）被实际存放在物理内存上的位置也不相交。于是开发者在开发应用的时候无需顾及其他应用，整个系统的安全性也得到了一定保证。

事实上，由于我们还没有充分发掘这些抽象的能力，应用的开发和使用仍然比较受限，且用户在应用运行过程中的灵活性和交互性不够强，这尤其体现在交互能力上。目前为止，所有的应用都是在内核初始化阶段被一并加载到内存中的，之后也无法对应用进行动态增删，从用户的角度来看这和第二章的批处理系统似乎并没有什么不同。

.. _term-terminal:
.. _term-command-line:

于是，本章我们会开发一个用户 **终端** (Terminal) 或称 **命令行** 应用(Command Line Application, 俗称 **Shell** ) ，形成用户与操作系统进行交互的命令行界面(Command Line Interface)，它就和我们今天常用的 OS 中的命令行应用（如 Linux中的bash，Windows中的CMD等）没有什么不同：只需在其中输入命令即可启动或杀死应用，或者监控系统的运行状况。这自然是现代 OS 中不可缺少的一部分，并大大增加了系统的 **可交互性** ，使得用户可以更加灵活地控制系统。

为了在用户态就可以借助操作系统的服务动态灵活地管理和控制应用的执行，我们需要在已有的 **任务** 抽象的基础上进一步扩展，形成新的抽象： **进程** ，并实现若干基于 **进程** 的强大系统调用。

- *创建* (Create)：操作系统需要提供一些创建新进程的服务。用户在shell中键入命令或用鼠标双击应用程序图标(这需要GUI界面，目前我们还没有实现)时，会调用操作系统服务来创建新进程，运行指定的程序。
- *销毁* (Destroy)：操作系统还需提供退出并销毁进程的服务。进程会在运行完成后可自行退出，但还需要其他进程（如创建这些进程的父进程）来回收这些进程最后的资源并销毁这些进程。
- *等待* (Wait)：操作系统提供等待进程停止运行是很有用的，比如上面提到的退出信息的收集。
- *信息* (Info)：操作系统也可提供有关进程的身份和状态等进程信息，例如进程的ID，进程的运行状态，进程的优先级等。
- 其他控制：操作系统还可有其他的进程控制服务。例如，让一个进程能够杀死另外一个进程，暂停进程（停止运行一段时间），恢复进程（继续运行）等。


.. note::

   **任务和进程的关系与区别**

   第三章提到的 **任务** 和这里提到的 **进程** 有何关系和区别？ 这需要从二者对资源的占用和执行的过程这两个方面来进行分析。

   任务和进程都是一个程序的执行过程，或表示了一个运行的程序；都是能够被操作系统打断并通过切换来分时占用CPU资源；都需要 **地址空间** 来放置代码和数据；都有从开始运行到结束运行这样的生命周期。

   第三章提到的 **任务** 是这里提到的 **进程** 的初级阶段，还没进化到拥有更强大的动态变化的功能：进程可以在运行的过程中，创建 **子进程** 、 用新的 **程序** 内容覆盖已有的 **程序** 内容、可管理更多的 物理或虚拟的 **资源** 。
 


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

将 Maix 系列开发板连接到 PC，并在上面运行本章代码：

.. code-block:: console

   $ cd os
   $ make run BOARD=k210

待内核初始化完毕之后，将在屏幕上打印可用的应用列表并进入shell程序（以 K210 平台为例）：

.. code-block::

   [rustsbi] RustSBI version 0.1.1
   .______       __    __      _______.___________.  _______..______   __
   |   _  \     |  |  |  |    /       |           | /       ||   _  \ |  |
   |  |_)  |    |  |  |  |   |   (----`---|  |----`|   (----`|  |_)  ||  |
   |      /     |  |  |  |    \   \       |  |      \   \    |   _  < |  |
   |  |\  \----.|  `--'  |.----)   |      |  |  .----)   |   |  |_)  ||  |
   | _| `._____| \______/ |_______/       |__|  |_______/    |______/ |__|

   [rustsbi] Platform: K210 (Version 0.1.0)
   [rustsbi] misa: RV64ACDFIMSU
   [rustsbi] mideleg: 0x22
   [rustsbi] medeleg: 0x1ab
   [rustsbi] Kernel entry: 0x80020000
   [kernel] Hello, world!
   last 808 Physical Frames.
   .text [0x80020000, 0x8002e000)
   .rodata [0x8002e000, 0x80032000)
   .data [0x80032000, 0x800c7000)
   .bss [0x800c7000, 0x802d8000)
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

其中 ``usertests`` 打包了很多应用，只要执行它就能够自动执行一系列应用。

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

当应用执行完毕后，将继续回到shell程序的命令输入模式。

本章代码树
--------------------------------------

.. code-block::
   :linenos:

   ./os/src
   Rust        25 Files    1760 Lines
   Assembly     3 Files      88 Lines

   ├── bootloader
   │   ├── rustsbi-k210.bin
   │   └── rustsbi-qemu.bin
   ├── LICENSE
   ├── os
   │   ├── build.rs(修改：基于应用名的应用构建器)
   │   ├── Cargo.toml
   │   ├── Makefile
   │   └── src
   │       ├── config.rs
   │       ├── console.rs
   │       ├── entry.asm
   │       ├── lang_items.rs
   │       ├── link_app.S
   │       ├── linker-k210.ld
   │       ├── linker-qemu.ld
   │       ├── loader.rs(修改：基于应用名的应用加载器)
   │       ├── main.rs(修改)
   │       ├── mm(修改：为了支持本章的系统调用对此模块做若干增强)
   │       │   ├── address.rs
   │       │   ├── frame_allocator.rs
   │       │   ├── heap_allocator.rs
   │       │   ├── memory_set.rs
   │       │   ├── mod.rs
   │       │   └── page_table.rs
   │       ├── sbi.rs
   │       ├── syscall
   │       │   ├── fs.rs(修改：新增 sys_read)
   │       │   ├── mod.rs(修改：新的系统调用的分发处理)
   │       │   └── process.rs（修改：新增 sys_getpid/fork/exec/waitpid）
   │       ├── task
   │       │   ├── context.rs
   │       │   ├── manager.rs(新增：任务管理器，为上一章任务管理器功能的一部分)
   │       │   ├── mod.rs(修改：调整原来的接口实现以支持进程)
   │       │   ├── pid.rs(新增：进程标识符和内核栈的 Rust 抽象)
   │       │   ├── processor.rs(新增：处理器管理结构 ``Processor`` ，为上一章任务管理器功能的一部分)
   │       │   ├── switch.rs
   │       │   ├── switch.S
   │       │   └── task.rs(修改：支持进程机制的任务控制块)
   │       ├── timer.rs
   │       └── trap
   │           ├── context.rs
   │           ├── mod.rs(修改：对于系统调用的实现进行修改以支持进程系统调用)
   │           └── trap.S
   ├── README.md
   ├── rust-toolchain
   ├── tools
   │   ├── kflash.py
   │   ├── LICENSE
   │   ├── package.json
   │   ├── README.rst
   │   └── setup.py
   └── user(对于用户库 user_lib 进行修改，替换了一套新的测例)
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
         │   ├── sleep.rs
         │   ├── sleep_simple.rs
         │   ├── stack_overflow.rs
         │   ├── user_shell.rs
         │   ├── usertests.rs
         │   └── yield.rs
         ├── console.rs
         ├── lang_items.rs
         ├── lib.rs
         ├── linker.ld
         └── syscall.rs


本章代码导读
-----------------------------------------------------

本章的第一小节 :doc:`/chapter5/1process` 介绍了操作系统中经典的进程概念，并描述我们将要实现的参考自 Unix 系内核并经过简化的精简版进程模型。在该模型下，若想对进程进行管理，实现创建、退出等操作，核心就在于 ``fork/exec/waitpid`` 三个系统调用。

首先我们修改运行在应用态的应用软件，它们均放置在 ``user`` 目录下。在新增系统调用的时候，需要在 ``user/src/lib.rs`` 中新增一个 ``sys_*`` 的函数，它的作用是将对应的系统调用按照与内核约定的 ABI 在 ``syscall`` 中转化为一条用于触发系统调用的 ``ecall`` 的指令；还需要在用户库 ``user_lib`` 将 ``sys_*`` 进一步封装成一个应用可以直接调用的与系统调用同名的函数。通过这种方式我们新增三个进程模型中核心的系统调用 ``fork/exec/waitpid`` ，一个查看进程 PID 的系统调用 ``getpid`` ，还有一个允许应用程序获取用户键盘输入的 ``read`` 系统调用。

基于进程模型，我们在 ``user/src/bin`` 目录下重新实现了一组应用程序。其中有两个特殊的应用程序：用户初始程序 ``initproc.rs`` 和 shell 程序 ``user_shell.rs`` ，可以认为它们位于内核和其他应用程序之间的中间层提供一些基础功能，但是它们仍处于应用层。前者会被内核唯一自动加载、也是最早加载并执行，后者则负责从键盘接收用户输入的应用名并执行对应的应用。剩下的应用从不同层面测试了我们内核实现的正确性，读者可以自行参考。值得一提的是， ``usertests`` 可以按照顺序执行绝大部分应用，会在测试的时候为我们提供很多方便。

接下来就需要在内核中实现简化版的进程机制并支持新增的系统调用。在本章第二小节 :doc:`/chapter5/2core-data-structures` 中我们对一些进程机制相关的数据结构进行了重构或者修改：

- 为了支持基于应用名而不是应用 ID 来查找应用 ELF 可执行文件，从而实现灵活的应用加载，在 ``os/build.rs`` 以及 ``os/src/loader.rs`` 中更新了 ``link_app.S`` 的格式使得它包含每个应用的名字，另外提供 ``get_app_data_by_name`` 接口获取应用的 ELF 数据。
- 在本章之前，任务管理器 ``TaskManager`` 不仅负责管理所有的任务状态，还维护着我们的 CPU 当前正在执行哪个任务。这种设计耦合度较高，我们将后一个功能分离到 ``os/src/task/processor.rs`` 中的处理器管理结构 ``Processor`` 中，它负责管理 CPU 上执行的任务和一些其他信息；而 ``os/src/task/manager.rs`` 中的任务管理器 ``TaskManager`` 仅负责管理所有任务。
- 针对新的进程模型，我们复用前面章节的任务控制块 ``TaskControlBlock`` 作为进程控制块来保存进程的一些信息，相比前面章节还要新增 PID、内核栈、应用数据大小、父子进程、退出码等信息。它声明在 ``os/src/task/task.rs`` 中。
- 从本章开始，内核栈在内核地址空间中的位置由所在进程的 PID 决定，我们需要在二者之间建立联系并提供一些相应的资源自动回收机制。可以参考 ``os/src/task/pid.rs`` 。

有了这些数据结构的支撑，我们在本章第三小节 :doc:`/chapter5/3implement-process-mechanism` 实现进程机制。它可以分成如下几个方面：

- 初始进程的自动创建。在内核初始化的时候需要调用 ``os/src/task/mod.rs`` 中的 ``add_initproc`` 函数，它会调用 ``TaskControlBlock::new`` 读取并解析初始应用 ``initproc`` 的 ELF 文件数据并创建初始进程 ``INITPROC`` ，随后会将它加入到全局任务管理器 ``TASK_MANAGER`` 中参与调度。
- 进程切换机制。当一个进程退出或者是主动/被动交出 CPU 使用权之后需要由内核将 CPU 使用权交给其他进程。在本章中我们沿用 ``os/src/task/mod.rs`` 中的 ``suspend_current_and_run_next`` 和 ``exit_current_and_run_next`` 两个接口来实现进程切换功能，但是需要适当调整它们的实现。我们需要调用 ``os/src/task/task.rs`` 中的 ``schedule`` 函数进行进程切换，它会首先切换到处理器的 idle 控制流（即 ``os/src/task/processor`` 的 ``Processor::run`` 方法），然后在里面选取要切换到的进程并切换过去。
- 进程调度机制。在进程切换的时候我们需要选取一个进程切换过去。选取进程逻辑可以参考 ``os/src/task/manager.rs`` 中的 ``TaskManager::fetch_task`` 方法。
- 进程生成机制。这主要是指 ``fork/exec`` 两个系统调用。它们的实现分别可以在 ``os/src/syscall/process.rs`` 中找到，分别基于 ``os/src/process/task.rs`` 中的 ``TaskControlBlock::fork/exec`` 。
- 进程资源回收机制。当一个进程主动退出或出错退出的时候，在 ``exit_current_and_run_next`` 中会立即回收一部分资源并在进程控制块中保存退出码；而需要等到它的父进程通过 ``waitpid`` 系统调用（与 ``fork/exec`` 两个系统调用放在相同位置）捕获到它的退出码之后，它的进程控制块才会被回收，从而所有资源都被回收。
- 为了支持用户终端 ``user_shell`` 读取用户键盘输入的功能，还需要实现 ``read`` 系统调用，它可以在 ``os/src/syscall/fs.rs`` 中找到。