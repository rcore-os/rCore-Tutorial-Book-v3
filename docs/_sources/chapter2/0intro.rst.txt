引言
================================

本章导读
---------------------------------

..
  chyyuu：有一个ascii图，画出我们做的OS。

  
上一章，我们在 RV64 裸机平台上成功运行起来了 ``Hello, world!`` 。看起来这个过程非常顺利，只需要一条命令就能全部完成。但实际上，在那个
计算机刚刚诞生的年代，很多事情并不像我们想象的那么简单。 当时，程序被记录在打孔的卡片上，使用汇编语言甚至机器语言来编写。而稀缺且昂贵的
计算机由专业的管理员负责操作，就和我们在上一章所做的事情一样，他们手动将卡片输入计算机，等待程序运行结束或者终止程序的运行。最后，他们从
计算机的输出端——也就是打印机中取出程序的输出并交给正在休息室等待的程序提交者。

实际上，这样做是一种对于珍贵的计算资源的浪费。因为当时的计算机和今天的个人计算机不同，它的体积极其庞大，能够占满一整个空调房间，象巨大的史前生物。
管理员在房间的各个地方跑来跑去、或是等待打印机的输出的这些时间段，计算机都并没有在工作。于是，人们希望计算机能够不间断的工作且专注于计算任务本身。

.. _term-batch-system:

**批处理系统** (Batch System) 应运而生。它的核心思想是：将多个程序打包到一起输入计算机。而当一个程序运行结束后，计算机会 *自动* 加载
下一个程序到内存并开始执行。这便是最早的真正意义上的操作系统。

.. _term-privilege:

程序总是难免出现错误。但人们希望一个程序的错误不要影响到操作系统本身，它只需要终止出错的程序，转而运行执行序列中的下一个程序即可。如果后面的
程序都无法运行就太糟糕了。这种 *保护* 操作系统不受有意或无意出错的程序破坏的机制被称为 **特权级** (Privilege) 机制，它实现了用户态和
内核态的隔离，需要软件和硬件的共同努力。


本章主要是设计和实现建立支持**批处理系统**的泥盆纪“邓式鱼”操作系统，从而对可支持运行一批应用程序的执行环境有一个全面和深入的理解。

本章我们的目标让泥盆纪“邓式鱼”操作系统能够感知多个应用程序的存在，并一个接一个地运行这些应用程序，当一个应用程序执行完毕后，会启动下一个应用程序，
直到所有的应用程序都执行完毕。


.. image:: deng-fish.png
   :align: center
   :name: fish-os



实践体验
---------------------------

本章我们的批处理系统将连续运行三个应用程序，放在 ``user/src/bin`` 目录下。

获取本章代码：

.. code-block:: console

   $ git clone https://github.com/rcore-os/rCore-Tutorial-v3.git
   $ cd rCore-Tutorial-v3
   $ git checkout ch2

在 qemu 模拟器上运行本章代码：

.. code-block:: console

   $ cd os
   $ make run

将 Maix 系列开发版连接到 PC，并在上面运行本章代码：

.. code-block:: console

   $ cd os
   $ make run BOARD=k210

如果顺利的话，我们可以看到批处理系统自动加载并运行所有的程序并且正确在程序出错的情况下保护了自身：

.. code-block:: 
   
   [rustsbi] Version 0.1.0
   .______       __    __      _______.___________.  _______..______   __
   |   _  \     |  |  |  |    /       |           | /       ||   _  \ |  |
   |  |_)  |    |  |  |  |   |   (----`---|  |----`|   (----`|  |_)  ||  |
   |      /     |  |  |  |    \   \       |  |      \   \    |   _  < |  |
   |  |\  \----.|  `--'  |.----)   |      |  |  .----)   |   |  |_)  ||  |
   | _| `._____| \______/ |_______/       |__|  |_______/    |______/ |__|

   [rustsbi] Platform: QEMU
   [rustsbi] misa: RV64ACDFIMSU
   [rustsbi] mideleg: 0x222
   [rustsbi] medeleg: 0xb1ab
   [rustsbi] Kernel entry: 0x80020000
   [kernel] Hello, world!
   [kernel] num_app = 3
   [kernel] app_0 [0x8002b028, 0x8002c328)
   [kernel] app_1 [0x8002c328, 0x8002d6c0)
   [kernel] app_2 [0x8002d6c0, 0x8002eb98)
   [kernel] Loading app_0
   Hello, world!
   [kernel] Application exited with code 0
   [kernel] Loading app_1
   Into Test store_fault, we will insert an invalid store operation...
   Kernel should kill this application!
   [kernel] PageFault in application, core dumped.
   [kernel] Loading app_2
   3^10000=5079
   3^20000=8202
   3^30000=8824
   3^40000=5750
   3^50000=3824
   3^60000=8516
   3^70000=2510
   3^80000=9379
   3^90000=2621
   3^100000=2749
   Test power OK!
   [kernel] Application exited with code 0
   [kernel] Panicked at src/batch.rs:61 All applications completed!