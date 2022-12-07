信号
============================================

本节导读
--------------------------------------------

在本节之前的 IPC 机制主要集中在进程间的数据传输和数据交换方面，这需要两个进程之间相互合作，同步地来实现。比如，一个进程发出 ``read`` 系统调用，另外一个进程需要发出对应的 ``write`` 系统调用，这样两个进程才能协同完成基于 ``pipe`` 机制的数据传输。这种双向协作的方式不太适合单向的事件通知机制。

在进程间还存在“事件通知”的需求：操作系统或某进程希望能单方面通知另外一个正在忙其它事情的进程产生了某个事件，并让这个进程能迅速响应。如果采用之前同步的 IPC 机制，难以高效地应对这样的需求。比如，用户想中断当前正在运行的一个程序，于是他敲击 `Ctrl-C` 的组合键，正在运行的程序会迅速退出它正在做的任何事情，截止程序的执行。

我们需要有一种类似于硬件中断的软件级异步通知机制，使得进程在接收到特定事件的时候能够暂停当前的工作并及时响应事件，并在响应事件之后可以恢复当前工作继续执行。如果进程没有接收到任何事件，它可以执行自己的任务。这里的暂停与恢复的工作，都由操作系统来完成，应用程序只需设置好响应某事件的事件处理例程就够了。这在很大程度上简化了应用程序响应事件的开发工作。这些需求和想法推动了 **信号** (Signal) 机制的产生。


信号机制简介
--------------------------------------------

信号（Signals）是类 UNIX 操作系统中实现进程间通信的一种异步通知机制，用来提醒某进程一个特定事件已经发生，需要及时处理。当一个信号发送给一个进程时，操作系统会中断接收到信号的进程的正常执行流程并对信号进行处理。如果该进程定义了信号的处理函数，那么这个处理函数会被调用，否则就执行默认的处理行为，比如让该进程退出。在处理完信号之后，如果进程还没有退出，则会恢复并继续进程的正常执行。

如果将信号与硬件中断进行比较，我们可以把信号描述为软件中断。当硬件发出中断后，中断响应的对象是操作系统，并由操作系统预设的中断处理例程来具体地进行中断的响应和处理；对于信号来说，当某进程或操作系统发出信号时，会指定信号响应的对象，即某个进程的 ``pid`` ，并由该进程预设的信号处理例程来进行具体的信号响应。

进程间发送的信号是某种事件，为了简单起见，UNIX 采用了整数来对信号进行编号，这些整数编号都定义了对应的信号的宏名，宏名都是以 SIG 开头，比如SIGABRT, SIGKILL, SIGSTOP, SIGCONT。

信号的发送方可以是进程或操作系统内核：进程可以通过系统调用 ``kill`` 给其它进程发信号；内核在碰到特定事件，比如用户对当前进程按下 ``Ctrl+C`` 按键时，内核会收到包含 ``Ctrl+C`` 按键的外设中断和按键信息，随后会向正在运行的当前进程发送 ``SIGINT`` 信号，将其终止。

信号的接收方是一个进程，接收到信号有多种处理方式，最常见的三种如下：

- 忽略：就像信号没有发生过一样。
- 捕获：进程会调用相应的处理函数进行处理。
- 终止：终止进程。

如果应用没有手动设置接收到某种信号之后如何处理，则操作系统内核会以默认方式处理该信号，一般是终止收到信号的进程或者忽略此信号。每种信号都有自己的默认处理方式。

.. note::

   **Linux 有哪些信号？** 

   Linux 中有 62 个信号，每个信号代表着某种事件，一般情况下，当进程收到某个信号时，意味着该信号所代表的事件发生了。下面列出了一些常见的信号。

   ===========  ========================================================== 
    信号         含义      
   ===========  ==========================================================  
    SIGABRT     非正常的进程退出，可能由调用 ``abort`` 函数产生
    SIGCHLD     进程状态变更时（通常是进程退出时），由内核发送给它的父进程
    SIGINT      在终端界面按下 ``CTRL+C`` 组合键时，由内核会发送给当前终端的前台进程
    SIGKILL     终止某个进程，由内核或其他进程发送给被终止进程
    SIGSEGV     非法内存访问异常，由内核发送给触发异常的进程
    SIGILL      非法指令异常，由内核发送给触发异常的进程
    SIGTSTP     在终端界面按下  ``CTRL+Z`` 组合键时，会发送给当前进程让它暂停
    SIGSTOP     也用于暂停进程，与 ``SIGTSTP`` 的区别在于 ``SIGSTOP`` 不能被忽略或捕获，即 ``SIGTSTP`` 更加灵活
    SIGCONT     恢复暂停的进程继续执行
    SIGUSR1/2   用户自定义信号 1/2
   ===========  ==========================================================

   和之前介绍过的硬件中断一样，信号作为软件中断也可以分成同步和异步两种，这里的同步/异步指的是信号的触发同步/异步于接收到信号进程的执行。比如 ``SIGILL`` 和 ``SIGSEGV`` 就属于同步信号，而 ``SIGCHLD`` 和 ``SIGINT`` 就属于异步信号。

信号处理流程
--------------------------------------------

信号的处理流程如下图所示：

.. image:: signal.png
    :align: center
    :width: 500px

信号有两种来源：最开始的时候进程在正常执行，此时可能内核或者其他进程给它发送了一个信号，这些就属于异步信号，是信号的第一种来源；信号的第二种来源则是由进程自身的执行触发，在处理 Trap 的时候的时候内核会将相应的信号直接附加到进程控制块中，这种属于同步信号。

内核会在 Trap 处理完成即将返回用户态之前检查要返回到的进程是否还有信号待处理。如果需要处理的话，取决于进程是否提供该种信号的处理函数，有两种处理方法：

- 如果进程通过下面介绍的 ``sigaction`` 系统调用提供了相应信号的处理函数，那么内核会将该进程 Trap 进来时留下的 Trap 上下文保存在另一个地方，并回到用户态执行进程提供的处理函数。内核要求处理函数的编写者在函数的末尾手动进行另一个 ``sigreturn`` 系统调用，表明处理结束并请求恢复进程原来的执行。内核将处理该系统调用并恢复之前保存的 Trap 上下文，等到再次回到用户态的时候，便会继续进程在处理信号之前的执行。
- 反之，如果进程未提供处理函数，这是一种比较简单的情况。此时，内核会直接默认的方式处理信号。之后便会回到用户态继续进程原先的执行。

信号机制系统调用原型
--------------------------------------------

发送信号
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

为了与其他进程进行通信，一个进程可以使用 ``kill`` 系统调用发送信号给另一个进程：

.. code-block:: rust

    // user/src/lib.rs

    /// 功能：当前进程向另一个进程（可以是自身）发送一个信号。
    /// 参数：pid 表示接受信号的进程的进程 ID, signum 表示要发送的信号的编号。
    /// 返回值：如果传入参数不正确（比如指定进程或信号类型不存在）则返回 -1 ,否则返回 0 。
    /// syscall ID: 129
    pub fn kill(pid: usize, signum: i32) -> isize;

我们的内核中各信号的编号定义如下：

.. code-block:: rust

    // user/src/lib.rs

    pub const SIGDEF: i32 = 0; // Default signal handling
    pub const SIGHUP: i32 = 1;
    pub const SIGINT: i32 = 2;
    pub const SIGQUIT: i32 = 3;
    pub const SIGILL: i32 = 4;
    pub const SIGTRAP: i32 = 5;
    pub const SIGABRT: i32 = 6;
    pub const SIGBUS: i32 = 7;
    pub const SIGFPE: i32 = 8;
    pub const SIGKILL: i32 = 9;
    ...

从中可以看出，每次调用 ``kill`` 只能发送一个类型的信号。 

处理信号
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

与信号处理相关的系统调用则有三个：

- ``sys_sigaction`` :设置信号处理例程
- ``sys_procmask`` :设置进程的信号屏蔽掩码
- ``sys_sigreturn`` :清除栈帧，从信号处理例程返回

下面依次对它们进行说明。

首先，进程可以通过 ``sigaction`` 系统调用捕获某种信号，即：当接收到某种信号的时候，暂停进程当前的执行，调用进程为该种信号提供的函数对信号进行处理，处理完成之后再恢复进程原先的执行。 ``sigaction`` 的接口如下：

.. code-block:: rust

    // user/src/lib.rs

    /// 功能：为当前进程设置某种信号的处理函数，同时保存设置之前的处理函数。
    /// 参数：signum 表示信号的编号，action 表示要设置成的处理函数的指针
    /// old_action 表示用于保存设置之前的处理函数的指针（SignalAction 结构稍后介绍）。
    /// 返回值：如果传入参数错误（比如传入的 action 或 old_action 为空指针或者）
    /// 信号类型不存在返回 -1 ，否则返回 0 。
    /// syscall ID: 134
    pub fn sigaction(
        signum: i32,
        action: Option<&SignalAction>,
        old_action: Option<&mut SignalAction>,
    ) -> isize;

注意这里参数 ``action`` 和 ``old_action`` 在裸指针外面使用一层 ``Option`` 包裹。这意味着传值的时候当传递实际存在的引用的时候使用 ``Some`` 包裹，当传递空指针的时候则直接传 ``None`` 。这样可以提前对引用和空指针做出区分。在实现系统调用的时候，如果发现是 ``None`` ，我们再将其转换成空指针：

.. code-block:: rust

    // user/src/lib.rs

    pub fn sigaction(
        signum: i32,
        action: Option<&SignalAction>,
        old_action: Option<&mut SignalAction>,
    ) -> isize {
        sys_sigaction(signum, action, old_action)
    }

    // user/src/syscall.rs

    pub fn sys_sigaction(
        signum: i32,
        action: Option<&SignalAction>,
        old_action: Option<&mut SignalAction>,
    ) -> isize {
        syscall(
            SYSCALL_SIGACTION,
            [
                signum as usize,
                action.map_or(0, |r| r as *const _ as usize),
                old_action.map_or(0, |r| r as *mut _ as usize),
            ],
        )
    }

接下来介绍 ``SignalAction`` 数据结构：

.. code-block:: rust

    // user/src/lib.rs

    /// Action for a signal
    #[repr(C)]
    #[derive(Debug, Clone, Copy)]
    pub struct SignalAction {
        pub handler: usize,
        pub mask: SignalFlags,
    }

可以看到它有两个字段： ``handler`` 表示信号处理函数的入口地址； ``mask`` 则表示执行该信号处理函数期间的信号掩码。这个信号掩码是用于在执行信号处理函数的期间屏蔽掉一些信号，每个 ``handler`` 都可以设置它在执行期间屏蔽掉哪些信号。“屏蔽”的意思是指在执行该信号处理函数期间，即使 Trap 到内核态发现当前进程又接收到了一些信号，只要这些信号被屏蔽，内核就不会对这些信号进行处理而是直接回到用户态继续执行信号处理函数。但这不意味着这些被屏蔽的信号就此被忽略，它们仍被记录在进程控制块中，当信号处理函数执行结束之后它们便不再被屏蔽，从而后续可能被处理。

``mask`` 作为一个掩码可以代表屏蔽掉一组信号，因此它的类型 ``SignalFlags`` 是一个信号集合：

.. code-block:: rust

    // user/src/lib.rs

    bitflags! {
        pub struct SignalFlags: i32 {
            const SIGDEF = 1; // Default signal handling
            const SIGHUP = 1 << 1;
            const SIGINT = 1 << 2;
            const SIGQUIT = 1 << 3;
            const SIGILL = 1 << 4;
            const SIGTRAP = 1 << 5;
            ...
            const SIGSYS = 1 << 31;
        }
    }

需要注意的是，我们目前的实现比较简单，暂时不支持信号嵌套，也就是在执行一个信号处理函数期间再去执行另一个信号处理函数。

``sigaction`` 可以设置某个信号处理函数的信号掩码，而 ``sigprocmask`` 是设置这个进程的全局信号掩码：

.. code-block:: rust

    // user/src/lib.rs

    /// 功能：设置当前进程的全局信号掩码。
    /// 参数：mask 表示当前进程要设置成的全局信号掩码，代表一个信号集合，
    /// 在集合中的信号始终被该进程屏蔽。
    /// 返回值：如果传入参数错误返回 -1 ，否则返回 0 。
    /// syscall ID: 135
    pub fn sigprocmask(mask: u32) -> isize;

最后一个系统调用是 ``sigreturn`` 。介绍信号处理流程的时候提到过，在进程向内核提供的信号处理函数末尾，函数的编写者需要手动插入一个 ``sigreturn`` 系统调用来通知内核信号处理过程结束，可以恢复进程先前的执行。它的接口如下：

.. code-block:: rust

    // user/src/lib.rs

    /// 功能：进程通知内核信号处理函数退出，可以恢复原先的进程执行。
    /// 返回值：如果出错返回 -1，否则返回 0 。
    /// syscall ID: 139
    pub fn sigreturn() -> isize;

信号系统调用使用示例
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

我们来从简单的信号例子 ``sig_simple`` 中介绍如何使用信号机制：


.. code-block:: rust
    :linenos:

    // user/src/bin/sig_simple.rs

    #![no_std]
    #![no_main]

    extern crate user_lib;

    // use user_lib::{sigaction, sigprocmask, SignalAction, SignalFlags, fork, exit, wait, kill, getpid, sleep, sigreturn};
    use user_lib::*;

    fn func() {
        println!("user_sig_test passed");
        sigreturn();
    }

    #[no_mangle]
    pub fn main() -> i32 {
        let mut new = SignalAction::default();
        let mut old = SignalAction::default();
        new.handler = func as usize;

        println!("signal_simple: sigaction");
        if sigaction(SIGUSR1, Some(&new), Some(&mut old)) < 0 {
            panic!("Sigaction failed!");
        }
        println!("signal_simple: kill");
        if kill(getpid() as usize, SIGUSR1) < 0 {
            println!("Kill failed!");
            exit(1);
        }
        println!("signal_simple: Done");
        0
    }


在此进程中：

- 在第 18~20 行，首先建立了 ``new`` 和 ``old`` 两个 ``SignalAction`` 结构的变量，并设置 ``new.handler`` 为信号处理函数 ``func`` 的地址。 
- 然后在第 23 行，调用 ``sigaction`` 函数，提取 ``new`` 结构中的信息设置当前进程收到 ``SIGUSR1`` 信号之后的处理方式，其效果是该进程在收到 ``SIGUSR1`` 信号后，会执行 ``func`` 函数来具体处理响应此信号。 
- 接着在第 27 行，通过 ``getpid`` 函数获得自己的 pid，并以自己的 pid 和 ``SIGUSR1`` 为参数，调用 ``kill`` 函数，给自己发 ``SIGUSR1`` 信号。

执行这个应用，可以看到下面的输出：

.. code-block::

    >> sig_simple
    signal_simple: sigaction
    signal_simple: kill
    user_sig_test passed
    signal_simple: Done
    
可以看出，看到进程在收到自己给自己发送的 ``SIGUSR1`` 信号之后，内核调用它作为信号处理函数的 ``func`` 函数并打印出了标志性输出。在信号处理函数结束之后，还能够看到含有 ``Done`` 的输出，这意味着进程原先的执行被正确恢复。 

.. 操作系统在收到 ``sys_kill`` 系统调用后，会保存该进程老的 Trap 上下文，然后修改其 Trap 上下文，使得从内核返回到该进程的 ``func`` 函数执行，并在 ``func`` 函数的末尾，进程通过调用 ``sigreturn`` 函数，恢复到该进程之前被 ``func`` 函数截断的地方，即 ``sys_kill`` 系统调用后的指令处，继续执行，直到进程结束。

信号的系统调用原型及使用方法
--------------------------------------------

为了支持应用使用信号机制，我们需要新增4个系统调用：

- ``sys_sigaction`` : 设置信号处理例程
- ``sys_sigprocmask`` : 设置要阻止的信号
- ``sys_kill`` : 将某信号发送给某进程
- ``sys_sigreturn`` : 清除堆栈帧，从信号处理例程返回

具体描述如下：

.. code-block:: rust
    
    // user/src/syscall.rs
    
    // 设置信号处理例程
    // signum：指定信号
    // action：新的信号处理配置
    // old_action：老的的信号处理配置
    fn sys_sigaction(
        signum: i32, 
        action: *const SignalAction,
        old_action: *mut SignalAction) -> isize

    pub struct SignalAction {
        // 信号处理例程的地址
        pub handler: usize, 
        // 信号掩码
        pub mask: SignalFlags
    }   

    // 设置要阻止的信号
    // mask：信号掩码
    fn sys_sigprocmask(mask: u32) -> isize 
 
    // 清除堆栈帧，从信号处理例程返回
    fn sys_sigreturn() -> isize
 
    // 将某信号发送给某进程
    // pid：进程pid
    // signal：信号的整数码
    fn sys_kill(pid: usize, signal: i32) -> isize

在用户库中会将其包装为 ``sigaction`` 等函数：

.. code-block:: rust

    // user/src/lib.rs

    pub fn kill(pid: usize, signal: i32) -> isize {
        sys_kill(pid, signal)
    }

    pub fn sigaction(
        signum: i32,
        action: *const SignalAction,
        old_action: *mut SignalAction) -> isize {
        sys_sigaction(signum, action, old_action)
    }

    pub fn sigprocmask(mask: u32) -> isize {
        sys_sigprocmask(mask)
    }

    pub fn sigreturn() -> isize {
        sys_sigreturn()
    }





信号设计与实现
---------------------------------------------

核心数据结构
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

信号属于进程的一种资源，所以需要在进程控制块中添加 signal 核心数据结构：

.. code-block:: rust
    :linenos:

    // os/src/task/task.rs

    pub struct TaskControlBlockInner {
        ...
        pub signals: SignalFlags,          // 要响应的信号
        pub signal_mask: SignalFlags,      // 要屏蔽的信号
        pub handling_sig: isize,           // 正在处理的信号
        pub signal_actions: SignalActions, // 信号处理例程表
        pub killed: bool,                  // 任务是否已经被杀死了
        pub frozen: bool,                  // 任务是否已经被暂停了
        pub trap_ctx_backup: Option<TrapContext> //被打断的trap上下文
    }

    pub struct SignalAction {
        pub handler: usize,         // 信号处理函数的地址
        pub mask: SignalFlags       // 信号掩码
    }

进程控制块中新增字段的含义如下：

- ``SignalAction`` 数据结构包含信号所对应的信号处理函数的地址和信号掩码。进程控制块中的 ``signal_actions`` 是每个信号对应的 SignalAction 的数组，操作系统根据这个数组中的内容，可以知道该进程应该如何响应信号。
- ``killed`` 的作用是标志当前进程是否已经被杀死。因为进程收到杀死信号的时候并不会立刻结束，而是会在适当的时候退出。这个时候需要 killed 作为标记，退出不必要的信号处理循环。
- ``frozen`` 的标志与 SIGSTOP 和 SIGCONT 两个信号有关。SIGSTOP 会暂停进程的执行，即将frozen 置为 true。此时当前进程会阻塞等待 SIGCONT（即解冻的信号）。当信号收到 SIGCONT 的时候，frozen 置为 false，退出等待信号的循环，返回用户态继续执行。


建立信号处理函数(signal_handler)
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

.. code-block:: rust
    :linenos:

    // os/src/syscall/process.rs

    fn sys_sigaction(
        signum: i32
        action: *const SignalAction, 
        old_action: *mut SignalAction) -> isize {
        
        ...

        //1. 保存老的 signal_handler 地址到 old_action 中
        let old_kernel_action = inner.signal_actions.table[signum as usize];
        *translated_refmut(token, old_action) = old_kernel_action;
     
        //2. 保存新的 signal_handler 地址到 TCB 的 signal_actions 中
        let ref_action = translated_ref(token, action);
        inner.signal_actions.table[signum as usize] = *ref_action;

        ...
    }

``sys_sigaction`` 的主要工作就是保存该进程的 ``signal_actions`` 中对应信号的 ``sigaction`` 到 ``old_action`` 中，然后再把新的 ``ref_action`` 保存到该进程的 ``signal_actions`` 对应项中。


发送信号
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

.. code-block:: rust
    :linenos:

    // os/src/syscall/process.rs
    
    fn sys_kill(pid: usize, signum: i32) -> isize {
        let Some(task) = pid2task(pid);
        // insert the signal if legal
        let mut task_ref = task.inner_exclusive_access();
        task_ref.signals.insert(flag);
        ...
    }

``sys_kill`` 的主要工作是对进程号为 pid 的进程发值为 ``signum`` 的信号。具体而言，先根据 ``pid`` 找到对应的进程控制块，然后把进程控制块中的 ``signals`` 中 ``signum`` 所对应的位设置 ``1`` 。


在信号处理后恢复继续执行
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

.. code-block:: rust
    :linenos:

    pub fn sys_sigretrun() -> isize {
        if let Some(task) = current_task() {
            let mut inner = task.inner_exclusive_access();
            inner.handling_sig = -1;
            // restore the trap context
            let trap_ctx = inner.get_trap_cx();
            *trap_ctx = inner.trap_ctx_backup.unwrap();
            0
        } else {
            -1
        }
    }

``sys_sigreturn`` 的主要工作是在信号处理函数完成信号响应后要执行的一个恢复操作，即把操作系统在响应信号前保存的 ``trap`` 上下文重新恢复回来，这样就可以从信号处理前的进程正常执行的位置继续执行了。 

响应信号
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

当一个进程给另外一个进程发出信号后，操作系统为需要响应信号的进程所做的事情相对复杂一些。操作系统会在进程在从内核态回到用户态的最后阶段进行响应信号的处理。其总体的处理流程如下所示：


.. code-block:: 
    :linenos:

    执行APP --> __alltraps 
             --> trap_handler 
                --> handle_signals 
                    --> check_pending_signals 
                        --> call_kernel_signal_handler
                        --> call_user_signal_handler
                           -->  // backup trap Context
                                // modify trap Context
                                trap_ctx.sepc = handler; //设置回到中断处理例程的入口
                                trap_ctx.x[10] = sig;   //把信号值放到Reg[10]
                --> trap_return //找到并跳转到位于跳板页的`__restore`汇编函数
           -->  __restore //恢复被修改过的trap Context，执行sret
    执行APP的signal_handler函数


这里需要先分析处于从内核态回到用户态的最后阶段的 ``trap_handler`` 函数：

.. code-block:: rust
    :linenos:

    // os/src/trap/mod.rs

    pub fn trap_handler() -> ! {
     ...
     match scause.cause() {
        ... 
        | Trap::Exception(Exception::LoadPageFault) => {
            current_add_signal(SignalFlags::SIGSEGV);
        }
        Trap::Exception(Exception::IllegalInstruction) => {
            current_add_signal(SignalFlags::SIGILL);
        }
        ...
     } // end of match scause.cause() 
     // handle signals (handle the sent signal)
     handle_signals();

    // check error signals (if error then exit)
    if let Some((errno, msg)) = check_signals_error_of_current() {
        println!("[kernel] {}", msg);
        exit_current_and_run_next(errno);
    }
    trap_return();
    } 

在 ``trap_handler`` 函数中，如何内核发现进程由于内存访问错误等产生异常，会添加 ``SIGSEGV`` 或 ``SIGILL`` 信号到该进程控制块的``signals`` 对应的位中；然后会在返回到用户态前，调用 ``handle_signals`` 检查该进程的控制块的``signals`` ，是否有需要处理的信号，如果有，会进行相应的 ``trap`` 上下文保存与设置。


这里需要进一步分析 ``handle_signals`` 函数。 

.. code-block:: rust
    :linenos:

    pub fn handle_signals() {
        check_pending_signals();
        loop {
            ...
            if (!frozen_flag) || killed_flag {
                break;
            }
            check_pending_signals();
            suspend_current_and_run_next()
        }
    }


    fn check_pending_signals() {
        for sig in 0..(MAX_SIG + 1) {
              ...
                    {
                        // signal is a kernel signal
                        call_kernel_signal_handler(signal);
                    } else {
                        // signal is a user signal
                        call_user_signal_handler(sig, signal);
                        return;
                    }
              ...
    }

``handle_signals`` 函数会调用 ``check_pending_signals`` 函数来检查发送给该进程的信号。信号分为必须由内核处理的信号和可由用户进程处理的信号两类。内核处理的信号有

- ``SIGSTOP``  :  暂停该进程
- ``SIGCONT``  :  继续该进程
- ``SIGKILL``  :  杀死该进程
- ``SIGDEF``   :  缺省行为：杀死该进程

主要由 ``call_kernel_signal_handler`` 函数完成，如果是 ``SIGKILL`` 或 ``SIGDEF`` 信号，该函数，会把进程控制块中的 ``killed`` 设置位 ``true``。 

而其它信号都属于可由用户进程处理的信号，由 ``call_user_signal_handler`` 函数进行进一步处理。

.. code-block:: rust
    :linenos:

    fn call_user_signal_handler(sig: usize, signal: SignalFlags) {
        ...
        let handler = task_inner.signal_actions.table[sig].handler;
        if handler != 0 {
            // user handler

            // change current mask
            task_inner.signal_mask = task_inner.signal_actions.table[sig].mask;
            // handle flag
            task_inner.handling_sig = sig as isize;
            task_inner.signals ^= signal;

            // backup trapframe
            let mut trap_ctx = task_inner.get_trap_cx();
            task_inner.trap_ctx_backup = Some(*trap_ctx);

            // modify trapframe
            trap_ctx.sepc = handler;

            // put args (a0)
            trap_ctx.x[10] = sig;
        } else {
            // default action
            println!("[K] task/call_user_signal_handler: default action: ignore it or kill process");
        }
    }

从 ``call_user_signal_handler`` 的实现可以看到，第14~15行，把进程之前的``trap``上下文保存在进程控制块的 ``trap_ctx_backup`` 中；然后在第18行，修改``trap``上下文的 ``sepc`` 的值为对应信号 ``sig`` 的用户态的信号处理函数地址，并设置该函数的第一个参数为 ``sig`` 。这样在从内核回到用户态时，将不执行之前进入内核时的用户进程代码，而是执行该进程的信号处理函数。该信号处理函数最后通过执行 ``sys_sigreturn`` 来恢复保存在``trap_ctx_backup`` 中的``trap``上下文，从而能够回到之前进程在用户态的正常执行位置继续执行。

小结
--------------------------------------------

这里仅仅给出了一个基本的信号机制的使用和实现的过程描述，在实际操作系统中，信号处理的过程要复杂很多，有兴趣的同学可以查找实际操作系统，如 Linux，在信号处理上的具体实现。

参考
--------------------------------------------

- https://venam.nixers.net/blog/unix/2016/10/21/unix-signals.html
- https://www.onitroad.com/jc/linux/man-pages/linux/man2/sigreturn.2.html
- http://web.stanford.edu/class/cs110/