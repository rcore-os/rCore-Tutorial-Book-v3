互斥锁
===============================================

本节导读
-----------------------------------------------

引子：多线程计数器
-----------------------------------------------

我们知道，同进程下的线程共享进程的地址空间，因此它们均可以读写程序内的全局/静态数据。通过这种方式，线程可以非常方便的相互协作完成一项任务。下面是一个简单的例子，同学可以在 Linux/Windows 等系统上运行这段代码：

.. code-block:: rust
    :linenos:

    // adder.rs

    static mut A: usize = 0;
    const THREAD_COUNT: usize = 4;
    const PER_THREAD: usize = 10000;
    fn main() {
        let mut v = Vec::new();
        for _ in 0..THREAD_COUNT {
            v.push(std::thread::spawn(|| {
                unsafe {
                    for _ in 0..PER_THREAD {
                        A = A + 1;
                    }
                }
            }));
        }
        for handle in v {
            handle.join().unwrap();
        }
        println!("{}", unsafe { A });
    }

前一节中我们已经熟悉了多线程应用的编程方法。因此我们很容易看出这个程序开了 ``THREAD_COUNT`` 个线程，每个线程都将一个全局变量 ``A`` 加 1 ，次数为 ``PER_THREAD`` 次。从中可以看出多线程协作确实比较方便，因为我们只需将单线程上的代码（即第 11~13 行的主循环）提交给多个线程就从单线程得到了多线程版本。然而，这样确实能够达到我们预期的效果吗？

全局变量 ``A`` 的初始值为 ``0`` ，而 ``THREAD_COUNT`` 个线程每个将其加 1 重复 ``PER_THREAD`` 次，因此当所有的线程均完成任务之后，我们预期 ``A`` 的值应该是二者的乘积即 40000 。让我们尝试运行一下这个程序，可以看到类似下面的结果：

.. code-block:: console

    $ rustc adder.rs
    $ ./adder
    40000
    $ ./adder
    17444
    $ ./adder
    36364
    $ ./adder
    39552
    $ ./adder
    21397

可以看到只有其中一次的结果是正确的，其他的情况下结果都比较小且各不相同，这是为什么呢？我们可以尝试分析一下哪些因素会影响到代码的执行结果，使得结果与我们的预期不同。

1. 编译器在将源代码编译为汇编代码或者机器码的时候会进行一些优化。
2. 操作系统在执行程序的时候会进行调度。
3. CPU 在执行指令的时候会进行一些调度或优化。

那么按照顺序首先来检查第一步，即编译器生成的汇编代码是否正确。可以用如下命令反汇编可执行文件 ``adder`` 生成汇编代码 ``adder.asm`` ：

.. code-block:: console

    $ rust-objdump -D adder > adder.asm

在 ``adder.asm`` 中找到传给每个线程的闭包函数（这部分是我们自己写的，更容易出错）的汇编代码：

.. code-block::
    :linenos:

    # adder.asm
    000000000000bce0 <_ZN5adder4main28_$u7b$$u7b$closure$u7d$$u7d$17hfcc06370a766a1c4E>:
        bce0: subq    $56, %rsp
        bce4: movq    $0, 8(%rsp)
        bced: movq    $10000, 16(%rsp)        # imm = 0x2710
        bcf6: movq    8(%rsp), %rdi
        bcfb: movq    16(%rsp), %rsi
        bd00: callq   0xb570 <_ZN63_$LT$I$u20$as$u20$core..iter..traits..collect..IntoIterator$GT$9into_iter17h0e9595229a318c79E>
        bd05: movq    %rax, 24(%rsp)
        bd0a: movq    %rdx, 32(%rsp)
        bd0f: leaq    24(%rsp), %rdi
        bd14: callq   0xb560 <_ZN4core4iter5range101_$LT$impl$u20$core..iter..traits..iterator..Iterator$u20$for$u20$core..ops..range..Range$LT$A$GT$$GT$4next17h703752eeba5b7a01E>
        bd19: movq    %rdx, 48(%rsp)
        bd1e: movq    %rax, 40(%rsp)
        bd23: cmpq    $0, 40(%rsp)
        bd29: jne     0xbd30 <_ZN5adder4main28_$u7b$$u7b$closure$u7d$$u7d$17hfcc06370a766a1c4E+0x50>
        bd2b: addq    $56, %rsp
        bd2f: retq
        bd30: movq    328457(%rip), %rax      # 0x5c040 <_ZN5adder1A17hce2f3c024bd1f707E>
        bd37: addq    $1, %rax
        bd3b: movq    %rax, (%rsp)
        bd3f: setb    %al
        bd42: testb   $1, %al
        bd44: jne     0xbd53 <_ZN5adder4main28_$u7b$$u7b$closure$u7d$$u7d$17hfcc06370a766a1c4E+0x73>
        bd46: movq    (%rsp), %rax
        bd4a: movq    %rax, 328431(%rip)      # 0x5c040 <_ZN5adder1A17hce2f3c024bd1f707E>
        bd51: jmp     0xbd0f <_ZN5adder4main28_$u7b$$u7b$closure$u7d$$u7d$17hfcc06370a766a1c4E+0x2f>
        bd53: leaq    242854(%rip), %rdi      # 0x47200 <str.0>
        bd5a: leaq    315511(%rip), %rdx      # 0x58dd8 <writev@GLIBC_2.2.5+0x58dd8>
        bd61: leaq    -15080(%rip), %rax      # 0x8280 <_ZN4core9panicking5panic17h73f802489c27713bE>
        bd68: movl    $28, %esi
        bd6d: callq   *%rax
        bd6f: ud2
        bd71: nopw    %cs:(%rax,%rax)
        bd7b: nopl    (%rax,%rax)

虽然函数名经过了一些混淆，还是能看出这是程序 ``adder`` 的 ``main`` 函数中的一个闭包（Closure）。我们现在基于 x86_64 而不是 RISC-V 架构，因此会有一些不同：

- 指令的目标寄存器后置而不是像 RISC-V 一样放在最前面；
- 使用 ``%rax,%rdx,%rsi,%rdi`` 作为 64 位通用寄存器，观察代码可以发现 ``%rsi`` 和 ``%rdi`` 用来传参， ``%rax`` 和 ``%rdx`` 用来保存返回值；
- ``%rsp`` 是 64 位栈指针，功能与 RISC-V 中的 ``sp`` 相同；
- ``%rip`` 是 64 位指令指针，指向当前指令的下一条指令的地址，等同于我们之前介绍的 PC 寄存器。
- ``callq`` 为函数调用， ``retq`` 则为函数返回。

在了解了这些知识之后，我们可以尝试读一读代码：

- 第 3 行是在分配栈帧；
- 第 4~8 行准备参数，并调用标准库实现的 ``IntoIterator`` trait 的 ``into_iter`` 方法将 Range 0..10000 转化为一个迭代器；
- 第 9 行的 ``24(%rsp)`` 应该保存的是生成的迭代器的地址；
- 第 11 行开始进入主循环。第 11 行加载 ``24(%rsp)`` 到 ``%rdi`` 作为参数并在第 12 行调用 ``Iterator::next`` 函数，返回值在 ``%rdx`` 和 ``%rax`` 中并被保存在栈上。我们知道 ``Iterator::next`` 返回的是一个 ``Option<T>`` 。观察第 15-16 行，当 ``%rax`` 里面的值不为 0 的时候就跳转到 0xbd30 ，否则就向下执行到第 17-18 行回收栈帧并退出。这意味着 ``%rax`` 如果为 0 的话说明返回的是 ``None`` ，这时迭代器已经用尽，就可以退出函数了。于是，主循环的次数为 10000 次就定下来了。
- 0xbd30 （第 19 行）开始才真正进入 ``A=A+1`` 的部分。第 19 行从虚拟地址 0x5c040（这就是全局变量 ``A`` 的地址）加载一个 usize 到寄存器 ``%rax`` 中；第 20 行将 ``%rax`` 加一；第 26 行将寄存器 ``%rax`` 的值写回到虚拟地址 0x5c040 中。也就是说 ``A=A+1`` 是通过这三条指令达成。第 27 行无条件跳转到 0xbd0f 也就是第 11 行，进入下一轮循环。

.. note::

    **Rust Tips: Rust 的无符号溢出是不可恢复错误**

    有兴趣的同学可以读一读第 21~25 行代码，它可以判断在将 ``%rax`` 加一的时候是否出现溢出（注意其中复用了 ``%rax`` ，因此有一次额外的保存/恢复）。如果出现溢出的话则会跳转到 0xbd53（第 28 行）直接 panic 。

    从中我们可以看出，相比 C/C++ 来说 Rust 的确会生成更多的代码来针对算术溢出、数组越界的情况进行判断，但是这并不意味着在现代 CPU 上就会有很大的性能损失。如果可以确保不会出现溢出的情况，可以考虑使用 unsafe 的 ``usize::unchecked_add`` 来避免生成相关的判断代码并提高性能。

我们可以得出结论：编译器生成的汇编代码是符合我们的预期的。那么接下来进行第二步，操作系统的调度是否会影响结果的正确性呢？在具体分析之前，我们先对汇编代码进行简化，只保留直接与结果相关的部分。那么，可以看成每个线程进行 ``PER_THREAD`` 次操作，每次操作按顺序进行下面三个步骤：

1. 使用访存指令，从全局变量 ``A`` 的地址 addr 加载 ``A`` 的值到寄存器 reg；
2. 使用算术指令将寄存器 reg 的值加一；
3. 使用访存指令，将 reg 的值写回到全局变量 ``A`` 的地址 addr，至此 ``A`` 的值成功加一。

这是一个可以认为与具体指令集架构无关的过程。

