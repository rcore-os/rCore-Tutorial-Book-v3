第三章：多道程序与分时多任务系统
==============================================

.. toctree::
   :hidden:
   :maxdepth: 4

   1multi-loader
   2task-switching
   3multiprogramming
   4time-sharing-system

上一章，我们实现了一个简单的批处理系统。首先，它能够自动按照顺序加载并运行序列中的每一个应用，当一个应用运行结束之后无需操作员的手动替换；
另一方面，在硬件提供的特权级机制的帮助下，运行在更高特权级的它不会受到有意或者无意出错的应用的影响，可以全方位监控应用的执行，一旦应用越过了
硬件所设置的界限，就会触发 Trap 并进入到批处理系统中进行处理。无论原因是应用出错或是应用声明自己执行完毕，批处理系统都只需要加载序列中
的下一个应用并进入执行。

可以看到批处理系统的特性是：在内存中同一时间最多只需驻留一个应用。这是因为只有当一个应用出错或退出之后，批处理系统才会去将另一个应用加载到
相同的一块内存区域。而本章所介绍的多道程序和分时多任务系统则是在内存中同一时间可以驻留多个应用。所有的应用都是在系统启动的时候分别加载到
内存的不同区域中。由于目前我们只有一个 CPU，则同一时间最多只有一个应用在执行，剩下的应用则处于就绪状态，需要内核将 CPU 分配给它们才能
开始执行。因此，我们能够看到多个应用在一个 CPU 上交替执行的现象。

.. note::

   读者也许会有疑问：由于只有一个 CPU，即使这样做，同一时间最多还是只能运行一个应用，还浪费了更多的内存来把所有
   的应用都加载进来。那么这样做有什么意义呢？

   读者可以带着这个问题继续看下去。后面我们会介绍这样做到底能够解决什么问题。

.. _term-multiprogramming:
.. _term-time-sharing-multitasking:

**多道程序** (Multiprogramming) 和 **分时多任务系统** (Time-Sharing Multitasking) 对于应用的要求是不同的，因此我们分别为它们
编写了不同的应用，代码也被放在两个不同的分支上。对于它们更加深入的讲解请参考本章正文，我们在引言中仅给出运行代码的方法。

获取多道程序的代码：

.. code-block:: console

   $ git clone https://github.com/rcore-os/rCore-Tutorial-v3.git
   $ cd rCore-Tutorial-v3
   $ git checkout ch3-coop

获取分时多任务系统的代码：

.. code-block:: console

   $ git clone https://github.com/rcore-os/rCore-Tutorial-v3.git
   $ cd rCore-Tutorial-v3
   $ git checkout ch3

在 qemu 模拟器上运行本章代码：

.. code-block:: console

   $ cd os
   $ make run

将 Maix 系列开发版连接到 PC，并在上面运行本章代码：

.. code-block:: console

   $ cd os
   $ make run BOARD=k210

多道程序的应用分别会输出一个不同的字母矩阵。当他们交替执行的时候，以 k210 平台为例，我们将看到字母行的交错输出：

.. code-block::

   [rustsbi] Version 0.1.0
   .______       __    __      _______.___________.  _______..______   __
   |   _  \     |  |  |  |    /       |           | /       ||   _  \ |  |
   |  |_)  |    |  |  |  |   |   (----`---|  |----`|   (----`|  |_)  ||  |
   |      /     |  |  |  |    \   \       |  |      \   \    |   _  < |  |
   |  |\  \----.|  `--'  |.----)   |      |  |  .----)   |   |  |_)  ||  |
   | _| `._____| \______/ |_______/       |__|  |_______/    |______/ |__|

   [rustsbi] Platform: K210
   [rustsbi] misa: RV64ACDFIMSU
   [rustsbi] mideleg: 0x222
   [rustsbi] medeleg: 0x1ab
   [rustsbi] Kernel entry: 0x80020000
   [kernel] Hello, world!
   AAAAAAAAAA [1/5]
   BBBBBBBBBB [1/2]
   CCCCCCCCCC [1/3]
   AAAAAAAAAA [2/5]
   BBBBBBBBBB [2/2]
   CCCCCCCCCC [2/3]
   AAAAAAAAAA [3/5]
   Test write_b OK!
   [kernel] Application exited with code 0
   CCCCCCCCCC [3/3]
   AAAAAAAAAA [4/5]
   Test write_c OK!
   [kernel] Application exited with code 0
   AAAAAAAAAA [5/5]
   Test write_a OK!
   [kernel] Application exited with code 0
   [kernel] Panicked at src/task/mod.rs:97 All applications completed!
   [rustsbi] reset triggered! todo: shutdown all harts on k210; program halt

分时多任务系统应用分为两种。编号为 00/01/02 的应用分别会计算质数 3/5/7 的幂次对一个大质数取模的余数，并会将结果阶段性输出。编号为 03 的
应用则会等待三秒钟之后再退出。以 k210 平台为例，我们将会看到 00/01/02 三个应用分段完成它们的计算任务，而应用 03 由于等待时间过长总是
最后一个结束执行。

.. code-block::

   [rustsbi] Version 0.1.0
   .______       __    __      _______.___________.  _______..______   __
   |   _  \     |  |  |  |    /       |           | /       ||   _  \ |  |
   |  |_)  |    |  |  |  |   |   (----`---|  |----`|   (----`|  |_)  ||  |
   |      /     |  |  |  |    \   \       |  |      \   \    |   _  < |  |
   |  |\  \----.|  `--'  |.----)   |      |  |  .----)   |   |  |_)  ||  |
   | _| `._____| \______/ |_______/       |__|  |_______/    |______/ |__|

   [rustsbi] Platform: K210
   [rustsbi] misa: RV64ACDFIMSU
   [rustsbi] mideleg: 0x222
   [rustsbi] medeleg: 0x1ab
   [rustsbi] Kernel entry: 0x80020000
   [kernel] Hello, world!
   power_3 [10000/200000]
   power_3 [20000/200000]
   power_3 [30000/200000power_5 [10000/140000]
   power_5 [20000/140000]
   power_5 [30000/140000power_7 [10000/160000]
   power_7 [20000/160000]
   power_7 [30000/160000]
   ]
   power_3 [40000/200000]
   power_3 [50000/200000]
   power_3 [60000/200000]
   power_5 [40000/140000]
   power_5 [50000/140000]
   power_5 [60000/140000power_7 [40000/160000]
   power_7 [50000/160000]
   power_7 [60000/160000]
   ]
   power_3 [70000/200000]
   power_3 [80000/200000]
   power_3 [90000/200000]
   power_5 [70000/140000]
   power_5 [80000/140000]
   power_5 [90000/140000power_7 [70000/160000]
   power_7 [80000/160000]
   power_7 [90000/160000]
   ]
   power_3 [100000/200000]
   power_3 [110000/200000]
   power_3 [120000/]
   power_5 [100000/140000]
   power_5 [110000/140000]
   power_5 [120000/power_7 [100000/160000]
   power_7 [110000/160000]
   power_7 [120000/160000200000]
   power_3 [130000/200000]
   power_3 [140000/200000]
   power_3 [150000140000]
   power_5 [130000/140000]
   power_5 [140000/140000]
   5^140000 = 386471875]
   power_7 [130000/160000]
   power_7 [140000/160000]
   power_7 [150000/160000/200000]
   power_3 [160000/200000]
   power_3 [170000/200000]
   power_3 [
   Test power_5 OK!
   [kernel] Application exited with code 0
   ]
   power_7 [160000/160000]
   7180000/200000]
   power_3 [190000/200000]
   power_3 [200000/200000]
   3^200000 = 871008973^160000 = 667897727
   Test power_7 OK!
   [kernel] Application exited with code 0

   Test power_3 OK!
   [kernel] Application exited with code 0
   Test sleep OK!
   [kernel] Application exited with code 0
   [kernel] Panicked at src/task/mod.rs:97 All applications completed!
   [rustsbi] reset triggered! todo: shutdown all harts on k210; program halt

输出结果看上去有一些混乱，原因是用户程序的每个 ``println!`` 往往会被拆分成多个 ``sys_write`` 系统调用提交给内核。有兴趣的同学可以参考 
``println!`` 宏的实现。

另外需要说明的是一点是：与上一章不同，应用的编号不再决定其被加载运行的先后顺序，而仅仅能够改变应用被加载到内存中的位置。