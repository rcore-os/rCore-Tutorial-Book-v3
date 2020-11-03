移除标准库依赖
==========================

.. toctree::
   :hidden:
   :maxdepth: 4

本节我们尝试移除之前的 ``Hello world!`` 程序对于标准库的依赖，使得它能够编译到裸机平台 RV64GC 上。

我们首先在 ``os`` 目录下新建 ``.cargo`` 目录，并在这个目录下创建 ``config`` 文件，并在里面输入如下内容：

.. code-block::

   [build]
   target = "riscv64gc-unknown-none-elf"

这会对于 Cargo 工具在 os 目录下的行为进行调整：现在默认会使用 riscv64gc 作为目标平台而不是原先的默认 x86_64-unknown-linux-gnu。
事实上，这是一种编译器运行所在的平台与编译器生成可执行文件的目标平台不同（分别是后者和前者）的情况。这是一种 **交叉编译** (Cross Compile)。

当然，这只是使得我们之后在 ``cargo build`` 的时候不必再加上 ``--target`` 参数的一个小 trick。如果我们现在 ``cargo build`` ，还是会和
上一小节一样出现找不到标准库 std 的错误。于是我们开始着手移除标准库。当然，这会产生一些副作用。

移除 println! 宏
----------------------------------

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

我们之前提到过， println! 宏是由标准库 std 提供的，且会使用到一个名为 write 的系统调用。现在我们的条件还不足以自己实现一个 println! 宏，由于
使用了系统调用也不能在核心库 core 中找到它。我们目前先通过将它注释掉来绕过它。

提供语义项 panic_handler
----------------------------------------------------

.. error::

   .. code-block:: console

      $ cargo build
         Compiling os v0.1.0 (/home/shinbokuow/workspace/v3/rCore-Tutorial-v3/os)
      error: `#[panic_handler]` function required, but not found

在使用 Rust 编写应用程序的时候，我们常常在遇到了一些无法恢复的致命错误导致程序无法继续向下运行的时候手动或自动调用 panic! 宏来并打印出错的
位置让我们能够意识到它的存在，并进行一些后续处理。panic! 宏最典型的应用场景包括断言宏 assert! 失败或者对 ``Option::None/Result::Err`` 
进行 ``unwrap`` 操作。

在标准库 std 中提供了 panic 的处理函数 ``#[panic_handler]``，其大致功能是打印出错位置和原因并杀死当前应用。可惜的是在核心库 core 中并没有提供，
因此我们需要自己实现 panic 处理函数。

.. note::

   **Rust 语义项 lang_items**

   Rust 编译器内部的某些功能的实现并不是硬编码在语言内部的，而是以一种可插入的形式在库中提供。库只需要通过某种方式告诉编译器它的某个方法实现了
   编译器内部的哪些功能，编译器就会采用库提供的方法来实现它内部对应的功能。通常只需要在库的方法前面加上一个标记即可。

我们开一个新的子模块 ``lang_items.rs`` 保存这些语义项，在里面提供 panic 处理函数的实现并通过标记通知编译器采用我们的实现：

.. code-block:: rust

   // os/src/lang_items.rs
   use core::panic::PanicInfo;

   #[panic_handler]
   fn panic(_info: &PanicInfo) -> ! {
       loop {}
   }

注意，panic 处理函数的函数签名需要一个 ``PanicInfo`` 的不可变借用作为输入参数，它在核心库中得以保留，这也是我们第一次与核心库打交道。之后我们
会从 ``PanicInfo`` 解析出错位置并打印出来，然后杀死应用程序。但目前我们什么都不做只是在原地 loop。

移除 main 函数
-----------------------------

.. error::

   .. code-block::

      $ cargo build
         Compiling os v0.1.0 (/home/shinbokuow/workspace/v3/rCore-Tutorial-v3/os)
      error: requires `start` lang_item

编译器提醒我们缺少一个名为 ``start`` 的语义项。我们回忆一下，之前提到语言标准库和三方库作为应用程序的执行环境，需要负责在执行应用程序之前进行
一些初始化工作，然后才跳转到应用程序的入口点（也就是跳转到我们编写的 ``main`` 函数）开始执行。事实上 ``start`` 语义项正代表着标准库 std 在
执行应用程序之前需要进行的一些初始化工作。由于我们禁用了标准库，编译器也就找不到这项功能的实现了。

最简单的解决方案就是压根不让编译器使用这项功能。我们在 ``main.rs`` 的开头加入设置 ``#![no_main]`` 告诉编译器我们没有一般意义上的 ``main`` 函数，
并将原来的 ``main`` 函数删除。在失去了 ``main`` 函数的情况下，编译器也就不需要完成所谓的初始化工作了。

至此，我们成功移除了标准库的依赖并完成裸机平台上的构建。

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

本小节我们固然脱离了标准库，通过了编译器的检验，但也是伤筋动骨，将原有的很多功能弱化甚至直接删除，看起来距离在 RV64GC 平台上打印 
``Hello world!`` 相去甚远了（我们甚至连 println! 和 ``main`` 函数都删除了）。不要着急，接下来我们会以自己的方式来重塑这些
功能，并最终完成我们的目标。

.. note::

   **在 x86_64 平台上移除标准库依赖**

   有兴趣的同学可以将目标平台换回之前默认的 ``x86_64-unknown-linux-gnu`` 并重复本小节所做的事情，比较两个平台从 ISA 到操作系统
   的差异。可以参考 `BlogOS 的相关内容 <https://os.phil-opp.com/freestanding-rust-binary/>`_ 。