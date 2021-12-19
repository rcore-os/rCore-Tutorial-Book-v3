引言
=====================

本章导读
--------------------------

.. chyyuu
  这是注释：我觉得需要给出执行环境（EE），Task，...等的描述。
  并且有一个图，展示这些概念的关系。
  
本章展现了操作系统的一个基本目标：让应用与硬件隔离，简化了应用访问硬件的难度和复杂性。这也是远古操作系统雏形和现代的一些简单嵌入式操作系统的主要功能。具有这样功能的操作系统的形态就是一个函数库，可以被应用访问，并通过函数库的函数来访问硬件。

大多数程序员的第一行代码都从 ``Hello, world!`` 开始，当我们满怀着好奇心在编辑器内键入仅仅数个字节，再经过几行命令编译（靠的是编译器）、运行（靠的是操作系统），终于在黑洞洞的终端窗口中看到期望中的结果的时候，一扇通往编程世界的大门已经打开。在本章第一节 :doc:`1app-ee-platform` 中，可以看到用Rust语言编写的非常简单的“Hello, world”应用程序是如何被进一步拆解和分析的。

不过我们能够隐约意识到编程工作能够如此方便简洁并不是理所当然的，实际上有着多层硬件和软件工具和支撑环境隐藏在它背后，才让我们不必付出那么多努力就能够创造出功能强大的应用程序。生成应用程序二进制执行代码所依赖的是以 **编译器** 为主的开发环境；运行应用程序执行码所依赖的是以 **操作系统** 为主的执行环境。

本章主要是讲解如何设计和实现建立在裸机上的执行环境，从中对应用程序和它所依赖的执行环境有一个全面和深入的理解。

本章我们的目标仍然只是输出 ``Hello, world!`` ，但这一次，我们将离开舒适区，基于一个几乎空无一物的平台从零开始搭建我们自己的高楼大厦，而不是仅仅通过一行语句就完成任务。所以，在接下来的内容中，我们将描述如何让 ``Hello, world!`` 应用程序逐步脱离对编译器、运行时库和操作系统的现有复杂依赖，最终以最小的依赖需求能在裸机上运行。这时，我们也可把这个能在裸机上运行的 ``Hello, world!`` 应用程序称为一种支持输出字符串的非常初级的寒武纪“三叶虫”操作系统，它其实就是一个给应用提供各种服务（比如输出字符串）的库，方便了单一应用程序在裸机上的开发与运行。输出字符串功能好比是三叶虫的眼睛，有了它，我们就有了最基本的调试功能，即通过在代码中的不同位置插入特定内容的输出语句来实现对程序运行的调试。


.. chyyuu note
   
    在练习一节前面，是否有一个历史故事???
    目前发现，英国的OS（也可称之为雏形）出现的可能更早
    Timeline of operating systems https://en.wikipedia.org/wiki/Timeline_of_operating_systems#cite_note-1
    1950 https://h2g2.com/edited_entry/A1000729  LEO I 'Lyons Electronic Office'[1] was the commercial development of EDSAC computing platform, supported by British firm J. Lyons and Co.    
    https://en.wikipedia.org/wiki/EDSAC  
    https://en.wikipedia.org/wiki/LEO_(computer)  
    https://www.theregister.com/2021/11/30/leo_70/  
    https://www.sciencemuseum.org.uk/objects-and-stories/meet-leo-worlds-first-business-computer 
    https://warwick.ac.uk/services/library/mrc/archives_online/digital/leo/story
    https://www.kzwp.com/lyons1/leo.htm 介绍了leo i 计算工资远快于人工,随着时间的推移，英国的计算机制造逐渐消失。
    https://en.wikipedia.org/wiki/Wheeler_Jump 
    https://en.wikipedia.org/wiki/EDSAC
    https://people.cs.clemson.edu/~mark/edsac.html 模拟器， 提到了操作系统
    The EDSAC (electronic delay storage automatic calculator) performed its first calculation at Cambridge University, England, in May 1949. EDSAC contained 3,000 vacuum tubes and used mercury delay lines for memory. Programs were input using paper tape and output results were passed to a teleprinter. Additionally, EDSAC is credited as using one of the first assemblers called "Initial Orders," which allowed it to be programmed symbolically instead of using machine code. [http://www.maxmon.com/1946ad.htm]

    The operating system or "initial orders" consisted of 31 instructions which were hard-wired on uniselectors, a mechanical read-only memory. These instructions assembled programs in symbolic form from paper tape into the main memory and set them running. The second release of the initial orders was installed in August 1949. This occupied the full 41 words of read-only memory and included facilities for relocation or "coordination" to facilitate the use of subroutines (an important invention by D.J. Wheeler). [http://www.cl.cam.ac.uk/UoCCL/misc/EDSAC99/statistics.html]

    The EDSAC programming system was based on a set of "initial orders" and a subroutine library. The initial orders combined in a rudimentary fashion the functions performed by a bootstrap loader and an assembler in later computer systems. The initial orders existed in three versions. The first version, Initial Orders 1, was devised by David Wheeler, then a research student, in 1949. The initial orders resided in locations 0 to 30, and loaded a program tape into locations 31 upwards. The program was punched directly onto tape in a symbolic form using mnemonic operation codes and decimal addresses, foreshadowing in a remarkable way much later assembly systems. ... In September 1949 the first form of the initial orders was replaced by a new version. Again written by Wheeler, Initial Orders 2 was a tour de force of programming that combined a surprisingly sophisticated assembler and relocating loader in just 41 instructions. The initial orders read in a master routine (main program) in symbolic form, converted it to binary and placed it in the main memory; this could be followed by any number of subroutines, which would be relocated and packed end-to-end so that there were none of the memory allocation problems associated with less sophisticated early attempts to organise a subroutine library. [http://www.inf.fu-berlin.de/~widiger/ICHC/papers/campbell.html]   

.. note::
   

   **最早的操作系统雏形是计算工资单的程序库**

   操作系统需要给程序员提供支持：高效便捷地开发应用和执行应用。远古时期的计算机硬件昂贵笨重，能力弱，单靠硬件还不能高效地执行应用，能够减少程序员的开发成本就已经很不错了。

   程序库一般由一些子程序（函数）组成。通过调用程序库中的子程序，应用程序可以更加方便的实现其应用功能。但在早期的软件开发中，还缺少便捷有效的子程序调用机制。

   根据维基百科的操作系统时间线 [#OSTIMELINE]_ 上的记录，1949-1951 年，英国 J. Lyons and Co. 公司（一家包括连锁餐厅和食品制造的大型集团公司）开创性地引入并使用剑桥大学的 EDSAC 计算机，联合设计实现了 LEO I 'Lyons Electronic Office' 软硬件系统，利用计算机的高速度(按当时的标准)来高效地计算薪资，以及组织蛋糕和其他易腐烂的商品的分配等。这样计算机就成为了一个高效的专用事务处理系统。但软件开发还是一个很困难的事情，需要减少软件编程人员的开发负担。而通过函数库来重用软件功能并简化应用的编程是当时自然的想法。但在软件编程中，由于硬件的局限性（缺少索引寄存器、保存函数返回地址的寄存器、栈寄存器、硬件栈等），早期的程序员不得不使用在程序中修改自身代码的方式来访问数组或调用函数。从现在的视角看来，这样具有自修改能力的程序是一种黑科技。

   参与 EDSAC 项目的 David Wheeler 发明了子程序的概念 --  **Wheeler Jump** 。Wheeler 的方法是在子程序的最后一行添加 **“jump to this address”** 指令，并在指令后跟一个内存空间，这个内存空间通常被设置为 0，在子程序被调用后，这个内存空间的值会被修改为返回地址。当调用子程序时，调用者（Caller）的地址将被放置在累加寄存器中，然后代码将跳转到子程序的入口。子程序的第一条指令将根据累加寄存器中的值计算返回地址，通常是调用指令的下一条指令所在的内存位置，然后将计算出的返回地址写入先前预留的内存空间中。当子程序继续执行，自然会到达子程序的末尾，即 **“jump to this address”** 指令处，这条指令读取位于它之后的内存单元，获得返回地址，就可以正常返回了。

   在有了便捷有效的子程序概念和子程序调用机制后，软件开发人员在EDSAC计算机开发了大量的子程序库，其中就包括了检查计算机系统，加载应用软件，写数据到持久性存储设备中，打印数据等硬件系统相关功能的系统子程序库。这样程序员就可以方便开发应用程序来使用计算机了。这也是为何维基百科的的操作系统时间线 [#OSTIMELINE]_ 一文中，把LEO I 'Lyons Electronic Office' 软件系统（其实就是硬件系统相关的子程序库）定位为最早（1951年）的操作系统的起因。这样的计算机系统只支持一个应用的运行，可以称为专用计算机系统。1951年9月5日，计算机首次执行了一个名为 Bakeries Valuations 的应用程序，并在后续承担计算工资单这一必须按时执行的任务，因为必须向员工按时支付周薪。计算员工薪酬的任务需要一位经验丰富的文员 8 分钟内完成，而LEO I 在 1.5 秒内完成了这项工作，快了320倍，这在当时英国社会上引起了轰动。


   即使到了现在，以子程序库形式存在的简单嵌入式操作系统大量存在，运行在很多基于微控制单元(Microcontroller Unit，简称MCU)的单片机中，并支持简单应用甚至是单一应用，在智能仪表、玩具、游戏机、小家电等领域广泛存在。



实践体验
---------------------------

本章设计实现了一个支持显示字符串应用的简单操作系统--“三叶虫”操作系统，它的形态就是一个函数库，给应用程序提供了显示字符串的函数。

获取本章代码：

.. code-block:: console

   $ git clone https://github.com/rcore-os/rCore-Tutorial-v3.git
   $ cd rCore-Tutorial-v3
   $ git checkout ch1

在 qemu 模拟器上运行本章代码，看看一个小应用程序是如何在QEMU模拟的计算机上运行的：

.. code-block:: console

   $ cd os
   $ make run

将 Maix 系列开发板连接到 PC，并在上面运行本章代码，看看一个小应用程序是如何在真实计算机上运行的：

.. code-block:: console

   $ cd os
   $ make run BOARD=k210

.. warning::

   **FIXME: 提供 wsl/macOS 等更多平台支持**

如果顺利的话，以 qemu 平台为例，将输出：

.. code-block::

    [rustsbi] RustSBI version 0.2.0-alpha.6
    .______       __    __      _______.___________.  _______..______   __
    |   _  \     |  |  |  |    /       |           | /       ||   _  \ |  |
    |  |_)  |    |  |  |  |   |   (----`---|  |----`|   (----`|  |_)  ||  |
    |      /     |  |  |  |    \   \       |  |      \   \    |   _  < |  |
    |  |\  \----.|  `--'  |.----)   |      |  |  .----)   |   |  |_)  ||  |
    | _| `._____| \______/ |_______/       |__|  |_______/    |______/ |__|

    [rustsbi] Implementation: RustSBI-QEMU Version 0.0.2
    [rustsbi-dtb] Hart count: cluster0 with 1 cores
    [rustsbi] misa: RV64ACDFIMSU
    [rustsbi] mideleg: ssoft, stimer, sext (0x222)
    [rustsbi] medeleg: ima, ia, bkpt, la, sa, uecall, ipage, lpage, spage (0xb1ab)
    [rustsbi] pmp0: 0x10000000 ..= 0x10001fff (rwx)
    [rustsbi] pmp1: 0x80000000 ..= 0x8fffffff (rwx)
    [rustsbi] pmp2: 0x0 ..= 0xffffffffffffff (---)
    qemu-system-riscv64: clint: invalid write: 00000004
    [rustsbi] enter supervisor 0x80200000
    Hello, world!
    .text [0x80200000, 0x80202000)
    .rodata [0x80202000, 0x80203000)
    .data [0x80203000, 0x80203000)
    boot_stack [0x80203000, 0x80213000)
    .bss [0x80213000, 0x80213000)
    Panicked at src/main.rs:46 Shutdown machine!

除了 ``Hello, world!`` 之外还有一些额外的信息，最后关机。


.. note::
   
    :doc:`../appendix-c/index` 中可以找到关于 RustSBI 的更多信息。

本章代码树
------------------------------------------------

.. code-block::

   ./os/src
   Rust        4 Files   119 Lines
   Assembly    1 Files    11 Lines

   ├── bootloader(内核依赖的运行在 M 特权级的 SBI 实现，本项目中我们使用 RustSBI) 
   │   ├── rustsbi-k210.bin(可运行在 k210 真实硬件平台上的预编译二进制版本)
   │   └── rustsbi-qemu.bin(可运行在 qemu 虚拟机上的预编译二进制版本)
   ├── LICENSE
   ├── os(我们的内核实现放在 os 目录下)
   │   ├── Cargo.toml(内核实现的一些配置文件)
   │   ├── Makefile
   │   └── src(所有内核的源代码放在 os/src 目录下)
   │       ├── console.rs(将打印字符的 SBI 接口进一步封装实现更加强大的格式化输出)
   │       ├── entry.asm(设置内核执行环境的的一段汇编代码)
   │       ├── lang_items.rs(需要我们提供给 Rust 编译器的一些语义项，目前包含内核 panic 时的处理逻辑)
   │       ├── linker-k210.ld(控制内核内存布局的链接脚本以使内核运行在 k210 真实硬件平台上)
   │       ├── linker-qemu.ld(控制内核内存布局的链接脚本以使内核运行在 qemu 虚拟机上)
   │       ├── main.rs(内核主函数)
   │       └── sbi.rs(调用底层 SBI 实现提供的 SBI 接口)
   ├── README.md
   ├── rust-toolchain(控制整个项目的工具链版本)
   └── tools(自动下载的将内核烧写到 k210 开发板上的工具)
      ├── kflash.py
      ├── LICENSE
      ├── package.json
      ├── README.rst
      └── setup.py


本章代码导读
-----------------------------------------------------

操作系统虽然是软件，但它不是常规的应用软件，需要运行在没有操作系统的裸机环境中。如果采用通常编程方法和编译手段，无法开发出操作系统。其中一个重要的原因是：编译器编译出的应用软件在缺省情况下是要链接标准库（Rust 编译器和 C 编译器都是这样的），而标准库是依赖于操作系统（如 Linux、Windows 等）的。所以，本章主要是让同学能够脱离常规应用软件开发的思路，理解如何开发没有操作系统支持的操作系统内核。

为了做到这一步，首先需要写出不需要标准库的软件并通过编译。为此，先把一般应用所需要的标准库的组件给去掉，这会导致编译失败。然后再逐步添加不需要操作系统的极少的运行时支持代码，让编译器能够正常编译出不需要标准库的正常程序。但此时的程序没有显示输出，更没有输入等，但可以正常通过编译，这样就为进一步扩展程序内容打下了一个 **可正常编译OS** 的前期基础。具体可看 :ref:`移除标准库依赖 <term-remove-std>` 一节的内容。

操作系统代码无法像应用软件那样，可以有方便的调试（Debug）功能。这是因为应用之所以能够被调试，也是由于操作系统提供了方便的调试相关的系统调用。而我们不得不再次认识到，需要运行在没有操作系统的裸机环境中，当然没法采用依赖操作系统的传统调试方法了。所以，我们只能采用 ``print`` 这种原始且有效的调试方法。这样，第二步就是让脱离了标准库的软件有输出，这样，我们就能看到程序的运行情况了。为了简单起见，我们可以先在用户态尝试构建没有标准库的支持显示输出的最小运行时执行环境，比较特别的地方在于如何写内嵌汇编调用更为底层的输出接口来实现这一功能。具体可看 :ref:`构建用户态执行环境 <term-print-userminienv>` 一节的内容。

接下来就是尝试构建可在裸机上支持显示的最小运行时执行环境。相对于用户态执行环境，同学需要能够做更多的事情，比如如何关机，如何配置软件运行所在的物理内存空间，特别是栈空间，如何清除 ``bss`` 段，如何通过 ``RustSBI`` 的 ``SBI_CONSOLE_PUTCHAR`` 接口简洁地实现信息输出。这里比较特别的地方是需要了解 ``linker.ld`` 文件中对 OS 的代码和数据所在地址空间布局的描述，以及基于 RISC-V 64 的汇编代码 ``entry.asm`` 如何进行栈的设置和初始化，以及如何跳转到 Rust 语言编写的 ``rust_main`` 主函数中，并开始内核最小运行时执行环境的运行。具体可看 :ref:`构建裸机执行环境 <term-print-kernelminienv>` 一节的内容。


.. [#OSTIMELINE] https://en.wikipedia.org/wiki/Timeline_of_operating_systems 