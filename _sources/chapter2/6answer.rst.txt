练习参考答案
=====================================================

.. toctree::
   :hidden:
   :maxdepth: 4


课后练习
-------------------------------

编程题
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
1. `***` 实现一个裸机应用程序A，能打印调用栈。

   以 rCore tutorial ch2 代码为例，在编译选项中我们已经让编译器对所有函数调用都保存栈指针（参考 ``os/.cargo/config`` ），因此我们可以直接从 `fp` 寄存器追溯调用栈：

   .. code-block:: rust
      :caption: ``os/src/stack_trace.rs``

      use core::{arch::asm, ptr};

      pub unsafe fn print_stack_trace() -> () {
          let mut fp: *const usize;
          asm!("mv {}, fp", out(reg) fp);

          println!("== Begin stack trace ==");
          while fp != ptr::null() {
              let saved_ra = *fp.sub(1);
              let saved_fp = *fp.sub(2);

              println!("0x{:016x}, fp = 0x{:016x}", saved_ra, saved_fp);

              fp = saved_fp as *const usize;
          }
          println!("== End stack trace ==");
      }

   之后我们将其加入 ``main.rs`` 作为一个子模块：

   .. code-block:: rust
      :caption: 加入 ``os/src/main.rs``
      :emphasize-lines: 4

      // ...
      mod syscall;
      mod trap;
      mod stack_trace;
      // ...

   作为一个示例，我们可以将打印调用栈的代码加入 panic handler 中，在每次 panic 的时候打印调用栈：

   .. code-block:: rust
      :caption: ``os/lang_items.rs``
      :emphasize-lines: 3,9

      use crate::sbi::shutdown;
      use core::panic::PanicInfo;
      use crate::stack_trace::print_stack_trace;

      #[panic_handler]
      fn panic(info: &PanicInfo) -> ! {
          // ...

          unsafe { print_stack_trace(); }

          shutdown()
      }

   现在，panic 的时候输入的信息变成了这样：

   .. code-block::

      Panicked at src/batch.rs:68 All applications completed!
      == Begin stack trace ==
      0x0000000080200e12, fp = 0x0000000080205cf0
      0x0000000080201bfa, fp = 0x0000000080205dd0
      0x0000000080200308, fp = 0x0000000080205e00
      0x0000000080201228, fp = 0x0000000080205e60
      0x00000000802005b4, fp = 0x0000000080205ef0
      0x0000000080200424, fp = 0x0000000000000000
      == End stack trace ==

   这里打印的两个数字，第一个是栈帧上保存的返回地址，第二个是保存的上一个 frame pointer。


2. `**` 扩展内核，实现新系统调用get_taskinfo，能显示当前task的id和task name；实现一个裸机应用程序B，能访问get_taskinfo系统调用。
3. `**` 扩展内核，能够统计多个应用的执行过程中系统调用编号和访问此系统调用的次数。
4. `**` 扩展内核，能够统计每个应用执行后的完成时间。
5. `***` 扩展内核，统计执行异常的程序的异常情况（主要是各种特权级涉及的异常），能够打印异常程序的出错的地址和指令等信息。
   
   在trap.c中添加相关异常情况的处理：

   .. code-block:: c
      :caption: ``os/trap.c``

      void usertrap()
      {        
         set_kerneltrap();
         struct trapframe *trapframe = curr_proc()->trapframe;

         if ((r_sstatus() & SSTATUS_SPP) != 0)
                  panic("usertrap: not from user mode");

         uint64 cause = r_scause();
         if (cause & (1ULL << 63)) {
                  cause &= ~(1ULL << 63);
                  switch (cause) {
                  case SupervisorTimer:
                        tracef("time interrupt!\n");
                        set_next_timer();
                        yield();
                        break;
                  default:
                        unknown_trap();
                        break;
                  }
         } else {
                  switch (cause) {
                  case UserEnvCall:
                        trapframe->epc += 4;
                        syscall();
                        break;
                  case StoreMisaligned:
                  case StorePageFault:
                  case InstructionMisaligned:
                  case InstructionPageFault:
                  case LoadMisaligned:
                  case LoadPageFault:
                        printf("%d in application, bad addr = %p, bad instruction = %p, "
                                 "core dumped.\n",
                                 cause, r_stval(), trapframe->epc);
                        exit(-2);
                        break;
                  case IllegalInstruction:
                        printf("IllegalInstruction in application, core dumped.\n");
                        exit(-3);
                        break;
                  default:
                        unknown_trap();
                        break;
                  }
         }
         usertrapret();
      }


注：上述编程基于 rcore/ucore tutorial v3: Branch ch2

问答题
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

1. `*` 函数调用与系统调用有何区别？

   * 函数调用用普通的控制流指令，不涉及特权级的切换；系统调用使用专门的指令（如 RISC-V 上的 `ecall`），会切换到内核特权级。
   * 函数调用可以随意指定调用目标；系统调用只能将控制流切换给调用操作系统内核给定的目标。

2. `**` 为了方便操作系统处理，Ｍ态软件会将 S 态异常/中断委托给 S 态软件，请指出有哪些寄存器记录了委托信息，rustsbi 委托了哪些异常/中断？（也可以直接给出寄存器的值）

   * 两个寄存器记录了委托信息： ``mideleg`` （中断委托）和 ``medeleg`` （异常委托）

   * 参考 RustSBI 输出

     .. code-block::

        [rustsbi] mideleg: ssoft, stimer, sext (0x222)
        [rustsbi] medeleg: ima, ia, bkpt, la, sa, uecall, ipage, lpage, spage (0xb1ab)

     可知委托了中断：

     * ``ssoft`` : S-mode 软件中断
     * ``stimer`` : S-mode 时钟中断
     * ``sext`` : S-mode 外部中断

     委托了异常：

     * ``ima`` : 指令未对齐
     * ``ia`` : 取指访问异常
     * ``bkpt`` : 断点
     * ``la`` : 读异常
     * ``sa`` : 写异常
     * ``uecall`` : U-mode 系统调用
     * ``ipage`` : 取指 page fault
     * ``lpage`` : 读 page fault
     * ``spage`` : 写 page fault

3. `**` 如果操作系统以应用程序库的形式存在，应用程序可以通过哪些方式破坏操作系统？

   如果操作系统以应用程序库的形式存在，那么编译器在链接OS库时会把应用程序跟OS库链接成一个可执行文件，两者处于同一地址空间，这也是LibOS（Unikernel）架构，此时存在如下几个破坏操作系统的方式：
   
   * 缓冲区溢出：应用程序可以覆盖写其合法内存边界之外的部分，这可能会危及 OS；
   * 整数溢出：当对整数值的运算产生的值超出整数数据类型可以表示的范围时，就会发生整数溢出， 这可能会导致OS出现意外行为和安全漏洞。 例如，如果允许应用程序分配大量内存，攻击者可能会在内存分配例程中触发整数溢出，从而可能导致缓冲区溢出或其他安全漏洞；
   * 系统调用拦截：应用程序可能会拦截或重定向系统调用，从而可能损害OS的行为。例如，攻击者可能会拦截读取敏感文件的系统调用并将其重定向到他们选择的文件，从而可能危及 unikernel 的安全性。
   * 资源耗尽：应用程序可能会消耗内存或网络带宽等资源，可能导致拒绝服务或其他安全漏洞。

4. `**` 编译器/操作系统/处理器如何合作，可采用哪些方法来保护操作系统不受应用程序的破坏？

   硬件操作系统运行在一个硬件保护的安全执行环境中，不受到应用程序的破坏；应用程序运行在另外一个无法破坏操作系统的受限执行环境中。
   现代CPU提供了很多硬件机制来保护操作系统免受恶意应用程序的破坏，包括如下几个：

   * 特权级模式：处理器能够设置不同安全等级的执行环境，即用户态执行环境和内核态特权级的执行环境。处理器在执行指令前会进行特权级安全检查，如果在用户态执行环境中执行内核态特权级指令，会产生异常阻止当前非法指令的执行。
   * TEE（可信执行环境）：CPU的TEE能够构建一个可信的执行环境，用于抵御恶意软件或攻击，能够确保处理敏感数据的应用程序（例如移动银行和支付应用程序）的安全。 
   * ASLR（地址空间布局随机化）：ASLR 是CPU的一种随机化进程地址空间布局的安全功能，其能够随机生成进程地址空间，例如栈、共享库等关键部分的起始地址，使攻击者预测特定数据或代码的位置。
5. `**` RISC-V处理器的S态特权指令有哪些，其大致含义是什么，有啥作用？

   RISC-V处理器的S态特权指令有两类：指令本身属于高特权级的指令，如 sret 指令（表示从 S 模式返回到 U 模式）。指令访问了S模式特权级下才能访问的寄存器或内存，如表示S模式系统状态的 控制状态寄存器 sstatus 等。如下所示：

   * sret：从 S 模式返回 U 模式。如可以让位于S模式的驱动程序返回U模式。
   * wfi：让CPU在空闲时进入等待状态，以降低CPU功耗。
   * sfence.vma：刷新 TLB 缓存，在U模式下执行会尝试非法指令异常。
   * 访问 S 模式 CSR 的指令：通过访问spce/stvec/scause/sscartch/stval/sstatus/satp等CSR来改变系统状态。

6. `**` RISC-V处理器在用户态执行特权指令后的硬件层面的处理过程是什么？

   CPU 执行完一条指令（如 ecall ）并准备从用户特权级 陷入（ Trap ）到 S 特权级的时候，硬件会自动完成如下这些事情：

   * sstatus 的 SPP 字段会被修改为 CPU 当前的特权级（U/S）。
   * sepc 会被修改为 Trap 处理完成后默认会执行的下一条指令的地址。
   * scause/stval 分别会被修改成这次 Trap 的原因以及相关的附加信息。
   * cpu 会跳转到 stvec 所设置的 Trap 处理入口地址，并将当前特权级设置为 S ，然后从Trap 处理入口地址处开始执行。

   CPU 完成 Trap 处理准备返回的时候，需要通过一条 S 特权级的特权指令 sret 来完成，这一条指令具体完成以下功能：
   * CPU 会将当前的特权级按照 sstatus 的 SPP 字段设置为 U 或者 S ；
   * CPU 会跳转到 sepc 寄存器指向的那条指令，然后继续执行。

7. `**` 操作系统在完成用户态<-->内核态双向切换中的一般处理过程是什么？
   
   当 CPU 在用户态特权级（ RISC-V 的 U 模式）运行应用程序，执行到 Trap，切换到内核态特权级（ RISC-V的S 模式），批处理操作系统的对应代码响应 Trap，并执行系统调用服务，处理完毕后，从内核态返回到用户态应用程序继续执行后续指令。

8. `**` 程序陷入内核的原因有中断、异常和陷入（系统调用），请问 riscv64 支持哪些中断 / 异常？如何判断进入内核是由于中断还是异常？描述陷入内核时的几个重要寄存器及其值。

   * 具体支持的异常和中断，参见 RISC-V 特权集规范 *The RISC-V Instruction Set Manual Volume II: Privileged Architecture* 。其它很多问题在这里也有答案。
   * `scause` 的最高位，为 1 表示中断，为 0 表示异常
   * 重要的寄存器：

     * `scause` ：发生了具体哪个异常或中断
     * `sstatus` ：其中的一些控制为标志发生异常时的处理器状态，如 `sstatus.SPP` 表示发生异常时处理器在哪个特权级。
     * `sepc` ：发生异常或中断的时候，将要执行但未成功执行的指令地址
     * `stval` ：值与具体异常相关，可能是发生异常的地址，指令等

9. `*` 在哪些情况下会出现特权级切换：用户态-->内核态，以及内核态-->用户态？

   * 用户态–>内核态：应用程序发起系统调用；应用程序执行出错，需要到批处理操作系统中杀死该应用并加载运行下一个应用；应用程序执行结束，需要到批处理操作系统中加载运行下一个应用。
   * 内核态–>用户态：启动应用程序需要初始化应用程序的用户态上下文时；应用程序发起的系统调用执行完毕返回应用程序时。

10. `**` Trap上下文的含义是啥？在本章的操作系统中，Trap上下文的具体内容是啥？如果不进行Trap上下文的保存于恢复，会出现什么情况？

   Trap上下文的主要有两部分含义：

   * 在触发 Trap 之前 CPU 运行在哪个特权级；
   * CPU 需要切换到哪个特权级来处理该 Trap ，并在处理完成之后返回原特权级。在本章的实际操作系统中，Trap上下文的具体内容主要包括通用寄存器和栈两部分。如果不进行Trap的上下文保存与恢复，CPU就无法在处理完成之后，返回原特权级。


实验练习
-------------------------------

问答作业
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

1. 正确进入 U 态后，程序的特征还应有：使用 S 态特权指令，访问 S 态寄存器后会报错。请自行测试这些内容 (运行 Rust 三个 bad 测例 ) ，描述程序出错行为，注明你使用的 sbi 及其版本。

2. 请结合用例理解 `trap.S <https://github.com/rcore-os/rCore-Tutorial-v3/blob/ch2/os/src/trap/trap.S>`_ 中两个函数 ``__alltraps`` 和 ``__restore`` 的作用，并回答如下几个问题:

   1. L40：刚进入 ``__restore`` 时，``a0`` 代表了什么值。请指出 ``__restore`` 的两种使用情景。

   2. L46-L51：这几行汇编代码特殊处理了哪些寄存器？这些寄存器的的值对于进入用户态有何意义？请分别解释。

      .. code-block:: riscv

         ld t0, 32*8(sp)
         ld t1, 33*8(sp)
         ld t2, 2*8(sp)
         csrw sstatus, t0
         csrw sepc, t1
         csrw sscratch, t2

   3. L53-L59：为何跳过了 ``x2`` 和 ``x4``？

      .. code-block:: riscv

         ld x1, 1*8(sp)
         ld x3, 3*8(sp)
         .set n, 5
         .rept 27
            LOAD_GP %n
            .set n, n+1
         .endr

   4. L63：该指令之后，``sp`` 和 ``sscratch`` 中的值分别有什么意义？

      .. code-block:: riscv

         csrrw sp, sscratch, sp

   5. ``__restore``：中发生状态切换在哪一条指令？为何该指令执行之后会进入用户态？

   6. L13：该指令之后，``sp`` 和 ``sscratch`` 中的值分别有什么意义？

      .. code-block:: riscv

         csrrw sp, sscratch, sp

   7. 从 U 态进入 S 态是哪一条指令发生的？



3. 对于任何中断，``__alltraps`` 中都需要保存所有寄存器吗？你有没有想到一些加速 ``__alltraps`` 的方法？简单描述你的想法。
