引言
================================

本章导读
---------------------------------

..
  chyyuu：有一个ascii图，画出我们做的OS。

本章展现了操作系统一系列功能：

- 通过批处理支持多个程序的自动加载和运行
- 操作系统利用硬件特权级机制，实现对操作系统自身的保护

上一章，我们在 RV64 裸机平台上成功运行起来了 ``Hello, world!`` 。看起来这个过程非常顺利，只需要一条命令就能全部完成。但实际上，在那个计算机刚刚诞生的年代，很多事情并不像我们想象的那么简单。 当时，程序被记录在打孔的卡片上，使用汇编语言甚至机器语言来编写。而稀缺且昂贵的计算机由专业的管理员负责操作，就和我们在上一章所做的事情一样，他们手动将卡片输入计算机，等待程序运行结束或者终止程序的运行。最后，他们从计算机的输出端——也就是打印机中取出程序的输出并交给正在休息室等待的程序提交者。

实际上，这样做是一种对于珍贵的计算资源的浪费。因为当时的计算机和今天的个人计算机不同，它的体积极其庞大，能够占满一整个空调房间，像巨大的史前生物。管理员在房间的各个地方跑来跑去、或是等待打印机的输出的这些时间段，计算机都并没有在工作。于是，人们希望计算机能够不间断的工作且专注于计算任务本身。

.. _term-batch-system:

**批处理系统** (Batch System) 应运而生。它的核心思想是：将多个程序打包到一起输入计算机。而当一个程序运行结束后，计算机会 *自动* 加载下一个程序到内存并开始执行。这便是最早的真正意义上的操作系统。

.. _term-privilege:

应用程序总是难免会出现错误，如果一个程序的执行错误导致其它程序都无法运行就太糟糕了。人们希望一个应用程序的错误不要影响到操作系统和整个计算机系统。这就需要操作系统能够终止出错的应用程序，转而运行下一个应用程序。这种 *保护* 操作系统不受有意或无意出错的程序破坏的机制被称为 **特权级** (Privilege) 机制，它实现了用户态和内核态的隔离，这需要软件和硬件的共同努力。


本章主要是设计和实现建立支持批处理系统的泥盆纪“邓式鱼” [#dunk]_ 操作系统，从而对可支持运行一批应用程序的执行环境有一个全面和深入的理解。

本章我们的目标让泥盆纪“邓式鱼”操作系统能够感知多个应用程序的存在，并一个接一个地运行这些应用程序，当一个应用程序执行完毕后，会启动下一个应用程序，直到所有的应用程序都执行完毕。

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

将 Maix 系列开发板连接到 PC，并在上面运行本章代码：

.. code-block:: console

   $ cd os
   $ make run BOARD=k210

如果顺利的话，我们可以看到批处理系统自动加载并运行所有的程序并且正确在程序出错的情况下保护了自身：

.. code-block:: 

   [rustsbi] RustSBI version 0.1.1
   <rustsbi-logo>
   [rustsbi] Platform: QEMU (Version 0.1.0)
   [rustsbi] misa: RV64ACDFIMSU
   [rustsbi] mideleg: 0x222
   [rustsbi] medeleg: 0xb1ab
   [rustsbi-dtb] Hart count: cluster0 with 1 cores
   [rustsbi] Kernel entry: 0x80200000
   [kernel] Hello, world!
   [kernel] num_app = 3
   [kernel] app_0 [0x8020b028, 0x8020c048)
   [kernel] app_1 [0x8020c048, 0x8020d100)
   [kernel] app_2 [0x8020d100, 0x8020e4b8)
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

本章代码树
-------------------------------------------------

.. code-block::

   ./os/src
   Rust        10 Files   311 Lines
   Assembly     2 Files    58 Lines

   ├── bootloader
   │   ├── rustsbi-k210.bin
   │   └── rustsbi-qemu.bin
   ├── LICENSE
   ├── os
   │   ├── build.rs(新增：生成 link_app.S 将应用作为一个数据段链接到内核)
   │   ├── Cargo.toml
   │   ├── Makefile(修改：构建内核之前先构建应用)
   │   └── src
   │       ├── batch.rs(新增：实现了一个简单的批处理系统)
   │       ├── console.rs
   │       ├── entry.asm
   │       ├── lang_items.rs
   │       ├── link_app.S(构建产物，由 os/build.rs 输出)
   │       ├── linker-k210.ld
   │       ├── linker-qemu.ld
   │       ├── main.rs(修改：主函数中需要初始化 Trap 处理并加载和执行应用)
   │       ├── sbi.rs
   │       ├── syscall(新增：系统调用子模块 syscall)
   │       │   ├── fs.rs(包含文件 I/O 相关的 syscall)
   │       │   ├── mod.rs(提供 syscall 方法根据 syscall ID 进行分发处理)
   │       │   └── process.rs(包含任务处理相关的 syscall)
   │       └── trap(新增：Trap 相关子模块 trap)
   │           ├── context.rs(包含 Trap 上下文 TrapContext)
   │           ├── mod.rs(包含 Trap 处理入口 trap_handler)
   │           └── trap.S(包含 Trap 上下文保存与恢复的汇编代码)
   ├── README.md
   ├── rust-toolchain
   ├── tools
   │   ├── kflash.py
   │   ├── LICENSE
   │   ├── package.json
   │   ├── README.rst
   │   └── setup.py
   └── user(新增：应用测例保存在 user 目录下)
      ├── Cargo.toml
      ├── Makefile
      └── src
         ├── bin(基于用户库 user_lib 开发的应用，每个应用放在一个源文件中)
         │   ├── 00hello_world.rs
         │   ├── 01store_fault.rs
         │   └── 02power.rs
         ├── console.rs
         ├── lang_items.rs
         ├── lib.rs(用户库 user_lib)
         ├── linker.ld(应用的链接脚本)
         └── syscall.rs(包含 syscall 方法生成实际用于系统调用的汇编指令，
                        各个具体的 syscall 都是通过 syscall 来实现的)


本章代码导读
-----------------------------------------------------

相比于上一章的两个简单操作系统，本章的操作系统有两个最大的不同之处，一个是操作系统自身运行在内核态，且支持应用程序在用户态运行，且能完成应用程序发出的系统调用；另一个是能够一个接一个地自动运行不同的应用程序。所以，我们需要对操作系统和应用程序进行修改，也需要对应用程序的编译生成过程进行修改。

首先改进应用程序，让它能够在用户态执行，并能发出系统调用。这其实就是上一章中  :ref:`构建用户态执行环境 <term-print-userminienv>` 小节介绍内容的进一步改进。具体而言，编写多个应用小程序，修改编译应用所需的 ``linker.ld`` 文件来   :ref:`调整程序的内存布局  <term-app-mem-layout>` ，让操作系统能够把应用加载到指定内存地址，然后顺利启动并运行应用程序。

应用程序运行中，操作系统要支持应用程序的输出功能，并还能支持应用程序退出。这需要完成 ``sys_write`` 和 ``sys_exit`` 系统调用访问请求的实现。 具体实现涉及到内联汇编的编写，以及应用与操作系统内核之间系统调用的参数传递的约定。为了让应用在还没实现操作系统之前就能进行运行测试，我们采用了Linux on RISC-V64 的系统调用参数约定。具体实现可参看 :ref:`系统调用 <term-call-syscall>` 小节中的内容。 这样写完应用小例子后，就可以通过  ``qemu-riscv64`` 模拟器进行测试了。  

写完应用程序后，还需实现支持多个应用程序轮流启动运行的操作系统。这里首先能把本来相对松散的应用程序执行代码和操作系统执行代码连接在一起，便于   ``qemu-system-riscv64`` 模拟器一次性地加载二者到内存中，并让操作系统能够找到应用程序的位置。为把二者连在一起，需要对生成的应用程序进行改造，首先是把应用程序执行文件从ELF执行文件格式变成Binary格式（通过 ``rust-objcopy`` 可以轻松完成）；然后这些Binary格式的文件通过编译器辅助脚本 ``os/build.rs`` 转变变成 ``os/src/link_app.S`` 这个汇编文件的一部分，并生成各个Binary应用的辅助信息，便于操作系统能够找到应用的位置。编译器会把把操作系统的源码和 ``os/src/link_app.S`` 合在一起，编译出操作系统+Binary应用的ELF执行文件，并进一步转变成Binary格式。

操作系统本身需要完成对Binary应用的位置查找，找到后（通过 ``os/src/link_app.S`` 中的变量和标号信息完成），会把Binary应用拷贝到 ``user/src/linker.ld`` 指定的物理内存位置（OS的加载应用功能）。在一个应执行完毕后，还能加载另外一个应用，这主要是通过 ``AppManagerInner`` 数据结构和对应的函数 ``load_app`` 和 ``run_next_app`` 等来完成对应用的一系列管理功能。这主要在 :ref:`实现批处理操作系统  <term-batchos>` 小节中讲解。

为了让Binary应用能够启动和运行，操作系统还需给Binary应用分配好执行环境所需一系列的资源。这主要包括设置好用户栈和内核栈（在用户态的应用程序与在内核态的操作系统内核需要有各自的栈，避免应用程序破坏内核的执行），实现Trap 上下文的保存与恢复（让应用能够在发出系统调用到内核态后，还能回到用户态继续执行），完成Trap 分发与处理等工作。由于系统调用和中断处理等内核代码实现涉及用户态与内核态之间的特权级切换细节的汇编代码，与硬件细节联系紧密，所以 :ref:`这部分内容 <term-trap-handle>` 是本章中理解比较困难的地方。如果要了解清楚，需要对涉及到的RISC-V CSR寄存器的功能有清楚的认识。这就需要看看 `RISC-V手册 <http://crva.ict.ac.cn/documents/RISC-V-Reader-Chinese-v2p1.pdf>`_ 的第十章或更加详细的RISC-V的特权级规范文档了。有了上面的实现后，就剩下最后一步，实现 **执行应用程序** 的操作系统功能，其主要实现在 ``run_next_app`` 内核函数中 。完成所有这些功能的实现，“邓式鱼” [#dunk]_ 操作系统就可以正常运行，并能管理多个应用按批处理方式在用户态一个接一个地执行了。


.. [#dunk] 邓氏鱼是一种晚泥盆纪（距今约3.82亿至3.59亿年前）的盾皮鱼，其中最大种类体长可达8.79米，重量可达4吨，是当时最大的海洋掠食者，但巨大而沉重的身躯极大地影响了它的运动速度和灵敏度。