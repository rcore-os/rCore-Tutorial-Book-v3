实现应用程序
===========================

.. toctree::
   :hidden:
   :maxdepth: 5

本节导读
-------------------------------

本节主要讲解如何设计实现被批处理系统逐个加载并运行的应用程序。应用程序是假定在用户态（U 特权级模式）下运行的前提下而设计实现的。实际上，如果应用程序的代码都符合它要运行的用户态的约束，那它完全可能在用户态中运行；但如果应用程序执行特权指令或非法操作（如访问一个非法的地址等），那会产生异常，并导致程序退出。保证应用程序的代码在 U 模式运行是接下来将实现的批处理系统的关键任务之一。其涉及的设计实现要点是：

- 应用程序的内存布局
- 应用程序发出的系统调用

从某种程度上讲，这里设计的应用程序与第一章中的最小用户态执行环境有很多相同的地方。即设计一个应用程序和基本的支持功能库，这样应用程序在用户态通过操作系统提供的服务完成自身的任务。

应用程序设计
-----------------------------

应用程序、用户库（包括入口函数、初始化函数、I/O函数和系统调用接口等多个rs文件组成）放在项目根目录的 ``user`` 目录下，它和第一章的裸机应用不同之处主要在项目的目录文件结构和内存布局上：

- user/src/bin/*.rs：各个应用程序
- user/src/*.rs：用户库（包括入口函数、初始化函数、I/O函数和系统调用接口等）
- user/src/linker.ld：应用程序的内存布局说明

项目结构
^^^^^^^^^^^^^^^^^^^^^^

我们看到 ``user/src`` 目录下面多出了一个 ``bin`` 目录。``bin`` 里面有多个文件，目前里面至少有三个程序（一个文件是一个应用程序），分别是：

- ``00hello_world``：在屏幕上打印一行 ``Hello, world!``
- ``01store_fault``：访问一个非法的物理地址，测试批处理系统是否会被该错误影响
- ``02power``：不断在计算操作和打印字符串操作之间切换

批处理系统会按照文件名开头的数字编号从小到大的顺序加载并运行它们。

每个应用程序的实现都在对应的单个文件中。打开其中一个文件，会看到里面只有一个 ``main`` 函数和若干相关的函数所形成的整个应用程序逻辑。

我们还能够看到代码中尝试引入了外部库：

.. code-block:: rust

    #[macro_use]
    extern crate user_lib;

这个外部库其实就是 ``user`` 目录下的 ``lib.rs`` 以及它引用的若干子模块中。至于这个外部库为何叫 ``user_lib`` 而不叫 ``lib.rs`` 
所在的目录的名字 ``user`` ，是因为在 ``user/Cargo.toml`` 中我们对于库的名字进行了设置： ``name =  "user_lib"`` 。它作为 
``bin`` 目录下的源程序所依赖的用户库，等价于其他编程语言提供的标准库。

在 ``lib.rs`` 中我们定义了用户库的入口点 ``_start`` ：

.. code-block:: rust
    :linenos:

    #[no_mangle]
    #[link_section = ".text.entry"]
    pub extern "C" fn _start() -> ! {
        clear_bss();
        exit(main());
        panic!("unreachable after sys_exit!");
    }

第 2 行使用 Rust 的宏将 ``_start`` 这段代码编译后的汇编代码中放在一个名为 ``.text.entry`` 的代码段中，方便我们在后续链接的时候
调整它的位置使得它能够作为用户库的入口。

而从第 4 行开始我们能够看到进入用户库入口之后，首先和第一章一样手动清空需要被零初始化 ``.bss`` 段（很遗憾到目前为止底层的批处理系统还
没有这个能力，所以我们只能在用户库中完成），然后是调用 ``main`` 函数得到一个类型为 ``i32`` 的返回值。

第 5 行我们调用后面会提到的用户库提供的 ``exit`` 接口退出应用程序，并将这个返回值告知批处理系统。

我们还在 ``lib.rs`` 中看到了另一个 ``main`` ：

.. code-block:: rust
    :linenos:

    #[linkage = "weak"]
    #[no_mangle]
    fn main() -> i32 {
        panic!("Cannot find main!");
    }

第 1 行，我们使用 Rust 的宏将其函数符号 ``main`` 标志为弱链接。这样在最后链接的时候，虽然在 ``lib.rs`` 和 ``bin`` 目录下的某个
应用程序都有 ``main`` 符号，但由于 ``lib.rs`` 中的 ``main`` 符号是弱链接，链接器会使用 ``bin`` 目录下的应用主逻辑作为 ``main`` 。
这里我们主要是进行某种程度上的保护，如果在 ``bin`` 目录下找不到任何 ``main`` ，那么编译也能够通过，并会在运行时报错。

为了支持上述这些链接操作，我们需要在 ``lib.rs`` 的开头加入：

.. code-block:: rust

    #![feature(linkage)]


.. _term-app-mem-layout:

内存布局
^^^^^^^^^^^^^^^^^^^^^^

在 ``user/.cargo/config`` 中，我们和第一章一样设置链接时使用链接脚本 ``user/src/linker.ld`` 。在其中我们做的重要的事情是：

- 将程序的起始物理地址调整为 ``0x80400000`` ，三个应用程序都会被加载到这个物理地址上运行；
- 将 ``_start`` 所在的 ``.text.entry`` 放在整个程序的开头，也就是说批处理系统只要在加载之后跳转到 ``0x80400000`` 就已经进入了
  用户库的入口点，并会在初始化之后跳转到应用程序主逻辑；
- 提供了最终生成可执行文件的 ``.bss`` 段的起始和终止地址，方便 ``clear_bss`` 函数使用。

其余的部分和第一章基本相同。

.. _term-call-syscall:

系统调用
^^^^^^^^^^^^^^^^^^^^^^

在子模块 ``syscall`` 中我们作为应用程序来通过 ``ecall`` 调用批处理系统提供的接口，由于应用程序运行在用户态（即 U 模式）， ``ecall`` 指令会触发 
名为 ``Environment call from U-mode`` 的异常，并 Trap 进入 S 模式执行批处理系统针对这个异常特别提供的服务代码。由于这个接口处于 
S 模式的批处理系统和 U 模式的应用程序之间，从上一节我们可以知道，这个接口可以被称为 ABI 或者系统调用。现在我们不关心底层的批处理系统如何
提供应用程序所需的功能，只是站在应用程序的角度去使用即可。

在本章中，应用程序和批处理系统之间按照API的结构，约定如下两个系统调用：

.. code-block:: rust
    :caption: 第二章新增系统调用

    /// 功能：将内存中缓冲区中的数据写入文件。
    /// 参数：`fd` 表示待写入文件的文件描述符；
    ///      `buf` 表示内存中缓冲区的起始地址；
    ///      `len` 表示内存中缓冲区的长度。
    /// 返回值：返回成功写入的长度。
    /// syscall ID：64               
    fn sys_write(fd: usize, buf: *const u8, len: usize) -> isize;

    /// 功能：退出应用程序并将返回值告知批处理系统。
    /// 参数：`xstate` 表示应用程序的返回值。
    /// 返回值：该系统调用不应该返回。
    /// syscall ID：93
    fn sys_exit(xstate: usize) -> !;

我们知道系统调用实际上是汇编指令级的二进制接口，因此这里给出的只是使用 Rust 语言描述的API版本。在实际调用的时候，我们需要按照 RISC-V 调用
规范（即ABI格式）在合适的寄存器中放置系统调用的参数，然后执行 ``ecall`` 指令触发 Trap。在 Trap 回到 U 模式的应用程序代码之后，会从 ``ecall`` 的
下一条指令继续执行，同时我们能够按照调用规范在合适的寄存器中读取返回值。


.. note::

   RISC-V 寄存器编号和别名

   RISC-V 寄存器编号从 ``0~31`` ，表示为 ``x0~x31`` 。 其中：

   -  ``x10~x17`` : 对应  ``a0~a7`` 
   -  ``x1`` ：对应 ``ra`` 

在 RISC-V 调用规范中，和函数调用的ABI情形类似，约定寄存器 ``a0~a6`` 保存系统调用的参数， ``a0~a1`` 保存系统调用的返回值。有些许不同的是
寄存器 ``a7`` 用来传递 syscall ID，这是因为所有的 syscall 都是通过 ``ecall`` 指令触发的，除了各输入参数之外我们还额外需要一个寄存器
来保存要请求哪个系统调用。由于这超出了 Rust 语言的表达能力，我们需要在代码中使用内嵌汇编来完成参数/返回值绑定和 ``ecall`` 指令的插入：

.. code-block:: rust
    :linenos:

    // user/src/syscall.rs

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

第 3 行，我们将所有的系统调用都封装成 ``syscall`` 函数，可以看到它支持传入 syscall ID 和 3 个参数。

第 6 行开始，我们使用 Rust 提供的 ``llvm_asm!`` 宏在代码中内嵌汇编，在本行也给出了具体要插入的汇编指令，也就是 ``ecall``，但这并不是
全部，后面我们还需要进行一些相关设置。这个宏在 Rust 中还不稳定，因此我们需要在 ``lib.rs`` 开头加入 ``#![feature(llvm_asm)]`` 。
此外，编译器无法判定插入汇编代码这个行为的安全性，所以我们需要将其包裹在 unsafe 块中自己来对它负责。

Rust 中的 ``llvm_asm!`` 宏的完整格式如下：

.. code-block:: rust

   llvm_asm!(assembly template
      : output operands
      : input operands
      : clobbers
      : options
   );

下面逐行进行说明。

第 7 行指定输出操作数。这里由于我们的系统调用返回值只有一个 ``isize`` ，根据调用规范它会被保存在 ``a0`` 寄存器中。在双引号内，我们
可以对于使用的操作数进行限制，由于是输出部分，限制的开头必须是一个 ``=`` 。我们可以在限制内使用一对花括号再加上一个寄存器的名字告诉
编译器汇编的输出结果会保存在这个寄存器中。我们将声明出来用来保存系统调用返回值的变量 ``ret`` 包在一对普通括号里面放在操作数限制的
后面，这样可以把变量和寄存器建立联系。于是，在系统调用返回之后我们就能在变量 ``ret`` 中看到返回值了。注意，变量 ``ret`` 必须为可变
绑定，否则无法通过编译，这也说明在 unsafe 块内编译器还是会进行力所能及的安全检查。

第 8 行指定输入操作数。由于是输入部分，限制的开头不用加上 ``=`` 。同时在限制中设置使用寄存器 ``a0~a2`` 来保存系统调用的参数，以及
寄存器 ``a7`` 保存 syscall ID ，而它们分别 ``syscall`` 的参数变量 ``args`` 和 ``id`` 绑定。

第 9 行用于告知编译器插入的汇编代码会造成的一些影响以防止编译器在不知情的情况下误优化。常用的使用方法是告知编译器某个寄存器在执行嵌入
的汇编代码中的过程中会发生变化。我们这里则是告诉编译器：程序在执行嵌入汇编代码中指令的时候会修改内存。这能给编译器提供更多信息以生成正确的代码。

第 10 行用于告知编译器将我们在程序中给出的嵌入汇编代码保持原样放到最终构建的可执行文件中。如果不这样做的话，编译器可能会把它和其他代码
一视同仁并放在一起进行一些我们期望之外的优化。为了保证语义的正确性，一些比较关键的汇编代码需要加上该选项。

上面这一段汇编代码的含义和内容与第一章中的 :ref:`第一章中U-Mode应用程序中的系统调用汇编代码 <term-llvm-syscall>` 的是一致的，且与 :ref:`第一章中的RustSBI输出到屏幕的SBI调用汇编代码 <term-llvm-sbicall>` 涉及的汇编指令一样，但传递参数的寄存器的含义是不同的。有兴趣的读者可以回顾第一章的 ``console.rs`` 和 ``sbi.rs`` 。

.. note::

   **Rust 语法卡片：内联汇编**

   我们这里使用的 ``llvm_asm!`` 宏是将 Rust 底层 IR LLVM 中提供的内联汇编包装成的，更多信息可以参考 `llvm_asm 文档 <https://doc.rust-lang.org/unstable-book/library-features/llvm-asm.html>`_ 。 

   在未来的 Rust 版本推荐使用功能更加强大且方便易用的 ``asm!`` 宏，但是目前还未稳定，可以查看 `inline-asm RFC <https://doc.rust-lang.org/beta/unstable-book/library-features/asm.html>`_ 了解最新进展。

于是 ``sys_write`` 和 ``sys_exit`` 只需将 ``syscall`` 进行包装：

.. code-block:: rust
    :linenos:

    // user/src/syscall.rs

    const SYSCALL_WRITE: usize = 64;
    const SYSCALL_EXIT: usize = 93;

    pub fn sys_write(fd: usize, buffer: &[u8]) -> isize {
        syscall(SYSCALL_WRITE, [fd, buffer.as_ptr() as usize, buffer.len()])
    }

    pub fn sys_exit(xstate: i32) -> isize {
        syscall(SYSCALL_EXIT, [xstate as usize, 0, 0])
    }

.. _term-fat-pointer:

注意 ``sys_write`` 使用一个 ``&[u8]`` 切片类型来描述缓冲区，这是一个 **胖指针** (Fat Pointer)，里面既包含缓冲区的起始地址，还
包含缓冲区的长度。我们可以分别通过 ``as_ptr`` 和 ``len`` 方法取出它们并独立的作为实际的系统调用参数。

我们将上述两个系统调用在用户库 ``user_lib`` 中进一步封装，从而更加接近在 Linux 等平台的实际体验：

.. code-block:: rust
    :linenos:

    // user/src/lib.rs
    use syscall::*;

    pub fn write(fd: usize, buf: &[u8]) -> isize { sys_write(fd, buf) }
    pub fn exit(exit_code: i32) -> isize { sys_exit(exit_code) }

我们把 ``console`` 子模块中 ``Stdout::write_str`` 改成基于 ``write`` 的实现，且传入的 ``fd`` 参数设置为 1，它代表标准输出，
也就是输出到屏幕。目前我们不需要考虑其他的 ``fd`` 选取情况。这样，应用程序的 ``println!`` 宏借助系统调用变得可用了。
参考下面的代码片段：

.. code-block:: rust
    :linenos:

    // user/src/console.rs
    const STDOUT: usize = 1;

    impl Write for Stdout {
        fn write_str(&mut self, s: &str) -> fmt::Result {
            write(STDOUT, s.as_bytes());
            Ok(())
        }
    }

``exit`` 接口则在用户库中的 ``_start`` 内使用，当应用程序主逻辑 ``main`` 返回之后，使用它退出应用程序并将返回值告知
底层的批处理系统。



编译生成应用程序二进制码
-------------------------------

这里简要介绍一下应用程序的自动构建。只需要在 ``user`` 目录下 ``make build`` 即可：

1. 对于 ``src/bin`` 下的每个应用程序，在 ``target/riscv64gc-unknown-none-elf/release`` 目录下生成一个同名的 ELF 可执行文件；
2. 使用 objcopy 二进制工具将上一步中生成的 ELF 文件删除所有 ELF header 和符号得到 ``.bin`` 后缀的纯二进制镜像文件。它们将被链接
   进内核并由内核在合适的时机加载到内存。

实现操作系统前执行应用程序
----------------------------------- 

我们还没有实现操作系统，能提前执行或测试应用程序吗？可以！ 这是因为我们除了一个能模拟一台RISC-V 64 计算机的全系统模拟器 ``qemu-system-riscv64`` 外，还有一个 :ref:`直接支持运行RISC-V64 用户程序的半系统模拟器qemu-riscv64 <term-qemu-riscv64>` 。

.. note::

   如果想让用户态应用程序在Linux和在我们自己写的OS上执行效果一样，需要做到二者的系统调用的接口是一样的（包括系统调用编号，参数约定的具体的寄存器和栈等）。


.. _term-csr-instr-app:

假定我们已经完成了编译并生成了ELF 可执行文件格式的应用程序，我们就可以来试试。首先看看应用程序执行 :ref:`RV64的S模式特权指令 <term-csr-instr>` 会出现什么情况。

.. note::

   下载编译特权指令的应用需要获取

   .. code-block:: console

    $ git clone -b v4-illegal-priv-code-csr-in-u-mode-app https://github.com/chyyuu/os_kernel_lab.git
    $ cd os_kernel_lab/user
    $ make build

我们先看看代码：

.. code-block:: rust
    :linenos:

    // usr/src/bin/03priv_intr.rs
    ...
        println!("Hello, world!");
        unsafe {
            llvm_asm!("sret"
                : : : :
            );
        }
    ...

在上述代码中，在显示 ``Hello, world`` 字符串后，会执行 ``sret`` 特权指令。

.. code-block:: rust
    :linenos:

    // usr/src/bin/04priv_intr.rs
    ...
        println!("Hello, world!");
        let mut sstatus = sstatus::read();
        sstatus.set_spp(SPP::User);
    ...

在上述代码中，在显示 ``Hello, world`` 字符串后，会读写 ``sstatus`` 特权CSR。

.. code-block:: console

   $ cd user
   $ cd target/riscv64gc-unknown-none-elf/release/ 
   $ ls
    00hello_world      01store_fault      02power   
    03priv_intr      04priv_csr
    ...
   # 上面的文件就是ELF格式的应用程序
   $ qemu-riscv64 ./03priv_intr
     Hello, world!
     非法指令 (核心已转储)
   # 执行特权指令出错
   $ qemu-riscv64 ./04priv_csr
     Hello, world!
     非法指令 (核心已转储)
   # 执行访问特权级CSR的指令出错

看来RV64的特权级机制确实有用。那对于一般的应用程序，在 ``qemu-riscv64`` 模拟器下能正确执行吗？

.. code-block:: console

   $ cd user
   $ cd target/riscv64gc-unknown-none-elf/release/ 
   $ ls
    00hello_world      01store_fault      02power   
    03priv_intr      04priv_csr
    ...
   # 上面的文件就是ELF格式的应用程序
   $ qemu-riscv64 ./00hello_world
     Hello, world!
   # 正确显示了字符串   
   $ qemu-riscv64 01store_fault
     qemu-riscv64 01store_fault
     Into Test store_fault, we will insert an invalid store operation...
     Kernel should kill this application!
     段错误 (核心已转储)
   # 故意访问了一个非法地址，导致应用和qemu-riscv64被Linux内核杀死
   $ qemu-riscv64 02power
    3^10000=5079
    3^20000=8202
    3^30000=8824
    3^40000=5750
    3^50000=3824
    3^60000=8516
    3^70000=2510
    3^80000=9379
    3^90000=2621
    3^100000=2749
    Test power OK!
   # 正确地完成了计算

三个应用都能够执行并顺利结束！是由于得到了本机操作系统Linux的支持。我们期望我们在下一节开始实现的泥盆纪“邓式鱼”操作系统也能够正确加载和执行上面的应用程序。
