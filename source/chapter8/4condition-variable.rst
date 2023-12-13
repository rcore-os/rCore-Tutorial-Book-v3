条件变量机制
=========================================

本节导读
-----------------------------------------

到目前为止，我们已经了解了操作系统提供的互斥锁和信号量两种同步原语。它们可以用来实现各种同步互斥需求，但是它们比较复杂（特别是信号量），对于程序员的要求较高。如果使用不当，就有可能导致效率低下或者产生竞态条件、死锁或一些不可预测的情况。为了简化编程，避免错误，计算机科学家针对某些情况设计了一种抽象层级较高、更易于使用的同步原语，这就是本节要介绍的条件变量机制。

.. 到目前为止，我们已经了解了操作系统提供的互斥锁和信号量。但在某些情况下，应用程序在使用这两者时需要非常小心，如果使用不当，就会产生效率低下、竞态条件、死锁或者一些不可预测的情况。为了简化编程，避免错误，计算机科学家针对某些情况设计了一种高层的同步互斥原语。具体而言，在有些情况下，线程需要检查某一条件（condition）满足之后，才会继续执行。

.. 我们来看一个例子，有两个线程first和second在运行，线程first会把全局变量 A设置为1，而线程second在 ``! A == 0`` 的条件满足后，才能继续执行，如下面的伪代码所示：

条件变量的背景
----------------------------------------------

.. _link-condsync-problem:

首先来看我们需要解决的一类一种同步互斥问题。在信号量一节中提到的 :ref:`条件同步问题 <link-cond-sync>` 的基础上，有的时候我们还需要基于共享资源的状态进行同步。如下面的例子所示：

.. code-block:: rust
    :linenos:

    static mut A: usize = 0;
    unsafe fn first() -> ! {
        A = 1;
        ...
    }

    unsafe fn second() -> ! {
        while A == 0 {
          // 忙等直到 A==1
        };
        //继续执行相关事务
    }

其中，全局变量 ``A`` 初始值为 0。假设两个线程并发运行，分别执行 ``first`` 和 ``second`` 函数，那么这里的同步需求是第二个线程必须等待第一个线程将 ``A`` 修改成 1 之后再继续执行。 

.. 在上面的例子中，如果线程second先执行，会忙等在while循环中，在操作系统的调度下，线程first会执行并把A赋值为1后，然后线程second再次执行时，就会跳出while循环，进行接下来的工作。配合互斥锁，可以正确完成上述带条件的同步流程，如下面的伪代码所示：

如何实现这种同步需求呢？首先需要注意到全局变量 ``A`` 是一种共享资源，需要用互斥锁保护它的并发访问：

.. code-block:: rust
    :linenos:

    unsafe fn first() -> ! {
        mutex_lock(MUTEX_ID);
        A = 1;
        mutex_unlock(MUTEX_ID);
        ...
    }

    unsafe fn second() -> ! {
        mutex_lock(MUTEX_ID);
        while A == 0 { }
        mutex_unlock(MUTEX_ID);
        //继续执行相关事务
    }

然而，这种实现并不正确。假设执行 ``second`` 的线程先拿到锁，那么它需要等到执行 ``first`` 的线程将 ``A`` 改成 1 之后才能退出忙等并释放锁。然而，由于线程 ``second`` 一开始就拿着锁也不会释放，线程 ``first`` 无法拿到锁并修改 ``A`` 。这样，实际上构成了死锁，线程 ``first`` 可能被阻塞，而线程 ``second`` 一直在忙等，两个线程无法做任何有意义的事情。

为了解决这个问题，我们需要修改 ``second`` 中忙等时锁的使用方式：

.. code-block:: rust

    unsafe fn second() -> ! {
        loop {
            mutex_lock(MUTEX_ID);
            if A == 0 {
                mutex_unlock(MUTEX_ID);
            } else {
                mutex_unlock(MUTEX_ID);
                break;
            }
        }
        //继续执行相关事务
    }

在这种实现中，我们对忙等循环中的每一次对 ``A`` 的读取独立加锁。这样的话，当 ``second`` 线程发现 ``first`` 还没有对 ``A`` 进行修改的时候，就可以先将锁释放让 ``first`` 可以进行修改。这种实现是正确的，但是基于忙等会浪费大量 CPU 资源和产生不必要的上下文切换。于是，我们可以利用基于阻塞机制的信号量进一步进行改造：

.. _link-condsync-sem:

.. code-block:: rust
    :linenos:
    :emphasize-lines: 6,16

    // user/src/bin/condsync_sem.rs

    unsafe fn first() -> ! {
        mutex_lock(MUTEX_ID);
        A = 1;
        semaphore_up(SEM_ID);
        mutex_unlock(MUTEX_ID);
        ...
    }

    unsafe fn second() -> ! {
        loop {
            mutex_lock(MUTEX_ID);
            if A == 0 {
                mutex_unlock(MUTEX_ID);
                semaphore_down(SEM_ID);
            } else {
                mutex_unlock(MUTEX_ID);
                break;
            }
        }
        //继续执行相关事务
    }

按照使用信号量解决条件同步问题的通用做法，我们创建一个 :math:`N=0` 的信号量，其 ID 为 ``SEM_ID`` 。在线程 ``first`` 成功修改 ``A`` 之后，进行 ``SEM_ID`` 的 up 操作唤醒线程 ``second`` ；而在线程 ``second`` 发现 ``A`` 为 0，也即线程 ``first`` 还没有完成修改的时候，会进行 ``SEM_ID`` 的 down 操作进入阻塞状态。这样的话，在线程 ``first`` 唤醒它之前，操作系统都不会调度到它。

上面的实现中有一个非常重要的细节：请同学思考， ``second`` 函数中第 15 行解锁和第 16 行信号量的 down 操作可以交换顺序吗？显然是不能的。如果这样做的话，假设 ``second`` 先拿到锁，它发现 ``A`` 为 0 就会进行信号量的 down 操作在拿着锁的情况下进入阻塞。这将会导致什么问题？如果想要线程 ``second`` 被唤醒，就需要线程 ``first`` 修改 ``A`` 并进行信号量 up 操作，然而前提条件是线程 ``first`` 能拿到锁。这是做不到的，因为线程 ``second`` 已经拿着锁进入阻塞状态了，在被唤醒之前都不会将锁释放。于是两个线程都会进入阻塞状态，再一次构成了死锁。可见，这种 **带着锁进入阻塞的情形是我们需要特别小心的** 。

从上面的例子可以看出，互斥锁和信号量能实现很多功能，但是它们对于程序员的要求较高，一旦使用不当就很容易出现难以调试的死锁问题。对于这种比较复杂的同步互斥问题，就可以用本节介绍的条件变量来解决。

.. 然而，这种实现并不正确，假设执行 ``second`` 的线程先拿到锁，那么它会一直忙等在 while 循环中，也不会把锁释放。而执行 ``first`` 的线程始终拿不到锁，也没有办法将 ``A`` 改成 1

.. 这种实现能执行，但效率低下，因为线程second会忙等检查，浪费处理器时间。我们希望有某种方式让线程second休眠，直到等待的条件满足，再继续执行。于是，我们可以写出如下的代码：

.. .. code-block:: rust
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

.. 粗略地看，这样就可以实现睡眠等待了。但请同学仔细想想，当线程second在睡眠的时候，mutex是否已经上锁了？ 确实，线程second是带着上锁的mutex进入等待睡眠状态的。如果这两个线程的调度顺序是先执行线程second，再执行线程first，那么线程second会先睡眠且拥有mutex的锁；当线程first执行时，会由于没有mutex的锁而进入等待锁的睡眠状态。结果就是两个线程都睡了，都执行不下去，这就出现了 **死锁** 。

.. 这里需要解决的两个关键问题： **如何等待一个条件？** 和 **在条件为真时如何向等待线程发出信号** 。我们的计算机科学家给出了 **管程（Monitor）** 和 **条件变量（Condition Variables）** 这种巧妙的方法。接下来，我们就会深入讲解条件变量的设计与实现。

管程与条件变量
-------------------------------------------

我们再回顾一下我们需要解决的一类同步互斥问题：首先，线程间共享一些资源，于是必须使用互斥锁对这些资源进行保护，确保同一时间最多只有一个线程在资源的临界区内；其次，我们还希望能够高效且灵活地支持线程间的条件同步。这应该基于阻塞机制实现：即线程在条件未满足时将自身阻塞，之后另一个线程执行到了某阶段之后，发现条件已经满足，于是将之前阻塞的线程唤醒。 :ref:`刚刚 <link-condsync-sem>` ，我们用信号量与互斥锁的组合解决了这一问题，但是这并不是一种通用的解决方案，而是有局限性的：

- 信号量本质上是一个整数，它不足以描述所有类型的等待条件/事件；
- 在使用信号量的时候需要特别小心。比如，up 和 down 操作必须配对使用。而且在和互斥锁组合使用的时候需要注意操作顺序，不然容易导致死锁。

.. _term-monitor:

针对这种情况，Brinch Hansen（1973）和 Hoare（1974）结合操作系统和 Concurrent Pascal 编程语言，提出了一种高级同步原语，称为 **管程** (Monitor)。管程是一个由过程（Procedures，是 Pascal 语言中的术语，等同于我们今天所说的函数）、共享变量及数据结构等组成的一个集合，体现了面向对象思想。编程语言负责提供管程的底层机制，程序员则可以根据需求设计自己的管程，包括自定义管程中的过程和共享资源。在管程帮助下，线程可以更加方便、安全、高效地进行协作：线程只需调用管程中的过程即可，过程会对管程中线程间的共享资源进行操作。需要注意的是，管程中的共享资源不允许直接访问，而是只能通过管程中的过程间接访问，这是在编程语言层面对共享资源的一种保护，与 C++/Java 等语言中类的私有成员类似。

下面这段代码是 `使用 Concurrent Pascal 语言编写的管程示例的一部分 <https://en.wikipedia.org/wiki/Concurrent_Pascal#Example>`_ ：

.. code-block:: pascal
    :linenos:

    type
        buffer = Monitor
            { 管程数据成员定义 }
            var
                { 共享资源 }
                saved: Integer;
                full : Boolean;
                { 条件变量 }
                fullq, emptyq: Queue;
                
            { 管程过程定义 }
            procedure entry put(item: Integer);
            begin
                if full then
                    { 条件不满足，阻塞当前线程 }
                    delay(fullq);
                saved := item;
                full := true;
                { 条件已经满足，唤醒其他线程 }
                continue(emptyq);
            end;

.. .. note::

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

那么，管程是如何满足互斥访问和条件同步这两个要求的呢？

- **互斥访问** ：区别于 Pascal 语言中的一般过程，管程中的过程使用 ``entry`` 关键字（见第 12 行）描述。编程语言保证同一时刻最多只有一个活跃线程在执行管程中的过程，这保证了线程并发调用管程过程的时候能保证管程中共享资源的互斥访问。管程是编程语言的组成部分，编译器知道其特殊性，因此可以采用与其他过程调用不同的方法来处理对管程的调用，比如编译器可以在管程中的每个过程的入口/出口处自动加上互斥锁的获取/释放操作。这一过程对程序员是透明的，降低了程序员的心智负担，也避免了程序员误用互斥锁而出错。
- **条件同步** ：管程还支持线程间的条件同步机制，它也是基于阻塞等待的，因而也分成阻塞和唤醒两部分。对于阻塞而言，第 14 行发现条件不满足，当前线程需要等待，于是在第 16 行阻塞当前线程；对于唤醒而言，第 17~18 行的执行满足了某些条件，随后在第 20 行唤醒等待该条件的线程（如果存在）。

.. _term-condition-variable:

在上面的代码片段中，阻塞和唤醒操作分别叫做 ``delay`` 和 ``continue`` （分别在第 16 和 20 行），它们都是在数据类型 ``Queue`` 上进行的。这里的 ``Queue`` 本质上是一个阻塞队列： ``delay`` 会将当前线程阻塞并加入到该阻塞队列中；而 ``continue`` 会从该阻塞队列中移除一个线程并将其唤醒。今天我们通常将这个 ``Queue`` 称为 **条件变量** (Condition Variable) ，而将条件变量的阻塞和唤醒操作分别叫做 ``wait`` 和 ``signal`` 。

.. image:: monitor-condvar.png
   :align: center
   :scale: 46 %
   :name: Monitor and Condition Variable
   :alt: 管程和条件变量示意图

一个管程中可以有多个不同的条件变量，每个条件变量代表多线程并发执行中需要等待的一种特定的条件，并保存所有阻塞等待该条件的线程。注意条件变量与管程过程自带的互斥锁是如何交互的：当调用条件变量的 ``wait`` 操作阻塞当前线程的时候，注意到该操作是在管程过程中，因此此时当前线程是持有锁的。经验告诉我们 **不要在持有锁的情况下陷入阻塞** ，因此在陷入阻塞状态之前当前线程必须先释放锁；当被阻塞的线程被其他线程使用 ``signal`` 操作唤醒之后，需要重新获取到锁才能继续执行，不然的话就无法保证管程过程的互斥访问。因此，站在线程的视角，必须持有锁才能调用条件变量的 ``wait`` 操作阻塞自身，且 ``wait`` 的功能按顺序分成下述多个阶段，由编程语言保证其原子性：

- 释放锁；
- 阻塞当前线程；
- 当前线程被唤醒之后，重新获取到锁。
- ``wait`` 返回，当前线程成功向下执行。

由于互斥锁的存在， ``signal`` 操作也不只是简单的唤醒操作。当线程 :math:`T_1` 在执行过程（位于管程过程中）中发现某条件满足准备唤醒线程 :math:`T_2` 的时候，如果直接让线程 :math:`T_2` 继续执行（也位于管程过程中），就会违背管程过程的互斥访问要求。因此，问题的关键是，在 :math:`T_1` 唤醒 :math:`T_2` 的时候， :math:`T_1` 如何处理它正持有的锁。具体来说，根据相关线程的优先级顺序，唤醒操作有这几种语义：

- Hoare 语义：优先级 :math:`T_2>T_1>其他线程` 。也就是说，当 :math:`T_1` 发现条件满足之后，立即通过 ``signal`` 唤醒 :math:`T_2` 并 **将锁转交** 给 :math:`T_2` ，这样 :math:`T_2` 就能立即继续执行，而 :math:`T_1` 则暂停执行并进入一个 *紧急等待队列* 。当 :math:`T_2` 退出管程过程后会将锁交回给紧急等待队列中的 :math:`T_1` ，从而 :math:`T_1` 可以继续执行。
- Hansen 语义：优先级 :math:`T_1>T_2>其他线程` 。即 :math:`T_1` 发现条件满足之后，先继续执行，直到退出管程之前再使用 ``signal`` 唤醒并 **将锁转交** 给 :math:`T_2` ，于是 :math:`T_2` 可以继续执行。注意在 Hansen 语义下， ``signal`` 必须位于管程过程末尾。
- Mesa 语义：优先级 :math:`T_1>T_2=其他线程` 。即 :math:`T_1` 发现条件满足之后，就可以使用 ``signal`` 唤醒 :math:`T_2` ，但是并 **不会将锁转交** 给 :math:`T_2` 。这意味着在 :math:`T_1` 退出管程过程释放锁之后， :math:`T_2` 还需要和其他线程竞争，直到抢到锁之后才能继续执行。

这些优先级顺序如下图所示：

.. image:: condvar-priority.png
    :align: center

可以看出， Hoare 和 Hansen 语义的区别在于 :math:`T_1` 和 :math:`T_2` 的优先级顺序不同。 Hoare 语义认为被唤醒的线程应当立即执行，而 Hensen 语义则认为应该优先继续执行当前线程。二者的相同之处在于它们都将锁直接转交给唤醒的线程，也就保证了 :math:`T_2` 一定紧跟着 :math:`T_1` 回到管程过程中，于是在 :math:`T_2` **被唤醒之后其等待的条件一定是成立的** （因为 :math:`T_1` 和 :math:`T_2` 中间没有其他线程），因此 **没有必要重复检查条件是否成立就可以向下执行** 。相对的， Mesa 语义中 :math:`T_1` 就不会将锁转交给 :math:`T_2` ，而是将锁释放让 :math:`T_2` 和其他同优先级的线程竞争。这样， :math:`T_1` 和 :math:`T_2` 之间可能存在其他线程，这些线程的执行会影响到共享资源，以至于 :math:`T_2` 抢到锁继续执行的时候，它所等待的条件又已经不成立了。所以，在 Mesa 语义下， **wait 操作返回之时不见得线程等待的条件一定成立，有必要重复检查确认之后再继续执行** 。

.. note::

    **条件等待应该使用 if/else 还是 while?**

    在使用 ``wait`` 操作进行条件等待的时候，通常有以下两种方式：

    .. code-block:: c

        // 第一种方法，基于 if/else
        if (!condition) {
            wait();
        } else {
            ...
        }

        // 第二种方法，基于 while
        while (!condition) {
            wait();
        }

    如果基于 if/else 的话，其假定了 ``wait`` 返回之后条件一定已经成立，于是不再做检查直接向下执行。而基于 while 循环的话，则是无法确定 ``wait`` 返回之后条件是否成立，于是将 ``wait`` 包裹在一个 while 循环中重复检查直到条件成立。

    根据上面的分析可以，如果条件变量是 Mesa 语义，则必须将 ``wait`` 操作放在 while 循环中；如果是 Hoare/Hansen 语义，则使用 if/else 或者 while 均可。在不能确定条件变量为何种语义的情况下，应使用 while 循环，这样保证不会出错。


.. 管程有一个很重要的特性，即任一时刻只能有一个活跃线程调用管程中过程，这一特性使线程在调用执行管程中过程时能保证互斥，这样线程就可以放心地访问共享变量。管程是编程语言的组成部分，编译器知道其特殊性，因此可以采用与其他过程调用不同的方法来处理对管程的调用，比如编译器可以在管程中的每个过程的入口/出口处加上互斥锁的加锁/释放锁的操作。因为是由编译器而非程序员来生成互斥锁相关的代码，所以出错的可能性要小。

.. 管程虽然借助编译器提供了一种实现互斥的简便途径，但这还不够，还需要一种线程间的沟通机制。首先是等待机制：由于线程在调用管程中某个过程时，发现某个条件不满足，那就在无法继续运行而被阻塞。这里需要注意的是：在阻塞之前，操作系统需要把进入管程的过程入口处的互斥锁给释放掉，这样才能让其他线程有机会调用管程的过程。

.. 其次是唤醒机制：另外一个线程可以在调用管程的过程中，把某个条件设置为真，并且还需要有一种机制及时唤醒等待条件为真的阻塞线程。这里需要注意的是：唤醒线程（本身执行位置在管程的过程中）如果把阻塞线程(其执行位置还在管程的过程中)唤醒了，那么需要避免两个活跃的线程都在管程中导致互斥被破坏的情况。为了避免管程中同时有两个活跃线程，我们需要一定的规则来约定线程发出唤醒操作的行为。目前有三种典型的规则方案：

.. - Hoare语义：线程发出唤醒操作后，马上阻塞自己，让新被唤醒的线程运行。注：此时唤醒线程的执行位置还在管程中。
.. - Hansen语义：是执行唤醒操作的线程必须立即退出管程，即唤醒操作只可能作为一个管程过程的最后一条语句。注：此时唤醒线程的执行位置离开了管程。
.. - Mesa语义：唤醒线程在发出行唤醒操作后继续运行，并且只有它退出管程之后，才允许等待的线程开始运行。注：此时唤醒线程的执行位置还在管程中。

一般情况下条件变量会使用 Hansen 语义，因为它在概念上更简单，并且更容易实现。其实除了条件变量之外，这几种语义也作用于其他基于阻塞-唤醒机制的同步原语。例如，前两节的互斥锁和信号量就是基于 Hansen 语义实现的，有兴趣的同学可以回顾一下。在操作系统中 Mesa 语义也比较常用。

.. 一般开发者会采纳Brinch Hansen的建议，因为它在概念上更简单，并且更容易实现。这种沟通机制的具体实现就是  **条件变量** 和对应的操作：wait和signal。线程使用条件变量来等待一个条件变成真。条件变量其实是一个线程等待队列，当条件不满足时，线程通过执行条件变量的wait操作就可以把自己加入到等待队列中，睡眠等待（waiting）该条件。另外某个线程，当它改变条件为真后，就可以通过条件变量的signal操作来唤醒一个或者多个等待的线程（通过在该条件上发信号），让它们继续执行。

早期提出的管程是基于 Concurrent Pascal 语言来设计的，其他语言，如 C 和 Rust 等，并没有在语言上支持这种机制。对此，我们的做法是从管程中将比较通用的同步原语——条件变量抽取出来，然后再将其和互斥锁组合使用（手动加入加锁/解锁操作代替编译器），以这种方式模拟原始的管程机制。在目前的 C 语言应用开发中，实际上也是这样做的。

.. 早期提出的管程是基于Concurrent Pascal来设计的，其他语言，如C和Rust等，并没有在语言上支持这种机制。我们还是可以用手动加入互斥锁的方式来代替编译器，就可以在C和Rust的基础上实现原始的管程机制了。在目前的C语言应用开发中，实际上也是这么做的。这样，我们就可以用互斥锁和条件变量来重现实现上述的同步互斥例子：

条件变量系统调用
----------------------------------------------------------

于是，我们新增条件变量相关系统调用如下：

.. code-block:: rust

    /// 功能：为当前进程新增一个条件变量。
    /// 返回值：假定该操作必定成功，返回创建的条件变量的 ID 。
    /// syscall ID : 1030
    pub fn sys_condvar_create() -> isize;

    /// 功能：对当前进程的指定条件变量进行 signal 操作，即
    /// 唤醒一个在该条件变量上阻塞的线程（如果存在）。
    /// 参数：condvar_id 表示要操作的条件变量的 ID 。
    /// 返回值：假定该操作必定成功，返回 0 。
    /// syscall ID : 1031
    pub fn sys_condvar_signal(condvar_id: usize) -> isize;

    /// 功能：对当前进程的指定条件变量进行 wait 操作，分为多个阶段：
    /// 1. 释放当前线程持有的一把互斥锁；
    /// 2. 阻塞当前线程并将其加入指定条件变量的阻塞队列；
    /// 3. 直到当前线程被其他线程通过 signal 操作唤醒；
    /// 4. 重新获取当前线程之前持有的锁。
    /// 参数：mutex_id 表示当前线程持有的互斥锁的 ID ，而
    /// condvar_id 表示要操作的条件变量的 ID 。
    /// 返回值：假定该操作必定成功，返回 0 。
    /// syscall ID : 1032
    pub fn sys_condvar_wait(condvar_id: usize, mutex_id: usize) -> isize;

这里，条件变量也被视作进程内的一种资源，进程内的不同条件变量使用条件变量 ID 区分。注意 ``wait`` 操作不仅需要提供条件变量的 ID ，还需要提供线程目前持有的锁的 ID 。需要注意的是， **我们内核中实现的条件变量是 Mesa 语义的** 。

条件变量的使用方法
-----------------------------------------------------------------

条件同步问题
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

下面展示了如何使用条件变量解决本节开头提到的 :ref:`条件同步问题 <link-condsync-problem>` ：

.. code-block:: rust
    :linenos:
    :emphasize-lines: 11,21

    // user/src/bin/condsync_condvar.rs

    const CONDVAR_ID: usize = 0;
    const MUTEX_ID: usize = 0;

    unsafe fn first() -> ! {
        sleep(10);
        println!("First work, Change A --> 1 and wakeup Second");
        mutex_lock(MUTEX_ID);
        A = 1;
        condvar_signal(CONDVAR_ID);
        mutex_unlock(MUTEX_ID);
        exit(0)
    }

    unsafe fn second() -> ! {
        println!("Second want to continue,but need to wait A=1");
        mutex_lock(MUTEX_ID);
        while A == 0 {
            println!("Second: A is {}", A);
            condvar_wait(CONDVAR_ID, MUTEX_ID);
        }
        println!("A is {}, Second can work now", A);
        mutex_unlock(MUTEX_ID);
        exit(0)
    }

    #[no_mangle]
    pub fn main() -> i32 {
        // create condvar & mutex
        assert_eq!(condvar_create() as usize, CONDVAR_ID);
        assert_eq!(mutex_blocking_create() as usize, MUTEX_ID);
        ...
    }

第 31 和 32 行我们分别创建要用到的条件变量和互斥锁。在 ``second`` 中，首先有一层互斥锁保护，然后由于条件变量是 Mesa 语义的，所以我们需要使用 while 循环进行等待，不符合条件调用 ``condvar_wait`` 阻塞自身的时候还要给出当前持有的互斥锁的 ID ；在 ``first`` 中，最外层同样有互斥锁保护。在修改完成之后只需调用 ``condvar_signal`` 即可唤醒执行 ``second`` 的线程。

**在使用条件变量的时候需要特别注意** :ref:`唤醒丢失 <term-lost-wakeup>` **问题** 。也就是说和信号量不同，如果调用 ``signal`` 的时候没有任何线程在条件变量的阻塞队列中，那么这次 ``signal`` 不会有任何效果，这次唤醒也不会被记录下来。对于这个例子来说，我们在 ``first`` 中还会修改 ``A`` ，因此如果 ``first`` 先执行，即使其中的 ``signal`` 没有任何效果，之后执行 ``second`` 的时候也会发现条件已经满足而不必进入阻塞。 

.. 有了上面的介绍，我们就可以实现条件变量的基本逻辑了。下面是条件变量的wait和signal操作的伪代码：

.. .. code-block:: rust
    :linenos:

    fn wait(mutex) {
        mutex.unlock();
        <block and enqueue the thread>;
        mutex.lock();
    }

    fn signal() {
       <unblock a thread>; 
    }


.. 条件变量的wait操作包含三步，1. 释放锁；2. 把自己挂起；3. 被唤醒后，再获取锁。条件变量的signal操作只包含一步：找到挂在条件变量上睡眠的线程，把它唤醒。

.. 注意，条件变量不像信号量那样有一个整型计数值的成员变量，所以条件变量也不能像信号量那样有读写计数值的能力。如果一个线程向一个条件变量发送唤醒操作，但是在该条件变量上并没有等待的线程，则唤醒操作实际上什么也没做。

同步屏障问题
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

接下来我们看一个有趣的问题。假设有 3 个线程，每个线程都执行如下 ``thread_fn`` 函数：

.. code-block:: rust

    // user/src/bin/barrier_fail.rs

    fn thread_fn() {
        for _ in 0..300 { print!("a"); }
        for _ in 0..300 { print!("b"); }
        for _ in 0..300 { print!("c"); }
        exit(0)
    }

可以将 ``thread_fn`` 分成打印字符 a、打印字符 b 和打印字符 c 这三个阶段。考虑这样一种同步需求：即在阶段间设置 **同步屏障** ，只有 *所有的* 线程都完成上一阶段之后，这些线程才能够进入下一阶段。也就是说，如果有线程更早完成了一个阶段，那么它需要等待其他较慢的线程也完成这一阶段才能进入下一阶段。最后的执行结果应该是所有的 a 被打印出来，然后是所有的 b ，最后是所有的 c 。同学们在向下阅读之前可以思考如何用我们学过的同步原语来实现这种同步需求。

这里给出基于互斥锁和条件变量的一种参考实现：

.. code-block:: rust
    :linenos:

    // user/src/bin/barrier_condvar.rs

    const THREAD_NUM: usize = 3;

    struct Barrier {
        mutex_id: usize,
        condvar_id: usize,
        count: UnsafeCell<usize>,
    }

    impl Barrier {
        pub fn new() -> Self {
            Self {
                mutex_id: mutex_create() as usize,
                condvar_id: condvar_create() as usize,
                count: UnsafeCell::new(0),
            }
        }
        pub fn block(&self) {
            mutex_lock(self.mutex_id);
            let count = self.count.get();
            // SAFETY: Here, the accesses of the count is in the
            // critical section protected by the mutex.
            unsafe { *count = *count + 1; } 
            if unsafe { *count } == THREAD_NUM {
                condvar_signal(self.condvar_id);
            } else {
                condvar_wait(self.condvar_id, self.mutex_id);
                condvar_signal(self.condvar_id);
            }
            mutex_unlock(self.mutex_id);
        }
    }

    unsafe impl Sync for Barrier {}

    lazy_static! {
        static ref BARRIER_AB: Barrier = Barrier::new();
        static ref BARRIER_BC: Barrier = Barrier::new();
    }

    fn thread_fn() {
        for _ in 0..300 { print!("a"); }
        BARRIER_AB.block();
        for _ in 0..300 { print!("b"); }
        BARRIER_BC.block();
        for _ in 0..300 { print!("c"); }
        exit(0)
    }

我们自定义一种 ``Barrier`` 类型，类似于前面讲到的管程。这里的关键在于 ``Barrier::block`` 方法。在拿到锁之后，首先检查 ``count`` 变量。 ``count`` 变量是一种共享资源，记录目前有多少线程阻塞在同步屏障中。如果所有的线程都已经到了，那么当前线程就可以唤醒其中一个；否则就需要先阻塞，在被唤醒之后再去唤醒一个其他的。最终来看会形成一条唤醒链。

有兴趣的同学可以思考如何用其他同步原语来解决这个问题。

实现条件变量
----------------------------------------------

最后我们来看在我们的内核中条件变量是如何实现的。首先还是将条件变量作为一种资源加入到进程控制块中：

.. code-block:: rust
    :linenos:
    :emphasize-lines: 7

    // os/src/task/process.rs

    pub struct ProcessControlBlockInner {
        ...
        pub mutex_list: Vec<Option<Arc<dyn Mutex>>>,
        pub semaphore_list: Vec<Option<Arc<Semaphore>>>,
        pub condvar_list: Vec<Option<Arc<Condvar>>>,
    }

条件变量 ``Condvar`` 在数据结构层面上比信号量还简单，只有一个阻塞队列 ``wait_queue`` （因此再次强调小心唤醒丢失问题）：

.. code-block:: rust
    :linenos:

    // os/src/sync/condvar.rs

    pub struct Condvar {
        pub inner: UPSafeCell<CondvarInner>,
    }

    pub struct CondvarInner {
        pub wait_queue: VecDeque<Arc<TaskControlBlock>>,
    }

条件变量相关的系统调用也是直接调用 ``Condvar`` 的同名方法实现的，因此这里我们主要看 ``Condvar`` 的方法：

.. code-block:: rust
    :linenos:
    :emphasize-lines: 17,26

    // os/src/sync/condvar.rs

    impl Condvar {
        pub fn new() -> Self {
            Self {
                inner: unsafe {
                    UPSafeCell::new(CondvarInner {
                        wait_queue: VecDeque::new(),
                    })
                },
            }
        }

        pub fn signal(&self) {
            let mut inner = self.inner.exclusive_access();
            if let Some(task) = inner.wait_queue.pop_front() {
                wakeup_task(task);
            }
        }

        pub fn wait(&self, mutex: Arc<dyn Mutex>) {
            mutex.unlock();
            let mut inner = self.inner.exclusive_access();
            inner.wait_queue.push_back(current_task().unwrap());
            drop(inner);
            block_current_and_run_next();
            mutex.lock();
        }
    }

- 第 4 行的 ``new`` 创建一个空的阻塞队列；
- 第 14 行的 ``signal`` 从阻塞队列中移除一个线程并调用唤醒原语 ``wakeup_task`` 将其唤醒。注意如果此时阻塞队列为空则此操作不会有任何影响；
- 第 21 行的 ``wait`` 接收一个当前线程持有的锁作为参数。首先将锁释放，然后将当前线程挂在条件变量阻塞队列中，之后调用阻塞原语 ``block_current_and_run_next`` 阻塞当前线程。在被唤醒之后还需要重新获取锁，这样 ``wait`` 才能返回。

.. 我们通过例子来看看如何实际使用条件变量。下面是面向应用程序对条件变量系统调用的简单使用，可以看到对它的使用与上一节介绍的信号量系统调用类似。 在这个例子中，主线程先创建了初值为1的互斥锁和一个条件变量，然后再创建两个线程 First和Second。线程First会先睡眠10ms，而当线程Second执行时，会由于条件不满足执行条件变量的wait操作而等待睡眠；当线程First醒来后，通过设置A为1，让线程second等待的条件满足，然后会执行条件变量的signal操作， 从而能够唤醒线程Second。这样线程First和线程Second就形成了一种稳定的同步与互斥关系。

.. 操作系统如何实现条件变量系统调用呢？我们还是采用通常的分析做法：数据结构+方法，即首先考虑一下与此相关的核心数据结构，然后考虑与数据结构相关的相关函数/方法的实现。

.. 在线程的眼里，条件变量 是一种每个线程能看到的共享资源，且在一个进程中，可以存在多个不同条件变量资源，所以我们可以把所有的条件变量资源放在一起让进程来管理，如下面代码第9行所示。这里需要注意的是： condvar_list: Vec<Option<Arc<Condvar>>> 表示的是条件变量资源的列表。而 Condvar 是条件变量的内核数据结构，由等待队列组成。操作系统需要显式地施加某种控制，来确定当一个线程执行wait操作和signal操作时，如何让线程睡眠或唤醒线程。在这里，wait操作是由Condvar的wait方法实现，而signal操作是由Condvar的signal方法实现。

参考文献
--------------------------------------------------------------

- Hansen, Per Brinch (1993). "Monitors and concurrent Pascal: a personal history". HOPL-II: The second ACM SIGPLAN conference on History of programming languages. History of Programming Languages. New York, NY, USA: ACM. pp. 1–35. doi:10.1145/155360.155361. ISBN 0-89791-570-4.
- `Monitor, Wikipedia <https://en.wikipedia.org/wiki/Monitor_(synchronization)>`_
- `Concurrent Pascal, Wikipedia <https://en.wikipedia.org/wiki/Concurrent_Pascal>`_