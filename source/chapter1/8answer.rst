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

    以使用 GCC 编译的 C 语言程序为例，使用编译参数 ``-fno-omit-frame-pointer`` 的情况下，会保存栈帧指针 ``fp`` 。

    ``fp`` 指向的栈位置的负偏移量处保存了两个值：

    * ``-8(fp)`` 是保存的 ``ra``
    * ``-16(fp)`` 是保存的上一个 ``fp``

    .. TODO：这个规范在哪里？

    因此我们可以像链表一样，从当前的 ``fp`` 寄存器的值开始，每次找到上一个 ``fp`` ，逐帧恢复我们的调用栈：

    .. code-block:: c

       #include <inttypes.h>
       #include <stdint.h>
       #include <stdio.h>

       // Compile with -fno-omit-frame-pointer
       void print_stack_trace_fp_chain() {
           printf("=== Stack trace from fp chain ===\n");

           uintptr_t *fp;
           asm("mv %0, fp" : "=r"(fp) : : );

           // When should this stop?
           while (fp) {
               printf("Return address: 0x%016" PRIxPTR "\n", fp[-1]);
               printf("Old stack pointer: 0x%016" PRIxPTR "\n", fp[-2]);
               printf("\n");

               fp = (uintptr_t *) fp[-2];
           }
           printf("=== End ===\n\n");
       }

    但是这里会遇到一个问题，因为我们的标准库并没有保存栈帧指针，所以找到调用栈到标准的库时候会打破我们对栈帧格式的假设，出现异常。

    我们也可以不做关于栈帧保存方式的假设，而是明确让编译器告诉我们每个指令处的调用栈如何恢复。在编译的时候加入 ``-funwind-tables`` 会开启这个功能，将调用栈恢复的信息存入可执行文件中。

    有一个叫做 `libunwind <https://www.nongnu.org/libunwind>`_ 的库可以帮我们读取这些信息生成调用栈信息，而且它可以正确发现某些栈帧不知道怎么恢复，避免异常退出。

    正确安装 libunwind 之后，我们也可以用这样的方式生成调用栈信息：

    .. code-block:: c

       #include <inttypes.h>
       #include <stdint.h>
       #include <stdio.h>

       #define UNW_LOCAL_ONLY
       #include <libunwind.h>

       // Compile with -funwind-tables -lunwind
       void print_stack_trace_libunwind() {
           printf("=== Stack trace from libunwind ===\n");

           unw_cursor_t cursor; unw_context_t uc;
           unw_word_t pc, sp;

           unw_getcontext(&uc);
           unw_init_local(&cursor, &uc);

           while (unw_step(&cursor) > 0) {
               unw_get_reg(&cursor, UNW_REG_IP, &pc);
               unw_get_reg(&cursor, UNW_REG_SP, &sp);

               printf("Program counter: 0x%016" PRIxPTR "\n", (uintptr_t) pc);
               printf("Stack pointer: 0x%016" PRIxPTR "\n", (uintptr_t) sp);
               printf("\n");
           }
           printf("=== End ===\n\n");
       }


3. `**` 实现一个基于rcore/ucore tutorial的应用程序C，用sleep系统调用睡眠5秒（in rcore/ucore tutorial v3: Branch ch1）

注： 尝试用GDB等调试工具和输出字符串的等方式来调试上述程序，能设置断点，单步执行和显示变量，理解汇编代码和源程序之间的对应关系。


问答题
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

1. `*` 应用程序在执行过程中，会占用哪些计算机资源？

    占用 CPU 计算资源（CPU 流水线，缓存等），内存（内存不够还会占用外存）等

2. `*` 请用相关工具软件分析并给出应用程序A的代码段/数据段/堆/栈的地址空间范围。

    简便起见，我们静态编译该程序生成可执行文件。使用 ``readelf`` 工具查看地址空间：

    .. 
        Section Headers:
        [Nr] Name              Type             Address           Offset
            Size              EntSize          Flags  Link  Info  Align
        ...
        [ 7] .text             PROGBITS         00000000004011c0  000011c0
            0000000000095018  0000000000000000  AX       0     0     64
        ... 
        [10] .rodata           PROGBITS         0000000000498000  00098000
            000000000001cadc  0000000000000000   A       0     0     32
        ...    
        [21] .data             PROGBITS         00000000004c50e0  000c40e0
            00000000000019e8  0000000000000000  WA       0     0     32
        ...    
        [25] .bss              NOBITS           00000000004c72a0  000c6290
            0000000000005980  0000000000000000  WA       0     0     32

    数据段（.data）和代码段（.text）的起止地址可以从输出信息中看出。

    应用程序的堆栈是由内核为其动态分配的，需要在运行时查看。将 A 程序置于后台执行，通过查看 ``/proc/[pid]/maps`` 得到堆栈空间的分布：

    .. 
        01bc9000-01beb000 rw-p 00000000 00:00 0                                  [heap]
        7ffff8e60000-7ffff8e82000 rw-p 00000000 00:00 0                          [stack]
        
3. `*` 请简要说明应用程序与操作系统的异同之处。

    这个问题相信大家完成了实验的学习后一定会有更深的理解。

4. `**` 请基于QEMU模拟RISC—V的执行过程和QEMU源代码，说明RISC-V硬件加电后的几条指令在哪里？完成了哪些功能？

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

5. `*` RISC-V中的SBI的含义和功能是啥？

    详情见 `SBI 官方文档 <https://github.com/riscv-non-isa/riscv-sbi-doc/blob/master/riscv-sbi.adoc>`_

6. `**` 为了让应用程序能在计算机上执行，操作系统与编译器之间需要达成哪些协议？

    编译器依赖操作系统提供的程序库，操作系统执行应用程序需要编译器提供段位置、符号表、依赖库等信息。 `ELF <https://en.wikipedia.org/wiki/Executable_and_Linkable_Format>`_ 就是比较常见的一种文件格式。

7.  `**` 请简要说明从QEMU模拟的RISC-V计算机加电开始运行到执行应用程序的第一条指令这个阶段的执行过程。

    接第 5 题，跳转到 RustSBI 后，SBI 会对部分硬件例如串口等进行初始化，然后通过 mret 跳转到 payload 也就是 kernel 所在的起始地址。kernel 进行一系列的初始化后（内存管理，虚存管理，线程（进程）初始化等），通过 sret 跳转到应用程序的第一条指令开始执行。

8.  `**` 为何应用程序员编写应用时不需要建立栈空间和指定地址空间？

    应用程度对内存的访问需要通过 MMU 的地址翻译完成，应用程序运行时看到的地址和实际位于内存中的地址是不同的，栈空间和地址空间需要内核进行管理和分配。应用程序的栈指针在 trap return 过程中初始化。此外，应用程序可能需要动态加载某些库的内容，也需要内核完成映射。

9.  `***` 现代的很多编译器生成的代码，默认情况下不再严格保存/恢复栈帧指针。在这个情况下，我们只要编译器提供足够的信息，也可以完成对调用栈的恢复。（题目剩余部分省略）

    * 首先，我们当前的 ``pc`` 在 ``flip`` 函数的开头，这是我们正在运行的函数。返回给调用者处的地址在 ``ra`` 寄存器里，是 ``0x10742`` 。因为我们还没有开始操作栈指针，所以调用处的 ``sp`` 与我们相同，都是 ``0x40007f1310`` 。
    * ``0x10742`` 在 ``flap`` 函数内。根据 ``flap`` 函数的开头可知，这个函数的栈帧大小是 16 个字节，所以调用者处的栈指针应该是 ``sp + 16 = 0x40007f1320``。调用 ``flap`` 的调用者返回地址保存在栈上 ``8(sp)`` ，可以读出来是 ``0x10750`` ，还在 ``flap`` 函数内。
    * 依次类推，只要能理解已知地址对应的函数代码，就可以完成恢复操作。

实验练习
-------------------------------

问答作业
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

1. 请学习 gdb 调试工具的使用(这对后续调试很重要)，并通过 gdb 简单跟踪从机器加电到跳转到 0x80200000 的简单过程。只需要描述重要的跳转即可，只需要描述在 qemu 上的情况。


.. [#qemu_bootrom] https://github.com/qemu/qemu/blob/0ebf76aae58324b8f7bf6af798696687f5f4c2a9/hw/riscv/boot.c#L300