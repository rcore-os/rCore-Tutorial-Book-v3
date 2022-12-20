条件变量机制
=========================================

本节导读
-----------------------------------------

到目前为止，我们已经了解了操作系统提供的互斥锁和信号量。但在某些情况下，应用程序在使用这两者时需要非常小心，如果使用不当，就会产生效率低下、竞态条件、死锁或者一些不可预测的情况。为了简化编程，避免错误，计算机科学家针对某些情况设计了一种高层的同步互斥原语。具体而言，在有些情况下，线程需要检查某一条件（condition）满足之后，才会继续执行。
我们来看一个例子，有两个线程first和second在运行，线程first会把全局变量 A设置为1，而线程second在 ``! A == 0`` 的条件满足后，才能继续执行，如下面的伪代码所示：

.. code-block:: rust
    :linenos:

    static mut A: usize = 0;
    unsafe fn first() -> ! {
        A=1;
        ...
    }

    unsafe fn second() -> ! {
        while A==0 {
          // 忙等或睡眠等待 A==1
        };
        //继续执行相关事务
    }


在上面的例子中，如果线程second先执行，会忙等在while循环中，在操作系统的调度下，线程first会执行并把A赋值为1后，然后线程second再次执行时，就会跳出while循环，进行接下来的工作。配合互斥锁，可以正确完成上述带条件的同步流程，如下面的伪代码所示：

.. code-block:: rust
    :linenos:

    static mut A: usize = 0;
    unsafe fn first() -> ! {
        mutex.lock();
        A=1;
        mutex.unlock();
        ...
    }

    unsafe fn second() -> ! {
        mutex.lock();
        while A==0 { };
        mutex.unlock();
        //继续执行相关事务
    }

这种实现能执行，但效率低下，因为线程second会忙等检查，浪费处理器时间。我们希望有某种方式让线程second休眠，直到等待的条件满足，再继续执行。于是，我们可以写出如下的代码：

.. code-block:: rust
    :linenos:

    static mut A: usize = 0;
    unsafe fn first() -> ! {
        mutex.lock();
        A=1;
        wakeup(second);
        mutex.unlock();
        ...
    }

    unsafe fn second() -> ! {
        mutex.lock();
        while A==0 { 
           wait();
        };
        mutex.unlock();
        //继续执行相关事务
    }

粗略地看，这样就可以实现睡眠等待了。但请同学仔细想想，当线程second在睡眠的时候，mutex是否已经上锁了？ 确实，线程second是带着上锁的mutex进入等待睡眠状态的。如果这两个线程的调度顺序是先执行线程second，再执行线程first，那么线程second会先睡眠且拥有mutex的锁；当线程first执行时，会由于没有mutex的锁而进入等待锁的睡眠状态。结果就是两个线程都睡了，都执行不下去，这就出现了 **死锁** 。

这里需要解决的两个关键问题： **如何等待一个条件？** 和 **在条件为真时如何向等待线程发出信号** 。我们的计算机科学家给出了 **管程（Monitor）** 和 **条件变量（Condition Variables）** 这种巧妙的方法。接下来，我们就会深入讲解条件变量的设计与实现。

条件变量的基本思路
-------------------------------------------

.. note::

    Brinch Hansen（1973）和Hoare（1974）结合操作系统和Concurrent Pascal编程语言，提出了一种高级同步原语，称为管程（monitor）。一个管程是一个由过程（procedures，Pascal语言的术语，即函数）、共享变量及数据结构等组成的一个集合。线程可以调用管程中的过程，但线程不能在管程之外声明的过程中直接访问管程内的数据结构。



    .. code-block:: pascal
        :linenos:

        monitor m1
            integer i;   //共享变量
            condition c; //条件变量

            procedure f1();
              ...       //对共享变量的访问，以及通过条件变量进行线程间的通知
            end;

            procedure f2();
              ...       //对共享变量的访问，以及通过条件变量进行线程间的通知
            end;
        end monitor    


管程有一个很重要的特性，即任一时刻只能有一个活跃线程调用管程中过程，这一特性使线程在调用执行管程中过程时能保证互斥，这样线程就可以放心地访问共享变量。管程是编程语言的组成部分，编译器知道其特殊性，因此可以采用与其他过程调用不同的方法来处理对管程的调用，比如编译器可以在管程中的每个过程的入口/出口处加上互斥锁的加锁/释放锁的操作。因为是由编译器而非程序员来生成互斥锁相关的代码，所以出错的可能性要小。

管程虽然借助编译器提供了一种实现互斥的简便途径，但这还不够，还需要一种线程间的沟通机制。首先是等待机制：由于线程在调用管程中某个过程时，发现某个条件不满足，那就在无法继续运行而被阻塞。这里需要注意的是：在阻塞之前，操作系统需要把进入管程的过程入口出的互斥锁给释放掉，这样才能让其他线程有机会调用管程的过程。

其次是唤醒机制：另外一个线程可以在调用管程的过程中，把某个条件设置为真，并且还需要有一种机制及时唤醒等待条件为真的阻塞线程。这里需要注意的是：唤醒线程（本身执行位置在管程的过程中）如果把阻塞线程(其执行位置还在管程的过程中)唤醒了，那么需要避免两个活跃的线程都在管程中导致互斥被破坏的情况。为了避免管程中同时有两个活跃线程，我们需要一定的规则来约定线程发出唤醒操作的行为。目前有三种典型的规则方案：

- Hoare语义：线程发出唤醒操作后，马上阻塞自己，让新被唤醒的线程运行。注：此时唤醒线程的执行位置还在管程中。
- Hansen语义：是执行唤醒操作的线程必须立即退出管程，即唤醒操作只可能作为一个管程过程的最后一条语句。注：此时唤醒线程的执行位置离开了管程。
- Mesa语义：唤醒线程在发出行唤醒操作后继续运行，并且只有它退出管程之后，才允许等待的线程开始运行。注：此时唤醒线程的执行位置还在管程中。

一般开发者会采纳Brinch Hansen的建议，因为它在概念上更简单，并且更容易实现。这种沟通机制的具体实现就是  **条件变量** 和对应的操作：wait和signal。线程使用条件变量来等待一个条件变成真。条件变量其实是一个线程等待队列，当条件不满足时，线程通过执行条件变量的wait操作就可以把自己加入到等待队列中，睡眠等待（waiting）该条件。另外某个线程，当它改变条件为真后，就可以通过条件变量的signal操作来唤醒一个或者多个等待的线程（通过在该条件上发信号），让它们继续执行。


早期提出的管程是基于Concurrent Pascal来设计的，其他语言，如C和Rust等，并没有在语言上支持这种机制。我们还是可以用手动加入互斥锁的方式来代替编译器，就可以在C和Rust的基础上实现原始的管程机制了。在目前的C语言应用开发中，实际上也是这么做的。这样，我们就可以用互斥锁和条件变量来重现实现上述的同步互斥例子：


.. code-block:: rust
    :linenos:

    static mut A: usize = 0;
    unsafe fn first() -> ! {
        mutex.lock();
        A=1;
        condvar.wakeup();
        mutex.unlock();
        ...
    }

    unsafe fn second() -> ! {
        mutex.lock();
        while A==0 { 
           condvar.wait(mutex); //在睡眠等待之前，需要释放mutex
        };
        mutex.unlock();
        //继续执行相关事务
    }



有了上面的介绍，我们就可以实现条件变量的基本逻辑了。下面是条件变量的wait和signal操作的伪代码：

.. code-block:: rust
    :linenos:

    fn wait(mutex) {
        mutex.unlock();
        <block and enqueue the thread>;
        mutex.lock();
    }

    fn signal() {
       <unblock a thread>; 
    }


条件变量的wait操作包含三步，1. 释放锁；2. 把自己挂起；3. 被唤醒后，再获取锁。条件变量的signal操作只包含一步：找到挂在条件变量上睡眠的线程，把它唤醒。

注意，条件变量不像信号量那样有一个整型计数值的成员变量，所以条件变量也不能像信号量那样有读写计数值的能力。如果一个线程向一个条件变量发送唤醒操作，但是在该条件变量上并没有等待的线程，则唤醒操作实际上什么也没做。



实现条件变量
-------------------------------------------

使用condvar系统调用
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~


我们通过例子来看看如何实际使用条件变量。下面是面向应用程序对条件变量系统调用的简单使用，可以看到对它的使用与上一节介绍的信号量系统调用类似。 在这个例子中，主线程先创建了初值为1的互斥锁和一个条件变量，然后再创建两个线程 First和Second。线程First会先睡眠10ms，而当线程Second执行时，会由于条件不满足执行条件变量的wait操作而等待睡眠；当线程First醒来后，通过设置A为1，让线程second等待的条件满足，然后会执行条件变量的signal操作， 从而能够唤醒线程Second。这样线程First和线程Second就形成了一种稳定的同步与互斥关系。

.. code-block:: rust
    :linenos:
    :emphasize-lines: 11,19,26,33,36,39

    static mut A: usize = 0;   //全局变量

    const CONDVAR_ID: usize = 0;
    const MUTEX_ID: usize = 0;

    unsafe fn first() -> ! {
        sleep(10);
        println!("First work, Change A --> 1 and wakeup Second");
        mutex_lock(MUTEX_ID);
        A=1;
        condvar_signal(CONDVAR_ID);
        mutex_unlock(MUTEX_ID);
        ...
    }
    unsafe fn second() -> ! {
        println!("Second want to continue,but need to wait A=1");
        mutex_lock(MUTEX_ID);
        while A==0 {
            condvar_wait(CONDVAR_ID, MUTEX_ID);
        }
        mutex_unlock(MUTEX_ID);
        ...
    }
    pub fn main() -> i32 {
        // create condvar & mutex
        assert_eq!(condvar_create() as usize, CONDVAR_ID);
        assert_eq!(mutex_blocking_create() as usize, MUTEX_ID);
        // create first, second threads
        ...
    }

    pub fn condvar_create() -> isize {
        sys_condvar_create(0)
    }
    pub fn condvar_signal(condvar_id: usize) {
        sys_condvar_signal(condvar_id);
    }
    pub fn condvar_wait(condvar_id: usize, mutex_id: usize) {
        sys_condvar_wait(condvar_id, mutex_id);
    }

- 第26行，创建了一个ID为 CONDVAR_ID 的条件量，对应的是第33行 SYSCALL_CONDVAR_CREATE 系统调用；
- 第19行，线程Second执行条件变量wait操作（对应的是第39行 SYSCALL_CONDVAR_WAIT 系统调用），该线程将释放mutex锁并阻塞；
- 第5行，线程First执行条件变量signal操作（对应的是第36行 SYSCALL_CONDVAR_SIGNAL 系统调用），会唤醒等待该条件变量的线程Second。


实现condvar系统调用
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

操作系统如何实现条件变量系统调用呢？我们还是采用通常的分析做法：数据结构+方法，即首先考虑一下与此相关的核心数据结构，然后考虑与数据结构相关的相关函数/方法的实现。

在线程的眼里，条件变量 是一种每个线程能看到的共享资源，且在一个进程中，可以存在多个不同条件变量资源，所以我们可以把所有的条件变量资源放在一起让进程来管理，如下面代码第9行所示。这里需要注意的是： condvar_list: Vec<Option<Arc<Condvar>>> 表示的是条件变量资源的列表。而 Condvar 是条件变量的内核数据结构，由等待队列组成。操作系统需要显式地施加某种控制，来确定当一个线程执行wait操作和signal操作时，如何让线程睡眠或唤醒线程。在这里，wait操作是由Condvar的wait方法实现，而signal操作是由Condvar的signal方法实现。


.. code-block:: rust
    :linenos:
    :emphasize-lines: 9,15,18,27,33

    pub struct ProcessControlBlock {
        // immutable
        pub pid: PidHandle,
        // mutable
        inner: UPSafeCell<ProcessControlBlockInner>,
    }
    pub struct ProcessControlBlockInner {
        ...
        pub condvar_list: Vec<Option<Arc<Condvar>>>,
    }
    pub struct Condvar {
        pub inner: UPSafeCell<CondvarInner>,
    }
    pub struct CondvarInner {
        pub wait_queue: VecDeque<Arc<TaskControlBlock>>,
    }
    impl Condvar {
        pub fn new() -> Self {
            Self {
                inner: unsafe { UPSafeCell::new(
                    CondvarInner {
                        wait_queue: VecDeque::new(),
                    }
                )},
            }
        }
        pub fn signal(&self) {
            let mut inner = self.inner.exclusive_access();
            if let Some(task) = inner.wait_queue.pop_front() {
                add_task(task);
            }
        }
        pub fn wait(&self, mutex:Arc<dyn Mutex>) {
            mutex.unlock();
            let mut inner = self.inner.exclusive_access();
            inner.wait_queue.push_back(current_task().unwrap());
            drop(inner);
            block_current_and_run_next();
            mutex.lock();
        }
    }


首先是核心数据结构：

- 第9行，进程控制块中管理的条件变量列表。
- 第15行，条件变量的核心数据成员：等待队列。

然后是重要的三个成员函数：

- 第18行，创建条件变量，即创建了一个空的等待队列。
- 第27行，实现signal操作，将从条件变量的等待队列中弹出一个线程放入线程就绪队列。
- 第33行，实现wait操作，释放mutex互斥锁，将把当前线程放入条件变量的等待队列，设置当前线程为挂起状态并选择新线程执行。在恢复执行后，再加上mutex互斥锁。



Hansen, Per Brinch (1993). "Monitors and concurrent Pascal: a personal history". HOPL-II: The second ACM SIGPLAN conference on History of programming languages. History of Programming Languages. New York, NY, USA: ACM. pp. 1–35. doi:10.1145/155360.155361. ISBN 0-89791-570-4.