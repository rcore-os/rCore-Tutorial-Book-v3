.. _term-remove-std:

移除标准库依赖
==========================

.. toctree::
   :hidden:
   :maxdepth: 5

本节导读
-------------------------------

.. 为了很好地理解一个简单应用所需的执行环境服务如何体现，本节将尝试开始构造一个小的执行环境。这个执行环境可以看成是一个函数库级的操作系统雏形，可建立在 Linux 之上，也可直接建立在裸机之上，我们称为“三叶虫”操作系统。作为第一步，本节将尝试移除之前的 ``Hello world!`` 程序对于 Rust std 标准库的依赖，使得它能够编译到裸机平台 RV64GC 或 Linux-RV64 上。

本章的目标是构建一个内核最小执行环境使得它能在 RV64GC （即实现了IMAFDC规范的 RISC-V 64位CPU）裸机上运行，在功能上它则像上一节最简单的 Rust 应用程序一样能够打印 ``Hello, world!`` ，这将会为我们的后续章节提供很多调试上的方便，我们将其称为“三叶虫”操作系统。本节我们来进行第一个步骤：即对上一节最简单的 Rust 应用程序进行改造使得它能够被编译到 RV64GC 裸机平台上，为此我们需要移除它对于 Rust std标准库的依赖，因为 Rust std标准库自己就需要操作系统内核的支持。这样我们需要添加能够支持应用的裸机级别的库操作系统（LibOS）。 

.. note::

   **库操作系统（Library OS，LibOS）**

   LibOS 以函数库的形式存在，为应用程序提供操作系统的基本功能。它最早来源于 MIT PDOS研究小组在1996年左右的Exokernel（外核）操作系统结构研究。Frans Kaashoek 教授的博士生Dawson Engler 提出了一种与以往操作系统架构大相径庭的 Exokernel（外核）架构设计 [#exokernel]_ ，即把传统的单体内核分为两部分，一部分以库操作系统的形式（即 LibOS）与应用程序紧耦合以实现传统的操作系统抽象，并进行面向应用的裁剪与优化；另外一部分（即外核）仅专注在最基本的安全复用物理硬件的机制上，来给 LibOS 提供基本的硬件访问服务。这样的设计思路可以针对应用程序的特征定制 LibOS ，达到高性能的目标。

   这种操作系统架构的设计思路比较超前，对原型系统的测试显示了很好的性能提升。但最终没有被工业界采用，其中一个重要的原因是针对特定应用定制一个LibOS的工作量大，难以重复使用。人力成本因素导致了它不太被工业界认可。


移除 ``println!`` 宏
----------------------------------

``println!`` 宏所在的 Rust 标准库 std 需要通过系统调用获得操作系统的服务，而如果要构建运行在裸机上的操作系统，就不能再依赖标准库了。所以我们第一步要尝试移除 ``println!`` 宏及其所在的标准库。

由于后续实验需要 ``rustc`` 编译器缺省生成RISC-V 64的目标代码，所以我们首先要给  ``rustc`` 添加一个target : ``riscv64gc-unknown-none-elf`` 。这可通过如下命令来完成：

.. code-block:: bash

   $ rustup target add riscv64gc-unknown-none-elf


然后在 ``os`` 目录下新建 ``.cargo`` 目录，并在这个目录下创建 ``config`` 文件，并在里面输入如下内容：

.. code-block:: toml

   # os/.cargo/config
   [build]
   target = "riscv64gc-unknown-none-elf"

.. _term-cross-compile:

这会对于 Cargo 工具在 os 目录下的行为进行调整：现在默认会使用 riscv64gc 作为目标平台而不是原先的默认 x86_64-unknown-linux-gnu。事实上，这是一种编译器运行的开发平台（x86_64）与可执行文件运行的目标平台（riscv-64）不同的情况。我们把这种情况称为 **交叉编译** (Cross Compile)。


.. note::

   **本地编译与交叉编译** 

   下面指的 **平台** 主要由CPU硬件和操作系统这两个要素组成。

   本地编译，即在当前开发平台下编译出来的程序，也只是放到这个平台下运行。如在 Linux x86-64 平台上编写代码并编译成可在 Linux x86-64 同样平台上执行的程序。
   
   交叉编译，是一个与本地编译相对应的概念，即在一种平台上编译出在另一种平台上运行的程序。程序编译的环境与程序运行的环境不一样。如我们后续会讲到，在Linux x86-64 开发平台上，编写代码并编译成可在 rCore Tutorial（这是我们要编写的操作系统内核）和 riscv64gc（这是CPU硬件）构成的目标平台上执行的程序。
   


当然，这只是使得我们之后在 ``cargo build`` 的时候不必再加上 ``--target`` 参数的一个小 trick。如果我们现在执行 ``cargo build`` ，还是会和上一小节一样出现找不到标准库 std 的错误。于是我们需要在着手移除标准库的过程中一步一步地解决这些错误。

我们在 ``main.rs`` 的开头加上一行 ``#![no_std]`` 来告诉 Rust 编译器不使用 Rust 标准库 std 转而使用核心库 core（core库不需要操作系统的支持）。编译器报出如下错误：

.. error::

   .. code-block:: console

      $ cargo build
         Compiling os v0.1.0 (/home/shinbokuow/workspace/v3/rCore-Tutorial-v3/os)
      error: cannot find macro `println` in this scope
      --> src/main.rs:4:5
        |
      4 |     println!("Hello, world!");
        |     ^^^^^^^

我们之前提到过， ``println!`` 宏是由标准库 std 提供的，且会使用到一个名为 write 的系统调用。现在我们的代码功能还不足以自己实现一个 ``println!`` 宏。由于程序使用了系统调用，但不能在核心库 core 中找到它，所以我们目前先通过将 ``println!`` 宏注释掉的简单粗暴方式，来暂时绕过这个问题。

.. chyyuu note::
   **Rust Tips: Rust std 库和 core 库**
   * Rust 的标准库--std，为绝大多数的 Rust 应用程序开发提供基础支持、跨硬件和操作系统平台支持，是应用范围最广、地位最重要的库，但需要有底层操作系统的支持。
   * Rust 的核心库--core，可以理解为是经过大幅精简的标准库，它被应用在标准库不能覆盖到的某些特定领域，如裸机(bare metal) 环境下，用于操作系统和嵌入式系统的开发，它不需要底层操作系统的支持。


提供panic_handler功能应对致命错误
--------------------------------------------------------

我们重新编译简单的os程序，之前的 `println` 宏缺失的错误消失了，但又出现了如下新的编译错误：

.. error::

   .. code-block:: console

      $ cargo build
         Compiling os v0.1.0 (/home/shinbokuow/workspace/v3/rCore-Tutorial-v3/os)
      error: `#[panic_handler]` function required, but not found

在使用 Rust 编写应用程序的时候，我们常常在遇到了一些无法恢复的致命错误（panic），导致程序无法继续向下运行。这时手动或自动调用 ``panic!`` 宏来打印出错的位置，让软件能够意识到它的存在，并进行一些后续处理。 ``panic!`` 宏最典型的应用场景包括断言宏 ``assert!`` 失败或者对 ``Option::None/Result::Err`` 进行 ``unwrap`` 操作。所以Rust编译器在编译程序时，从安全性考虑，需要有 ``panic!`` 宏的具体实现。

.. chyyuu  rust-lang/rust/library/std/src/panic.rs  `pub macro panic_2015/2021 {`

.. chyyuu  rust-lang/rust/library/core/src/macros/modrs `macro_rules! panic {`

在标准库 std 中提供了关于 ``panic!`` 宏的具体实现，其大致功能是打印出错位置和原因并杀死当前应用。但本章要实现的操作系统不能使用还需依赖操作系统的标准库std，而更底层的核心库 core 中只有一个 ``panic!`` 宏的空壳，并没有提供 ``panic!`` 宏的精简实现。因此我们需要自己先实现一个简陋的 panic 处理函数，这样才能让“三叶虫”操作系统 -- LibOS的编译通过。

.. note::

   **#[panic_handler]**

   ``#[panic_handler]`` 是一种编译指导属性，用于标记核心库core中的 ``panic!`` 宏要对接的函数（该函数实现对致命错误的具体处理）。该编译指导属性所标记的函数需要具有 ``fn(&PanicInfo) -> !`` 函数签名，函数可通过 ``PanicInfo`` 数据结构获取致命错误的相关信息。这样Rust编译器就可以把核心库core中的 ``panic!`` 宏定义与 ``#[panic_handler]`` 指向的panic函数实现合并在一起，使得no_std程序具有类似std库的应对致命错误的功能。

.. chyyuu https://doc.rust-lang.org/beta/unstable-book/language-features/lang-items.html

.. chyyuu  note::

..    **Rust Tips：语义项（lang_items）**

..    为了满足编译器和运行时库的灵活性，Rust 编译器内部的某些功能并不仅仅硬编码在语言内部来实现，而是以一种可插入的形式在库中提供，而且可以定制。标准库或第三方库只需要通过某种方式（在方法前面加上一个标记，称为`语义项`标记)，如 ``#[panic_handler]`` 、 ``#[]`` 、 ``#[]`` 、 ``#[]`` 等，即可告诉编译器它实现了编译器内部的哪些功能，编译器就会采用库提供的方法来替换它内部对应的功能。

我们创建一个新的子模块 ``lang_items.rs`` 实现panic函数，并通过 ``#[panic_handler]`` 属性通知编译器用panic函数来对接 ``panic!`` 宏。为了将该子模块添加到项目中，我们还需要在 ``main.rs`` 的 ``#![no_std]`` 的下方加上 ``mod lang_items;`` ，相关知识可参考 :ref:`Rust 模块编程 <rust-modular-programming>` ：

.. code-block:: rust
   :linenos:

   // os/src/lang_items.rs
   use core::panic::PanicInfo;

   #[panic_handler]
   fn panic(_info: &PanicInfo) -> ! {
       loop {}
   }

在把 ``panic_handler`` 配置在单独的文件 ``os/src/lang_items.rs`` 后，需要在os/src/main.rs文件中添加以下内容才能正常编译整个软件：

.. code-block:: rust
   :linenos:

   // os/src/main.rs
   #![no_std]
   mod lang_items;
   // ... other code

注意，panic 处理函数的函数签名需要一个 ``PanicInfo`` 的不可变借用作为输入参数，它在核心库中得以保留，这也是我们第一次与核心库打交道。之后我们会从 ``PanicInfo`` 解析出错位置并打印出来，然后杀死应用程序。但目前我们什么都不做只是在原地  ``loop`` 。



移除 main 函数
-----------------------------

我们再次重新编译简单的os程序，之前的 `#[panic_handler]` 函数缺失的错误消失了，但又出现了如下新的编译错误：
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

目前的主要代码包括 ``main.rs`` 和 ``lang_items.rs`` ，大致内容如下：

.. code-block:: rust
   :linenos:

   // os/src/main.rs
   #![no_main]
   #![no_std]
   mod lang_items;
   // ... other code


   // os/src/lang_items.rs
   use core::panic::PanicInfo;

   #[panic_handler]
   fn panic(_info: &PanicInfo) -> ! {
       loop {}
   }

本小节我们固然脱离了标准库，通过了编译器的检验，但也是伤筋动骨，将原有的很多功能弱化甚至直接删除，看起来距离在 RV64GC 平台上打印 ``Hello world!`` 相去甚远了（我们甚至连 ``println!`` 和 ``main`` 函数都删除了）。不要着急，接下来我们会以自己的方式来重塑这些基本功能，并最终完成我们的目标。

.. _rust-modular-programming:

.. note::

   **Rust Tips：Rust 模块化编程**

   将一个软件工程项目划分为多个子模块分别进行实现是一种被广泛应用的编程技巧，它有助于促进复用代码，并显著提升代码的可读性和可维护性。因此，众多编程语言均对模块化编程提供了支持，Rust 语言也不例外。

   每个通过 Cargo 工具创建的 Rust 项目均是一个模块，取决于 Rust 项目类型的不同，模块的根所在的位置也不同。当使用 ``--bin`` 创建一个可执行的 Rust 项目时，模块的根是 ``src/main.rs`` 文件；而当使用 ``--lib`` 创建一个 Rust 库项目时，模块的根是 ``src/lib.rs`` 文件。在模块的根文件中，我们需要声明所有可能会用到的子模块。如果不声明的话，即使子模块对应的文件存在，Rust 编译器也不会用到它们。如上面的代码片段中，我们就在根文件 ``src/main.rs`` 中通过 ``mod lang_items;`` 声明了子模块 ``lang_items`` ，该子模块实现在文件 ``src/lang_item.rs`` 中，我们将项目中所有的语义项放在该模块中。

   当一个子模块比较复杂的时候，它往往不会被放在一个独立的文件中，而是放在一个 ``src`` 目录下与子模块同名的子目录之下，在后面的章节中我们常会用到这种方法。例如第二章代码（参见代码仓库的 ``ch2`` 分支）中的 ``syscall`` 子模块就放在 ``src/syscall`` 目录下。对于这样的子模块，其所在目录下的 ``mod.rs`` 为该模块的根，其中可以进而声明它的子模块。同样，这些子模块既可以放在一个文件中，也可以放在一个目录下。

   每个模块可能会对其他模块公开一些变量、类型或函数，而该模块的其他内容则是对其他模块不可见的，也即其他模块不允许引用或访问这些内容。在模块内，仅有被显式声明为 ``pub`` 的内容才会对其他模块公开。Rust 类内部声明的属性域和方法也可以对其他类公开或是不对其他类公开，这取决于它们是否被声明为 ``pub`` 。我们在 C++/Java 语言中能够找到相同功能的关键字：即 ``public/private`` 。提供上述可见性机制的原因在于让其他类/模块能够访问当前类/模块公开提供的内容而无需关心它们是如何实现的，它们实际上也无法看到这些具体实现，因为这些具体实现并未向它们公开。编译器会对可见性进行检查，例如，当一个类/模块试图访问其他类/模块未公开的方法时，将无法通过编译。

   我们可以使用绝对路径或相对路径来引用其他模块或当前模块的内容。参考上面的 ``use core::panic::PanicInfo;`` ，类似 C++ ，我们将模块的名字按照层级由浅到深排列，并在相邻层级之间使用分隔符 ``::`` 进行分隔。路径的最后一级（如 ``PanicInfo``）则表示我们具体要引用或访问的内容，可能是变量、类型或者方法名。当通过绝对路径进行引用时，路径最开头可能是项目依赖的一个外部库的名字，或者是 ``crate`` 表示项目自身的根模块。在后面的章节中，我们会多次用到它们。

分析被移除标准库的程序
-----------------------------

对于上面这个被移除标准库的应用程序，通过了Rust编译器的检查和编译，形成了二进制代码。但这个二进制代码的内容是什么，它能否在RISC-V 64计算机上正常执行呢？为了分析这个二进制可执行程序，首先需要安装 cargo-binutils 工具集：

.. code-block:: console

   $ cargo install cargo-binutils
   $ rustup component add llvm-tools-preview

这样我们可以通过各种工具来分析目前的程序：

.. code-block:: console

   # 文件格式
   $ file target/riscv64gc-unknown-none-elf/debug/os
   target/riscv64gc-unknown-none-elf/debug/os: ELF 64-bit LSB executable, UCB RISC-V, ......

   # 文件头信息
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

   # 反汇编导出汇编程序
   $ rust-objdump -S target/riscv64gc-unknown-none-elf/debug/os
      target/riscv64gc-unknown-none-elf/debug/os:	file format elf64-littleriscv

通过 ``file`` 工具对二进制程序 ``os`` 的分析可以看到它好像是一个合法的 RISC-V 64 可执行程序，但通过 ``rust-readobj`` 工具进一步分析，发现它的入口地址 Entry 是 ``0`` ，从 C/C++ 等语言中得来的经验告诉我们， ``0`` 一般表示 NULL 或空指针，因此等于 ``0`` 的入口地址看上去无法对应到任何指令。再通过 ``rust-objdump`` 工具把它反汇编，可以看到没有生成汇编代码。所以，我们可以断定，这个二进制程序虽然合法，但它是一个空程序。产生该现象的原因是：目前我们的程序（参考上面的源代码）没有进行任何有意义的工作，由于我们移除了 ``main`` 函数并将项目设置为 ``#![no_main]`` ，它甚至没有一个传统意义上的入口点（即程序首条被执行的指令所在的位置），因此 Rust 编译器会生成一个空程序。

在下面几节，我们将建立有支持显示字符串的最小执行环境。

.. note::

   **在 x86_64 平台上移除标准库依赖**

   有兴趣的同学可以将目标平台换回之前默认的 ``x86_64-unknown-linux-gnu`` 并重复本小节所做的事情，比较两个平台从 ISA 到操作系统的差异。可以参考 `BlogOS 的相关内容 <https://os.phil-opp.com/freestanding-rust-binary/>`_ [#blogos]_ 。

.. note:: 

   本节内容部分参考自 `BlogOS 的相关章节 <https://os.phil-opp.com/freestanding-rust-binary/>`_ 。


.. [#exokernel] D. R. Engler, M. F. Kaashoek, and J. O'Toole. 1995. Exokernel: an operating system architecture for application-level resource management. In Proceedings of the fifteenth ACM symposium on Operating systems principles (SOSP '95). Association for Computing Machinery, New York, NY, USA, 251–266. 
.. [#blogos] https://os.phil-opp.com/freestanding-rust-binary/