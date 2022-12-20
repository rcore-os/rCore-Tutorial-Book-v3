锁机制
=========================================

本节导读
-----------------------------------------

.. chyyuu https://en.wikipedia.org/wiki/Lock_(computer_science)

到目前为止，我们已经实现了进程和线程，也能够理解在一个时间段内，会有多个线程在执行，这就是并发。而且，由于线程的引入，多个线程可以共享进程中的全局数据。如果多个线程都想读和更新全局数据，那么谁先更新取决于操作系统内核的抢占式调度和分派策略。在一般情况下，每个线程都有可能先执行，且可能由于中断等因素，随时被操作系统打断其执行，而切换到另外一个线程运行，形成在一段时间内，多个线程交替执行的现象。如果没有一些保障机制（比如互斥、同步等），那么这些对共享数据进行读写的交替执行的线程，其期望的共享数据的正确结果可能无法达到。

所以，我们需要研究一种保障机制 -- 锁 ，确保无论操作系统如何抢占线程，调度和切换线程的执行，都可以保证对拥有锁的线程，可以独占地对共享数据进行读写，从而能够得到正确的共享数据结果。这种机制的能力来自于处理器的指令、操作系统系统调用的基本支持，从而能够保证线程间互斥地读写共享数据。下面各个小节将从为什么需要锁、锁的基本思路、锁的不同实现方式等逐步展开讲解。

为什么需要锁
-----------------------------------------

上一小节已经提到，没有保障机制的多个线程，在对共享数据进行读写的过程中，可能得不到预期的结果。这需要有一个简单的例子来看看：

.. code-block:: c
    :linenos:
    :emphasize-lines: 4

    // 线程的入口函数
    int a=0;
    void f() {
        a=a+1;
    }

对于上述函数中的第4行代码，一般人理解处理器会一次就执行完这条简单的语句，但实际情况并不是这样。我们可以用GCC编译出上述函数的汇编码：

.. code-block:: shell
    :linenos:

    $ riscv64-unknown-elf-gcc -o f.s -S f.c


可以看到生成的汇编代码如下：

.. code-block:: asm
    :linenos:
    :emphasize-lines: 18-23

    //f.s
      .text
      .globl	a
      .section	.sbss,"aw",@nobits
      .align	2
      .type	a, @object
      .size	a, 4
    a:
      .zero	4
      .text
      .align	1
      .globl	f
      .type	f, @function
    f:
      addi	sp,sp,-16
      sd	s0,8(sp)
      addi	s0,sp,16
      lui	a5,%hi(a)
      lw	a5,%lo(a)(a5)
      addiw	a5,a5,1
      sext.w	a4,a5
      lui	a5,%hi(a)
      sw	a4,%lo(a)(a5)
      nop
      ld	s0,8(sp)
      addi	sp,sp,16
      jr	ra


.. chyyuu 可以给上面的汇编码添加注释???

从中可以看出，对于高级语言的一条简单语句（C代码的第4行，对全局变量进行读写），很可能是由多条汇编代码（汇编代码的第18~23行）组成。如果这个函数是多个线程要执行的函数，那么在上述汇编代码第18行到第23行中的各行之间，可能会发生中断，从而导致操作系统执行抢占式的线程调度和切换，就会得到不一样的结果。由于执行这段汇编代码（第18~23行））的多个线程在访问全局变量过程中可能导致竞争状态，因此我们将此段代码称为临界区（critical section）。临界区是访问共享变量（或共享资源）的代码片段，不能由多个线程同时执行，即需要保证互斥。

下面是有两个线程T0、T1在一个时间段内的一种可能的执行情况：


=====  =====  =======   =======   ===========   =========
时间     T0     T1        OS        共享变量a      寄存器a5
=====  =====  =======   =======   ===========   =========
1       L18      --       --         0          a的高位地址
2       --      --      切换         0              0
3       --      L18       --         0          a的高位地址
4       L20      --       --         0              1
5       --      --      切换         0           a的高位地址
6       --      L20       --         0              1
7       --      --      切换         0              1
8       L23     --       --         1              1
9       --      --      切换         1              1
10      --      L23      --          1          a的高位地址
=====  =====  =======   =======   ===========   =========

一般情况下，线程T0执行完毕后，再执行线程T1，那么共享全局变量 ``a`` 的值为 2 。但在上面的执行过程中，可以看到在线程执行指令的过程中会发生线程切换，这样在时刻10的时候，共享全局变量 ``a`` 的值为 1，这不是我们预期的结果。出现这种情况的原因是两个线程在操作系统的调度下（在哪个时刻调度具有不确定性），交错执行 ``a=a+1`` 的不同汇编指令序列，导致虽然增加全局变量 ``a`` 的代码被执行了两次，但结果还是只增加了1。这种多线程的最终执行结果不确定（indeterminate），取决于由于调度导致的不确定指令执行序列的情况就是竞态条件（race condition）。

如果每个线程在执行 ``a=a+1`` 这个C语句所对应多条汇编语句过程中，不会被操作系统切换，那么就不会出现多个线程交叉读写全局变量的情况，也就不会出现结果不确定的问题了。

所以，访问（特指写操作）共享变量代码片段，不能由多个线程同时执行（即并行）或者在一个时间段内都去执行（即并发）。要做到这一点，需要互斥机制的保障。从某种角度上看，这种互斥性也是一种原子性，即线程在临界区的执行过程中，不会出现只执行了一部分，就被打断并切换到其他线程执行的情况。即，要么线程执行的这一系列操作/指令都完成，要么这一系列操作/指令都不做，不会出现指令序列执行中被打断的情况。



锁的基本思路
-----------------------------------------

要保证多线程并发执行中的临界区的代码具有互斥性或原子性，我们可以建立一种锁，只有拿到锁的线程才能在临界区中执行。这里的锁与现实生活中的锁的含义很类似。比如，我们可以写出如下的伪代码：

.. code-block:: Rust
    :linenos:

    lock(mutex);    // 尝试取锁
    a=a+1;          // 临界区，访问临界资源 a
    unlock(mutex);  // 是否锁
    ...             // 剩余区

对于一个应用程序而言，它的执行是受到其执行环境的管理和限制的，而执行环境的主要组成就是用户态的系统库、操作系统和更底层的处理器，这说明我们需要有硬件和操作系统来对互斥进行支持。一个自然的想法是，这个 ``lock/unlock`` 互斥操作就是CPU提供的机器指令，那上面这一段程序就很容易在计算机上执行了。但需要注意，这里互斥的对象是线程的临界区代码，而临界区代码可以访问各种共享变量（简称临界资源）。只靠两条机器指令，难以识别各种共享变量，不太可能约束可能在临界区的各种指令执行共享变量操作的互斥性。所以，我们还是需要有一些相对更灵活和复杂一点的方法，能够设置一种所有线程能看到的标记，在一个能进入临界区的线程设置好这个标记后，其他线程都不能再进入临界区了。总体上看，对临界区的访问过程分为四个部分：

   1. 尝试取锁:查看锁是否可用，即临界区是否可访问（看占用临界区标志是否被设置），如果可以访问，则设置占用临界区标志（锁不可用）并转到步骤2，否则线程忙等或被阻塞;
   2. 临界区:访问临界资源的系列操作
   3. 释放锁:清除占用临界区标志（锁可用），如果有线程被阻塞，会唤醒阻塞线程；
   4. 剩余区：与临界区不相关部分的代码

根据上面的步骤，可以看到锁机制有两种：让线程忙等的忙等锁（spin lock），已经让线程阻塞的睡眠锁（sleep lock）。接下来，我们会基于用户态软件级、机器指令硬件级、内核态操作系统级三类方法来实现支持互斥的锁。

这里，我们还需要知道如何评价各种锁实现的效果。一般我们需要关注锁的三种属性：

1. 互斥性（mutual exclusion），即锁是否能够有效阻止多个线程进入临界区，这是最基本的属性。
2. 公平性（fairness），当锁可用时，每个竞争线程是否有公平的机会抢到锁。
3. 性能（performance），即使用锁的时间开销。

用户态软件级方法实现锁
------------------------------------------

我们可以快速想到的一个很朴素的锁的实现，用一个变量来表示锁的状态：已占用临界区 -- 1，未占用临界区 -- 0 ，然后根据这个变量的值来判断是否能进入临界区执行，伪代码如下：


.. code-block:: Rust
    :linenos:

    static mut mutex :i32 = 0;

    fn lock(mutex: i32) {
    	while (mutex);
    	mutex = 1;
    }
    
    fn unlock(mutex: i32){
    	mutex = 0;
    }
    

这样的锁实现是否能保证线程在临界区执行的互斥性呢？这里我们要注意到 ``mutex`` 其实也是一个全局共享变量，它也会把多个线程访问，在多个线程执行 ``lock`` 函数的时候，其实不能保证 ``lock`` 函数本身的互斥性。这就会带来问题，下面是一种可能的两线程在 ``lock`` 函数中的执行序列：

=====  ==============  ===============   =======   ==============
时间     T0                T1               OS        共享变量mutex   
=====  ==============  ===============   =======   ==============
1       L4               --                 --         0          
2       --               --                切换         0             
3       --               L4                 --         0         
4       --               --                切换         0            
5       L5(赋值1之前)      --                --         0           
6       --               --                切换         0            
7       --              L5(赋值1之前)        --         0           
8       --              --                切换         0              
9       L5(赋值1之后)     --                 --        1              
10      --              --                 切换          1
11      --              L5(赋值1之后)        --         1             
=====  ==============  ===============   =======   ==============

这样到第11步，两个线程都能够继续执行，并进入临界区，我们期望的互斥性并没有达到。那我们能否为 ``mutex`` 这个变量加上一种锁的互斥保护呢？如果这样做，我们将进入一个无限互斥保护的怪圈。要打破这种僵局，需要再思考一下，在用户态用软件方法实现锁，单靠一个 ``mutex`` 变量无法阻止线程在操作系统任意调度的情况下，越过 ``while`` 这个阻挡的判断循环。我们需要新的全局变量来帮忙：

.. code-block:: Rust
    :linenos:
  
    static mut flag : [i32;2] = [0,0]; // 哪个线程想拿到锁？
    static mut turn : i32 = 0;         // 排号：轮到哪个线程? (线程 0 or 1?)
　
    fn lock() {
        flag[self] = 1;             // 设置自己想取锁 self: 线程 ID
        turn = 1 - self;            // 设置另外一个线程先排号
        while ((flag[1-self] == 1) && (turn == 1 - self)); // 忙等
    }

    fn unlock() {
        flag[self] = 0;             // 设置自己放弃锁
    }

变量 turn 表示哪个线程可以进入临界区。即如果 turn == i，那么线程 Ti 允许在临界区内执行。数组 flag[i] 表示哪个线程准备进入临界区。例如，如果 flag[i] 为 1，那么线程 Ti 准备进入临界区，否则表示线程 Ti 不打算进入临界区。


为了进入临界区，线程 Ti 首先设置 flag[i] 的值为 1 ；并且设置 turn 的值为 j，从而表示如果另一个线程 Tj 希望进入临界区，那么 Tj 能够进入。如果两个线程同时试图进入，那么 turn 会几乎在同时设置成 i 或 j。但只有一个赋值语句的结果会保持；另一个也会设置，但会立即被重写。变量 turn 的最终值决定了哪个线程允许先进入临界区。


这里是如何保证互斥的呢？仔细分析代码，可注意到：

1. 只有当 flag[j] == 0 或者 turn == i 时，线程 Ti 才能进入临界区。
2. 如果两个线程同时在临界区内执行，那么 flag[0]==flag[1]==true。

这意味着线程T0 和 T1 不可能同时成功地执行它们的 while 语句，因为 turn 的值只可能为 0 或 1，而不可能同时为两个值。因此，如果turn的值为j, 那么只有一个线程 Tj 能成功跳出 while 语句，而另外一个线程 Ti 不得不再次陷入判断（“turn == j”）的循环而无法跳出。最终结果是，只要在临界区内，flag[j]==true 和 turn==j 就同时成立。这就保证了只有一个线程能进入临界区的互斥性。

.. chyyuu   性能上有不足，需要说明???  也可介绍一下peterson 算法

机器指令硬件级方法实现锁
-----------------------------------------

导致多线程结果不确定的一个重要因素是操作系统随时有可能切换线程。如果操作系统在临界区执行时，无法进行线程调度和切换，就可以解决结果不确定的问题了。
而操作系统能抢占式调度的一个前提是硬件中断机制，如时钟中断能确保操作系统按时获得对处理器的控制权。如果应用程序能够控制中断的打开/使能与关闭/屏蔽，那就能提供互斥解决方案了。代码如下：


.. code-block:: Rust
    :linenos:
  
    fn lock() {
        disable_Interrupt(); //屏蔽中断的机器指令
    }
    
    fn unlock() {
        enable_Interrupt(); ////使能中断的机器指令
    }
    
这个方法的特点是简单。没有中断，线程可以确信它的代码会继续执行下去，不会被其他线程干扰。注：目前实现的操作系统内核就是在屏蔽中断的情况下执行的。

但这种方法也有不足之处，它给了用户态程序执行特权操作的能力。如果用户态线程在执行过程中刻意关闭中断，它就可以独占处理器，让操作系统无法获得对处理器的控制权。

另外，这种方法不支持多处理器。如果多个线程运行在不同的处理器上，每个线程都试图进入同一个临界区，它关闭的中断只对其正在运行的处理器有效，其他线程可以运行在其他处理器上，还是能够进入临界区，无法保证互斥性。所以，采用控制中断的方式仅对一些非常简单，且信任应用的单处理器场景有效，而对于更广泛的其他场景是不够的。
　

实现锁：原子指令
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

再次关注一下之前不成功的朴素的锁实现，我们可以看到其主要的问题是第2行读 ``mutex`` 和第3行写 ``mutex`` 之间，可以被操作系统切换出去，导致其产生不确定的结果。

.. code-block:: Rust
    :linenos:
    :emphasize-lines: 2-3

    fn lock(mutex: i32) {
        while (mutex);
        mutex = 1;
    }
    

CAS原子指令和TAS原子指令
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

如果能完成读写一个变量的两个操作是一条不会被操作系统打断的机器指令来执行，那我们就可以很容易实现锁机制了，这种机器指令我们称为原子指令。

假定处理器体系结构提供了一条原子指令：比较并交换(Compare-And-Swap，简称CAS)指令，即
比较一个寄存器中的值和另一个寄存器中的内存地址指向的值,如果它们相等,将第三个寄
存器中的值和内存中的值进行交换。这是一条通用的同步指令，在SPARC系统中是 ``compare-and-swap``  指令，在x86系统是 ``compare-and-exchange`` 指令。
其伪代码如下：

.. code-block:: Rust
    :linenos:

    fn CompareAndSwap(ptr: *i32, expected: i32, new: i32) -> i32 {
        let actual :i32 = *ptr;
        if actual == expected {
            *ptr = new;
        }
        actual
    }

    fn lock(mutex : *i32) {
        while (CompareAndSwap(mutex, 0, 1) == 1);
    }

    fn unlock((mutex : *i32){
        *mutex = 0;
    }

比较并交换原子指令的基本思路是检测ptr指向的实际值是否和expected相等；如果相等，更新ptr所指的值为new值；最后返回该内存地址之前指向的实际值。有了比较并交换指令，就可以实现对锁读写的原子操作了。在lock函数中，检查锁标志是否为0，如果是，原子地交换为1，从而获得锁。锁被持有时，竞争锁的线程会忙等在while循环中。


尽管上面例子的想法很好，但没有硬件的支持是无法实现的。幸运的是，一些系统提供了这一指令，支持基于这种概念创建简单的锁。这个更强大的指令有不同的名字：在SPARC上，这个指令叫ldstub（load/store unsigned byte，加载/保存无符号字节）；在x86上，是xchg（atomic exchange，原子交换）指令。但它们基本上在不同的平台上做同样的事，


假定处理器体系结构提供了另外一条原子指令：测试并设置（Test-And-Set，简称 TAS）。因为既可以测试旧值，又可以设置新值，所以我们把这条指令叫作“测试并设置”。其伪代码如下所示：


.. code-block:: Rust
    :linenos:

    fn TestAndSet(old_ptr: &mut i32, new:i32) -> i32 {
        let old :i32 = *old_ptr; // 取得 old_ptr 指向内存单元的旧值 old
        *old_ptr = new;           // 把新值 new 存入到 old_ptr 指向的内存单元中
        old                       // 返回旧值 old
    }

TAS原子指令完成返回old_ptr指向的旧值，同时更新为new的新值这一整个原子操作。基于这一条指令就可以实现一个简单的自旋锁（spin lock）。

我们来确保理解为什么这个锁能工作。首先假设一个线程在运行，调用lock()，没有其他线程持有锁，所以flag是0。当调用TestAndSet(flag, 1)方法，返回0，线程会跳出while循环，获取锁。同时也会原子的设置flag为1，标志锁已经被持有。当线程离开临界区，调用unlock()将flag清理为0。


.. code-block:: Rust
    :linenos:

    static mut mutex :i32 = 0;

    fn lock(mutex: &mut i32) {
        while (TestAndSet(mutex, 1) == 1);
    }
    
    fn unlock(mutex: &mut i32){
        *mutex = 0;
    }


在一开始时，假设一个线程在运行，调用lock()，没有其他线程持有锁，所以mutex为0。当调用TestAndSet(&mutex, 1)函数后，返回0，线程会跳出while循环，获取锁。同时也会原子的设置mutex为1，标志锁已经被持有。当线程离开临界区，调用unlock(mutex)将mutex设置为0，表示没有线程在临界区，其他线程可以尝试获取锁。


如果当某线程已经持有锁（即mutex为1），而另外的线程调用lock(mutex)函数，然后调用TestAndSet(&mutex, 1)函数，这一次将返回1，导致该线程会一直执行while循环。只要某线程一直持有锁，TestAndSet()会重复返回1，导致另外的其他线程会一直自旋忙等。当某线程离开临界区时，会调用unlock(mutex) 函数把mutex改为0，这之后另外的其他一个线程会调用TestAndSet()，返回0并且原子地设置为1，从而获得锁，进入临界区。这样进行了对临界区的互斥保证。

这里的关键是将测试（读旧的锁值）和设置（写新的锁值）合并为一个原子操作，从而保证只有一个线程能获取锁，达到互斥的要求。

注：如果是单处理器环境，要求操作系统支持抢占式调度，否则自旋锁无法使用，因为一个自旋的线程永远不会放弃处理器。


RISC-V的AMO指令与LR/SC指令
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

RISC-V 指令集虽然没有TAS指令和CAS指令，但它提供了一个可选的原子指令集合，主要有两类：

-  内存原子操作(AMO)
- 加载保留/条件存储(Load Reserved / Store Conditional，检查LR/SC)


AMO 类的指令对内存中的操作数执行一个原子的读写操作，并将目标寄存器设置为操作前的内存值。 **原子** 在这里表示指令在执行内存读写之间的过程不会被打断，内存值也不会被其它处理器修改。
LR/SC指令保证了它们两条指令之间的操作的原子性。LR指令读取一个内存字，存入目标寄存器中，并留下这个字的保留记录。而如果SR指令的目标地址上存在保留
记录，它就把字存入这个地址。如果存入成功，它向目标寄存器中写入 0，否则写入一个非 0 值，表示错误码。

这里我们可以用LR/SC来实现上面基于TAS原子指令或CAS原子指令的锁机制：

.. code-block:: Asm
    :linenos:

    # RISC-V sequence for implementing a TAS  at (s1)
    li t2, 1                 # t2 <-- 1 
    Try: lr  t1, s1          # t1 <-- mem[s1]  (load reserved)
            bne t1, x0, Try     # if t1 != 0, goto Try:
            sc  t0, s1, t2      # mem[s1] <-- t2  (store conditional)
            bne t0, x0, Try     # if t0 !=0 ('sc' Instr failed), goto Try:
    Locked: 
            ...                 # critical section 
    Unlock: 
            sw x0,0(s1)         # mem[s1] <-- 0

.. chyyuu https://inst.eecs.berkeley.edu/~cs61c/sp19/pdfs/lectures/lec20.pdf
.. chyyuu    :##code-block:: Asm
.. chyyuu    :linenos:

    # Sample code for compare-and-swap function using LR/SC
    # atomically {
    #   if (M[a0] == a1)
    #     M[a0] = a2;
    # }     
    Try: lr   t0, a0         #  t0 <-- mem[a0] (load reserved)
         bne  t0, a1, fail   #  if t0 != a1, goto fail
         sc   t0, a0, a2     #  mem[a0] <-- a2 (store conditional)     
         bnez t0, Try      #  


.. chyyuu https://people.eecs.berkeley.edu/~krste/papers/EECS-2016-1.pdf Page48 （page 35 figure 4.1）
.. chyyuu https://github.com/riscv/riscv-isa-manual/blob/master/src/a.tex 不够好
.. chyyuu https://inst.eecs.berkeley.edu/~cs152/sp20/lectures/L22-Synch.pdf

基于硬件实现的锁简洁有效，但在某些场景下会效率低下。比如两个线程运行在单处理器上，当一个线程持有锁时，被中断并切换到第二个线程。第二个线程想去获取锁，发现锁已经被前一个线程持有，导致它不得不自旋忙等，直到其时间片耗尽后，被中断并切换回第一个线程。如果有多个线程去竞争一个锁，那么浪费的时间片会更多。要想提高效率，减少不必要的处理器空转的资源浪费，就需要操作系统的帮忙了。

内核态操作系统级方法实现锁
-----------------------------------------


实现锁：yield系统调用
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~


解决忙等的简单方法就是线程主动放弃处理器，而这可以通过操作系统提供的 ``yield`` 系统调用就可以达到目的。


.. code-block:: Rust
    :linenos:

    static mut mutex :i32 = 0;

    fn lock(mutex: &mut i32) {
        while (TestAndSet(mutex, 1) == 1){
            yield_();
        }
    }

    fn unlock(mutex: &mut i32){
        *mutex = 0;
    }


当线程可以调用 ``yield`` 系统调用后，它就会主动放弃CPU，从运行（running）态变为就绪（ready）态，让其他线程运行。

在有许多线程反复竞争一把锁的情况下，一个线程持有锁，但在释放锁之前被抢占，这时其他多个线程分别调用lock()，发现锁被抢占，然后执行线程切换让出CPU。这种方法引入了多次不必要的线程切换，仍然开销比较大。这时让拿不到锁的线程睡眠，就成为了一个更有效的手段了。

目前的操作系统中有一个可以让线程睡眠的 ``sleep`` 系统调用，能让线程休眠（处于阻塞状态）一段时间。但由于另外一个线程释放锁的时间与休眠线程被唤醒时间一般都不相同，这会导致引入不必要的线程切换或等待。所以，简单的采用 ``sleep`` 系统调用也是不合适的。


实现锁：mutex系统调用
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~


使用mutex系统调用
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

既然上面的方法存在这样那样的开销或问题，我们需要进一步思考一下，如何能够实现轻量的可睡眠锁。一个自然的想法就是，让等待锁的线程睡眠，让释放锁的线程显式地唤醒等待锁的线程。如果有多个等待锁的线程，可以全部释放，让大家再次竞争锁；也可以只释放最早等待的那个线程。这就需要更多的操作系统支持，特别是需要一个等待队列来保存等待锁的线程。

我们先看看多线程应用程序如何使用mutex系统调用的：


.. code-block:: Rust
    :linenos:
    :emphasize-lines: 8,13,21,32,35,38

    // user/src/bin/race_adder_mutex_blocking.rs

    static mut A: usize = 0;
    ...
    unsafe fn f() -> ! {
        let mut t = 2usize;
        for _ in 0..PER_THREAD {
            mutex_lock(0);
            let a = &mut A as *mut usize;
            let cur = a.read_volatile();
            for _ in 0..500 { t = t * t % 10007; }
            a.write_volatile(cur + 1);
            mutex_unlock(0);
        }
        exit(t as i32)
    }

    #[no_mangle]
    pub fn main() -> i32 {
        let start = get_time();
        assert_eq!(mutex_blocking_create(), 0);
        let mut v = Vec::new();    
        for _ in 0..THREAD_COUNT {
            v.push(thread_create(f as usize, 0) as usize);
        }
        ...
    }

    // usr/src/syscall.rs

    pub fn sys_mutex_create(blocking: bool) -> isize {
        syscall(SYSCALL_MUTEX_CREATE, [blocking as usize, 0, 0])
    }
    pub fn sys_mutex_lock(id: usize) -> isize {
        syscall(SYSCALL_MUTEX_LOCK, [id, 0, 0])
    }
    pub fn sys_mutex_unlock(id: usize) -> isize {
        syscall(SYSCALL_MUTEX_UNLOCK, [id, 0, 0])
    }    


- 第21行，创建了一个ID为 ``0`` 的互斥锁，对应的是第32行 ``SYSCALL_MUTEX_CREATE`` 系统调用；
- 第8行，尝试获取锁（对应的是第35行 ``SYSCALL_MUTEX_LOCK`` 系统调用），如果取得锁，将继续向下执行临界区代码；如果没有取得锁，将阻塞；
- 第13行，释放锁（对应的是第38行 ``SYSCALL_MUTEX_UNLOCK`` 系统调用），如果有等待在该锁上的线程，则唤醒这些等待线程。



mutex系统调用的实现
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

操作系统如何实现这些系统调用呢？首先考虑一下与此相关的核心数据结构，然后考虑与数据结构相关的相关函数/方法的实现。

在线程的眼里，**互斥** 是一种每个线程能看到的资源，且在一个进程中，可以存在多个不同互斥资源，所以我们可以把所有的互斥资源放在一起让进程来管理，如下面代码第9行所示。这里需要注意的是： ``mutex_list: Vec<Option<Arc<dyn Mutex>>>`` 表示的是实现了 ``Mutex`` trait 的一个“互斥资源”的向量。而 ``MutexBlocking`` 是会实现 ``Mutex`` trait 的内核数据结构，它就是我们提到的 ``互斥资源`` 即 **互斥锁** 。操作系统需要显式地施加某种控制，来确定当一个线程释放锁时，等待的线程谁将能抢到锁。为了做到这一点，操作系统需要有一个等待队列来保存等待锁的线程，如下面代码的第20行所示。


.. code-block:: Rust
    :linenos:
    :emphasize-lines: 9,20

    pub struct ProcessControlBlock {
        // immutable
        pub pid: PidHandle,
        // mutable
        inner: UPSafeCell<ProcessControlBlockInner>,
    }
    pub struct ProcessControlBlockInner {
        ...
        pub mutex_list: Vec<Option<Arc<dyn Mutex>>>,
    }
    pub trait Mutex: Sync + Send {
        fn lock(&self);
        fn unlock(&self);
    }
    pub struct MutexBlocking {
        inner: UPSafeCell<MutexBlockingInner>,
    }
    pub struct MutexBlockingInner {
        locked: bool,
        wait_queue: VecDeque<Arc<TaskControlBlock>>,
    }


这样，在操作系统中，需要设计实现三个核心成员变量。互斥锁的成员变量有两个：表示是否锁上的 ``locked`` 和管理等待线程的等待队列 ``wait_queue`` ；进程的成员变量：锁向量 ``mutex_list`` 。

	
首先需要创建一个互斥锁，下面是应对``SYSCALL_MUTEX_CREATE`` 系统调用的创建互斥锁的函数：	

.. code-block:: Rust
    :linenos:
    :emphasize-lines: 17,20

    // os/src/syscall/sync.rs
    pub fn sys_mutex_create(blocking: bool) -> isize {
        let process = current_process();
        let mutex: Option<Arc<dyn Mutex>> = if !blocking {
            Some(Arc::new(MutexSpin::new()))
        } else {
            Some(Arc::new(MutexBlocking::new()))
        };
        let mut process_inner = process.inner_exclusive_access();
        if let Some(id) = process_inner
            .mutex_list
            .iter()
            .enumerate()
            .find(|(_, item)| item.is_none())
            .map(|(id, _)| id)
        {
            process_inner.mutex_list[id] = mutex;
            id as isize
        } else {
            process_inner.mutex_list.push(mutex);
            process_inner.mutex_list.len() as isize - 1
        }
    }

- 第17行，如果向量中有空的元素，就在这个空元素的位置创建一个可睡眠的互斥锁；
- 第20行，如果向量满了，就在向量中添加新的可睡眠的互斥锁；


有了互斥锁，接下来就是实现 ``Mutex`` trait的内核函数：对应 ``SYSCALL_MUTEX_LOCK`` 系统调用的 ``sys_mutex_lock`` 。操作系统主要工作是，在锁已被其他线程获取的情况下，把当前线程放到等待队列中，并调度一个新线程执行。主要代码如下：

.. code-block:: Rust
    :linenos:		
    :emphasize-lines: 8,15,16,18,20

    // os/src/syscall/sync.rs
    pub fn sys_mutex_lock(mutex_id: usize) -> isize {
        let process = current_process();
        let process_inner = process.inner_exclusive_access();
        let mutex = Arc::clone(process_inner.mutex_list[mutex_id].as_ref().unwrap());
        drop(process_inner);
        drop(process);
        mutex.lock();
        0
    }    
    // os/src/sync/mutex.rs
    impl Mutex for MutexBlocking {
        fn lock(&self) {
            let mut mutex_inner = self.inner.exclusive_access();
            if mutex_inner.locked {
                mutex_inner.wait_queue.push_back(current_task().unwrap());
                drop(mutex_inner);
                block_current_and_run_next();
            } else {
                mutex_inner.locked = true;
            }
        }
    }


.. chyyuu drop的作用？？？

- 第 8 行，调用ID为mutex_id的互斥锁mutex的lock方法，具体工作由lock方法来完成的。
- 第15行，如果互斥锁mutex已经被其他线程获取了，	那么在第16行，将把当前线程放入等待队列中，在第18行，并让当前线程处于等待状态，并调度其他线程执行。
- 第20行，如果互斥锁mutex还没被获取，那么当前线程会获取给互斥锁，并返回系统调用。

最后是实现 ``Mutex`` trait的内核函数：对应 ``SYSCALL_MUTEX_UNLOCK`` 系统调用的 ``sys_mutex_unlock`` 。操作系统的主要工作是，如果有等待在这个互斥锁上的线程，需要唤醒最早等待的线程。主要代码如下：

.. code-block:: Rust
    :linenos:	

    // os/src/syscall/sync.rs
    pub fn sys_mutex_unlock(mutex_id: usize) -> isize {
        let process = current_process();
        let process_inner = process.inner_exclusive_access();
        let mutex = Arc::clone(process_inner.mutex_list[mutex_id].as_ref().unwrap());
        drop(process_inner);
        drop(process);
        mutex.unlock();
        0
    }
    // os/src/sync/mutex.rs
    impl Mutex for MutexBlocking {	
        fn unlock(&self) {
            let mut mutex_inner = self.inner.exclusive_access(); 
            assert_eq!(mutex_inner.locked, true);
            mutex_inner.locked = false;
            if let Some(waking_task) = mutex_inner.wait_queue.pop_front() {
                add_task(waking_task);
            }
        }
    }	    

- 第8行，调用ID为mutex_id的互斥锁mutex的unlock方法，具体工作由unlock方法来完成的。
- 第16行，释放锁。
- 第17-18行，如果有等待的线程，唤醒等待最久的那个线程。


