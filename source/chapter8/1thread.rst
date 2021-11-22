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



线程的结构
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^



线程控制块
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^


线程创建
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^



线程切换
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^