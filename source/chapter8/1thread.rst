线程并发
=========================================

.. toctree::
   :hidden:
   :maxdepth: 5


本节导读
-----------------------------------------

在本章的起始介绍中，给出了线程的基本定义，但没有具体的实现，这可能让同学在理解线程上还有些不够深入。其实实现多线程不一定需要操作系统的支持，完全可以在用户态实现。本节的主要目标是理解线程的基本要素、多线程应用的执行方式以及如何在用户态构建一个多线程的的基本执行环境。
在这里，我们首先分析了一个简单的用户态多线程应用的执行过程，然后设计支持这种简单多线程应用的执行环境，包括线程的总体结构、管理线程执行的线程控制块数据结构、以及对线程管理相关的重要函数：线程创建和线程切换。这样设计实现的原因是，
它能帮助我们直接理解线程最核心的设计思想与具体实现，并对后续在有进程支持的操作系统内核中 进一步实现线程机制打下一个基础。



用户态多线程应用
------------------------------------------------

我们先看看一个简单的用户态多线程应用。

.. code-block:: rust
    :linenos:

    // 多线程基本执行环境的代码
    ...
    // 多线程应用的主体代码
	fn main() {
	    let mut runtime = Runtime::new();
	    runtime.init();
	    runtime.spawn(|| {
	        println!("TASK 1 STARTING");
	        let id = 1;
	        for i in 0..10 {
	            println!("task: {} counter: {}", id, i);
	            yield_task();
	        }
	        println!("TASK 1 FINISHED");
	    });
	    runtime.spawn(|| {
	        println!("TASK 2 STARTING");
	        let id = 2;
	        for i in 0..15 {
	            println!("task: {} counter: {}", id, i);
	            yield_task();
	        }
	        println!("TASK 2 FINISHED");
	    });
	    runtime.run();
	}


可以看出，多线程应用的结构很简单，大致含义如下：

- 第 5~6 行 首先是多线程执行环境的创建和初始化，具体细节在后续小节会进一步展开讲解。
- 第 7~15 行 创建了第一个线程；第 16~24 行 创建了第二个线程。这两个线程都是用闭包的形式创建的。
- 第 25 行 开始执行这两个线程。

这里面需要注意的是第12行和第21行的 ``yield_task()`` 函数。这个函数与我们在第二章讲的 :ref:`sys_yield系统调用 <term-sys-yield>` 在功能上是一样的，即当前线程主动交出CPU并切换到其它线程执行。

假定同学在一个linux for RISC-V 64的开发环境中，我们可以执行上述的程序：

.. chyyuu 建立linux for RISC-V 64的开发环境的说明???

注：可参看指导，建立linux for RISC-V 64的开发环境

.. code-block:: console

    $ git clone -b rv64 https://github.com/chyyuu/example-greenthreads.git
    $ cd example-greenthreads
    $ cargo run
    ...
	TASK 1 STARTING
	task: 1 counter: 0
	TASK 2 STARTING
	task: 2 counter: 0
	task: 1 counter: 1
	task: 2 counter: 1
	...
	task: 1 counter: 9
	task: 2 counter: 9
	TASK 1 FINISHED
	...
	task: 2 counter: 14
	TASK 2 FINISHED


可以看到，在一个进程内的两个线程交替执行。这是如何实现的呢？

多线程的基本执行环境
------------------------------------------------

线程的运行需要一个执行环境，这个执行环境可以是操作系统内核，也可以是更简单的用户态的一个线程管理运行时库。如果是基于用户态的线程管理运行时库来实现对线程的支持，那我们需要对线程的管理、调度和执行方式进行一些限定。由于是在用户态进行线程的创建，调度切换等，这就意味着我们不需要操作系统提供进一步的支持，即操作系统不需要感知到这种线程的存在。如果一个线程A想要运行，它只有等到目前正在运行的线程B主动交出处理器的使用权，从而让线程管理运行时库有机会得到处理器的使用权，且线程管理运行时库通过调度，选择了线程A，再完成线程B和线程A的线程上下文切换后，线程A才能占用处理器并运行。这其实就是第三章讲到的 :ref:`任务切换的设计与实现 <term-task-switch-impl>` 和 :ref:`协作式调度 <term-coop-impl>` 的另外一种更简单的具体实现。

线程的结构与执行状态
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

为了实现用户态的协作式线程管理，我们首先需要考虑这样的线程大致的结构应该是什么？在上一节的 :ref:`线程的基本定义 <term-thread-define>` 中，已经给出了具体的答案：

- 线程ID
- 执行状态
- 当前指令指针(PC)
- 寄存器集合
- 栈

基于这个定义，我们就可以实现线程的结构了。我把上述内容集中在一起管理，形成线程控制块：


.. code-block:: rust
    :linenos:

    //线程控制块
	struct Task {
	    id: usize,            // 线程ID
	    stack: Vec<u8>,       // 栈
	    ctx: TaskContext,     // 当前指令指针(PC)和寄存器集合
	    state: State,         // 执行状态
	}

	struct TaskContext {
	    // 15 u64
	    x1: u64,  //ra: return addres，即当前正在执行线程的当前指令指针(PC)
	    x2: u64,  //sp
	    x8: u64,  //s0,fp
	    x9: u64,  //s1
	    x18: u64, //x18-27: s2-11
	    x19: u64,
	    ...
	    x27: u64,
	    nx1: u64, //new return addres, 即下一个要执行线程的当前指令指针(PC)
	}


线程在执行过程中的状态与之前描述的进程执行状态类似：

.. code-block:: rust
    :linenos:

	enum State {
	    Available, // 初始态：线程空闲，可被分配一个任务去执行
	    Running,   // 运行态：线程正在执行
	    Ready,     // 就绪态：线程已准备好，可恢复执行
	}


线程管理运行时初始化
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^



.. code-block:: rust
    :linenos:

	impl Task {
	    fn new(id: usize) -> Self {
	        Task {
	            id,
	            stack: vec![0_u8; DEFAULT_STACK_SIZE],
	            ctx: TaskContext::default(),
	            state: State::Available,
	        }
	    }
	}
	impl Runtime {
	    pub fn new() -> Self {
	        // This will be our base task, which will be initialized in the `running` state
	        let base_task = Task {
	            id: 0,
	            stack: vec![0_u8; DEFAULT_STACK_SIZE],
	            ctx: TaskContext::default(),
	            state: State::Running,
	        };

	        // We initialize the rest of our tasks.
	        let mut tasks = vec![base_task];
	        let mut available_tasks: Vec<Task> = (1..MAX_TASKS).map(|i| Task::new(i)).collect();
	        tasks.append(&mut available_tasks);

	        Runtime {
	            tasks,
	            current: 0,
	        }
	    }

	    pub fn init(&self) {
	        unsafe {
	            let r_ptr: *const Runtime = self;
	            RUNTIME = r_ptr as usize;
	        }
	    }
	}    
	...
	fn main() {
	    let mut runtime = Runtime::new();
	    runtime.init();
	    ...
	}    

线程创建
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^


.. code-block:: rust
    :linenos:

	impl Runtime {
	    pub fn spawn(&mut self, f: fn()) {
	        let available = self
	            .tasks
	            .iter_mut()
	            .find(|t| t.state == State::Available)
	            .expect("no available task.");

	        let size = available.stack.len();
	        unsafe {
	            let s_ptr = available.stack.as_mut_ptr().offset(size as isize);
	            let s_ptr = (s_ptr as usize & !7) as *mut u8;

	            available.ctx.x1 = guard as u64;  //ctx.x1  is old return address
	            available.ctx.nx1 = f as u64;     //ctx.nx2 is new return address
	            available.ctx.x2 = s_ptr.offset(32) as u64; //cxt.x2 is sp

	        }
	        available.state = State::Ready;
	    }
	}
	...
	fn guard() {
	    unsafe {
	        let rt_ptr = RUNTIME as *mut Runtime;
	        (*rt_ptr).t_return();
	    };
	}
	...
	fn main() {
        ...
	    runtime.spawn(|| {
	        println!("TASK 1 STARTING");
	        let id = 1;
	        for i in 0..10 {
	            println!("task: {} counter: {}", id, i);
	            yield_task();
	        }
	        println!("TASK 1 FINISHED");
	    });
	    ...
	}   



线程切换
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^


.. code-block:: rust
    :linenos:

	impl Runtime {
	    fn t_yield(&mut self) -> bool {
	        let mut pos = self.current;
	        while self.tasks[pos].state != State::Ready {
	            pos += 1;
	            if pos == self.tasks.len() {
	                pos = 0;
	            }
	            if pos == self.current {
	                return false;
	            }
	        }

	        if self.tasks[self.current].state != State::Available {
	            self.tasks[self.current].state = State::Ready;
	        }

	        self.tasks[pos].state = State::Running;
	        let old_pos = self.current;
	        self.current = pos;

	        unsafe {
	            switch(&mut self.tasks[old_pos].ctx, &self.tasks[pos].ctx);
	        }
	        self.tasks.len() > 0
	    }
	}

	pub fn yield_task() {
	    unsafe {
	        let rt_ptr = RUNTIME as *mut Runtime;
	        (*rt_ptr).t_yield();
	    };
	}


.. code-block:: rust
    :linenos:

	#[naked]
	#[inline(never)]
	unsafe fn switch(old: *mut TaskContext, new: *const TaskContext) {
	    // a0: old, a1: new
	    llvm_asm!("
	        //if comment below lines: sd x1..., ld x1..., TASK2 can not finish, and will segment fault
	        sd x1, 0x00(a0)
	        sd x2, 0x08(a0)
	        sd x8, 0x10(a0)
	        sd x9, 0x18(a0)
	        sd x18, 0x20(a0)
	        sd x19, 0x28(a0)
	        sd x20, 0x30(a0)
	        sd x21, 0x38(a0)
	        sd x22, 0x40(a0)
	        sd x23, 0x48(a0)
	        sd x24, 0x50(a0)
	        sd x25, 0x58(a0)
	        sd x26, 0x60(a0)
	        sd x27, 0x68(a0)
	        sd x1, 0x70(a0)

	        ld x1, 0x00(a1)
	        ld x2, 0x08(a1)
	        ld x8, 0x10(a1)
	        ld x9, 0x18(a1)
	        ld x18, 0x20(a1)
	        ld x19, 0x28(a1)
	        ld x20, 0x30(a1)
	        ld x21, 0x38(a1)
	        ld x22, 0x40(a1)
	        ld x23, 0x48(a1)
	        ld x24, 0x50(a1)
	        ld x25, 0x58(a1)
	        ld x26, 0x60(a1)
	        ld x27, 0x68(a1)
	        ld t0, 0x70(a1)

	        jr t0
	    "
	    :    :    :    : "volatile", "alignstack"
	    );
	}




开始执行
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^	


.. code-block:: rust
    :linenos:

	impl Runtime {
	   pub fn run(&mut self) -> ! {
	        while self.t_yield() {}
	        std::process::exit(0);
	    }
	}
	...
	fn main() {
        ...
		runtime.run();
	}   
