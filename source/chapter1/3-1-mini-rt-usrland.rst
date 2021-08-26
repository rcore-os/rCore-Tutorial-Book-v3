.. _term-print-userminienv:

构建用户态执行环境
=================================

.. toctree::
   :hidden:
   :maxdepth: 5

本节导读
-------------------------------

在这里，我们先设计实现一个用户态的最小执行环境（就是上节提到的用户态的LibOS）以支持最简单的用户态 ``Hello, world!`` 程序，再改进这个最小执行环境，让它能在内核态运行（即可以在裸机上运行的嵌入式OS），支持裸机应用程序。这样设计实现的原因是，
它能帮助我们理解这两个不同的执行环境在支持同样一个应用程序时的的相同和不同之处，这将加深对执行环境的理解，并对后续写自己的OS和运行在OS上的应用程序都有帮助。
所以，本节将先建立一个用户态的最小执行环境，即 **恐龙虾** 操作系统 [#shrimp]_ 。

本节开始我们将着手自己来实现之前被我们移除的 ``Hello, world!`` 程序中用户态执行环境的功能。
在这一小节，我们首先介绍如何进行 **执行环境初始化** 。



用户态最小化执行环境
----------------------------

执行环境初始化
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

在上一节，我们构造的二进制程序是一个空程序，其原因是 Rust 编译器找不到执行环境的入口函数，于是就没有生产后续的代码。所以，我们首先要把入口函数
找到。通过查找资料，发现Rust编译器要找的入口函数是 ``_start()`` ，于是我们可以在 ``main.rs`` 中添加如下内容：


.. code-block:: rust

  // os/src/main.rs
  #[no_mangle]
  extern "C" fn _start() {
      loop{};
  }


对上述代码重新编译，再用分析工具分析，可以看到：


.. code-block:: console

   $ cargo build
      Compiling os v0.1.0 (/home/shinbokuow/workspace/v3/rCore-Tutorial-v3/os)
       Finished dev [unoptimized + debuginfo] target(s) in 0.06s

   [文件格式]
   $ file target/riscv64gc-unknown-none-elf/debug/os
   target/riscv64gc-unknown-none-elf/debug/os: ELF 64-bit LSB executable, UCB RISC-V, ......

   [文件头信息]
   $ rust-readobj -h target/riscv64gc-unknown-none-elf/debug/os
      File: target/riscv64gc-unknown-none-elf/debug/os
      Format: elf64-littleriscv
      Arch: riscv64
      AddressSize: 64bit
      ......
      Type: Executable (0x2)
      Machine: EM_RISCV (0xF3)
      Version: 1
      Entry: 0x11120      
      ......
      }
   
   [反汇编导出汇编程序]
   $ rust-objdump -S target/riscv64gc-unknown-none-elf/debug/os
      target/riscv64gc-unknown-none-elf/debug/os:	file format elf64-littleriscv

      Disassembly of section .text:

      0000000000011120 <_start>:
      ;     loop {}
        11120: 09 a0        	j	2 <_start+0x2>
        11122: 01 a0        	j	0 <_start+0x2>


通过 ``file`` 工具对二进制程序 ``os`` 的分析可以看到它依然是一个合法的 RV64 执行程序，但通过 ``rust-readobj`` 工具进一步分析，发现它的入口地址 Entry 是 ``0x11120`` ，这好像是一个合法的地址。再通过 ``rust-objdump`` 工具把它反汇编，可以看到编译器生成的汇编代码！


仔细读读这两条指令，发现就是一个死循环的汇编代码，且其第一条指令的地址与入口地址 Entry 的值一致，这说明编译器生成的目标执行程序已经是一个合理的程序了。如果我们用 ``qemu-riscv64 target/riscv64gc-unknown-none-elf/debug/os`` 执行这个程序，可以看到好像就是在执行死循环。


程序正常退出
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

我们能让程序正常退出吗？我们把 ``_start()`` 函数中的循环语句注释掉，重新编译并分析，看到其汇编代码是：


.. code-block:: console

   $ rust-objdump -S target/riscv64gc-unknown-none-elf/debug/os

    target/riscv64gc-unknown-none-elf/debug/os:	file format elf64-littleriscv


    Disassembly of section .text:

    0000000000011120 <_start>:
    ; }
      11120: 82 80        	ret

看起来是有内容(具有 ``ret`` 函数返回汇编指令）且合法的执行程序。但如果我们执行它，就发现有问题了：

.. code-block:: console

  $ qemu-riscv64 target/riscv64gc-unknown-none-elf/debug/os
    段错误 (核心已转储)

*段错误 (核心已转储)* 是常见的一种应用程序出错，而我们这个非常简单的应用程序导致了 Linux 环境模拟程序 ``qemu-riscv64`` 崩溃了！为什么会这样？

.. _term-qemu-riscv64:

.. note::

   QEMU有两种运行模式： ``User mode`` 模式，即用户态模拟，如 ``qemu-riscv64`` 程序，能够模拟不同处理器的用户态指令的执行，并可以直接解析ELF可执行文件，加载运行那些为不同处理器编译的用户级Linux应用程序（ELF可执行文件）；在翻译并执行不同应用程序中的不同处理器的指令时，如果碰到是系统调用相关的汇编指令，它会把不同处理器（如RISC-V）的Linux系统调用转换为本机处理器（如x86-64）上的Linux系统调用，这样就可以让本机Linux完成系统调用，并返回结果（再转换成RISC-V能识别的数据）给这些应用。 ``System mode`` 模式，即系统态模式，如 ``qemu-system-riscv64`` 程序，能够模拟一个完整的基于不同CPU的硬件系统，包括处理器、内存及其他外部设备，支持运行完整的操作系统。

回顾一下最开始的输出 ``Hello, world!`` 的简单应用程序，其入口函数名字是 ``main`` ，编译时用的是标准库 std 。它可以正常执行。再仔细想想，当一个应用程序出错的时候，最上层为操作系统的执行环境会把它给杀死。但如果一个应用的入口函数正常返回，执行环境应该优雅地让它退出才对。没错！目前的执行环境还缺了一个退出机制。

先了解一下，操作系统会提供一个退出的系统调用服务接口，但应用程序调用这个接口，那这个程序就退出了。这里先给出代码：

.. _term-llvm-syscall:

.. code-block:: rust
  
  // os/src/main.rs
  #![feature(llvm_asm)]

  const SYSCALL_EXIT: usize = 93;

  fn syscall(id: usize, args: [usize; 3]) -> isize {
      let mut ret: isize;
      unsafe {
          llvm_asm!("ecall"
              : "={x10}" (ret)
              : "{x10}" (args[0]), "{x11}" (args[1]), "{x12}" (args[2]), "{x17}" (id)
              : "memory"
              : "volatile"
          );
      }
      ret
  }

  pub fn sys_exit(xstate: i32) -> isize {
      syscall(SYSCALL_EXIT, [xstate as usize, 0, 0])
  }

  #[no_mangle]
  extern "C" fn _start() {
      sys_exit(9);
  }
 
``main.rs`` 增加的内容不多，但还是有点与一般的应用程序有所不同，因为它引入了汇编和系统调用。如果你看不懂上面内容的细节，没关系，在第二章的第二节 :doc:`/chapter2/2application` 会有详细的介绍。这里只需知道 ``_start`` 函数调用了一个 ``sys_exit`` 函数，来向操作系统发出一个退出服务的系统调用请求，并传递给OS的退出码为 ``9`` 。

我们编译执行以下修改后的程序：

.. code-block:: console

    $ cargo build --target riscv64gc-unknown-none-elf
      Compiling os v0.1.0 (/media/chyyuu/ca8c7ba6-51b7-41fc-8430-e29e31e5328f/thecode/rust/os_kernel_lab/os)
        Finished dev [unoptimized + debuginfo] target(s) in 0.26s
    
    [$?表示执行程序的退出码，它会被告知 OS]    
    $ qemu-riscv64 target/riscv64gc-unknown-none-elf/debug/os; echo $?
    9

可以看到，返回的结果确实是 ``9`` 。这样，我们在没有任何显示功能的情况下，勉强完成了一个简陋的用户态最小化执行环境。

上面实现的最小化执行环境貌似能够在 Linux 操作系统上支持只调用一个 ``SYSCALL_EXIT`` 系统调用服务的程序，但这也说明了
在操作系统的支持下，实现一个基本的用户态执行环境还是比较容易的。其中的原因是，操作系统帮助用户态执行环境完成了程序加载、程序退出、资源分配、资源回收等各种琐事。如果没有操作系统，那么实现一个支持在裸机上运行应用程序的执行环境，就要考虑更多的事情了，或者干脆简化一切可以不必干的事情（比如对于单个应用，不需要调度功能等）。
能在裸机上运行的执行环境，其实就是之前提到的“三叶虫”操作系统。


有显示支持的用户态执行环境
----------------------------

没有显示功能，终究觉得缺了点啥。在没有通常开发应用程序时常用的动态调试工具的情况下，其实能显示字符串，就已经能够满足绝大多数情况下的操作系统调试需求了。

Rust 的 core 库内建了以一系列帮助实现显示字符的基本 Trait 和数据结构，函数等，我们可以对其中的关键部分进行扩展，就可以实现定制的 ``println!`` 功能。


实现输出字符串的相关函数
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

首先封装一下对 ``SYSCALL_WRITE`` 系统调用。这个是 Linux 操作系统内核提供的系统调用，其 ``ID`` 就是 ``SYSCALL_WRITE``。

.. code-block:: rust
  
  const SYSCALL_WRITE: usize = 64;

  pub fn sys_write(fd: usize, buffer: &[u8]) -> isize {
    syscall(SYSCALL_WRITE, [fd, buffer.as_ptr() as usize, buffer.len()])
  }

然后实现基于 ``Write`` Trait 的数据结构，并完成 ``Write`` Trait 所需要的  ``write_str`` 函数，并用 ``print`` 函数进行包装。


.. code-block:: rust
  
  struct Stdout;

  impl Write for Stdout {
      fn write_str(&mut self, s: &str) -> fmt::Result {
          sys_write(1, s.as_bytes());
          Ok(())
      }
  }

  pub fn print(args: fmt::Arguments) {
      Stdout.write_fmt(args).unwrap();
  }

最后，实现基于 ``print`` 函数，实现Rust语言 **格式化宏** ( `formatting macros <https://doc.rust-lang.org/std/fmt/#related-macros>`_ )。


.. code-block:: rust

  #[macro_export]
  macro_rules! print {
      ($fmt: literal $(, $($arg: tt)+)?) => {
          $crate::console::print(format_args!($fmt $(, $($arg)+)?));
      }
  }

  #[macro_export]
  macro_rules! println {
      ($fmt: literal $(, $($arg: tt)+)?) => {
          print(format_args!(concat!($fmt, "\n") $(, $($arg)+)?));
      }
  }

上面的代码没有读懂？没关系，你只要了解到应用程序发出的宏调用 ``println!`` 就是通过上面的实现，一步一步地调用，最终通过操作系统提供的 ``SYSCALL_WRITE`` 系统调用服务，帮助我们完成了字符串显示输出。这就完成了有显示支持的用户态执行环境。

接下来，我们调整一下应用程序，让它发出显示字符串和退出的请求：

.. code-block:: rust

  #[no_mangle]
  extern "C" fn _start() {
      println!("Hello, world!");
      sys_exit(9);
  } 

整体工作完成！当然，我们实现的很简陋，用户态执行环境和应用程序都放在一个文件里面，以后会通过我们学习的软件工程的知识，进行软件重构，让代码更清晰和模块化。

现在，我们编译并执行一下，可以看到正确的字符串输出，且程序也能正确结束！


.. code-block:: console

  $ cargo build --target riscv64gc-unknown-none-elf
     Compiling os v0.1.0 (/media/chyyuu/ca8c7ba6-51b7-41fc-8430-e29e31e5328f/thecode/rust/os_kernel_lab/os)
    Finished dev [unoptimized + debuginfo] target(s) in 0.61s

  $ qemu-riscv64 target/riscv64gc-unknown-none-elf/debug/os; echo $?
    Hello, world!
    9


.. 下面出错的情况是会在采用 linker.ld，加入了 .cargo/config 
.. 的内容后会出错：
.. .. [build]
.. .. target = "riscv64gc-unknown-none-elf"
.. .. [target.riscv64gc-unknown-none-elf]
.. .. rustflags = [
.. ..    "-Clink-arg=-Tsrc/linker.ld", "-Cforce-frame-pointers=yes"
.. .. ]

.. 重新定义了栈和地址空间布局后才会出错    

.. 段错误 (核心已转储)

.. 系统崩溃了！借助以往的操作系统内核编程经验和与下一节调试kernel的成果经验，我们直接定位为是 **栈** (Stack) 没有设置的问题。我们需要添加建立栈的代码逻辑。

.. .. code-block:: asm

..   # entry.asm
  
..       .section .text.entry
..       .globl _start
..   _start:
..       la sp, boot_stack_top
..       call rust_main

..       .section .bss.stack
..       .globl boot_stack
..   boot_stack:
..       .space 4096 * 16
..       .globl boot_stack_top
..   boot_stack_top:

.. 然后把汇编代码嵌入到 ``main.rs`` 中，并进行微调。

.. .. code-block:: rust

..   #![feature(global_asm)]

..   global_asm!(include_str!("entry.asm"));

..   #[no_mangle]
..   #[link_section=".text.entry"]
..   extern "C" fn rust_main() {

.. 再次编译执行，可以看到正确的字符串输出，且程序也能正确结束！


.. [#shrimp] 恐龙虾是一类有三只眼的小型甲壳生物，最早出现在三亿年前的古生代石炭纪，在经历了三次地球世纪大灭绝之后，至今仍广泛地分布于世界各地。 