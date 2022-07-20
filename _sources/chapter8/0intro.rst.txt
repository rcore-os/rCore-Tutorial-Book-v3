引言
=========================================

本章导读
-----------------------------------------

到本章开始之前，我们已经完成了组成应用程序执行环境的操作系统的三个重要抽象：进程、地址空间和文件，让应用程序开发、运行和存储数据更加方便和灵活。特别是操作系统通过硬件中断机制，支持分时多任务和抢占式调度机制。这样操作系统能强制打断进程的执行，及时处理I/O交互操作，从而提高整个系统的执行效率。有了进程以后，可以让操作系统从宏观层面实现多个应用的 :ref:`并发执行 <term-parallel-concurrency>` ，而并发是通过操作系统不断地切换进程来达到的。

对于单核处理器而言，在任意一个时刻只会有一个进程被操作系统调度，在被处理器上执行。到目前为止的并发，仅仅是进程间的并发，而对于一个进程内部，还没有并发性的体现。而这就是线程（Thread）出现的起因：提高一个进程内的并发性。


.. chyyuu 
   https://en.wikipedia.org/wiki/Per_Brinch_Hansen 关于操作系统并发  Binch Hansen 和 Hoare ??？
	https://en.wikipedia.org/wiki/Thread_(computing) 关于线程
	http://www.serpentine.com/blog/threads-faq/the-history-of-threads/ The history of threads
	https://en.wikipedia.org/wiki/Core_War 我喜欢的一种早期游戏
	[Dijkstra, 65] Dijkstra, E. W., Cooperating sequential processes, in Programming Languages, Genuys, F. (ed.), Academic Press, 1965.
	[Saltzer, 66] Saltzer, J. H., Traffic control in a multiplexed computer system, MAC-TR-30 (Sc.D. Thesis), July, 1966.
	https://en.wikipedia.org/wiki/THE_multiprogramming_system
	http://www.cs.utexas.edu/users/EWD/ewd01xx/EWD196.PDF
	https://en.wikipedia.org/wiki/Edsger_W._Dijkstra
	https://en.wikipedia.org/wiki/Per_Brinch_Hansen
	https://en.wikipedia.org/wiki/Tony_Hoare
	https://en.wikipedia.org/wiki/Mutual_exclusion
	https://en.wikipedia.org/wiki/Semaphore_(programming)
	https://en.wikipedia.org/wiki/Monitor_(synchronization)
	Dijkstra, Edsger W. The structure of the 'THE'-multiprogramming system (EWD-196) (PDF). E.W. Dijkstra Archive. Center for American History, University of Texas at Austin. (transcription) (Jun 14, 1965)

.. note::

	**解决并发问题的THE操作系统**

	早期的计算机硬件没有内存隔离保护机制，多个程序以任务（task）的形式进行执行，但各个任务之间是依次执行（批处理方式）或相互独立执行，基本没有数据共享的情况，所以还没有形成线程的概念。当多个任务需要共享数据和同步行为时，就需要扩展任务针对共享数据的执行特征，并建立相应的同步互斥机制。在1962年，荷兰的E.W.Dijkstra 教授和他的团队正在为 Electrologica X8 计算机开发 THE 操作系统。他们观察到如果多个程序在执行中访问共享变量，在E.W.Dijkstra 教授在信号量机制的研究中，提出了多个“sequential processes”可以通过信号量机制合作访问共享变量，避免冲突导致结果不确定。这里的“sequential processes”的含义就是线程。

	**贝尔实验室Victor A. Vyssotsky提出线程（thead）概念**

	1964年开始设计的Multics操作系统已经有进程的概念，也有多处理器并行处理的GE 645硬件设计，甚至提出了线程的概念。1966年，参与Multics开发的MIT博士生 Jerome Howard Saltzer在其博士毕业论文的一个注脚提到贝尔实验室的Victor A. Vyssotsky用 **thead** 这个名称来表示处理器（processor）执行程序（program）代码序列这个过程的抽象概念，Saltzer进一步把"进程（process）"描述为处理器执行程序代码的当前状态（即线程）和可访问的地址空间。但他们并没有建立类似信号量这样的有效机制来避免并发带来的同步互斥问题。

	**Dijkstra 教授设计出信号量机制**

	Dijkstra 教授带领他的小团队在设计开发THE操作系统的过程中，异步中断触发的难以重现的并发错误，让他们在调试操作系统中碰到了困难。这种困难激发了Dijkstra的灵感，他们除了设计了操作系统的分层结构之外，还设计了信号量机制和对应的P和V操作，来确保线程对共享变量的灵活互斥访问，并支持线程之间的同步操作。P和V是来自荷兰语单词“测试”和“增加”的首字母，是很罕见的非英语来源的操作系统术语。


	**Brinch Hansen、Tony Hoare和Dijkstra提出管程机制**

	丹麦的Brinch Hansen，英国的Tony Hoare和Dijkstra并不满足于信号量来解决操作系统和应用中的并发问题。因为对于复杂一些的同步互斥问题（如哲学家问题），如果使用信号量机制不小心，容易引起死锁等错误。在 1971年 的研讨会上，他们三人开始讨论管程（Monitor）的想法，希望设计一种更高级的并发管理语言结构，便于程序员开发并发程序。在1972年春天，Brinch Hansen 在他写的“操作系统原理”教科书中，提出了管程的概念，并把这一概念嵌入到了Concurrent Pascal 编程语言中，然后他和他的学生再接再厉，在PDP 11/45计算机上编写了Concurrent Pascal 编译器，并用Concurrent Pascal 编写了Solo操作系统。Brinch Hansen在操作系统和语言级并发处理方面的开创性工作影响了后续的操作系统并发处理机制（如条件变量等）和不少的编程语言并发方案。

	Brinch Hansen的两句名言：

	  - 写作是对简单性的严格测试：不可能令人信服地写出无法理解的想法。
	  - 编程是用清晰的散文写文章并使它们可执行的艺术

.. hint::

	**并行与并发的区别**

	可回顾一下 :ref:`并行与并发的解释 <term-parallel-concurrency>` 。在单处理器情况下，多个进程或线程是并发执行的。


有了进程以后，为什么还会出现线程（Thread）呢？考虑如下情况，对于很多应用（以单一进程的形式运行）而言，逻辑上存在多个可并行执行的任务，如果其中一个任务被阻塞，将会引起不依赖该任务的其他任务也被阻塞。举个具体的例子，我们平常用编辑器来编辑文本内容的时候，都会有一个定时自动保存的功能，这个功能的作用是在系统或应用本身出现故障的情况前，已有的文档内容会被提前保存。假设编辑器自动保存时由于磁盘性能导致写入较慢，导致整个进程被阻塞，这就会影响到用户编辑文档的人机交互体验：即软件的及时响应能力不足，用户只有等到磁盘写入完成后，操作系统重新调度该进程运行后，用户才可编辑。如果我们把一个进程内的多个可并行执行任务通过一种更细粒度的方式让操作系统进行调度，那么就可以通过处理器时间片切换实现这种细粒度的并发执行。这种细粒度的调度对象就是线程。


.. _term-thread-define:

线程定义
~~~~~~~~~~~~~~~~~~~~

简单地说，线程是进程的组成部分，进程可包含1 -- n个线程，属于同一个进程的线程共享进程的资源，比如地址空间，打开的文件等。基本的线程由线程ID、执行状态、当前指令指针(PC)、寄存器集合和栈组成。线程是可以被操作系统或用户态调度器独立调度（Scheduling）和分派（Dispatch）的基本单位。

在本章之前，进程是程序的基本执行实体，是程序关于某数据集合上的一次运行活动，是系统进行资源（处理器，地址空间和文件等）分配和调度的基本单位。在有了线程后，对进程的定义也要调整了，进程是线程的资源容器，线程成为了程序的基本执行实体。


.. hint::

   **线程与进程的区别**
   
   下面的比较是以线程为调度对象的操作系统作为分析对象：

   * 进程间相互独立（即资源隔离），同一进程的各线程间共享进程的资源（即资源共享）；
   * 子进程和父进程有不同的地址空间和资源，而多个线程（没有父子关系）则共享同一所属进程的地址空间和资源；
   * 每个线程有其自己的执行上下文（线程ID、程序计数器、寄存器集合和执行栈），而进程的执行上下文包括其管理的线程执行上下文和地址空间（故同一进程的线程上下文切换比进程上下文切换要快）；
   * 线程是一个可调度/分派/执行的实体（线程有就绪、阻塞和运行三种基本执行状态），进程不是可调度/分派/执行的的实体，而是线程的资源容器；
   * 进程间通信需要通过IPC机制（如管道等）， 属于同一进程的线程间可以共享“即直接读写”进程的数据，但需要同步互斥机制的辅助，以保证数据的一致性。


同步互斥
~~~~~~~~~~~~~~~~~~~~~~

在上面提到了同步互斥和数据一致性，它们的含义是什么呢？ 当多个线程共享同一进程的地址空间时，每个线程都可以访问属于这个进程的数据（全局变量）。如果每个线程使用到的变量都是其他线程不会读取或者修改的话，那么就不存在一致性问题。如果变量是只读的，多个线程读取该变量也不会有一致性问题。但是，当一个线程修改变量时，其他线程在读取这个变量时，可能会看到一个不一致的值，这就是数据不一致性的问题。


.. note::

	**线程的数据一致性**

	线程的数据一致性的定义：在单处理器（即只有一个核的CPU）下，如果某线程更新了一个可被其他线程读到的共享数据，那么后续其他线程都能读到这个最新被更新的共享数据。

为什么会出现线程的数据不一致问题呢？其根本原因是 **调度的不可控性** ：即读写共享变量的代码片段会随时可能被操作系统调度和切换。先看看如下的伪代码例子：

.. code-block:: rust
    :linenos:

    //全局共享变量 NUM初始化为 0
    static mut NUM : usize=0;
    ...

    //主进程中的所有线程都会执行如下的核心代码
    unsafe { NUM = NUM + 1; }
    ...
    

    //所有线程执行完毕后，主进程显示num的值
    unsafe {
     println!("NUM = {:?}", NUM);
    }


如果线程的个数为 ``n`` ，那么最后主进程会显示的数应该是多少呢？ 也许同学觉得应该也是 ``n`` ，但现实并不是这样。为了了解事实真相，我们首先必须了解Rust编译器对 ``num = num + 1;`` 这一行源代码生成的汇编代码序列。

.. code-block:: asm
    :linenos:

    # 假设NUM的地址为 0x1000
    # unsafe { NUM = NUM + 1; } 对应的汇编代码如下
    addi x6, x0, 0x1000        # addr 100: 计算NUM的地址
                               # 由于时钟中断可能会发生线程切换
    ld 	 x5, 0(x6)             # addr 104: 把NUM的值加载到x5寄存器中
                               # 由于时钟中断可能会发生线程切换
    addi x5, x5, 1             # addr 108: x5 <- x5 + 1
                               # 由于时钟中断可能会发生线程切换
    sd   x5, 0(x6)             # addr 112: 把NUM+1的值写回到NUM地址中
    

在这个例子中，一行Rust源代码其实被Rust编译器生成了四行RISC-V汇编代码。如果多个线程在操作系统的管理和调度下都执行这段代码，那么在上述四行汇编代码之间（即第4，6，8行的地方）的时刻可能产生时钟中断，并导致线程调度和切换。

设有两个线程，线程A先进入上述汇编代码区，将要把 ``NUM`` 增加一，为此线程A将 ``NUM`` 的值（假设它这时是 ``0`` ）加载到 ``x5`` 寄存器中，然后执行加一操作，此时 ``x5 = 1`` 。这时时钟中断发生，操作系统将当前正在运行的线程A的上下文（（它的程序计数器、寄存器，包括 ``x5`` 等））保存到线程控制块（在内存中）中。

再接下来，线程B被选中运行，并进入同一段代码。它也执行了前两条条指令，获取NUM的值（此时仍为 ``0`` ）并将其放入 ``x5`` 中，线程B继续执行接下来指令，将 ``x5`` 加一，然后将 ``x5`` 的内容保存到 ``NUM``（地址0x1000）中。因此，全局变量 ``NUM`` 现在的值是 ``1`` 。

最后又发生一次线程上下文切换，线程A恢复运行，此时的 ``x5=1``，现在线程A准备执行最后一条 ``sd`` 指令，将 ``x5`` 的内容保存到 ``NUM`` （地址0x1000）中，``NUM`` 再次被设置为 ``1`` 。

简单总结，这两个线程执行的结果是：增加 ``NUM`` 的代码被执行两次，初始值为 ``0`` ，但是结果为 ``1`` 。而我们一般理解这两个线程执行的“正确”结果应该是全局变量 ``NUM`` 等于  ``2`` 。


.. note::

	**并发相关术语** 　

	- 共享资源（shared resource）：不同的线程/进程都能访问的变量或数据结构。	
	- 临界区（critical section）：访问共享资源的一段代码。
	- 竞态条件（race condition）：多个线程/进程都进入临界区时，都试图更新共享的数据结构，导致产生了不期望的结果。
	- 不确定性（indeterminate）： 多个线程/进程在执行过程中出现了竞态条件，导致执行结果取决于哪些线程在何时运行，即执行结果不确定，而开发者期望得到的是确定的结果。
	- 互斥（mutual exclusion）：一种操作原语，能保证只有一个线程进入临界区，从而避免出现竞态，并产生确定的执行结果。
	- 原子性（atomic）：一系列操作要么全部完成，要么一个都没执行，不会看到中间状态。在数据库领域，具有原子性的一系列操作称为事务（transaction）。
	- 同步（synchronization）：多个并发执行的进程/线程在一些关键点上需要互相等待，这种相互制约的等待称为进程/线程同步。
	- 死锁（dead lock）：一个线程/进程集合里面的每个线程/进程都在等待只能由这个集合中的其他一个线程/进程（包括他自身）才能引发的事件，这种情况就是死锁。
	- 饥饿（hungry）：指一个可运行的线程/进程尽管能继续执行，但由于操作系统的调度而被无限期地忽视，导致不能执行的情况。


在后续的章节中，会大量使用上述术语，如果现在还不够理解，没关系，随着后续的一步一步的分析和实验，相信大家能够掌握上述术语的实际含义。	


实践体验
-----------------------------------------

获取本章代码：

.. code-block:: console

   $ git clone https://github.com/rcore-os/rCore-Tutorial-v3.git
   $ cd rCore-Tutorial-v3
   $ git checkout ch8

在 qemu 模拟器上运行本章代码：

.. code-block:: console

   $ cd os
   $ make run  # 编译后，最终执行如下命令模拟rv64 virt计算机运行：
   ......
   $ qemu-system-riscv64 \
   -machine virt \
   -nographic \
   -bios ../bootloader/rustsbi-qemu.bin \
   -device loader,file=target/riscv64gc-unknown-none-elf/release/os.bin,addr=0x80200000 \
   -drive file=../user/target/riscv64gc-unknown-none-elf/release/fs.img,if=none,format=raw,id=x0 \
        -device virtio-blk-device,drive=x0,bus=virtio-mmio-bus.0


在执行 ``qemu-system-riscv64`` 的参数中，``../user/target/riscv64gc-unknown-none-elf/release/fs.img`` 是包含应用程序集合的文件系统镜像，这个镜像是放在虚拟硬盘块设备 ``virtio-blk-device`` （在下一章会进一步介绍这种存储设备）中的。

若要在 k210 平台上运行，首先需要将 microSD 通过读卡器插入 PC ，然后将打包应用 ELF 的文件系统镜像烧写到 microSD 中：

.. code-block:: console

   $ cd os
   $ make sdcard
   Are you sure write to /dev/sdb ? [y/N]
   y
   16+0 records in
   16+0 records out
   16777216 bytes (17 MB, 16 MiB) copied, 1.76044 s, 9.5 MB/s
   8192+0 records in
   8192+0 records out
   4194304 bytes (4.2 MB, 4.0 MiB) copied, 3.44472 s, 1.2 MB/s

途中需要输入 ``y`` 确认将文件系统烧写到默认的 microSD 所在位置 ``/dev/sdb`` 中（注：这个位置在不同的Linux开发环境下可能是不同的）。这个位置可以在 ``os/Makefile`` 中的 ``SDCARD`` 处进行修改，在烧写之前请确认它被正确配置为 microSD 的实际目录的位置，否则可能会造成数据损失。

烧写之后，将 microSD 插入到 Maix 系列开发板并连接到 PC，然后在开发板上运行本章代码：

.. code-block:: console

   $ cd os
   $ make run BOARD=k210

内核初始化完成之后就会进入shell程序，我们可以体会一下线程的创建和执行过程。在这里我们运行一下本章的测例 ``threads`` ：

.. code-block::

    >> threads
    aaa....bbb...ccc...
    thread#1 exited with code 1
	thread#2 exited with code 2
	thread#3 exited with code 3
	main thread exited.
	Shell: Process 2 exited with code 0

    >> 

它会有4个线程在执行，等前3个线程执行完毕后，主线程退出，导致整个进程退出。

此外，在本章的操作系统支持通过互斥来执行“哲学家就餐问题”这个应用程序：

.. code-block::

   >> phil_din_mutex
	 time cost = 7260
	'-' -> THINKING; 'x' -> EATING; ' ' -> WAITING 
	#0: -------                 xxxxxxxx----------       xxxx-----  xxxxxx--xxx
	#1: ---xxxxxx--      xxxxxxx----------    x---xxxxxx                       
	#2: -----          xx---------xx----xxxxxx------------        xxxx         
	#3: -----xxxxxxxxxx------xxxxx--------    xxxxxx--   xxxxxxxxx             
	#4: ------         x------          xxxxxx--    xxxxx------   xx           
	#0: -------                 xxxxxxxx----------       xxxx-----  xxxxxx--xxx
	Shell: Process 2 exited with code 0
   >> 

我们可以看到5个代表“哲学家”的线程通过操作系统的**信号量**互斥机制在进行“THINKING”、“EATING”、“WAITING”的日常生活。没有哲学家由于拿不到筷子而饥饿，也没有两个哲学家同时拿到一个筷子。


.. note::

	**哲学家就餐问题** 　

	计算机科学家Dijkstra提出并解决的哲学家就餐问题是经典的进程同步互斥问题。哲学家就餐问题描述如下：

	有5个哲学家共用一张圆桌，分别坐在周围的5张椅子上，在圆桌上有5个碗和5只筷子，他们的生活方式是交替地进行思考和进餐。平时，每个哲学家进行思考，饥饿时便试图拿起其左右最靠近他的筷子，只有在他拿到两只筷子时才能进餐。进餐完毕，放下筷子继续思考。


本章代码树
-----------------------------------------

.. code-block::
   :linenos:

	.
	├── bootloader
	│   ├── rustsbi-k210.bin
	│   └── rustsbi-qemu.bin
	├── dev-env-info.md
	├── Dockerfile
	├── easy-fs
	│   ├── Cargo.lock
	│   ├── Cargo.toml
	│   └── src
	│       ├── bitmap.rs
	│       ├── block_cache.rs
	│       ├── block_dev.rs
	│       ├── efs.rs
	│       ├── layout.rs
	│       ├── lib.rs
	│       └── vfs.rs
	├── easy-fs-fuse
	│   ├── Cargo.lock
	│   ├── Cargo.toml
	│   └── src
	│       └── main.rs
	├── LICENSE
	├── Makefile
	├── os
	│   ├── build.rs
	│   ├── Cargo.lock
	│   ├── Cargo.toml
	│   ├── last-qemu
	│   ├── Makefile
	│   └── src
	│       ├── config.rs
	│       ├── console.rs
	│       ├── drivers
	│       │   ├── block
	│       │   │   ├── mod.rs
	│       │   │   ├── sdcard.rs
	│       │   │   └── virtio_blk.rs
	│       │   └── mod.rs
	│       ├── entry.asm
	│       ├── fs
	│       │   ├── inode.rs
	│       │   ├── mod.rs
	│       │   ├── pipe.rs
	│       │   └── stdio.rs
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
	│       │   └── page_table.rs
	│       ├── sbi.rs
	│       ├── sync
	│       │   ├── mod.rs
	│       │   ├── mutex.rs
	│       │   ├── semaphore.rs
	│       │   └── up.rs
	│       ├── syscall
	│       │   ├── fs.rs
	│       │   ├── mod.rs
	│       │   ├── process.rs
	│       │   ├── sync.rs
	│       │   └── thread.rs
	│       ├── task
	│       │   ├── context.rs
	│       │   ├── id.rs
	│       │   ├── manager.rs
	│       │   ├── mod.rs
	│       │   ├── processor.rs
	│       │   ├── process.rs
	│       │   ├── switch.rs
	│       │   ├── switch.S
	│       │   └── task.rs
	│       ├── timer.rs
	│       └── trap
	│           ├── context.rs
	│           ├── mod.rs
	│           └── trap.S
	├── pushall.sh
	├── README.md
	├── rust-toolchain
	└── user
	    ├── Cargo.lock
	    ├── Cargo.toml
	    ├── Makefile
	    └── src
	        ├── bin
	        │   ├── cat.rs
	        │   ├── cmdline_args.rs
	        │   ├── exit.rs
	        │   ├── fantastic_text.rs
	        │   ├── filetest_simple.rs
	        │   ├── forktest2.rs
	        │   ├── forktest.rs
	        │   ├── forktest_simple.rs
	        │   ├── forktree.rs
	        │   ├── hello_world.rs
	        │   ├── huge_write.rs
	        │   ├── initproc.rs
	        │   ├── matrix.rs
	        │   ├── mpsc_sem.rs
	        │   ├── phil_din_mutex.rs
	        │   ├── pipe_large_test.rs
	        │   ├── pipetest.rs
	        │   ├── race_adder_atomic.rs
	        │   ├── race_adder_loop.rs
	        │   ├── race_adder_mutex_blocking.rs
	        │   ├── race_adder_mutex_spin.rs
	        │   ├── race_adder.rs
	        │   ├── run_pipe_test.rs
	        │   ├── sleep.rs
	        │   ├── sleep_simple.rs
	        │   ├── stack_overflow.rs
	        │   ├── threads_arg.rs
	        │   ├── threads.rs
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