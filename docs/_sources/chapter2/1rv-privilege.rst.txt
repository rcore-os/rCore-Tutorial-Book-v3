RISC-V 特权级架构
=====================================

.. toctree::
   :hidden:
   :maxdepth: 5

为了保护我们的批处理系统不受到出错应用程序的影响并全程稳定工作，单凭软件实现是很难做到的，而是需要 CPU 提供一种特权级隔离机制，使得它在执行
应用程序和内核代码的时候处于不同的特权级。特权级可以看成 CPU 随时间变化而处于的不同的工作模式。

RISC-V 架构中一共定义了 4 种特权级：

.. list-table:: RISC-V 特权级
   :widths: 30 30 60
   :header-rows: 1
   :align: center

   * - 级别
     - 编码
     - 名称
   * - 0
     - 00
     - 机器模式 (M, Machine)
   * - 1
     - 01
     - 监督模式 (S, Supervisor)
   * - 2
     - 10
     - H, Hypervisor
   * - 3
     - 11
     - 用户/应用模式 (U, User/Application)

其中，级别的数值越小，特权级越高，掌控硬件的能力越强。从表中可以看出， M 模式处在最高的特权级，而 U 模式处于最低的特权级。

之前我们给出过支持应用程序运行的一套 :ref:`执行环境栈 <app-software-stack>` ，现在我们站在特权级架构的角度去重新看待它：

.. image:: PrivilegeStack.png
   :align: center
   :name: PrivilegeStack

和之前一样，白色块表示一层执行环境，黑色块表示相邻两层执行环境之间的接口。这张图片给出了能够支持运行 Unix 这类复杂系统的软件栈。其中
内核代码运行在 S 模式上；应用程序运行在 U 模式上。运行在 M 模式上的软件被称为 **监督模式执行环境** (SEE, Supervisor Execution Environment)
，这是站在运行在 S 模式上的软件的视角来看，它的下面也需要一层执行环境支撑，因此被命名为 SEE，它需要在相比 S 模式更高的特权级下运行，
一般情况下在 M 模式上运行。

之前我们提到过，执行环境的其中一种功能是在执行它支持的上层软件之前进行一些初始化工作。我们之前提到的引导加载程序会在加电后对整个系统进行
初始化，它实际上是 SEE 功能的一部分，也就是说在 RISC-V 架构上引导加载程序一般运行在 M 模式上。此外，编程语言的标准库也会在执行程序员
编写的逻辑之前进行一些初始化工作，但是在这张图中我们并没有将其展开，而是统一归类到 U 模式软件，也就是应用程序中。

执行环境的另一种功能是对上层软件的执行进行监控管理。监控管理可以理解为，当上层软件执行的时候出现了一些情况导致需要用到执行环境中提供的功能，
因此需要暂停上层软件的执行，转而运行执行环境的代码。由于上层软件和执行环境被设计为运行在不同的特权级，这个过程也往往（而 **不一定** ）
伴随着 CPU 的 **特权级切换** 。当执行环境的代码运行结束后，我们需要回到上层软件暂停的位置继续执行。在 RISC-V 架构中，这种与常规控制流
（顺序、循环、分支、函数调用）不同的 **异常控制流** (ECF, Exception Control Flow) 被称为 **陷入** (Trap) 。

触发 Trap 的原因总体上可以分为两种： **中断** (Interrupt) 和 **异常** (Exception) 。本章我们只会用到异常，因此暂且略过中断。异常
就是指上层软件需要执行环境功能的原因确切的与上层软件的 **某一条指令的执行** 相关。下表中我们给出了 RISC-V 特权级定义的一些异常：

.. list-table:: RISC-V 异常一览表
   :align: center
   :header-rows: 1
   :widths: 30 30 60

   * - Interrupt
     - Exception Code
     - Description
   * - 0
     - 0
     - Instruction address misaligned
   * - 0
     - 1
     - Instruction access fault
   * - 0
     - 2
     - Illegal instruction
   * - 0
     - 3
     - Breakpoint
   * - 0
     - 4
     - Load address misaligned
   * - 0
     - 5
     - Load access fault
   * - 0
     - 6
     - Store/AMO address misaligned
   * - 0
     - 7
     - Store/AMO access fault
   * - 0
     - 8
     - Environment call from U-mode
   * - 0
     - 9
     - Environment call from S-mode
   * - 0
     - 11
     - Environment call from M-mode
   * - 0
     - 12
     - Instruction page fault
   * - 0
     - 13
     - Load page fault
   * - 0
     - 14
     - Store/AMO page fault

其中断点异常 (Breakpoint) 和执行环境调用 (Environment call) 两个异常是通过在上层软件中执行一条特定的指令触发的：当执行 ``ebreak`` 
这条指令的之后就会触发断点异常；而执行 ``ecall`` 这条指令的时候则会随着 CPU 当前所处特权级而触发不同的异常。从表中可以看出，当 CPU 分别
处于 M/S/U 三种特权级时执行 ``ecall`` 这条指令会触发三种异常。

在这里我们需要说明一下执行环境调用，这是一种很特殊的异常， :ref:`上图 <PrivilegeStack>` 中相邻两特权级软件之间的接口正是基于这种异常
机制实现的。M 模式软件 SEE 和 S 模式的内核之间的接口被称为 **监督模式二进制接口** (SBI, Supervisor Binary Interface)，而内核和 
U 模式的应用程序之间的接口被称为 **应用程序二进制接口** (Application Binary Interface)，当然它有一个更加通俗的名字—— **系统调用** 
(syscall, System Call) 。而之所以叫做二进制接口，是因为它和在同一种编程语言内部调用接口不同，是汇编指令级的一种接口。事实上 M/S/U 
三个特权级的软件可能分别由不同的编程语言实现，即使是用同一种编程语言实现的，其调用也并不是普通的函数调用执行流，而是陷入，在该过程中有可能
切换 CPU 特权级。因此只有将接口下降到汇编指令级才能够满足其通用性。可以看到，在这样的架构之下，每层特权级的软件都只能做高特权级软件允许
它做的、且对于高特权级软件不会产生什么撼动的事情，一旦超出了能力范围，就必须寻求高特权级软件的帮助。因此，在一条执行流中我们经常能够看到
特权级切换。

.. 
随着特权级的逐渐降低，硬件的能力受到限制，
从每一个特权级看来，比它特权级更低的部分都可以看成是它的应用。（这个好像没啥用？）
M 模式是每个 RISC-V CPU 都需要实现的模式，而剩下的模式都是可选的。常见的模式组合：普通嵌入式应用只需要在 M 模式上运行；追求安全的
嵌入式应用需要在 M/U 模式上运行；像 Unix 这样比较复杂的系统这需要 M/S/U 三种模式。
RISC-V 特权级规范中给出了一些特权寄存器和特权指令...
重要的是保护，也就是特权级的切换。当 CPU 处于低特权级的时候，如果发生了错误或者一些需要处理的情况，CPU 会切换到高特权级进行处理。这个
就是所谓的 Trap 机制。
RISC-V 架构规范分为两部分： `RISC-V 无特权级规范 <https://github.com/riscv/riscv-isa-manual/releases/download/Ratified-IMAFDQC/riscv-spec-20191213.pdf>`_ 
和 `RISC-V 特权级规范 <https://github.com/riscv/riscv-isa-manual/releases/download/Ratified-IMFDQC-and-Priv-v1.11/riscv-privileged-20190608.pdf>`_ 。
RISC-V 无特权级规范中给出的指令和寄存器无论在 CPU 处于哪个特权级下都可以使用。
