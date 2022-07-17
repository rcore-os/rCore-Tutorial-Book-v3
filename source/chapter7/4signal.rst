信号
============================================

本节导读
--------------------------------------------
在本节之前的IPC机制主要集中在进程间的数据传输和数据交换方面，这需要两个进程之间相互合作，同步地来实现。比如，一个进程发出 ``read`` 系统调用，另外一个进程需要发出对应的 ``write`` 系统调用，这样两个进程才能协同完成基于 ``pipe`` 机制的数据传输。这种双向协作的方式不太适合单向的事件通知机制。

在进程间还存在“事件通知”的需求：操作系统或某进程希望能单方面通知另外一个正在忙其它事情的进程产生了某个事件，并让这个进程能迅速响应。如果采用之前同步的IPC机制，难以高效地应对这样的需求。比如，用户想中断当前正在运行的一个程序，于是他敲击 `Ctrl-C` 的组合键，正在运行的程序会迅速退出它正在做的任何事情，截止程序的执行。

我们需要有一种类似于硬件中断的软件级异步通知机制，让进程在没有事件的时候，该忙啥就忙啥；如果一有事件产生，它能够暂停当前的工作，及时地响应事件，并在响应完事件后，恢复当前工作继续执行。这里的暂停与恢复的工作，都由操作系统来完成，应用程序只需设置好响应某事件的事件处理例程就够了。这在很大程度上简化了应用程序响应事件的开发工作。这些需求和想法推动了 ``信号（Signal）`` 机制的产生。


信号机制简介
--------------------------------------------

信号（Signals）是类UNIX操作系统中实现进程间通信的一种异步通知机制，用来提醒某进程一个特定事件已经发生，需要及时处理。当一个信号发送给一个进程时，操作系统会中断被发送进程的正常执行流程。如果被发送进程定义了信号的处理函数，那么它将被执行，否则就执行默认的处理行为，比如让该进程退出。

如果将信号与硬件中断进行比较，我们可以把信号描述为软件中断。当硬件发出中断后，中断响应的对象是操作系统，并由操作系统预设的中断处理例程来具体地进行中断的响应和处理；当某进程或操作系统发出信号时，会指定信号响应的对象，即某个进程的 ``pid`` ，并由该进程预设的信号处理例程来进行具体的信号响应。

进程间发送的信号是某种事件，为了简单起见，UNIX采用了整数来对信号进行编号，这些整数编号都定义了对应的信号的宏名，宏名都是以SIG开头，比如SIGABRT, SIGKILL, SIGSTOP, SIGCONT。

信号的发送方可以是进程或操作系统内核，进程通过系统调用 ``kill`` 给其它进程发信号；内核在碰到特定事件，比如用户对当前进程按下 ``Ctrl+C`` 按键时，内核收到包含 ``Ctrl+C`` 按键的外设中断和按键信息，并会向正在运行的当前进程发送 ``SIGINT`` 信号，将其终止。

信号的接收方是一个进程。接收信号的处理方式有三种：

- 忽略：就像信号没有发生过一样。
- 捕获：进程会调用相应的处理函数进行处理。
- 默认：如果不忽略也不捕获，此时进程会使用内核默认的处理方式来处理信号。内核默认的信号处理：在大多情况下就是杀死进程或者直接忽略信号。


.. note::

   Linux有哪些信号？ 

   Linux中有62个信号，每个信号代表着某种事件，一般情况下，当进程收到某个信号时，就表示该信号所代表的事件发生了。  下面列出了一些常见的信号。


   ===========  ========================================================== 
    信号         含义      
   ===========  ==========================================================  
    SIGABRT     由调用abort函数产生，进程非正常退出
    SIGCHLD     进程终止时，会发送给它的父进程
    SIGINT      对当前进程按下 ``CTRL+C`` 键时，会发送给当前进程
    SIGKILL     操作系统中止某个进程
    SIGSEGV     非法内存访问异常
    SIGILL      非法指令异常
    SIGTSTP     对当前进程按下 ``CTRL+Z`` 键时，会发送给当前进程让它暂停
    SIGCONT     恢复暂停的进程继续执行
    SIGUSR1/2     用户自定义signal 1或2
   ===========  ==========================================================  



信号的系统调用原型及使用方法
--------------------------------------------

为了支持应用使用信号机制，我们需要新增4个系统调用：

- sys_sigaction: 设置信号处理例程
- sys_sigprocmask: 设置要阻止的信号
- sys_kill: 将某信号发送给某进程
- sys_sigreturn: 清除堆栈帧，从信号处理例程返回

具体描述如下：

.. code-block:: rust
    
    // usr/src/syscall.rs
    
    // 设置信号处理例程
    // signum：指定信号
    // action：新的信号处理配置
    // old_action：老的的信号处理配置
    sys_sigaction(signum: i32, 
       action: *const SignalAction,
       old_action: *const SignalAction) 
       -> isize

    pub struct SignalAction {
        // 信号处理例程的地址
        pub handler: usize, 
        // 信号掩码
        pub mask: SignalFlags
    }   

    // 设置要阻止的信号
    // mask：信号掩码
    sys_sigprocmask(mask: u32) -> isize 
 
    // 清除堆栈帧，从信号处理例程返回
     sys_sigreturn() -> isize
 
    // 将某信号发送给某进程
    // pid：进程pid
    // signal：信号的整数码
    sys_kill(pid: usize, signal: i32) -> isize

在用户库中会将其包装为 ``sigaction`` 等函数：

.. code-block:: rust

    // usr/src/lib.rs

    pub fn kill(pid: usize, signal: i32) -> isize {
        sys_kill(pid, signal)
    }

    pub fn sigaction(signum: i32, action: *const SignalAction, old_action:
       *const SignalAction) -> isize {
        sys_sigaction(signum, action, old_action)
    }

    pub fn sigprocmask(mask: u32) -> isize {
        sys_sigprocmask(mask)
    }

    pub fn sigreturn() -> isize {
        sys_sigreturn()
    }


我们来从简单的信号例子 ``sig_simple`` 中介绍如何使用信号机制：


.. code-block:: rust
    :linenos:

    #![no_std]
    #![no_main]

    #[macro_use]
    extern crate user_lib;

    // use user_lib::{sigaction, sigprocmask, SignalAction, SignalFlags, fork, exit, wait, kill, getpid, sleep, sigreturn};
    use user_lib::*;

    fn func() {
        println!("user_sig_test succsess");
        sigreturn();
    }

    #[no_mangle]
    pub fn main() -> i32 {
        let mut new = SignalAction::default();
        let old = SignalAction::default();
        new.handler = func as usize;

        println!("signal_simple: sigaction");
        if sigaction(SIGUSR1, &new, &old) < 0 {
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

在此进程中，在第17~19行，首先建立了 ``new`` 和 ``old`` 两个 ``SignalAction`` 结构的变量，并设置 ``new.handler`` 为信号处理函数 ``func`` 的地址。 

然后在第22行，调用 ``sigaction`` 函数，设置 ``SIGUSR1`` 信号对应为 ``new`` 变量，即该进程在收到 ``SIGUSR1`` 信号后，会执行 ``func`` 函数来具体处理响应此信号。 

接着在第26行，通过 ``getpid`` 函数获得自己的pid，并以自己的pid和 ``SIGUSR1`` 为参数，调用 ``kill`` 函数，给自己发 ``SIGUSR1`` 信号。

操作系统在收到 ``sys_kill`` 系统调用后，会保存该进程老的``trap``上下文，然后修改其``trap``上下文，使得从内核返回到该进程的 ``func`` 函数执行，并在 ``func`` 函数的末尾，进程通过调用 ``sigreturn`` 函数，恢复到该进程之前被 ``func`` 函数截断的地方，即 ``sys_kill`` 系统调用后的指令处，继续执行，直到进程结束。


信号设计与实现
---------------------------------------------

核心数据结构
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

signal属于进程的一种资源，所以需要在进程控制块中添加signal核心数据结构：

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


``SignalAction`` 数据结构包含信号所对应的信号处理函数的地址和信号掩码。
``signal_actions`` 是每个信号对应的SignalAction的数组，操作系统根据这个数组中的内容，可以知道该进程应该如何响应信号。

``killed`` 的作用是标志当前进程是否已经被杀死。因为进程收到杀死信号的时候并不会立刻结束，而是会在适当的时候退出。这个时候需要killed作为标记，退出不必要的信号处理循环。

``frozen`` 的标志与SIGSTOP和SIGCONT两个信号有关。SIGSTOP会暂停进程的执行，即将frozen置为true。此时当前进程会阻塞等待SIGCONT（即解冻的信号）。当信号收到SIGCONT的时候，frozen置为false，退出等待信号的循环，返回用户态继续执行。


建立信号处理函数(signal_handler)
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

.. code-block:: rust
    :linenos:

    // os/src/syscall/process.rs

    fn sys_sigaction(signum: i32, action: *const SignalAction, 
                              old_action: *mut SignalAction) -> isize {
      ...

      //1. 保存老的signal_handler地址到old_action中
      let old_kernel_action = inner.signal_actions.table[signum as usize];
      *translated_refmut(token, old_action) = old_kernel_action;
     
      //2. 保存新的signal_handler地址到TCB的signal_actions中
      let ref_action = translated_ref(token, action);
      inner.signal_actions.table[signum as usize] = *ref_action;

``sys_sigaction`` 的主要工作就是保存该进程的``signal_actions``中对应信号的sigaction到old_action中，然后再把新的ref_action保存到该进程的signal_actions对应项中。


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

``sys_kill``的主要工作是对进程号为pid的进程发值为signum的信号。具体而言，先根据 ``pid`` 找到对应的进程控制块，然后把进程控制块中的 ``signals`` 中 ``signum`` 所对应的位设置 ``1`` 。


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

当一个进程给另外一个进程发出信号后，操作系统位需要响应信号的进程所做的事情相对复杂一些。操作系统会在进程在从内核态回到用户态的最后阶段进行响应信号的处理。其总体的处理流程如下所示：


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

这里仅仅给出了一个基本的信号机制的使用和实现的过程描述，在实际操作系统中，信号处理的过程要复杂很多，有兴趣的同学可以查找实际操作系统，如Linux，在信号处理上的具体实现。

参考
--------------------------------------------

- https://venam.nixers.net/blog/unix/2016/10/21/unix-signals.html
- https://www.onitroad.com/jc/linux/man-pages/linux/man2/sigreturn.2.html 