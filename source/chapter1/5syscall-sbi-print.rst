格式化输出
=====================

.. toctree::
   :hidden:
   :maxdepth: 5

这一小节我们要让我们的执行环节来自己实现 ``println!`` 的功能。按照从难到


 我们这里只是给出一些函数之间的调用关系，而不在这里进行一些实现细节上的展开。有兴趣的读者
可以自行参考代码提供的注释。

在屏幕上打印一个字符是最基础的功能，它已经由 bootloader （也就是放在 ``bootloader`` 目录下的预编译版本）提供，具体的调用方法可以参考 
``sbi.rs`` 中的 ``console_putchar`` 函数。

随后我们在 ``console.rs`` 中利用 ``console_putchar`` 来实现 ``print!`` 和 ``println!`` 两个宏。有兴趣的读者可以去代码注释中
参考有关 Rust ``core::fmt`` 库和宏编写的相关知识。在 ``main.rs`` 声明子模块 ``mod console`` 的时候加上 ``#[macro_use]`` 来让
整个引用都可以使用到该模块里面定义的宏。

接着我们在 ``lang_items.rs`` 中修改 panic 时的行为：

.. code-block:: rust

    // os/src/lang_items.rs
    use crate::sbi::shutdown;

    #[panic_handler]
    fn panic(info: &PanicInfo) -> ! {
        if let Some(location) = info.location() {
            println!("Panicked at {}:{} {}", location.file(), location.line(), info.message().unwrap());
        } else {
            println!("Panicked: {}", info.message().unwrap());
        }
        shutdown()
    }

我们尝试从传入的 ``PanicInfo`` 中解析 panic 发生的文件和行数。如果解析成功的话，就和 panic 的报错信息一起打印出来。我们需要在 
``main.rs`` 开头加上 ``#![feature(panic_info_message)]`` 才能通过 ``PanicInfo::message`` 获取报错信息。

.. note::

    **Rust 小知识： 错误处理**

    Rust 中常利用 ``Option<T>`` 和 ``Result<T, E>`` 进行方便的错误处理。它们都属于枚举结构：

    - ``Option<T>`` 既可以有值 ``Option::Some<T>`` ，也有可能没有值 ``Option::None``；
    - ``Result<T, E>`` 既可以保存某个操作的返回值 ``Result::Ok<T>`` ，也可以表明操作过程中出现了错误 ``Result::Err<E>`` 。

    我们可以使用 ``Option/Result`` 来保存一个不能确定存在/不存在或是成功/失败的值。之后可以通过匹配 ``if let`` 或是在能够确定
    的场合直接通过 ``unwrap`` 将里面的值取出。详细的内容可以参考 Rust 官方文档。


此外，我们还使用 bootloader 中提供的另一个接口 ``shutdown`` 关闭机器。

最终我们的应用程序 ``rust_main`` 如下：

.. code-block:: rust

    // os/src/main.rs
    
    #[no_mangle]
    pub fn rust_main() -> ! {
        extern "C" {
            fn stext();
            fn etext();
            fn srodata();
            fn erodata();
            fn sdata();
            fn edata();
            fn sbss();
            fn ebss();
            fn boot_stack();
            fn boot_stack_top();
        };
        clear_bss();
        println!("Hello, world!");
        println!(".text [{:#x}, {:#x})", stext as usize, etext as usize);
        println!(".rodata [{:#x}, {:#x})", srodata as usize, erodata as usize);
        println!(".data [{:#x}, {:#x})", sdata as usize, edata as usize);
        println!("boot_stack [{:#x}, {:#x})", boot_stack as usize, boot_stack_top as usize);
        println!(".bss [{:#x}, {:#x})", sbss as usize, ebss as usize);
        panic!("Shutdown machine!");
    }

当我们在 qemu 平台上运行的时候能够看到如下的运行结果：

.. code-block::
    :linenos:

    [rustsbi] Version 0.1.0
    .______       __    __      _______.___________.  _______..______   __
    |   _  \     |  |  |  |    /       |           | /       ||   _  \ |  |
    |  |_)  |    |  |  |  |   |   (----`---|  |----`|   (----`|  |_)  ||  |
    |      /     |  |  |  |    \   \       |  |      \   \    |   _  < |  |
    |  |\  \----.|  `--'  |.----)   |      |  |  .----)   |   |  |_)  ||  |
    | _| `._____| \______/ |_______/       |__|  |_______/    |______/ |__|

    [rustsbi] Platform: QEMU
    [rustsbi] misa: RV64ACDFIMSU
    [rustsbi] mideleg: 0x222
    [rustsbi] medeleg: 0xb109
    [rustsbi] Kernel entry: 0x80020000
    Hello, world!
    .text [0x80020000, 0x80022000)
    .rodata [0x80022000, 0x80023000)
    .data [0x80023000, 0x80023000)
    boot_stack [0x80023000, 0x80033000)
    .bss [0x80033000, 0x80033000)
    Panicked at src/main.rs:46 Shutdown machine!


其中前 13 行是 bootloader 的输出，剩下的部分是我们的应用程序的输出，打印了 ``Hello, world!``，输出了程序内部各个段的地址区间，
还展示了 panic 相关信息。