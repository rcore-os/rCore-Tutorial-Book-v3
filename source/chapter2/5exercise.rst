chapter2练习
=====================================================

.. toctree::
   :hidden:
   :maxdepth: 4

- 本节难度： **低** 

编程练习
-------------------------------

简单安全检查
+++++++++++++++++++++++++++++++

lab2 中，我们实现了第一个系统调用 ``sys_write``，这使得我们可以在用户态输出信息。但是 os 在提供服务的同时，还有保护 os 本身以及其他用户程序不受错误或者恶意程序破坏的功能。

由于还没有实现虚拟内存，我们可以在用户程序中指定一个属于其他程序字符串，并将它输出，这显然是不合理的，因此我们要对 sys_write 做检查：

- sys_write 仅能输出位于程序本身内存空间内的数据，否则报错。

实验要求
+++++++++++++++++++++++++++++++
- 实现分支: ch2。
- 完成实验指导书中的内容，能运行用户态程序并执行 sys_write，sys_exit 系统调用。
- 为 sys_write 增加安全性检查，并通过 `Rust测例 <https://github.com/DeathWish5/rCore_tutorial_tests>`_ 中 chapter2 对应的所有测例，测例详情见对应仓库。

challenge: 支持多核，实现多个核运行用户程序。

实验检查
++++++++++++++++++++++++++++++

- 实验目录要求(Rust)

.. code-block::

   ├── os(内核实现)
   │   ├── Cargo.toml(配置文件)
   │   ├── Makefile (要求 make run 可以正确执行，尽量不输出调试信息)
   │   ├── src(所有内核的源代码放在 os/src 目录下)
   │       ├── main.rs(内核主函数)
   │       ├── ...
   ├── reports
   │   ├── lab1.md/pdf
   │   └── ...
   ├── build.rs (在这里实现用户程序的打包)
   ├── README.md（其他必要的说明）
   ├── ...

参考示例目录结构。目标用户目录 ``../user/build/bin``。

- 检查

.. code-block:: console

   $ cd os
   $ git checkout ch2
   $ make run

可以正确执行正确执行目标用户测例，并得到预期输出（详见测例注释）。

注意：如果设置默认 log 等级，从 lab2 开始关闭所有 log 输出。

简答题
-------------------------------

1. 正确进入 U 态后，程序的特征还应有：使用 S 态特权指令，访问 S 态寄存器后会报错。目前由于一些其他原因，这些问题不太好测试，请同学们可以自行测试这些内容（参考 `前三个测例 <https://github.com/DeathWish5/rCore_tutorial_tests/tree/master/user/src/bin>`_ )，描述程序出错行为，同时注意注明你使用的 sbi 及其版本。

2. 请结合用例理解 `trap.S <https://github.com/rcore-os/rCore-Tutorial-v3/blob/ch2/os/src/trap/trap.S>`_ 中两个函数 ``__alltraps`` 和 ``__restore`` 的作用，并回答如下几个问题:

   1. L40: 刚进入 ``__restore`` 时，``a0`` 代表了什么值。请指出 ``__restore`` 的两种使用情景。

   2. L46-L51: 这几行汇编代码特殊处理了哪些寄存器？这些寄存器的的值对于进入用户态有何意义？请分别解释。
      
      .. code-block:: riscv

         ld t0, 32*8(sp)
         ld t1, 33*8(sp)
         ld t2, 2*8(sp)
         csrw sstatus, t0
         csrw sepc, t1
         csrw sscratch, t2

   3. L53-L59: 为何跳过了 ``x2`` 和 ``x4``？ 

      .. code-block:: riscv

         ld x1, 1*8(sp)
         ld x3, 3*8(sp)
         .set n, 5
         .rept 27
            LOAD_GP %n
            .set n, n+1
         .endr

   4. L63: 该指令之后，``sp`` 和 ``sscratch`` 中的值分别有什么意义？

      .. code-block:: riscv

         csrrw sp, sscratch, sp

   5. ``__restore``：中发生状态切换在哪一条指令？为何该指令执行之后会进入用户态？

   6. L13： 该指令之后，``sp`` 和 ``sscratch`` 中的值分别有什么意义？

      .. code-block:: riscv

         csrrw sp, sscratch, sp

   7. 从 U 态进入 S 态是哪一条指令发生的？

3. 程序陷入内核的原因有中断和异常（系统调用），请问 riscv64 支持哪些中断 / 异常？如何判断进入内核是由于中断还是异常？描述陷入内核时的几个重要寄存器及其值。

4. 对于任何中断， ``__alltraps`` 中都需要保存所有寄存器吗？你有没有想到一些加速 ``__alltraps`` 的方法？简单描述你的想法。

报告要求
-------------------------------

- 简单总结与上次实验相比本次实验你增加的东西（控制在5行以内，不要贴代码）。
- 完成问答问题。
- (optional) 你对本次实验设计及难度/工作量的看法，以及有哪些需要改进的地方，欢迎畅所欲言。

