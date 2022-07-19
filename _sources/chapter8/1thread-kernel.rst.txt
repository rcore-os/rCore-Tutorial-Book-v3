内核态的线程管理
=========================================

.. toctree::
   :hidden:
   :maxdepth: 5


本节导读
-----------------------------------------

在上一节介绍了如何在用户态实现对多线程的管理，让同学对多线程的实际运行机制：创建线程、切换线程等有了一个比较全面的认识。由于在用户态进行线程管理，带了的一个潜在不足是没法让线程管理运行时直接切换线程，只能等当前运行的线程主动让出处理器使用权后，线程管理运行时才能切换检查。在上一章的操作系统运行在内核态，如果扩展一下对线程的管理，那就可以基于时钟中断来直接打断当前用户态线程的运行，实现对线程的调度和切换等。

本节参考上一节的用户态线程管理机制，结合之前的操作系统实现：具有UNIX操作系统基本功能的 “迅猛龙” 操作系统，进化为更加迅捷的 “达科塔盗龙” [#dak]_ 操作系统，我们首先分析如何扩展现有的进程，以支持线程管理。然后设计线程的总体结构、管理线程执行的线程控制块数据结构、以及对线程管理相关的重要函数：线程创建和线程切换。并最终合并到现有的进程管理机制中。本节的内容能帮助我们理解进程和线程的关系，二者在设计思想与具体实现上的差异，为后续支持各种并发机制打下基础。


.. note::

   为何要在这里才引入线程

   学生对进程有一定了解后，再来理解线程也会更加容易。因为从对程序执行的控制流进行调度和切换上看，本章讲解的线程调度与切换操作是之前讲解的进程调度与切换的一个子集。另外，在这里引入线程的一个重要原因是为了便于引入并发。没在进程阶段引入并发这个专题的原因是，进程主要的目的是隔离，而线程的引入强调了共享，即属于同一进程的多个线程可共享进程的资源，这样就必须要解决同步问题了。


线程概念
---------------------------------------------

这里会结合与进程的比较来说明线程的概念。到本章之前，我们看到了进程这一抽象，操作系统让进程拥有相互隔离的虚拟的地址空间，让进程感到在独占一个虚拟的处理器。其实这只是操作系统通过时分复用和空分复用技术来让每个进程复用有限的物理内存和物理CPU。而线程是在进程内中的一个新的抽象。在没有线程之前，一个进程在一个时刻只有一个执行点（即程序计数器 （PC）寄存器保存的要执行指令的指针）。但线程的引入把进程内的这个单一执行点给扩展为多个执行点，即在进程中存在多个线程，每个线程都有一个执行点。而且这些线程共享进程的地址空间，所以可以不必采用相对比较复杂的IPC机制（一般需要内核的介入），而可以很方便地直接访问进程内的数据。

在线程的具体运行过程中，需要有程序计数器寄存器来记录当前的执行位置，需要有一组通用寄存器记录当前的指令的操作数据，需要有一个栈来保存线程执行过程的函数调用栈和局部变量等，这就形成了线程上下文的主体部分。这样如果两个线程运行在一个处理器上，就需要采用类似两个进程运行在一个处理器上的调度/切换管理机制，即需要在一定时刻进行线程切换，并进行线程上下文的保存与恢复。这样在一个进程中的多线程可以独立运行，取代了进程，成为操作系统调度的基本单位。

由于把进程的结构进行了细化，通过线程来表示对处理器的虚拟化，使得进程成为了管理线程的容器。在进程中的线程没有父子关系，大家都是兄弟，但还是有个老大。这个代表老大的线程其实就是创建进程（比如通过 ``fork`` 系统调用创建进程）时，建立的第一个线程，它的线程标识符（TID）为 ``0`` 。


.. chyyuu 需要有一个thread的结构图


通用操作系统多线程应用程序示例
-----------------------------------------------------

在Rust应用开发中，有比较完善的线程API来支持多线程应用的开发，当然这需要底层的操作系统（如Linux）的支持。Rust 语言标准库中的 std::thread 模块提供很很多方法用于创建线程、管理线程和结束线程，以支持多线程编程。一些基本的线程方法如下：

- spawn()：创建一个新线程。
- join()：把子线程加入主线程等待队列，等待子线程结束。

下面是一个Rust线程的例子：

.. code-block:: rust
   :linenos:

   // thread.rs

   use std::thread;

   fn mythread(args: i64) -> i64 {
       println!("{}", args);
       return args + 1;
   }

   fn main() {
       let handle = thread::spawn(|| mythread(100));
       let rvalue = handle.join().unwrap();
       println!("{}", rvalue);
   }

如果编译执行上述程序，可以看到在主线程创建了子线程后，讲调用 `join()` 函数等待子线程结束；而子线程 `mythread` 打印 `arg` 参数并返回 `arg+` ；主线程等待并获得子线程的返回值后，打印出返回值，然后结束应用进程。

.. code-block:: console

   $rustc thread.rs
   $./thread
     100
     101


为了在 “达科塔盗龙” [#dak]_ 操作系统中实现类似Linux操作系统的多线程支持，我们需要建立精简的线程模型和相关系统调用，并围绕这两点来改进操作系统。

线程模型与重要系统调用
----------------------------------------------

目前，我们只介绍本章实现的内核中采用的一种非常简单的线程模型。这个线程模型有三个运行状态：就绪态、运行态和等待态；共享所属进程的地址空间和其他共享资源（如文件等）；可被操作系统调度来分时占用CPU执行；可以动态创建和退出；可通过系统调用获得操作系统的服务。我们实现的线程模型建立在进程的地址空间抽象之上：每个线程都共享进程的代码段和和可共享的地址空间（如全局数据段、堆等），但有自己的独占的栈。线程模型需要操作系统支持一些重要的系统调用：创建线程、等待子线程结束等，来支持灵活的多线程应用。接下来会介绍这些系统调用的基本功能和设计思路。


线程创建系统调用
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

在一个进程的运行过程中，进程可以创建多个属于这个进程的线程，每个线程有自己的线程标识符（TID，Thread Identifier）。系统调用 ``thread_create`` 的原型如下：

.. code-block:: rust
   :linenos:

   /// 功能：当前进程创建一个新的线程
   /// 参数：entry 表示线程的入口函数地址
   /// 参数：arg：表示线程的一个参数
   pub fn sys_thread_create(entry: usize, arg: usize) -> isize 

当进程调用 ``thread_create`` 系统调用后，内核会在这个进程内部创建一个新的线程，这个线程能够访问到进程所拥有的代码段，堆和其他数据段。但内核会给这个新线程分配一个它专有的用户态栈，这样每个线程才能相对独立地被调度和执行。另外，由于用户态进程与内核之间有各自独立的页表，所以二者需要有一个跳板页 ``TRAMPOLINE`` 来处理用户态切换到内核态的地址空间平滑转换的事务。所以当出现线程后，在进程中的每个线程也需要有一个独立的跳板页 ``TRAMPOLINE`` 来完成同样的事务。


相比于创建进程的 ``fork`` 系统调用，创建线程不需要要建立新的地址空间，这是二者之间最大的不同。另外属于同一进程中的线程之间没有父子关系，这一点也与进程不一样。

等待子线程系统调用
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

当一个线程执行完代表它的功能后，会通过 ``exit`` 系统调用退出。内核在收到线程发出的 ``exit`` 系统调用后，会回收线程占用的部分资源，即用户态用到的资源，比如用户态的栈，用于系统调用和异常处理的跳板页等。而该线程的内核态用到的资源，比如内核栈等，需要通过进程/主线程调用 ``waittid`` 来回收了，这样整个线程才能被彻底销毁。系统调用 ``waittid`` 的原型如下：



.. code-block:: rust
   :linenos:

   /// 参数：tid表示线程id
   /// 返回值：如果线程不存在，返回-1；如果线程还没退出，返回-2；其他情况下，返回结束线程的退出码
   pub fn sys_waittid(tid: usize) -> i32   


一般情况下进程/主线程要负责通过 ``waittid`` 来等待它创建出来的线程（不是主线程）结束并回收它们在内核中的资源（如线程的内核栈、线程控制块等）。如果进程/主线程先调用了 ``exit`` 系统调用来退出，那么整个进程（包括所属的所有线程）都会退出，而对应父进程会通过 ``waitpid`` 回收子进程剩余还没被回收的资源。


进程相关的系统调用
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

在引入了线程机制后，进程相关的重要系统调用：``fork`` 、 ``exec`` 、 ``waitpid`` 虽然在接口上没有变化，但在它要完成的功能上需要有一定的扩展。首先，需要注意到把以前进程中与处理器执行相关的部分拆分到线程中。这样，在通过 ``fork`` 创建进程其实也意味着要单独建立一个主线程来使用处理器，并为以后创建新的线程建立相应的线程控制块向量。相对而言， ``exec`` 和 ``waitpid`` 这两个系统调用要做的改动比较小，还是按照与之前进程的处理方式来进行。总体上看，进程相关的这三个系统调用还是保持了已有的进程操作的语义，并没有由于引入了线程，而带来大的变化。


应用程序示例
----------------------------------------------

我们刚刚介绍了 thread_create/waittid 两个重要系统调用，我们可以借助它们和之前实现的系统调用开发出功能更为灵活的应用程序。下面我们通过描述一个多线程应用程序 ``threads`` 的开发过程，来展示这些系统调用的使用方法。


系统调用封装
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

同学可以在 user/src/syscall.rs 中看到以 sys_* 开头的系统调用的函数原型，它们后续还会在 user/src/lib.rs 中被封装成方便应用程序使用的形式。如 sys_thread_create 被封装成 thread_create ，而 sys_waittid 被封装成 waittid  ：   



.. code-block:: rust
   :linenos:

   pub fn thread_create(entry: usize, arg: usize) -> isize { sys_thread_create(entry, arg) }

   pub fn waittid(tid: usize) -> isize {
       loop {
           match sys_waittid(tid) {
               -2 => { yield_(); }
               exit_code => return exit_code,
           }
       }
   }


waittid 等待一个线程标识符的值为tid 的线程结束。在具体实现方面，我们看到当 sys_waittid 返回值为 -2 ，即要等待的线程存在但它却尚未退出的时候，主线程调用 ``yield_`` 主动交出 CPU 使用权，待下次 CPU 使用权被内核交还给它的时候再次调用 sys_waittid 查看要等待的线程是否退出。这样做是为了减小 CPU 资源的浪费。这种方法是为了尽可能简化内核的实现。


多线程应用程序 -- threads
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

多线程应用程序 -- threads 开始执行后，先调用 ``thread_create`` 创建了三个线程，加上进程自带的主线程，其实一共有四个线程。每个线程在打印了1000个字符后，会执行 ``exit`` 退出。进程通过 ``waittid`` 等待这三个线程结束后，最终结束进程的执行。下面是多线程应用程序 -- threads 的源代码：

.. code-block:: rust
   :linenos:

   //usr/src/bin/threads.rs

   #![no_std]
   #![no_main]

   #[macro_use]
   extern crate user_lib;
   extern crate alloc;

   use user_lib::{thread_create, waittid, exit};
   use alloc::vec::Vec;

   pub fn thread_a() -> ! {
       for _ in 0..1000 { print!("a"); }
       exit(1)
   }

   pub fn thread_b() -> ! {
       for _ in 0..1000 { print!("b"); }
       exit(2) 
   }

   pub fn thread_c() -> ! {
       for _ in 0..1000 { print!("c"); }
       exit(3)
   }

   #[no_mangle]
   pub fn main() -> i32 {
       let mut v = Vec::new();
       v.push(thread_create(thread_a as usize, 0));
       v.push(thread_create(thread_b as usize, 0));
       v.push(thread_create(thread_c as usize, 0));
       for tid in v.iter() {
           let exit_code = waittid(*tid as usize);
           println!("thread#{} exited with code {}", tid, exit_code);
       }
       println!("main thread exited.");
       0
   }

线程管理的核心数据结构
-----------------------------------------------

为了在现有进程管理的基础上实现线程管理，我们需要改进一些数据结构包含的内容及接口。基本思路就是把进程中与处理器相关的部分分拆出来，形成线程相关的部分。
本节将按照如下顺序来进行介绍：

- 任务控制块 TaskControlBlock ：表示线程的核心数据结构。
- 任务管理器 TaskManager ：管理线程集合的核心数据结构。
- 处理器管理结构 Processor ：用于线程调度，维护线程的处理器状态。


线程控制块
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

在内核中，每个线程的执行状态和线程上下文等均保存在一个被称为任务控制块 (TCB, Task Control Block) 的结构中，它是内核对线程进行管理的核心数据结构。在内核看来，它就等价于一个线程。


.. code-block:: rust
   :linenos:

   pub struct TaskControlBlock {
    // immutable
    pub process: Weak<ProcessControlBlock>,
    pub kstack: KernelStack,
    // mutable
    inner: UPSafeCell<TaskControlBlockInner>,
   }

   pub struct TaskControlBlockInner {
    pub res: Option<TaskUserRes>,
    pub trap_cx_ppn: PhysPageNum,
    pub task_cx: TaskContext,
    pub task_status: TaskStatus,
    pub exit_code: Option<i32>,
   }


线程控制块就是任务控制块（TaskControlBlock），主要包括在线程初始化之后就不再变化的元数据：线程所属的进程和线程的内核栈，以及在运行过程中可能发生变化的元数据： UPSafeCell<TaskControlBlockInner> 。大部分的细节放在 ``TaskControlBlockInner`` 中：

之前进程中的定义不存在的：

- ``res : TaskUserRes`` 指出了用户态的线程代码执行需要的信息，这些在线程初始化之后就不再变化：

.. code-block:: rust
   :linenos:

   pub struct TaskUserRes {
       pub tid: usize,
       pub ustack_base: usize,
       pub process: Weak<ProcessControlBlock>,
   }


- tid：线程标识符
- ustack_base：线程的栈顶地址
- process：线程所属的进程

与之前进程中的定义相同/类似的部分：

- ``trap_cx_ppn`` 指出了应用地址空间中线程的 Trap 上下文被放在的物理页帧的物理页号。
- ``task_cx`` 保存暂停线程的线程上下文，用于线程切换。
- ``task_status`` 维护当前线程的执行状态。
- ``exit_code`` 线程退出码。


包含线程的进程控制块
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

把线程相关数据单独组织成数据结构后，进程的结构也需要进行一定的调整：

.. code-block:: rust
   :linenos:

   pub struct ProcessControlBlock {
       // immutable
       pub pid: PidHandle,
       // mutable
       inner: UPSafeCell<ProcessControlBlockInner>,
   }

   pub struct ProcessControlBlockInner {
       ...
       pub tasks: Vec<Option<Arc<TaskControlBlock>>>,
       pub task_res_allocator: RecycleAllocator,
   }

从中可以看出，进程把与处理器执行相关的部分都移到了 ``TaskControlBlock`` 中，并组织为一个线程控制块向量中，这就自然对应到多个线程的管理上了。而 ``RecycleAllocator`` 是对之前的 ``PidAllocator`` 的一个升级版，即一个相对通用的资源分配器，可用于分配进程标识符（PID）和线程的内核栈（KernelStack）。

.. chyyuu 加一个PidAllocator的链接???

线程与处理器管理结构
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

线程管理的结构是线程管理器，即任务管理器，位于 ``os/src/task/manager.rs`` 中，其数据结构和方法与之前章节中进程的任务管理器完全一样，仅负责管理所有线程。而处理器管理结构 ``Processor`` 负责维护 CPU 状态、调度和特权级切换等事务。其数据结构与之前章节中进程的处理器管理结构完全一样。但在相关方法上面，由于多个线程有各自的用户栈和跳板页，所以有些不同，下面会进一步分析。

.. chyyuu 加一个taskmanager,processor的链接???

线程管理机制的设计与实现
-----------------------------------------------

在上述线程模型和内核数据结构的基础上，我们还需完成线程管理的基本实现，从而构造出一个完整的“达科塔盗龙”操作系统。本节将分析如何实现线程管理：

- 线程创建、线程退出与等待线程结束
- 线程执行中的特权级切换
- 进程管理中与线程相关的处理


线程创建、线程退出与等待线程结束
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~


线程创建
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

当一个进程执行中发出了创建线程的系统调用 ``sys_thread_create`` 后，操作系统就需要在当前进程的基础上创建一个线程了，这里重点是需要了解创建线程控制块，在线程控制块中初始化各个成员变量，建立好进程和线程的关系等。只有建立好这些成员变量，才能给线程建立一个灵活方便的执行环境。这里列出支持线程正确运行所需的重要的执行环境要素：

- 线程的用户态栈：确保在用户态的线程能正常执行函数调用；
- 线程的内核态栈：确保线程陷入内核后能正常执行函数调用；
- 线程的跳板页：确保线程能正确的进行用户态<-->内核态切换；
- 线程上下文：即线程用到的寄存器信息，用于线程切换。


线程创建的具体实现如下：

.. code-block:: rust
   :linenos:

   // os/src/syscall/thread.rs

   pub fn sys_thread_create(entry: usize, arg: usize) -> isize {
       let task = current_task().unwrap();
       let process = task.process.upgrade().unwrap();
       // create a new thread
       let new_task = Arc::new(TaskControlBlock::new(
           Arc::clone(&process),
           task.inner_exclusive_access().res.as_ref().unwrap().ustack_base,
           true,
       ));
       // add new task to scheduler
       add_task(Arc::clone(&new_task));
       let new_task_inner = new_task.inner_exclusive_access();
       let new_task_res = new_task_inner.res.as_ref().unwrap();
       let new_task_tid = new_task_res.tid;
       let mut process_inner = process.inner_exclusive_access();
       // add new thread to current process
       let tasks = &mut process_inner.tasks;
       while tasks.len() < new_task_tid + 1 {
           tasks.push(None);
       }
       tasks[new_task_tid] = Some(Arc::clone(&new_task));
       let new_task_trap_cx = new_task_inner.get_trap_cx();
       *new_task_trap_cx = TrapContext::app_init_context(
           entry,
           new_task_res.ustack_top(),
           kernel_token(),
           new_task.kstack.get_top(),
           trap_handler as usize,
       );
       (*new_task_trap_cx).x[10] = arg;
       new_task_tid as isize
   }


上述代码主要完成了如下事务：

- 第4-5行，找到当前正在执行的线程 ``task`` 和此线程所属的进程 ``process`` 。
- 第7-11行，调用 ``TaskControlBlock::new`` 方法，创建一个新的线程 ``new_task`` ，在创建过程中，建立与进程 ``process`` 的所属关系，分配了线程用户态栈、内核态栈、用于异常/中断的跳板页。
- 第13行，把线程挂到调度队列中。
- 第19-22行，把线程接入到所需进程的线程列表 ``tasks`` 中。
- 第25~32行，初始化位于该线程在用户态地址空间中的 Trap 上下文：设置线程的函数入口点和用户栈，使得第一次进入用户态时能从线程起始位置开始正确执行；设置好内核栈和陷入函数指针 ``trap_handler`` ，保证在 Trap 的时候用户态的线程能正确进入内核态。

线程退出
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

当一个非主线程的其他线程发出 ``sys_exit`` 系统调用时，内核会调用 ``exit_current_and_run_next`` 函数退出当前线程并切换到下一个线程，但不会导致其所属进程的退出。当 ``主线程`` 即进程发出这个系统调用，当内核收到这个系统调用后，会回收整个进程（这包括了其管理的所有线程）资源，并退出。具体实现如下：

.. code-block:: rust
   :linenos:

   // os/src/syscall/process.rs

   pub fn sys_exit(exit_code: i32) -> ! {
       exit_current_and_run_next(exit_code);
       panic!("Unreachable in sys_exit!");
   }

   // os/src/task/mod.rs

   pub fn exit_current_and_run_next(exit_code: i32) {
       let task = take_current_task().unwrap();
       let mut task_inner = task.inner_exclusive_access();
       let process = task.process.upgrade().unwrap();
       let tid = task_inner.res.as_ref().unwrap().tid;
       // record exit code
       task_inner.exit_code = Some(exit_code);
       task_inner.res = None;
       // here we do not remove the thread since we are still using the kstack
       // it will be deallocated when sys_waittid is called
       drop(task_inner);
       drop(task);
       // however, if this is the main thread of current process
       // the process should terminate at once
       if tid == 0 {
           let mut process_inner = process.inner_exclusive_access();
           // mark this process as a zombie process
           process_inner.is_zombie = true;
           // record exit code of main process
           process_inner.exit_code = exit_code;

           {
               // move all child processes under init process
               let mut initproc_inner = INITPROC.inner_exclusive_access();
               for child in process_inner.children.iter() {
                   child.inner_exclusive_access().parent = Some(Arc::downgrade(&INITPROC)); 
                   initproc_inner.children.push(child.clone());
               }
           }

           // deallocate user res (including tid/trap_cx/ustack) of all threads
           // it has to be done before we dealloc the whole memory_set
           // otherwise they will be deallocated twice
           for task in process_inner.tasks.iter().filter(|t| t.is_some()) {
               let task = task.as_ref().unwrap();
               let mut task_inner = task.inner_exclusive_access();
               task_inner.res = None;
           }

           process_inner.children.clear();
           // deallocate other data in user space i.e. program code/data section
           process_inner.memory_set.recycle_data_pages();
       }
       drop(process);
       // we do not have to save task context
       let mut _unused = TaskContext::zero_init();
       schedule(&mut _unused as *mut _);
   }


上述代码主要完成了如下事务：

- 第11-21行，回收线程的各种资源。
- 第24-53行，如果是主线程发出的退去请求，则回收整个进程的部分资源，并退出进程。第 33~37 行所做的事情是将当前进程的所有子进程挂在初始进程 INITPROC 下面，其做法是遍历每个子进程，修改其父进程为初始进程，并加入初始进程的孩子向量中。第 49 行将当前进程的孩子向量清空。
- 第55-56行，进行线程调度切换。

上述实现中很大一部分与第五章讲解的 进程的退出 的功能实现大致相同。

.. chyyuu 加上链接???

等待线程结束
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

主线程通过系统调用 ``sys_waittid`` 来等待其他线程的结束。具体实现如下：

.. code-block:: rust
   :linenos:

   // os/src/syscall/thread.rs

   pub fn sys_waittid(tid: usize) -> i32 {
       let task = current_task().unwrap();
       let process = task.process.upgrade().unwrap();
       let task_inner = task.inner_exclusive_access();
       let mut process_inner = process.inner_exclusive_access();
       // a thread cannot wait for itself
       if task_inner.res.as_ref().unwrap().tid == tid {
           return -1;
       }
       let mut exit_code: Option<i32> = None;
       let waited_task = process_inner.tasks[tid].as_ref();
       if let Some(waited_task) = waited_task {
           if let Some(waited_exit_code) = waited_task.inner_exclusive_access().exit_code {
               exit_code = Some(waited_exit_code);
           }
       } else {
           // waited thread does not exist
           return -1;
       }
       if let Some(exit_code) = exit_code {
           // dealloc the exited thread
           process_inner.tasks[tid] = None;
           exit_code
       } else {
           // waited thread has not exited
           -2
       }
   }


上述代码主要完成了如下事务：

- 第9-10行，如果是线程等自己，返回错误.
- 第12-21行，如果找到 ``tid`` 对应的退出线程，则收集该退出线程的退出码 ``exit_tid`` ，否则返回错误（退出线程不存在）。
- 第22-29行，如果退出码存在，则清空进程中对应此退出线程的线程控制块（至此，线程所占资源算是全部清空了），否则返回错误（线程还没退出）。


线程执行中的特权级切换和调度切换
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

线程执行中的特权级切换与第三章中 **任务切换的设计与实现** 小节中讲解的过程是一致的。而线程执行中的调度切换过程与第五章的 **进程调度机制** 小节中讲解的过程是一致的。
这里就不用再赘述一遍了。


.. [#dak] 达科塔盗龙是一种生存于距今6700万-6500万年前白垩纪晚期的兽脚类驰龙科恐龙，它主打的并不是霸王龙的力量路线，而是利用自己修长的后肢来提高敏捷度和奔跑速度。它全身几乎都长满了羽毛，可能会滑翔或者其他接近飞行行为的行动模式。