.. _term-print-kernelminienv:

构建裸机执行环境
=================================

.. toctree::
   :hidden:
   :maxdepth: 5

本节导读
-------------------------------

本节开始我们将着手自己来实现裸机上的最小执行环境，即我们的“三叶虫”操作系统，并能在裸机上运行 ``Hello, world!`` 程序。
有了上一节实现的用户态的最小执行环境，我们可以稍加改造，就可以完成裸机上的最小执行环境了。与上节不同，“恐龙虾”操作系统运行在用户态，通过下层的操作系统来帮助完成内存布局、初始化、显示字符串和关闭。由于我们选择的Rust编译器的目标平台 ``riscv64gc-unknown-none-elf`` 是假设没有任何操作系统支持的，所以在上节编写的程序中，需要禁用需要操作系统支持的标准库，并移除默认的 main 函数
入口。最终我们通过实现 ``_start`` 函数来代替了传统的 main 函数，并通过汇编实现的系统调用接口，来输出 ``Hello, world!`` 。


我们在上一小节提到过，一个应用程序的运行离不开下面多层执行环境栈的支撑。而“恐龙虾”操作系统本质上是一个没有std标准库支持的特殊的用户态应用程序。
在目前广泛使用的操作系统上，它就至少需要经历以下层层递进的初始化过程：

- 启动OS：硬件启动后，会有一段代码（一般统称为bootloader）对硬件进行初始化，让包括内核在内的系统软件得以运行；
- OS准备好应用程序执行的环境：要运行该应用程序的时候，内核分配相应资源，将程序代码和数据载入内存，并赋予 CPU 使用权，由此应用程序可以运行；
- 应用程序开始执行：程序员编写的代码是应用程序的一部分，它需要标准库/核心库进行一些初始化工作后才能运行。


而“三叶虫”操作系统的下面是没有操作系统了，它需要关注地方主要是：

- 物理内存的 DRAM 位置（放应用程序的地方）和应用程序的内存布局（如何在 DRAM 中放置应用程序的各个部分）
- SBI 的字符输出接口（执行环境提供的输出字符服务，可以被应用程序使用）
- 应用程序的初始化（起始的指令位置，对 ``栈 stack`` 和 ``bss`` 的初始化）


了解硬件组成和裸机启动过程
----------------------------

在这一小节，我们介绍如何进行裸机层面的 **执行环境初始化** ， 即我们需要知道具体需要做哪些初始化工作才能支持
应用程序在裸机上的运行。而这又需要明确三点：

- 首先，应用程序的裸机硬件系统是啥样子的？
- 其次，计算机系统在做这些初始化工作之前处于什么状态？
- 最后，在做完初始化工作也就是即将执行 main 入口函数之前，计算机系统又处于什么状态？


硬件组成
^^^^^^^^^^^^^^^^^^^^^^

我们采用的是QEMU软件 ``qemu-system-riscv64`` 来模拟一台RISC-V 64计算机，具体的硬件规格是：
 - 外设：16550A UART，virtio-net/block/console/gpu等和设备树
 - 硬件特权级：priv v1.10， user v2.2
 - 中断控制器：可参数化的CLINT（核心本地中断器）、可参数化的PLIC（平台级中断控制器）
 - 可参数化的RAM内存
 - 可配置的多核 RV64GC M/S/U mode CPU

这里列出的硬件功能很多还用不上，不过在后面的章节中会逐步用到上面的硬件功能，以支持更加强大的操作系统能力。

在QEMU模拟的硬件中，物理内存和外设都是通过对内存读写的方式来进行访问，下面列出了QEMU模拟的物理内存空间。

.. code-block:: c

    // qemu/hw/riscv/virt.c
    static const struct MemmapEntry {
        hwaddr base;
        hwaddr size;
    } virt_memmap[] = {
        [VIRT_DEBUG] =       {        0x0,         0x100 },
        [VIRT_MROM] =        {     0x1000,        0xf000 },
        [VIRT_TEST] =        {   0x100000,        0x1000 },
        [VIRT_RTC] =         {   0x101000,        0x1000 },
        [VIRT_CLINT] =       {  0x2000000,       0x10000 },
        [VIRT_PCIE_PIO] =    {  0x3000000,       0x10000 },
        [VIRT_PLIC] =        {  0xc000000, VIRT_PLIC_SIZE(VIRT_CPUS_MAX * 2) },
        [VIRT_UART0] =       { 0x10000000,         0x100 },
        [VIRT_VIRTIO] =      { 0x10001000,        0x1000 },
        [VIRT_FLASH] =       { 0x20000000,     0x4000000 },
        [VIRT_PCIE_ECAM] =   { 0x30000000,    0x10000000 },
        [VIRT_PCIE_MMIO] =   { 0x40000000,    0x40000000 },
        [VIRT_DRAM] =        { 0x80000000,           0x0 },
    };


在上面的代码中，需要注意的两个比较重要的内容是：
 - VIRT_DRAM：这是计算机的物理内存，DRAM的内存起始地址是 ``0x80000000`` ，缺省大小为128MB。在本书中一般限制为8MB。
 - VIRT_UART0：这是串口的控制寄存器区域，串口相关的寄存器起始地址是 ``0x10000000`` ，范围是 ``0x100`` ，我们通过访问这段特殊的区域来实现字符输入输出的管理与控制。

.. _term-bootloader:


裸机启动过程
^^^^^^^^^^^^^^^^^^

.. note::

  **QEMU 模拟 CPU 加电的执行过程**

  CPU加电后的执行细节与具体硬件相关，我们这里以QEMU模拟器为具体例子简单介绍一下。
  
  这需要从 CPU 加电后如何初始化，如何执行第一条指令开始讲起。对于我们采用的QEMU模拟器而言，它模拟了一台标准的RISC-V64计算机。我们启动QEMU时，通过设置参数，可控制QEMU模拟的RISC-V64计算机在其模拟的内存中的固定位置放置BootLoader程序和操作系统的二进制代码。这样，QEMU模拟的RISC-V64计算机在启动后，从这个固定位置开始执行就可以让BootLoader程序开始执行了。

  这可以通过查看 ``os/Makefile`` 文件中包含 ``qemu-system-riscv64`` 的相关内容来了解。
  
  -  ``-bios $(BOOTLOADER)`` 这个参数意味着硬件内存中的固定位置 ``0x80000000`` 处放置了一个BootLoader程序--RustSBI（戳 :doc:`../appendix-c/index` 可以进一步了解RustSBI。）。
  -  ``-device loader,file=$(KERNEL_BIN),addr=$(KERNEL_ENTRY_PA)`` 这个参数表示硬件内存中的特定位置 ``$(KERNEL_ENTRY_PA)`` 放置了操作系统的二进制代码 ``$(KERNEL_BIN)`` 。 ``$(KERNEL_ENTRY_PA)`` 的值是 ``0x80200000`` 。
  
  当我们执行包含上次启动参数的qemu-system-riscv64软件，就意味给这台虚拟的RISC-V64计算机加电了。此时，CPU的其它通用寄存器清零，
  而PC寄存器会指向 ``0x1000`` 的位置。
  这个 ``0x1000`` 位置上是CPU加电后执行的第一条指令（固化在硬件中的一小段引导代码），它会很快跳转到 ``0x80000000`` 处，
  即BootLoader程序--RustSBI的第一条指令。RustSBI完成基本的硬件初始化后，
  会跳转操作系统的二进制代码 ``$(KERNEL_BIN)`` 所在内存位置 ``0x80200000`` ，执行操作系统的第一条指令。
  这时我们的编写的操作系统才开始正式工作。

  为啥在 ``0x80000000`` 放置 ``Bootloader`` ？因为这是QEMU的硬件模拟代码中设定好的 ``Bootloader`` 的起始地址。

  为啥在 ``0x80200000`` 放置 ``os`` ？因为这是 ``Bootloader--RustSBI`` 的代码中设定好的 ``os``  的起始地址。


.. note::

  **操作系统与SBI之间是啥关系？**

  SBI是RISC-V的一种底层规范，操作系统内核与实现SBI规范的RustSBI的关系有点象应用与操作系统内核的关系，后者向前者提供一定的服务。只是SBI提供的服务很少，
  能帮助操作系统内核完成的功能有限，但这些功能很底层，很重要，比如关机，显示字符串等。通过操作系统内核也能直接实现，但比较繁琐，如果RustSBI提供了服务，
  那么操作系统内核直接调用就好了。


.. warning::

   chyyuu **FIXME: 提供一下分析展示**


实现关机功能
----------------------------

如果在裸机上的应用程序执行完毕并通知操作系统后，那么操作系统就没事干了，实现正常关机是一个合理的选择。所以我们要让“三叶虫”操作系统能够正常关机，这是需要调用SBI提供的关机功能 ``SBI_SHUTDOWN`` ，这与上一节的 ``SYSCALL_EXIT`` 类似，
只是在具体参数上有所不同。在上一节完成的没有显示功能的用户态最小化执行环境基础上，修改后的代码如下：

.. _term-llvm-sbicall:

.. code-block:: rust

    // bootloader/rustsbi-qemu.bin 直接添加的SBI规范实现的二进制代码，给操作系统提供基本支持服务

    // os/src/sbi.rs
    fn sbi_call(which: usize, arg0: usize, arg1: usize, arg2: usize) -> usize {
        let mut ret;
        unsafe {
            llvm_asm!("ecall"
                : "={x10}" (ret)
                : "{x10}" (arg0), "{x11}" (arg1), "{x12}" (arg2), "{x17}" (which)
    ...

    // os/src/main.rs
    const SBI_SHUTDOWN: usize = 8;

    pub fn shutdown() -> ! {
        sbi_call(SBI_SHUTDOWN, 0, 0, 0);
        panic!("It should shutdown!");
    }

    #[no_mangle]
    extern "C" fn _start() {
        shutdown();
    }




也许有同学比较迷惑，应用程序访问操作系统提供的系统调用的指令是 ``ecall`` ，操作系统访问
RustSBI提供的SBI服务的SBI调用的指令也是 ``ecall`` 。
这其实是没有问题的，虽然指令一样，但它们所在的特权级和特权级转换是不一样的。简单地说，应用程序位于最弱的用户特权级（User Mode），操作系统位于
很强大的内核特权级（Supervisor Mode），RustSBI位于完全掌控机器的机器特权级（Machine Mode），通过 ``ecall`` 指令，可以完成从弱的特权级
到强的特权级的转换。可以看下一章的进一步描述来了解具体细节。在这里，只要知道，如果“三叶虫”操作系统正确地向RustSBI发出了停机的SBI服务请求，
那么RustSBI能够通知QEMU模拟的RISC-V计算机停机（即 ``qemu-system-riscv64`` 软件能正常退出），就行了。

下面是编译执行，结果如下：


.. code-block:: console

  # 编译生成ELF格式的执行文件
  $ cargo build --release
   Compiling os v0.1.0 (/media/chyyuu/ca8c7ba6-51b7-41fc-8430-e29e31e5328f/thecode/rust/os_kernel_lab/os)
    Finished release [optimized] target(s) in 0.15s
  # 把ELF执行文件转成bianary文件
  $ rust-objcopy --binary-architecture=riscv64 target/riscv64gc-unknown-none-elf/release/os --strip-all -O binary target/riscv64gc-unknown-none-elf/release/os.bin

  #加载运行
  $ qemu-system-riscv64 -machine virt -nographic -bios ../bootloader/rustsbi-qemu.bin -device loader,file=target/riscv64gc-unknown-none-elf/release/os.bin,addr=0x80200000
  # 无法退出，风扇狂转，感觉碰到死循环

这样的结果是我们不期望的。问题在哪？仔细查看和思考，操作系统的入口地址不对！对 ``os`` ELF执行程序，通过rust-readobj分析，看到的入口地址不是
RustSBIS约定的 ``0x80200000`` 。我们需要修改 ``os`` ELF执行程序的内存布局。


设置正确的程序内存布局
----------------------------

.. _term-linker-script:

我们可以通过 **链接脚本** (Linker Script) 调整链接器的行为，使得最终生成的可执行文件的内存布局符合我们的预期。
我们修改 Cargo 的配置文件来使用我们自己的链接脚本 ``os/src/linker.ld`` 而非使用默认的内存布局：

.. code-block::
    :linenos:
    :emphasize-lines: 5,6,7,8

    // os/.cargo/config
    [build]
    target = "riscv64gc-unknown-none-elf"

    [target.riscv64gc-unknown-none-elf]
    rustflags = [
        "-Clink-arg=-Tsrc/linker.ld", "-Cforce-frame-pointers=yes"
    ]

具体的链接脚本 ``os/src/linker.ld`` 如下：

.. code-block::
    :linenos:

    OUTPUT_ARCH(riscv)
    ENTRY(_start)
    BASE_ADDRESS = 0x80200000;

    SECTIONS
    {
        . = BASE_ADDRESS;
        skernel = .;

        stext = .;
        .text : {
            *(.text.entry)
            *(.text .text.*)
        }

        . = ALIGN(4K);
        etext = .;
        srodata = .;
        .rodata : {
            *(.rodata .rodata.*)
        }

        . = ALIGN(4K);
        erodata = .;
        sdata = .;
        .data : {
            *(.data .data.*)
        }

        . = ALIGN(4K);
        edata = .;
        .bss : {
            *(.bss.stack)
            sbss = .;
            *(.bss .bss.*)
        }

        . = ALIGN(4K);
        ebss = .;
        ekernel = .;

        /DISCARD/ : {
            *(.eh_frame)
        }
    }

第 1 行我们设置了目标平台为 riscv ；第 2 行我们设置了整个程序的入口点为之前定义的全局符号 ``_start``；
第 3 行定义了一个常量 ``BASE_ADDRESS`` 为 ``0x80200000`` ，也就是我们之前提到的期望我们自己实现的初始化代码被放在的地址；

从第 5 行开始体现了链接过程中对输入的目标文件的段的合并。其中 ``.`` 表示当前地址，也就是链接器会从它指向的位置开始往下放置从输入的目标文件
中收集来的段。我们可以对 ``.`` 进行赋值来调整接下来的段放在哪里，也可以创建一些全局符号赋值为 ``.`` 从而记录这一时刻的位置。我们还能够
看到这样的格式：

.. code-block::

    .rodata : {
        *(.rodata)
    }

冒号前面表示最终生成的可执行文件的一个段的名字，花括号内按照放置顺序描述将所有输入目标文件的哪些段放在这个段中，每一行格式为 
``<ObjectFile>(SectionName)``，表示目标文件 ``ObjectFile`` 的名为 ``SectionName`` 的段需要被放进去。我们也可以
使用通配符来书写 ``<ObjectFile>`` 和 ``<SectionName>`` 分别表示可能的输入目标文件和段名。因此，最终的合并结果是，在最终可执行文件
中各个常见的段 ``.text, .rodata .data, .bss`` 从低地址到高地址按顺序放置，每个段里面都包括了所有输入目标文件的同名段，
且每个段都有两个全局符号给出了它的开始和结束地址（比如 ``.text`` 段的开始和结束地址分别是 ``stext`` 和 ``etext`` ）。




为了说明当前实现的正确性，我们需要讨论这样一个问题：

1. 如何做到执行环境的初始化代码被放在内存上以 ``0x80200000`` 开头的区域上？

	在链接脚本第 7 行，我们将当前地址设置为 ``BASE_ADDRESS`` 也即 ``0x80200000`` ，然后从这里开始往高地址放置各个段。第一个被放置的
	是 ``.text`` ，而里面第一个被放置的又是来自 ``entry.asm`` 中的段 ``.text.entry``，这个段恰恰是含有两条指令的执行环境初始化代码，
	它在所有段中最早被放置在我们期望的 ``0x80200000`` 处。


这样一来，我们就将运行时重建完毕了。在 ``os`` 目录下 ``cargo build --release`` 或者直接 ``make build`` 就能够看到
最终生成的可执行文件 ``target/riscv64gc-unknown-none-elf/release/os`` 。
通过分析，我们看到 ``0x80200000`` 处的代码是我们预期的 ``_start()`` 函数的内容。我们采用刚才的编译运行方式进行试验，发现还是同样的错误结果。
问题出在哪里？这时需要用上 ``debug`` 大法了。


.. code-block:: console

  # 在一个终端执行如下命令：
  $ qemu-system-riscv64 -machine virt -nographic -bios ../bootloader/rustsbi-qemu.bin -device loader,file=target/riscv64gc-unknown-none-elf/release/os.bin,addr=0x80200000 -S -s

  # 在另外一个终端执行如下命令：
  $ rust-gdb target/riscv64gc-unknown-none-elf/release/os
  (gdb) target remote :1234
  (gdb) break *0x80200000
  (gdb) x /16i 0x80200000
  (gdb) si

结果发现刚执行一条指令，整个系统就飞了（ ``pc`` 寄存器等已经变成为 ``0`` 了）。再一看， ``sp`` 寄存器是一个非常大的值 ``0xffffff...`` 。这就很清楚是 
**栈 stack** 出现了问题。我们没有设置好 **栈 stack** ！ 好吧，我们需要考虑如何合理设置 **栈 stack** 。


正确配置栈空间布局
----------------------------

为了说明如何实现正确的栈，我们需要讨论这样一个问题：应用函数调用所需的栈放在哪里？

    需要有一段代码来分配并栈空间，并把 ``sp`` 寄存器指向栈空间的起始位置（注意：栈空间是从上向下 ``push`` 数据的）。
    所以，我们要写一小段汇编代码 ``entry.asm`` 来帮助建立好栈空间。
    从链接脚本第 32 行开始，我们可以看出 ``entry.asm`` 中分配的栈空间对应的段 ``.bss.stack`` 被放入到可执行文件中的 
    ``.bss`` 段中的低地址中。在后面虽然有一个通配符 ``.bss.*`` ，但是由于链接脚本的优先匹配规则它并不会被匹配到后面去。
    这里需要注意的是地址区间 :math:`[\text{sbss},\text{ebss})` 并不包括栈空间，其原因后面再进行说明。

我们自己编写运行时初始化的代码：

.. code-block:: asm
    :linenos:

    # os/src/entry.asm
        .section .text.entry
        .globl _start
    _start:
        la sp, boot_stack_top
        call rust_main

        .section .bss.stack
        .globl boot_stack
    boot_stack:
        .space 4096 * 16
        .globl boot_stack_top
    boot_stack_top:

在这段汇编代码中，我们从第 8 行开始预留了一块大小为 4096 * 16 字节也就是 :math:`64\text{KiB}` 的空间用作接下来要运行的程序的栈空间，
这块栈空间的栈顶地址被全局符号 ``boot_stack_top`` 标识，栈底则被全局符号 ``boot_stack`` 标识。同时，这块栈空间单独作为一个名为 
``.bss.stack`` 的段，之后我们会通过链接脚本来安排它的位置。

从第 2 行开始，我们通过汇编代码实现执行环境的初始化，它其实只有两条指令：第一条指令将 sp 设置为我们预留的栈空间的栈顶位置，于是之后在函数
调用的时候，栈就可以从这里开始向低地址增长了。简单起见，我们目前暂时不考虑 sp 越过了栈底 ``boot_stack`` ，也就是栈溢出的情形，虽然这有
可能导致严重的错误。第二条指令则是通过伪指令 ``call`` 函数调用 ``rust_main`` ，这里的 ``rust_main`` 是一个我们稍后自己编写的应用
入口。因此初始化任务非常简单：正如上面所说的一样，只需要设置栈指针 sp，随后跳转到应用入口即可。这两条指令单独作为一个名为 
``.text.entry`` 的段，且全局符号 ``_start`` 给出了段内第一条指令的地址。

接着，我们在 ``main.rs`` 中嵌入这些汇编代码并声明应用入口 ``rust_main`` ：

.. code-block:: rust
    :linenos:
    :emphasize-lines: 4,8,10,11,12,13

    // os/src/main.rs
    #![no_std]
    #![no_main]
    #![feature(global_asm)]

    mod lang_items;

    global_asm!(include_str!("entry.asm"));

    #[no_mangle]
    pub fn rust_main() -> ! {
        loop {}
    }

背景高亮指出了 ``main.rs`` 中新增的代码。

第 4 行中，我们手动设置 ``global_asm`` 特性来支持在 Rust 代码中嵌入全局汇编代码。第 8 行，我们首先通过 
``include_str!`` 宏将同目录下的汇编代码 ``entry.asm`` 转化为字符串并通过 ``global_asm!`` 宏嵌入到代码中。

从第 10 行开始，
我们声明了应用的入口点 ``rust_main`` ，这里需要注意的是需要通过宏将 ``rust_main`` 标记为 ``#[no_mangle]`` 以避免编译器对它的
名字进行混淆，不然的话在链接的时候， ``entry.asm`` 将找不到 ``main.rs`` 提供的外部符号 ``rust_main`` 从而导致链接失败。


这样一来，我们就将初始的“三叶虫”操作系统编写完毕了。再次使用上节中的编译，生成和运行操作，我们看到QEMU模拟的RISC-V 64计算机 **优雅** 地退出了！



.. code-block:: console

    $ qemu-system-riscv64 \
    > -machine virt \
    > -nographic \
    > -bios ../bootloader/rustsbi-qemu.bin \
    > -device loader,file=target/riscv64gc-unknown-none-elf/release/os.bin,addr=0x80200000 
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
    [rustsbi] medeleg: 0xb1ab
    [rustsbi] Kernel entry: 0x80200000
    # “优雅”地退出了。 





清空 .bss 段
----------------------------------

与内存相关的部分太容易出错了。所以，我们再仔细检查代码后，发现在嵌入式系统中常见的 **清零 .bss段** 的工作并没有完成。

.. note::

    由于一般应用程序的 ``.bss`` 段在程序正式开始运行之前会被执环境（系统库或操作系统内核）固定初始化为零，因此在 ELF 文件中，为了节省磁盘空间，只会记录 ``.bss`` 段的位置，且应用程序的假定在它执行前，其 ``.bss段`` 的数据内容都已是 ``全0`` 。
    如果这块区域不是全零，且执行环境也没提前清零，那么会与应用的假定矛盾，导致程序出错。对于在裸机上执行的应用程序，其执行环境（就是QEMU模拟硬件+“三叶虫”操作系统内核）要负责将 ``.bss`` 所分配到的内存区域全部清零。

落实到我们正在实现的“三叶虫”操作系统内核，我们需要提供清零的 ``clear_bss()`` 函数。此函数属于执行环境，并在执行环境调用
应用程序的 ``rust_main`` 主函数前，把 ``.bss`` 段的全局数据清零。

.. code-block:: rust
    :linenos:

    // os/src/main.rs
    fn clear_bss() {
        extern "C" {
            fn sbss();
            fn ebss();
        }
        (sbss as usize..ebss as usize).for_each(|a| {
            unsafe { (a as *mut u8).write_volatile(0) }
        });
    }

在程序内自己进行清零的时候，我们就不用去解析 ELF执行文件格式（此时也没有 ELF 执行文件可供解析）来定位 ``.bss`` 段的位置，而是通过链接脚本 ``linker.ld`` 中给出的全局符号 
``sbss`` 和 ``ebss`` 来确定 ``.bss`` 段的位置。



我们可以松一口气了。接下来，我们要让“三叶虫”操作系统实现“Hello, world”输出！


添加裸机打印相关函数
----------------------------------



与上一节为输出字符实现的代码片段相比，裸机应用的执行环境支持字符输出的代码改动会很小。这里的原因是，二者的区别仅仅是系统调用的参数格式和SBI调用的参数格式的不同。
下面的代码是在基于上节有打印能力的执行环境的基础上做的变动。

.. code-block:: rust

    const SBI_CONSOLE_PUTCHAR: usize = 1;

    pub fn console_putchar(c: usize) {
        syscall(SBI_CONSOLE_PUTCHAR, [c, 0, 0]);
    }

    impl Write for Stdout {
        fn write_str(&mut self, s: &str) -> fmt::Result {
            //sys_write(STDOUT, s.as_bytes());
            for c in s.chars() {
                console_putchar(c as usize);
            }
            Ok(())
        }
    }


可以看到主要就只是把之前的操作系统系统调用改为了SBI调用。然后我们再编译运行试试，

.. code-block:: console

    $ cargo build
    $ rust-objcopy --binary-architecture=riscv64 target/riscv64gc-unknown-none-elf/debug/os --strip-all -O binary target/riscv64gc-unknown-none-elf/debug/os.bin
    $ qemu-system-riscv64 -machine virt -nographic -bios ../bootloader/rustsbi-qemu.bin -device loader,file=target/riscv64gc-unknown-none-elf/debug/os.bin,addr=0x80200000

    [rustsbi] Version 0.1.0
    .______       __    __      _______.___________.  _______..______   __
    |   _  \     |  |  |  |    /       |           | /       ||   _  \ |  |
    |  |_)  |    |  |  |  |   |   (----`---|  |----`|   (----`|  |_)  ||  |
    |      /     |  |  |  |    \   \       |  |      \   \    |   _  < |  |
    |  |\  \----.|  `--'  |.----)   |      |  |  .----)   |   |  |_)  ||  |
    | _| `._____| \______/ |_______/       |__|  |_______/    |______/ |__|

    [rustsbi] Platform: QEMU
    [rustsbi] misa: RV64ACDFIMSU
    [rustsbi] mideleg: 0x222
    [rustsbi] medeleg: 0xb1ab
    [rustsbi] Kernel entry: 0x80200000
    Hello, world!

可以看到，在裸机上输出了 ``Hello, world!`` ，而且qemu正常退出，表示RISC-V计算机也正常关机了。



添加处理异常错误的功能
----------------------------------

接着我们可提高“三叶虫”操作系统处理异常的能力，即给异常处理函数 ``panic`` 增加显示字符串能力，帮助我们理解出现异常时的代码执行情况。主要修改内容如下：

.. code-block:: rust

    // os/src/main.rs
    #![feature(panic_info_message)]

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

但我们在 ``main.rs`` 的 ``rust_main`` 函数中调用 ``panic!("It should shutdown!");`` 宏时，整个模拟执行的结果是：

.. code-block:: console

    $ cargo build --release 
    $ rust-objcopy --binary-architecture=riscv64 target/riscv64gc-unknown-none-elf/release/os \
        --strip-all -O binary target/riscv64gc-unknown-none-elf/release/os.bin
    $ qemu-system-riscv64 \
        -machine virt \
        -nographic \
        -bios ../bootloader/rustsbi-qemu.bin \
        -device loader,file=target/riscv64gc-unknown-none-elf/release/os.bin,addr=0x80200000

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
        [rustsbi] medeleg: 0xb1ab
        [rustsbi] Kernel entry: 0x80200000
        Hello, world!
        Panicked at src/main.rs:95 It should shutdown!

可以看到产生panic的地点在 ``main.rs`` 的第95行，与源码中的实际位置一致！到这里，我们基本上算是完成了第一章的实验内容，
除了实现支持应用程序在Linux操作系统上显示字符串的“恐龙虾”操作系统，还实现了支持应用程序在裸机上显示字符串的“三叶虫”操作系统。但也能看出，这些操作系统很脆弱，只能支持一个简单的易用，在本质上
是一个提供方便服务接口的库，只是一个是运行在用户态的库，一个是运行在裸机上的库。
在下一章，我们将进入“敏迷龙” [#minmi]_ 操作系统的设计与实现，来进化操作系统，并提升它的能力。


.. note::

    **Rust 小知识：错误处理**

    Rust 中常利用 ``Option<T>`` 和 ``Result<T, E>`` 进行方便的错误处理。它们都属于枚举结构：

    - ``Option<T>`` 既可以有值 ``Option::Some<T>`` ，也有可能没有值 ``Option::None``；
    - ``Result<T, E>`` 既可以保存某个操作的返回值 ``Result::Ok<T>`` ，也可以表明操作过程中出现了错误 ``Result::Err<E>`` 。

    我们可以使用 ``Option/Result`` 来保存一个不能确定存在/不存在或是成功/失败的值。之后可以通过匹配 ``if let`` 或是在能够确定
    的场合直接通过 ``unwrap`` 将里面的值取出。详细的内容可以参考 Rust 官方文档。

.. [#minmi] 敏迷龙是第一种发现于南半球的小型甲龙亚目恐龙，生存于早白垩纪，约1亿1900万年前到1亿1300万年前。