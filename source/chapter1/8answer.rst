练习参考答案
=====================================================

.. toctree::
   :hidden:
   :maxdepth: 4


课后练习
-------------------------------

编程题
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
1. `*` 实现一个linux应用程序A，显示当前目录下的文件名。（用C或Rust编程）

   参考实现：

   .. code-block:: c

      #include <dirent.h>
      #include <stdio.h>

      int main() {
          DIR *dir = opendir(".");

          struct dirent *entry;

          while ((entry = readdir(dir))) {
              printf("%s\n", entry->d_name);
          }

          return 0;
      }

   可能的输出：

   .. code-block:: console

      $ ./ls
      .
      ..
      .git
      .dockerignore
      Dockerfile
      LICENSE
      Makefile
      [...]


2. `***` 实现一个linux应用程序B，能打印出调用栈链信息。（用C或Rust编程）
3. `**` 实现一个基于rcore/ucore tutorial的应用程序C，用sleep系统调用睡眠5秒（in rcore/ucore tutorial v3: Branch ch1）

注： 尝试用GDB等调试工具和输出字符串的等方式来调试上述程序，能设置断点，单步执行和显示变量，理解汇编代码和源程序之间的对应关系。


问答题
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

1. `*` 应用程序在执行过程中，会占用哪些计算机资源？
2. `*` 请用相关工具软件分析并给出应用程序A的代码段/数据段/堆/栈的地址空间范围。
3. `*` 请用分析并给出应用程序C的代码段/数据段/堆/栈的地址空间范围。
4. `*` 请结合编译器的知识和编写的应用程序B，说明应用程序B是如何建立调用栈链信息的。
5. `*` 请简要说明应用程序与操作系统的异同之处。
6. `**` 请基于QEMU模拟RISC—V的执行过程和QEMU源代码，说明RISC-V硬件加电后的几条指令在哪里？完成了哪些功能？

   在 QEMU 源码 [#qemu_bootrom]_ 中可以找到“上电”的时候刚执行的几条指令，如下：

   .. code-block:: c

      uint32_t reset_vec[10] = {
          0x00000297,                   /* 1:  auipc  t0, %pcrel_hi(fw_dyn) */
          0x02828613,                   /*     addi   a2, t0, %pcrel_lo(1b) */
          0xf1402573,                   /*     csrr   a0, mhartid  */
      #if defined(TARGET_RISCV32)
          0x0202a583,                   /*     lw     a1, 32(t0) */
          0x0182a283,                   /*     lw     t0, 24(t0) */
      #elif defined(TARGET_RISCV64)
          0x0202b583,                   /*     ld     a1, 32(t0) */
          0x0182b283,                   /*     ld     t0, 24(t0) */
      #endif
          0x00028067,                   /*     jr     t0 */
          start_addr,                   /* start: .dword */
          start_addr_hi32,
          fdt_load_addr,                /* fdt_laddr: .dword */
          0x00000000,
                                        /* fw_dyn: */
      };

   完成的工作是：

   - 读取当前的 Hart ID CSR ``mhartid`` 写入寄存器 ``a0``
   - （我们还没有用到：将 FDT (Flatten device tree) 在物理内存中的地址写入 ``a1``）
   - 跳转到 ``start_addr`` ，在我们实验中是 RustSBI 的地址

7. `*` RISC-V中的SBI的含义和功能是啥？
8. `**` 为了让应用程序能在计算机上执行，操作系统与编译器之间需要达成哪些协议？
9.  `**` 请简要说明从QEMU模拟的RISC-V计算机加电开始运行到执行应用程序的第一条指令这个阶段的执行过程。
10. `**` 为何应用程序员编写应用时不需要建立栈空间和指定地址空间？


实验练习
-------------------------------

问答作业
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

1. 请学习 gdb 调试工具的使用(这对后续调试很重要)，并通过 gdb 简单跟踪从机器加电到跳转到 0x80200000 的简单过程。只需要描述重要的跳转即可，只需要描述在 qemu 上的情况。
