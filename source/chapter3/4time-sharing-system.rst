分时多任务系统与抢占式调度
===========================================================

本节导读
--------------------------

本节的重点是操作系统对中断的处理和对应用程序的抢占。为此，对 **任务** 的概念进行进一步扩展和延伸：

-  分时多任务：操作系统管理每个应用程序，以时间片为单位来分时占用处理器运行应用。
-  时间片轮转调度：操作系统在一个程序用完其时间片后，就抢占当前程序并调用下一个程序执行，周而复始，形成对应用程序在任务级别上的时间片轮转调度。


分时多任务系统的背景
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

.. _term-throughput:

上一节我们介绍了多道程序，它是一种允许应用在等待外设时主动切换到其他应用来达到总体 CPU 利用率最高的设计。那个时候，应用是不太注重自身的运行情况的，即使它 yield 交出 CPU 资源之后需要很久才能再拿到，使得它真正在 CPU 执行的相邻两时间段距离都很远，应用也是无所谓的。因为它们的目标是总体 CPU 利用率最高，可以换成一个等价的指标： **吞吐量** (Throughput) 。大概可以理解为在某个时间点将一组应用放进去，要求在一段固定的时间之内执行完毕的应用最多，或者是总进度百分比最大。因此，所有的应用和编写应用的程序员都有这样的共识：只要 CPU 一直在做实际的工作就好。

.. _term-background-application:
.. _term-interactive-application:
.. _term-latency:

从现在的眼光来看，当时的应用更多是一种 **后台应用** (Background Application) ，在将它加入执行队列之后我们只需定期确认它的运行状态。而随着技术的发展，涌现了越来越多的 **交互式应用** (Interactive Application) ，它们要达成的一个重要目标就是提高用户操作的响应速度，这样才能优化应用的使用体验。对于这些应用而言，即使需要等待外设或某些事件，它们也不会倾向于主动 yield 交出 CPU 使用权，因为这样可能会带来无法接受的延迟。也就是说，应用之间相比合作更多的是互相竞争宝贵的硬件资源。

.. _term-cooperative-scheduling:
.. _term-preemptive-scheduling:

如果应用自己很少 yield ，内核就要开始收回之前下放的权力，由它自己对 CPU 资源进行集中管理并合理分配给各应用，这就是内核需要提供的任务调度能力。我们可以将多道程序的调度机制分类成 **协作式调度** (Cooperative Scheduling) ，因为它的特征是：只要一个应用不主动 yield 交出 CPU 使用权，它就会一直执行下去。与之相对， **抢占式调度** (Preemptive Scheduling) 则是应用 *随时* 都有被内核切换出去的可能。

.. _term-time-slice:
.. _term-fairness:

现代的任务调度算法基本都是抢占式的，它要求每个应用只能连续执行一段时间，然后内核就会将它强制性切换出去。一般将 **时间片** (Time Slice) 作为应用连续执行时长的度量单位，每个时间片可能在毫秒量级。调度算法需要考虑：每次在换出之前给一个应用多少时间片去执行，以及要换入哪个应用。可以从性能和 **公平性** (Fairness) 两个维度来评价调度算法，后者要求多个应用分到的时间片占比不应差距过大。



时间片轮转调度
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

.. _term-round-robin:

简单起见，本书中我们使用 **时间片轮转算法** (RR, Round-Robin) 来对应用进行调度，只要对它进行少许拓展就能完全满足我们续的需求。本章中我们仅需要最原始的 RR 算法，用文字描述的话就是维护一个任务队列，每次从队头取出一个应用执行一个时间片，然后把它丢到队尾，再继续从队头取出一个应用，以此类推直到所有的应用执行完毕。


本节的代码可以在 ``ch3`` 分支上找到。


RISC-V 架构中的中断
-----------------------------------

.. _term-interrupt:
.. _term-sync:
.. _term-async:


时间片轮转调度的核心机制就在于计时。操作系统的计时功能是依靠硬件提供的时钟中断来实现的。在介绍时钟中断之前，我们先简单介绍一下中断。

**中断** (Interrupt) 和我们第二章中介绍的 用于系统调用的 **陷入**  ``Trap`` 一样都是异常 ，但是它们被触发的原因确是不同的。对于某个处理器核而言， **陷入** 与发起  **陷入** 的指令执行是 **同步** (Synchronous) 的， **陷入** 被触发的原因一定能够追溯到某条指令的执行；而中断则 **异步** (Asynchronous) 于当前正在进行的指令，也就是说中断来自于哪个外设以及中断如何触发完全与处理器正在执行的当前指令无关。

.. _term-parallel: 

.. note::

    **从底层硬件的角度区分同步和异步**

    从底层硬件的角度可能更容易理解这里所提到的同步和异步。以一个处理器传统的五级流水线设计而言，里面含有取指、译码、算术、
    访存、寄存器等单元，都属于执行指令所需的硬件资源。那么假如某条指令的执行出现了问题，一定能被其中某个单元看到并反馈给流水线控制单元，从而它会在执行预定的下一条指令之前先进入异常处理流程。也就是说，异常在这些单元内部即可被发现并解决。
    
    而对于中断，可以想象为想发起中断的是一套完全不同的电路（从时钟中断来看就是简单的计数和比较器），这套电路仅通过一根导线接入进来，当想要触发中断的时候则输入一个高电平或正边沿，处理器会在每执行完一条指令之后检查一下这根线，看情况决定是继续执行接下来的指令还是进入中断处理流程。也就是说，大多数情况下，指令执行的相关硬件单元和可能发起中断的电路是完全独立 **并行** (Parallel) 运行的，它们中间只有一根导线相连，除此之外指令执行的那些单元就完全不知道对方处于什么状态了。

在不考虑指令集拓展的情况下，RISC-V 架构中定义了如下中断：

.. list-table:: RISC-V 中断一览表
   :align: center
   :header-rows: 1
   :widths: 30 30 60

   * - Interrupt
     - Exception Code
     - Description
   * - 1
     - 1
     - Supervisor software interrupt
   * - 1
     - 3
     - Machine software interrupt
   * - 1
     - 5
     - Supervisor timer interrupt
   * - 1
     - 7
     - Machine timer interrupt
   * - 1
     - 9
     - Supervisor external interrupt
   * - 1
     - 11
     - Machine external interrupt

RISC-V 的中断可以分成三类：

.. _term-software-interrupt:
.. _term-timer-interrupt:
.. _term-external-interrupt:

- **软件中断** (Software Interrupt)
- **时钟中断** (Timer Interrupt)
- **外部中断** (External Interrupt)

另外，相比异常，中断和特权级之间的联系更为紧密，可以看到这三种中断每一个都有 M/S 特权级两个版本。中断的特权级可以决定该中断是否会被屏蔽，以及需要 Trap 到 CPU 的哪个特权级进行处理。

在判断中断是否会被屏蔽的时候，有以下规则：

- 如果中断的特权级低于 CPU 当前的特权级，则该中断会被屏蔽，不会被处理；
- 如果中断的特权级高于与 CPU 当前的特权级或相同，则需要通过相应的 CSR 判断该中断是否会被屏蔽。

以内核所在的 S 特权级为例，中断屏蔽相应的 CSR 有 ``sstatus`` 和 ``sie`` 。``sstatus`` 的 ``sie`` 为 S 特权级的中断使能，能够同时控制三种中断，如果将其清零则会将它们全部屏蔽。即使 ``sstatus.sie`` 置 1 ，还要看 ``sie`` 这个 CSR，它的三个字段  ``ssie/stie/seie`` 分别控制 S 特权级的软件中断、时钟中断和外部中断的中断使能。比如对于 S 态时钟中断来说，如果 CPU 不高于 S 特权级，需要 ``sstatus.sie`` 和 ``sie.stie`` 均为 1 该中断才不会被屏蔽；如果 CPU 当前特权级高于 S 特权级，则该中断一定会被屏蔽。

如果中断没有被屏蔽，那么接下来就需要 Trap 进行处理，而具体 Trap 到哪个特权级与一些中断代理 CSR 的设置有关。默认情况下，所有的中断都需要 Trap 到 M 特权级处理。而设置这些代理 CSR 之后，就可以 Trap 到低特权级处理，但是 Trap 到的特权级不能低于中断的特权级。事实上所有的异常默认也都是 Trap 到 M 特权级处理的，它们也有一套对应的异常代理 CSR ，设置之后也可以 Trap 到低优先级来处理异常。

我们会在 :doc:`/appendix-c/index` 中再深入介绍中断/异常代理。在正文中我们只需要了解：

- 包括系统调用（即来自 U 特权级的环境调用）在内的所有异常都会 Trap 到 S 特权级处理；
- 只需考虑 S 特权级的时钟/软件/外部中断，且它们都会被 Trap 到 S 特权级处理。

默认情况下，当 Trap 进入某个特权级之后，在 Trap 处理的过程中同特权级的中断都会被屏蔽。这里我们还需要对第二章介绍的 Trap 发生时的硬件机制做一下补充，同样以 Trap 到 S 特权级为例：

- 当 Trap 发生时，``sstatus.sie`` 会被保存在 ``sstatus.spie`` 字段中，同时 ``sstatus.sie`` 置零，这也就在 Trap 处理的过程中屏蔽了所有 S 特权级的中断；
- 当 Trap 处理完毕 ``sret`` 的时候， ``sstatus.sie`` 会恢复到 ``sstatus.spie`` 内的值。

.. _term-nested-interrupt:

也就是说，如果不去手动设置 ``sstatus`` CSR ，在只考虑 S 特权级中断的情况下，是不会出现 **嵌套中断** (Nested Interrupt) 的。嵌套中断是指在处理一个中断的过程中再一次触发了中断从而通过 Trap 来处理。由于默认情况下一旦进入 Trap 硬件就自动禁用所有同特权级中断，自然也就不会再次触发中断导致嵌套中断了。

.. note::

    **嵌套中断与嵌套 Trap**

    嵌套中断可以分为两部分：在处理一个中断的过程中又被同特权级/高特权级中断所打断。默认情况下硬件会避免前一部分，也可以通过手动设置来允许前一部分的存在；而从上面介绍的规则可以知道，后一部分则是无论如何设置都不可避免的。

    嵌套 Trap 则是指处理一个 Trap 过程中又再次发生 Trap ，嵌套中断算是嵌套 Trap 的一部分。

.. note::

    **RISC-V 架构的 U 特权级中断**

    目前，RISC-V 用户态中断作为代号 N 的一个指令集拓展而存在。有兴趣的读者可以阅读最新版的 RISC-V 特权级架构规范一探究竟。


时钟中断与计时器
------------------------------------------------------------------

由于需要一种计时机制，RISC-V 架构要求处理器要有一个内置时钟，其频率一般低于 CPU 主频。此外，还有一个计数器统计处理器自上电以来经过了多少个内置时钟的时钟周期。在 RV64 架构上，该计数器保存在一个 64 位的 CSR ``mtime`` 中，我们无需担心它的溢出问题，在内核运行全程可以认为它是一直递增的。

另外一个 64 位的 CSR ``mtimecmp`` 的作用是：一旦计数器 ``mtime`` 的值超过了 ``mtimecmp``，就会触发一次时钟中断。这使得我们可以方便的通过设置 ``mtimecmp`` 的值来决定下一次时钟中断何时触发。

可惜的是，它们都是 M 特权级的 CSR ，而我们的内核处在 S 特权级，是不被硬件允许直接访问它们的。好在运行在 M 特权级的 SEE 已经预留了相应的接口，我们可以调用它们来间接实现计时器的控制：

.. code-block:: rust

    // os/src/timer.rs

    use riscv::register::time;

    pub fn get_time() -> usize {
        time::read()
    }

``timer`` 子模块的 ``get_time`` 函数可以取得当前 ``mtime`` 计数器的值；

.. code-block:: rust
    :linenos:

    // os/src/sbi.rs

    const SBI_SET_TIMER: usize = 0;

    pub fn set_timer(timer: usize) {
        sbi_call(SBI_SET_TIMER, timer, 0, 0);
    }

    // os/src/timer.rs

    use crate::config::CLOCK_FREQ;
    const TICKS_PER_SEC: usize = 100;

    pub fn set_next_trigger() {
        set_timer(get_time() + CLOCK_FREQ / TICKS_PER_SEC);
    }

- 代码片段第 5 行， ``sbi`` 子模块有一个 ``set_timer`` 调用，是一个由 SEE 提供的标准 SBI 接口函数，它可以用来设置 ``mtimecmp`` 的值。
- 代码片段第 14 行， ``timer`` 子模块的 ``set_next_trigger`` 函数对 ``set_timer`` 进行了封装，它首先读取当前 ``mtime`` 的值，然后计算出 10ms 之内计数器的增量，再将 ``mtimecmp`` 设置为二者的和。这样，10ms 之后一个 S 特权级时钟中断就会被触发。

  至于增量的计算方式， ``CLOCK_FREQ`` 是一个预先获取到的各平台不同的时钟频率，单位为赫兹，也就是一秒钟之内计数器的增量。它可以在 ``config`` 子模块中找到。10ms 的话只需除以常数 ``TICKS_PER_SEC`` 也就是 100 即可。

后面可能还有一些计时的操作，比如统计一个应用的运行时长的需求，我们再设计一个函数：

.. code-block:: rust

    // os/src/timer.rs

    const MSEC_PER_SEC: usize = 1000;

    pub fn get_time_ms() -> usize {
        time::read() / (CLOCK_FREQ / MSEC_PER_SEC)
    }

``timer`` 子模块的 ``get_time_ms`` 可以以毫秒为单位返回当前计数器的值，这让我们终于能对时间有一个具体概念了。实现原理就不再赘述。

我们也新增一个系统调用方便应用获取当前的时间，以毫秒为单位：

.. code-block:: rust
    :caption: 第三章新增系统调用（二）

    /// 功能：获取当前的时间，以毫秒为单位。
    /// 返回值：返回当前的时间，以毫秒为单位。
    /// syscall ID：169
    fn sys_get_time() -> isize;

它在内核中的实现只需调用 ``get_time_ms`` 函数即可。


抢占式调度
-----------------------------------

有了时钟中断和计时器，抢占式调度就很容易实现了：

.. code-block:: rust

    // os/src/trap/mod.rs

    match scause.cause() {
        Trap::Interrupt(Interrupt::SupervisorTimer) => {
            set_next_trigger();
            suspend_current_and_run_next();
        }
    }

我们只需在 ``trap_handler`` 函数下新增一个分支，当发现触发了一个 S 特权级时钟中断的时候，首先重新设置一个 10ms 的计时器，然后调用上一小节提到的 ``suspend_current_and_run_next`` 函数暂停当前应用并切换到下一个。

为了避免 S 特权级时钟中断被屏蔽，我们需要在执行第一个应用之前进行一些初始化设置：

.. code-block:: rust
    :linenos:
    :emphasize-lines: 9,10

    // os/src/main.rs

    #[no_mangle]
    pub fn rust_main() -> ! {
        clear_bss();
        println!("[kernel] Hello, world!");
        trap::init();
        loader::load_apps();
        trap::enable_timer_interrupt();
        timer::set_next_trigger();
        task::run_first_task();
        panic!("Unreachable in rust_main!");
    }

    // os/src/trap/mod.rs

    use riscv::register::sie;

    pub fn enable_timer_interrupt() {
        unsafe { sie::set_stimer(); }
    }

- 第 9 行设置了 ``sie.stie`` 使得 S 特权级时钟中断不会被屏蔽；
- 第 10 行则是设置第一个 10ms 的计时器。

这样，当一个应用运行了 10ms 之后，一个 S 特权级时钟中断就会被触发。由于应用运行在 U 特权级，且 ``sie`` 寄存器被正确设置，该中断不会被屏蔽，而是 Trap 到 S 特权级内的我们的 ``trap_handler`` 里面进行处理，并顺利切换到下一个应用。这便是我们所期望的抢占式调度机制。从应用运行的结果也可以看出，三个 ``power`` 系列应用并没有进行 yield ，而是由内核负责公平分配它们执行的时间片。

目前在等待某些事件的时候仍然需要 yield ，其中一个原因是为了节约 CPU 计算资源，另一个原因是当事件依赖于其他的应用的时候，由于只有一个 CPU ，当前应用的等待可能永远不会结束。这种情况下需要先将它切换出去，使得其他的应用到达它所期待的状态并满足事件的生成条件，再切换回来。

.. _term-busy-loop:

这里我们先通过 yield 来优化 **轮询** (Busy Loop) 过程带来的 CPU 资源浪费。在 ``03sleep`` 这个应用中：

.. code-block:: rust

    // user/src/bin/03sleep.rs

    #[no_mangle]
    fn main() -> i32 {
        let current_timer = get_time();
        let wait_for = current_timer + 3000;
        while get_time() < wait_for {
            yield_();
        }
        println!("Test sleep OK!");
        0
    }

它的功能是等待 3000ms 然后退出。可以看出，我们会在循环里面 ``yield_`` 来主动交出 CPU 而不是无意义的忙等。尽管我们不这样做，已有的抢占式调度还是会在它循环 10ms 之后切换到其他应用，但是这样能让内核给其他应用分配更多的 CPU 资源并让它们更早运行结束。

三叠纪“腔骨龙”抢占式操作系统
---------------------------------

简介与画图！！！