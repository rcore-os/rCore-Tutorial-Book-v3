术语中英文对照表
=========================

.. toctree::
   :hidden:
   :maxdepth: 4

第一章
----------------------------------

.. list-table:: 
   :align: center
   :header-rows: 1
   :widths: 40 60 30

   * - 中文
     - 英文
     - 出现章节
   * - 执行环境
     - Execution Environment
     - :ref:`应用程序运行环境与平台支持 <term-execution-environment>`
   * - 系统调用
     - System Call
     - :ref:`应用程序运行环境与平台支持 <term-system-call>`
   * - 指令集体系结构
     - ISA, Instruction Set Architecture
     - :ref:`应用程序运行环境与平台支持 <term-isa>`
   * - 抽象
     - Abstraction
     - :ref:`应用程序运行环境与平台支持 <term-abstraction>`
   * - 平台
     - Platform
     - :ref:`应用程序运行环境与平台支持 <term-platform>`
   * - 目标三元组
     - Target Triplet
     - :ref:`应用程序运行环境与平台支持 <term-target-triplet>`
   * - 裸机平台
     - bare-metal
     - :ref:`应用程序运行环境与平台支持 <term-bare-metal>`
   * - 交叉编译
     - Cross Compile
     - :ref:`移除标准库依赖 <term-cross-compile>`
   * - 物理地址
     - Physical Address
     - :ref:`重建最小化运行时 <term-physical-address>`
   * - 物理内存
     - Physical Memory
     - :ref:`重建最小化运行时 <term-physical-memory>`
   * - 引导加载程序
     - Bootloader
     - :ref:`重建最小化运行时 <term-bootloader>`
   * - 控制流
     - Control Flow
     - :ref:`重建最小化运行时 <term-control-flow>`
   * - 函数调用
     - Function Call
     - :ref:`重建最小化运行时 <term-function-call>`
   * - 源寄存器
     - Source Register
     - :ref:`重建最小化运行时 <term-source-register>`
   * - 立即数
     - Immediate
     - :ref:`重建最小化运行时 <term-immediate>`
   * - 目标寄存器
     - Destination Register
     - :ref:`重建最小化运行时 <term-destination-register>`
   * - 伪指令
     - Pseudo Instruction
     - :ref:`重建最小化运行时 <term-pseudo-instruction>`
   * - 上下文
     - Context
     - :ref:`重建最小化运行时 <term-context>`
   * - 活动记录
     - Activation Record
     - :ref:`重建最小化运行时 <term-activation-record>`
   * - 保存/恢复
     - Save/Restore
     - :ref:`重建最小化运行时 <term-save-restore>`
   * - 被调用者保存
     - Callee-Saved
     - :ref:`重建最小化运行时 <term-callee-saved>`
   * - 调用者保存
     - Caller-Saved
     - :ref:`重建最小化运行时 <term-caller-saved>`
   * - 开场白
     - Prologue
     - :ref:`重建最小化运行时 <term-prologue>`
   * - 收场白
     - Epilogue
     - :ref:`重建最小化运行时 <term-epilogue>`
   * - 调用规范
     - Calling Convention
     - :ref:`重建最小化运行时 <term-calling-convention>`
   * - 栈/栈指针/栈帧
     - Stack/Stack Pointer/Stackframe
     - :ref:`重建最小化运行时 <term-stack>`
   * - 后入先出
     - LIFO, Last In First Out
     - :ref:`重建最小化运行时 <term-lifo>`
   * - 段
     - Section
     - :ref:`重建最小化运行时 <term-section>`
   * - 内存布局
     - Memory Layout
     - :ref:`重建最小化运行时 <term-memory-layout>`
   * - 堆
     - Heap
     - :ref:`重建最小化运行时 <term-heap>`
   * - 编译器
     - Compiler
     - :ref:`重建最小化运行时 <term-compiler>`
   * - 汇编器
     - Assembler
     - :ref:`重建最小化运行时 <term-assembler>`
   * - 链接器
     - Linker
     - :ref:`重建最小化运行时 <term-linker>`
   * - 目标文件
     - Object File
     - :ref:`重建最小化运行时 <term-object-file>`
   * - 链接脚本
     - Linker Script
     - :ref:`重建最小化运行时 <term-linker-script>`
   * - 可执行和链接格式
     - ELF, Executable and Linkable Format
     - :ref:`手动加载、运行应用程序 <term-elf>`
   * - 元数据
     - Metadata
     - :ref:`手动加载、运行应用程序 <term-metadata>`
   * - 魔数
     - Magic
     - :ref:`手动加载、运行应用程序 <term-magic>`
   * - 裸指针
     - Raw Pointer
     - :ref:`手动加载、运行应用程序 <term-raw-pointer>`
   * - 解引用
     - Dereference
     - :ref:`手动加载、运行应用程序 <term-dereference>`

第二章
-------------------------

.. list-table:: 
   :align: center
   :header-rows: 1
   :widths: 40 60 30

   * - 中文
     - 英文
     - 出现章节
   * - 批处理系统
     - Batch System
     - :ref:`引言 <term-batch-system>`
   * - 特权级
     - Privilege
     - :ref:`引言 <term-privilege>`
   * - 监督模式执行环境
     - SEE, Supervisor Execution Environment
     - :ref:`RISC-V 特权级架构 <term-see>`
   * - 异常控制流
     - ECF, Exception Control Flow
     - :ref:`RISC-V 特权级架构 <term-ecf>`
   * - 陷入
     - Trap
     - :ref:`RISC-V 特权级架构 <term-trap>`
   * - 中断
     - Interrupt
     - :ref:`RISC-V 特权级架构 <term-interrupt>`
   * - 异常
     - Exception
     - :ref:`RISC-V 特权级架构 <term-exception>`
   * - 监督模式二进制接口
     - SBI, Supervisor Binary Interface
     - :ref:`RISC-V 特权级架构 <term-sbi>`
   * - 应用程序二进制接口
     - ABI, Application Binary Interface
     - :ref:`RISC-V 特权级架构 <term-abi>`
   * - 控制状态寄存器
     - CSR, Control and Status Register
     - :ref:`RISC-V 特权级架构 <term-csr>`
   * - 胖指针
     - Fat Pointer
     - :ref:`实现应用程序 <term-fat-pointer>`
   * - 指令缓存
     - i-cache, Instruction Cache
     - :ref:`实现批处理系统 <term-icache>`
   * - 数据缓存
     - d-cache, Data Cache
     - :ref:`实现批处理系统 <term-dcache>`
   * - 执行流
     - Execution of Thread
     - :ref:`处理 Trap <term-execution-of-thread>`
   * - 原子指令
     - Atomic Instruction
     - :ref:`处理 Trap <term-atomic-instruction>`
   
第三章
-------------------------

.. list-table:: 
   :align: center
   :header-rows: 1
   :widths: 40 60 30

   * - 中文
     - 英文
     - 出现章节
   * - 多道程序
     - Multiprogramming
     - :ref:`引言 <term-multiprogramming>`   
   * - 分时多任务系统
     - Time-Sharing Multitasking
     - :ref:`引言 <term-time-sharing-multitasking>`
   * - 任务上下文
     - Task Context
     - :ref:`任务切换 <term-task-context>`
   * - 输入/输出
     - I/O, Input/Output
     - :ref:`多道程序与协作式调度 <term-input-output>`
   * - 任务控制块
     - Task Control Block
     - :ref:`多道程序与协作式调度 <term-task-control-block>`