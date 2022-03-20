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
4. `**` 编译器/操作系统/处理器如何合作，可采用哪些方法来保护操作系统不受应用程序的破坏？
5. `**` RISC-V处理器的S态特权指令有哪些，其大致含义是什么，有啥作用？
6. `**` RISC-V处理器在用户态执行特权指令后的硬件层面的处理过程是什么？
7. `**` 操作系统在完成用户态<-->内核态双向切换中的一般处理过程是什么？
8. `**` 程序陷入内核的原因有中断、异常和陷入（系统调用），请问 riscv64 支持哪些中断 / 异常？如何判断进入内核是由于中断还是异常？描述陷入内核时的几个重要寄存器及其值。

   * 具体支持的异常和中断，参见 RISC-V 特权集规范 *The RISC-V Instruction Set Manual Volume II: Privileged Architecture* 。其它很多问题在这里也有答案。
   * `scause` 的最高位，为 1 表示中断，为 0 表示异常
   * 重要的寄存器：

     * `scause` ：发生了具体哪个异常或中断
     * `sstatus` ：其中的一些控制为标志发生异常时的处理器状态，如 `sstatus.SPP` 表示发生异常时处理器在哪个特权级。
     * `sepc` ：发生异常或中断的时候，将要执行但未成功执行的指令地址
     * `stval` ：值与具体异常相关，可能是发生异常的地址，指令等

9. `*` 在哪些情况下会出现特权级切换：用户态-->内核态，以及内核态-->用户态？
10. `**` Trap上下文的含义是啥？在本章的操作系统中，Trap上下文的具体内容是啥？如果不进行Trap上下文的保存于恢复，会出现什么情况？

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
