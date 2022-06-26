信号量机制
=========================================

本节导读
-----------------------------------------

.. chyyuu https://en.wikipedia.org/wiki/Semaphore_(programming)

在上一节中，我们介绍了互斥锁（mutex 或  lock）的起因、使用和实现过程。通过互斥锁，可以让线程在临界区执行时，独占临界资源。当我们需要更灵活的互斥访问或同步操作方式，如提供了最多只允许N个线程访问临界资源的情况，让某个线程等待另外一个线程执行完毕后再继续执行的同步过程等，互斥锁这种方式就有点力不从心了。

在本节中，将介绍功能更加强大和灵活的同步互斥机制 -- Semaphore（信号量），设计它的设计思路，使用和在操作系统中的具体实现。可以看到，信号量的实现需要互斥锁和处理器原子指令的支持，它是一种更高级的同步互斥机制。


信号量的起源和基本思路
-----------------------------------------


1963年前后，当时的数学家（其实是计算机科学家）Edsger Dijkstra和他的团队正在为Electrologica X8计算机开发一个操作系统（称为 THE multiprogramming system，THE多道程序系统）的过程中，提出了信号（Semphore）是一种变量或抽象数据类型，用于控制多个线程对共同资源的访问。在1965年，Edsger Dijkstra发表了论文手稿 "Cooperating sequential processes" ，详细论述了在多个顺序代码执行流（论文用语：sequential processes）的并发执行过程中，如果没有约束机制，会有不确定的执行结果，为此他提出了信号量的设计思路，能够让这些松耦合的顺序代码执行流能进行同步操作并能对共享资源进行互斥访问。对于由于不当互斥同步操作引入的死锁（论文用语：Deadly Embrace），可通过其设计的银行家算法（The Banker's Algorithm）来解决。 

注：银行家算法将在下一节讲解。

Edsger Dijkstra和他的团队提出的信号量是对互斥锁的一种巧妙的扩展。上一节中的互斥锁的初始值一般设置为 1 的整型变量， 表示临界区还没有被某个线程占用。互斥锁用 0 表示临界区已经被占用了，用 1 表示临界区为空。再通过 lock/unlock 操作来协调多个线程轮流独占临界区执行。而信号量的初始值可设置为 N 的整数变量, 如果 N 大于 0， 表示最多可以有N个线程进入临界区执行，如果 N 小于等于 0 ， 表示不能有线程进入临界区了，必须在后续操作中让信号量的值加 1 ，才能唤醒某个等待的线程。


Dijkstra对信号量设立两种操作：P（Proberen（荷兰语），尝试）操作和V（Verhogen（荷兰语），增加）操作。P操作是检查信号量的值是否大于0，若该值大于0，则将其值减1并继续（表示可以进入临界区了）；若该值为0，则线程将睡眠。注意，此时P操作还未结束。而且由于信号量本身是一种临界资源（可回想一下上一节的锁，其实也是一种临界资源），所以在P操作中，检查/修改信号量值以及可能发生的睡眠这一系列操作是一个不可分割的原子操作过程。通过原子操作才能保证一旦P操作开始，则在该操作完成或阻塞睡眠之前，其他线程均不允许访问该信号量。

V操作会对信号量的值加1，然后检查是否有一个或多个线程在该信号量上睡眠等待。如有，则选择其中的一个线程唤醒并允许该线程继续完成它的P操作；如没有，则直接返回。注意，信号量的值加1，并可能唤醒一个线程的一系列操作同样也是不可分割的原子操作过程。不会有某个进程因执行v操作而阻塞。


如果信号量是一个任意的整数，通常被称为计数信号量（Counting Semaphore），或一般信号量（General Semaphore）；如果信号量只有0或1的取值，则称为二值信号量（Binary Semaphore）。可以看出，互斥锁只是信号量的一种特例 -- 二值信号量，信号量很好地解决了最多只允许N个线程访问临界资源的情况。



关于一种信号量实现的伪代码如下所示：


.. code-block:: rust
    :linenos:

    fn P(S) { 
          if S >= 1 
             S = S - 1;
          else 
             <block and enqueue the thread>;
    }
    fn V(S) { 
          if <some threads are blocked on the queue> 
             <unblock a thread>;
          else 
             S = S + 1;
    }


在上述实现中，S的取值范围为大于等于0 的整数。 S的初值一般设置为一个大于0的正整数，表示可以进入临界区的线程数。当S取值为1，表示是二值信号量，也就是互斥锁了。使用信号量实现线程互斥访问临界区的伪代码如下：


.. code-block:: rust
    :linenos:

    let static mut S: semaphore = 1;

    // Thread i
    fn  foo() {
        ...
        P(S);
        execute Cricital Section;
        V(S);
        ...
    }




下面是另外一种信号量实现的伪代码：

.. code-block:: rust
    :linenos:

    fn P(S) { 
          S = S - 1;
          if 0 > S then 
             <block and enqueue the thread>;
    }         
    fn V(S) { 
          S = S + 1;
          if <some threads are blocked on the queue> 
             <unblock a thread>;
    }

        
在这种实现中，S的初值一般设置为一个大于0的正整数，表示可以进入临界区的线程数。但S的取值范围可以是小于 0 的整数，表示等待进入临界区的睡眠线程数。

信号量的另一种用途是用于实现同步（synchronization）。比如，把信号量的初始值设置为 0 ，当一个线程A对此信号量执行一个P操作，那么该线程立即会被阻塞睡眠。之后有另外一个线程B对此信号量执行一个V操作，就会将线程A唤醒。这样线程B中执行V操作之前的代码序列B-stmts和线程A中执行P操作之后的代码A-stmts序列之间就形成了一种确定的同步执行关系，即线程B的B-stmts会先执行，然后才是线程A的A-stmts开始执行。相关伪代码如下所示：



.. code-block:: rust
    :linenos:

    let static mut S: semaphore = 0;
    
    //Thread A
    ...
    P(S);
    Label_2:
    A-stmts after Thread B::Label_1;
    ...

    //Thread B
    ...
    B-stmts before Thread A::Label_2;
    Label_1:
    V(S);

    ...    


实现信号量
------------------------------------------


使用semaphore系统调用
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

我们通过例子来看看如何实际使用信号量。下面是面向应用程序对信号量系统调用的简单使用，可以看到对它的使用与上一节介绍的互斥锁系统调用类似。
在这个例子中，主线程先创建了初值为0的信号量SEM_SYNC，然后再创建两个线程 First和Second。线程First会先睡眠10ms，而当线程Second执行时，会由于执行信号量的P操作而等待睡眠；当线程First醒来后，会执行V操作，
从而能够唤醒线程Second。这样线程First和线程Second就形成了一种稳定的同步关系。

.. code-block:: rust
    :linenos:
    :emphasize-lines: 5,10,16,22,25,28

    const SEM_SYNC: usize = 0; //信号量ID
    unsafe fn first() -> ! {
        sleep(10);
        println!("First work and wakeup Second");
        semaphore_up(SEM_SYNC); //信号量V操作
        exit(0)
    }
    unsafe fn second() -> ! {
        println!("Second want to continue,but need to wait first");
        semaphore_down(SEM_SYNC); //信号量P操作
        println!("Second can work now");
        exit(0)
    }
    pub fn main() -> i32 {
        // create semaphores
        assert_eq!(semaphore_create(0) as usize, SEM_SYNC); // 信号量初值为0
        // create first, second threads
        ...
    }

    pub fn sys_semaphore_create(res_count: usize) -> isize {
        syscall(SYSCALL_SEMAPHORE_CREATE, [res_count, 0, 0])
    }
    pub fn sys_semaphore_up(sem_id: usize) -> isize {
        syscall(SYSCALL_SEMAPHORE_UP, [sem_id, 0, 0])
    }
    pub fn sys_semaphore_down(sem_id: usize) -> isize {
        syscall(SYSCALL_SEMAPHORE_DOWN, [sem_id, 0, 0])
    }


- 第16行，创建了一个初值为0，ID为 SEM_SYNC 的信号量，对应的是第22行 SYSCALL_SEMAPHORE_CREATE 系统调用；
- 第10行，线程Second执行信号量P操作（对应的是第28行 SYSCALL_SEMAPHORE_DOWN 系统调用），由于信号量初值为0，该线程将阻塞；
- 第5行，线程First执行信号量V操作（对应的是第25行 SYSCALL_SEMAPHORE_UP 系统调用），会唤醒等待该信号量的线程Second。

实现semaphore系统调用
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~


操作系统如何实现信号量系统调用呢？我们首先考虑一下与此相关的核心数据结构，然后考虑与数据结构相关的相关函数/方法的实现。

在线程的眼里，信号量是一种每个线程能看到的共享资源，且可以存在多个不同信号量来合理使用不同的资源。所以我们可以把信号量也看成四一种资源，可放在一起让进程来管理，如下面代码第9行所示。这里需要注意的是： ``semaphore_list: Vec<Option<Arc<Semaphore>>>`` 表示的是信号量资源的列表。而 ``Semaphore`` 是信号量的内核数据结构，由信号量值和等待队列组成。操作系统需要显式地施加某种控制，来确定当一个线程执行P操作和V操作时，如何让线程睡眠或唤醒线程。在这里，P操作是由 ``Semaphore`` 的 ``down`` 方法实现，而V操作是由 ``Semaphore`` 的 ``up`` 方法实现。


.. code-block:: rust
    :linenos:
    :emphasize-lines: 9,16,17

    pub struct ProcessControlBlock {
        // immutable
        pub pid: PidHandle,
        // mutable
        inner: UPSafeCell<ProcessControlBlockInner>,
    }
    pub struct ProcessControlBlockInner {
        ...
        pub semaphore_list: Vec<Option<Arc<Semaphore>>>,
    }

    pub struct Semaphore {
        pub inner: UPSafeCell<SemaphoreInner>,
    }
    pub struct SemaphoreInner {
        pub count: isize,
        pub wait_queue: VecDeque<Arc<TaskControlBlock>>,
    }
    impl Semaphore {
        pub fn new(res_count: usize) -> Self {
            Self {
                inner: unsafe { UPSafeCell::new(
                    SemaphoreInner {
                        count: res_count as isize,
                        wait_queue: VecDeque::new(),
                    }
                )},
            }
        }

        pub fn up(&self) {
            let mut inner = self.inner.exclusive_access();
            inner.count += 1;
            if inner.count <= 0 {
                if let Some(task) = inner.wait_queue.pop_front() {
                    add_task(task);
                }
            }
        }

        pub fn down(&self) {
            let mut inner = self.inner.exclusive_access();
            inner.count -= 1;
            if inner.count < 0 {
                inner.wait_queue.push_back(current_task().unwrap());
                drop(inner);
                block_current_and_run_next();
            }
        }
    }


首先是核心数据结构：

- 第9行，进程控制块中管理的信号量列表。
- 第16-17行，信号量的核心数据成员：信号量值和等待队列。

然后是重要的三个成员函数：

- 第20行，创建信号量，信号量初值为参数 res_count。
- 第31行，实现V操作的up函数，第34行，当信号量值小于等于0时，将从信号量的等待队列中弹出一个线程放入线程就绪队列。
- 第41行，实现P操作的down函数，第44行，当信号量值小于0时，将把当前线程放入信号量的等待队列，设置当前线程为挂起状态并选择新线程执行。


Dijkstra, Edsger W. Cooperating sequential processes (EWD-123) (PDF). E.W. Dijkstra Archive. Center for American History, University of Texas at Austin. (transcription) (September 1965)  https://www.cs.utexas.edu/users/EWD/transcriptions/EWD01xx/EWD123.html

Downey, Allen B. (2016) [2005]. "The Little Book of Semaphores" (2nd ed.). Green Tea Press.

Leppäjärvi, Jouni (May 11, 2008). "A pragmatic, historically oriented survey on the universality of synchronization primitives" (pdf). University of Oulu, Finland.