.. _term-remove-std:

移除标准库依赖
==========================

.. toctree::
   :hidden:
   :maxdepth: 5




本节导读
-------------------------------

为了很好地理解一个简单应用所需的执行环境服务如何体现，本节将尝试开始构造一个小的执行环境。这个执行环境可以看成是一个函数库级的操作系统雏形，可建立在 Linux 之上，也可直接建立在裸机之上，我们称为“三叶虫”操作系统。作为第一步，本节将尝试移除之前的 ``Hello world!`` 程序对于 Rust std 标准库的依赖，使得它能够编译到裸机平台 RV64GC 或 Linux-RV64 上。

.. note::

   **库操作系统（Library OS，LibOS）**

   LibOS以函数库的形式存在，为应用程序提供操作系统的基本功能。它最早来源于MIT的Exokernel（外核）架构设计 [#exokernel]_ 中，即把传统的单体内核分为两部分，一部分以库的形式（即LibOS）与应用程序紧耦合，另外一部分（即外核）仅仅听最基础的硬件保护和复用机制，来给LibOS提供基本的硬件访问服务。这样的设计思路可以针对应用程序的特征定制LibOS，达到高性能的目标。


移除 println! 宏
----------------------------------

println! 宏所在的Rust标准库std需要通过系统调用获得操作系统的服务，而如果要构建运行在裸机上的操作系统，就不能直接用这个宏所在的标准库了。所以我们第一步要尝试移除 println! 宏及其所在的标准库。我们首先在 ``os`` 目录下新建 ``.cargo`` 目录，并在这个目录下创建 ``config`` 文件，并在里面输入如下内容：

.. code-block:: toml

   # os/.cargo/config
   [build]
   target = "riscv64gc-unknown-none-elf"

.. _term-cross-compile:

这会对于 cargo 工具在 os 目录下的行为进行调整：现在默认会使用 riscv64gc 作为目标平台而不是原先的默认 x86_64-unknown-linux-gnu。事实上，这是一种编译器运行的平台(x86_64)与可执行文件运行的目标平台(riscv-64)不同的情况。我们把这种情况称为 **交叉编译** (Cross Compile)。

..
  chyyuu：解释一下交叉编译？？？

当然，这只是使得我们之后在 ``cargo build`` 的时候不必再加上 ``--target`` 参数的一个小 trick。如果我们现在执行 ``cargo build`` ，还是会和上一小节一样出现找不到标准库 std 的错误。于是我们开始着手移除标准库，当然，这会产生一些副作用。

我们在 ``main.rs`` 的开头加上一行 ``#![no_std]`` 来告诉 Rust 编译器不使用 Rust 标准库 std 转而使用核心库 core。编译器报出如下错误：

.. error::

   .. code-block:: console

      $ cargo build
         Compiling os v0.1.0 (/home/shinbokuow/workspace/v3/rCore-Tutorial-v3/os)
      error: cannot find macro `println` in this scope
      --> src/main.rs:4:5
        |
      4 |     println!("Hello, world!");
        |     ^^^^^^^

我们之前提到过， println! 宏是由标准库 std 提供的，且会使用到一个名为 write 的系统调用。现在我们的代码功能还不足以自己实现一个 println! 宏。由于使用了系统调用也不能在核心库 core 中找到它，所以我们目前先通过将它注释掉来绕过它。

.. note::

   **Rust std库和core库**

   * Rust 的标准库--std，为绝大多数的 Rust 应用程序开发提供基础支持、跨硬件和操作系统平台支持，是应用范围最广、地位最重要的库，但需要有底层操作系统的支持。
   * Rust 的核心库--core，可以理解为是经过大幅精简的标准库，它被应用在标准库不能覆盖到的某些特定领域，如裸机(bare metal) 环境下，用于操作系统和嵌入式系统的开发，它不需要底层操作系统的支持。

提供语义项 panic_handler
----------------------------------------------------

.. error::

   .. code-block:: console

      $ cargo build
         Compiling os v0.1.0 (/home/shinbokuow/workspace/v3/rCore-Tutorial-v3/os)
      error: `#[panic_handler]` function required, but not found

在使用 Rust 编写应用程序的时候，我们常常在遇到了一些无法恢复的致命错误，导致程序无法继续向下运行。这时手动或自动调用 panic! 宏来打印出错的位置，让我们能够意识到它的存在，并进行一些后续处理。panic! 宏最典型的应用场景包括断言宏 assert! 失败或者对 ``Option::None/Result::Err`` 进行 ``unwrap`` 操作。

在标准库 std 中提供了 panic 的处理函数 ``#[panic_handler]``，其大致功能是打印出错位置和原因并杀死当前应用。但panic 的处理在核心库 core 中并没有提供，因此我们需要自己先实现一个简陋的 panic 处理函数，这样才能支持“三叶虫”操作系统的编译通过。

.. note::

   **Rust 语法卡片：语义项 lang_items**

   为了满足编译器和运行时库的灵活性，Rust 编译器内部的某些功能并不仅仅硬编码在语言内部来实现，而是以一种可插入的形式在库中提供，而且可以定制。标准库或第三方库只需要通过某种方式（在方法前面加上一个标记，如 ``#[panic_handler]`` ，即可）告诉编译器它实现了编译器内部的哪些功能，编译器就会采用库提供的方法来替换它内部对应的功能。

我们创建一个新的子模块 ``lang_items.rs`` 保存这些语义项，在里面提供 panic 处理函数的实现并通过标记通知编译器采用我们的实现：

.. code-block:: rust

   // os/src/lang_items.rs
   use core::panic::PanicInfo;

   #[panic_handler]
   fn panic(_info: &PanicInfo) -> ! {
       loop {}
   }

注意，panic 处理函数的函数签名需要一个 ``PanicInfo`` 的不可变借用作为输入参数，它在核心库中得以保留，这也是我们第一次与核心库打交道。之后我们会从 ``PanicInfo`` 解析出错位置并打印出来，然后杀死应用程序。但目前我们什么都不做只是在原地  ``loop`` 。

移除 main 函数
-----------------------------

.. error::

   .. code-block::

      $ cargo build
         Compiling os v0.1.0 (/home/shinbokuow/workspace/v3/rCore-Tutorial-v3/os)
      error: requires `start` lang_item

编译器提醒我们缺少一个名为 ``start`` 的语义项。我们回忆一下，之前提到语言标准库和三方库作为应用程序的执行环境，需要负责在执行应用程序之前进行一些初始化工作，然后才跳转到应用程序的入口点（也就是跳转到我们编写的 ``main`` 函数）开始执行。事实上 ``start`` 语义项代表了标准库 std 在执行应用程序之前需要进行的一些初始化工作。由于我们禁用了标准库，编译器也就找不到这项功能的实现了。

最简单的解决方案就是压根不让编译器使用这项功能。我们在 ``main.rs`` 的开头加入设置 ``#![no_main]`` 告诉编译器我们没有一般意义上的 ``main`` 函数，并将原来的 ``main`` 函数删除。在失去了 ``main`` 函数的情况下，编译器也就不需要完成所谓的初始化工作了。

至此，我们成功移除了标准库的依赖，并完成了构建裸机平台上的“三叶虫”操作系统的第一步工作--通过编译器检查并生成执行码。

.. code-block:: console

   $ cargo build
      Compiling os v0.1.0 (/home/shinbokuow/workspace/v3/rCore-Tutorial-v3/os)
       Finished dev [unoptimized + debuginfo] target(s) in 0.06s

目前的代码如下：

.. code-block:: rust

   // os/src/main.rs
   #![no_std]
   #![no_main]

   mod lang_items;

   // os/src/lang_items.rs
   use core::panic::PanicInfo;

   #[panic_handler]
   fn panic(_info: &PanicInfo) -> ! {
       loop {}
   }

本小节我们固然脱离了标准库，通过了编译器的检验，但也是伤筋动骨，将原有的很多功能弱化甚至直接删除，看起来距离在 RV64GC 平台上打印 ``Hello world!`` 相去甚远了（我们甚至连 println! 和 ``main`` 函数都删除了）。不要着急，接下来我们会以自己的方式来重塑这些基本功能，并最终完成我们的目标。


分析被移除标准库的程序
-----------------------------

对于上面这个被移除标准库的应用程序，通过了编译器的检查和编译，形成了二进制代码。但这个二进制代码是怎样的，它能否被正常执行呢？我们可以通过一些工具来分析一下。

.. code-block:: console

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
      Entry: 0x0
      ......
      }

   [反汇编导出汇编程序]
   $ rust-objdump -S target/riscv64gc-unknown-none-elf/debug/os
      target/riscv64gc-unknown-none-elf/debug/os:	file format elf64-littleriscv



通过 ``file`` 工具对二进制程序 ``os`` 的分析可以看到它好像是一个合法的 RV64 执行程序，但通过 ``rust-readobj`` 工具进一步分析，发现它的入口地址 Entry 是 ``0`` ，这就比较奇怪了，地址从 0 执行，好像不对。再通过 ``rust-objdump`` 工具把它反汇编，可以看到没有生成汇编代码。所以，我们可以断定，这个二进制程序虽然合法，但它是一个空程序。这不是我们希望的，我们希望的是与源码对应的有具体内容的执行程序。为什么会这样呢？原因是我们缺少了编译器需要找到的入口函数 ``_start`` 。


在下面几节，我们将建立有支持显示字符串的最小执行环境。

.. note::

   **在 x86_64 平台上移除标准库依赖**

   有兴趣的同学可以将目标平台换回之前默认的 ``x86_64-unknown-linux-gnu`` 并重复本小节所做的事情，比较两个平台从 ISA 到操作系统
   的差异。可以参考 `BlogOS 的相关内容 <https://os.phil-opp.com/freestanding-rust-binary/>`_ 。

.. note:: 

   本节内容部分参考自 `BlogOS 的相关章节 <https://os.phil-opp.com/freestanding-rust-binary/>`_ 。


.. [#exokernel] D. R. Engler, M. F. Kaashoek, and J. O'Toole. 1995. Exokernel: an operating system architecture for application-level resource management. In Proceedings of the fifteenth ACM symposium on Operating systems principles (SOSP '95). Association for Computing Machinery, New York, NY, USA, 251–266. 