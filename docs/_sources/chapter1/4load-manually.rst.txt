手动加载、运行应用程序
==================================

.. toctree::
   :hidden:
   :maxdepth: 5

在上一节中我们自己实现了一套运行时来代替标准库，并完整的构建了最终的可执行文件。但是它现在只是放在磁盘上的一个文件，若想将它运行起来的话，
就需要将它加载到内存中，在大多数情况下这是操作系统的任务。

让我们先来看看最终可执行文件的格式：

.. code-block:: console

   $ file os/target/riscv64gc-unknown-none-elf/release/os
   os/target/riscv64gc-unknown-none-elf/release/os: ELF 64-bit LSB executable, 
   UCB RISC-V, version 1 (SYSV), statically linked, not stripped

.. _term-elf:
.. _term-metadata:

从中可以看出可执行文件的格式为 **可执行和链接格式** (Executable and Linkable Format, ELF)，硬件平台是 RV64 。在 ELF 文件中，
除了程序必要的代码、数据段（它们本身都只是一些二进制的数据）之外，还有一些 **元数据** (Metadata) 描述这些段在地址空间中的位置和在
文件中的位置以及一些权限控制信息，这些元数据只能放在代码、数据段的外面。

我们可以通过二进制工具 ``readelf`` 来看看 ELF 文件中究竟包含什么内容，输入命令：

.. code-block:: console

   $ riscv64-unknown-elf-readelf os/target/riscv64gc-unknown-none-elf/release/os -a

首先可以看到一个 ELF header，它位于 ELF 文件的开头：

.. code-block:: objdump
   :linenos:
   :emphasize-lines: 2,11,12,13,17,19

   ELF Header:
   Magic:   7f 45 4c 46 02 01 01 00 00 00 00 00 00 00 00 00 
   Class:                             ELF64
   Data:                              2's complement, little endian
   Version:                           1 (current)
   OS/ABI:                            UNIX - System V
   ABI Version:                       0
   Type:                              EXEC (Executable file)
   Machine:                           RISC-V
   Version:                           0x1
   Entry point address:               0x80020000
   Start of program headers:          64 (bytes into file)
   Start of section headers:          9016 (bytes into file)
   Flags:                             0x1, RVC, soft-float ABI
   Size of this header:               64 (bytes)
   Size of program headers:           56 (bytes)
   Number of program headers:         3
   Size of section headers:           64 (bytes)
   Number of section headers:         8
   Section header string table index: 6

.. _term-magic:

- 第 2 行是一个称之为 **魔数** (Magic) 独特的常数，存放在 ELF header 的一个固定位置。当加载器将 ELF 文件加载到内存之前，通常会查看
  该位置的值是否正确，来快速确认被加载的文件是不是一个 ELF 。
- 第 11 行给出了可执行文件的入口点为 ``0x80020000`` ，这正是我们上一节所做的事情。
- 从 12/13/17/19 行中，我们可以知道除了 ELF header 之外，还有另外两种不同的 header，分别称为 program header 和 section header，
  它们都有多个。ELF header 中给出了三种 header 的大小、在文件中的位置以及数目。

一共有 3 个不同的 program header，它们从文件的 64 字节开始，每个 56 字节：

.. code-block:: objdump

   Program Headers:
   Type           Offset             VirtAddr           PhysAddr
                  FileSiz            MemSiz              Flags  Align
   LOAD           0x0000000000001000 0x0000000080020000 0x0000000080020000
                  0x000000000000001a 0x000000000000001a  R E    0x1000
   LOAD           0x0000000000002000 0x0000000080021000 0x0000000080021000
                  0x0000000000000000 0x0000000000010000  RW     0x1000
   GNU_STACK      0x0000000000000000 0x0000000000000000 0x0000000000000000
                  0x0000000000000000 0x0000000000000000  RW     0x0

每个 program header 指向一个在加载的时候可以连续加载的区域。

一共有 8 个不同的 section header，它们从文件的 9016 字节开始，每个 64 字节：

.. code-block:: objdump

   Section Headers:
   [Nr] Name              Type             Address           Offset
         Size              EntSize          Flags  Link  Info  Align
   [ 0]                   NULL             0000000000000000  00000000
         0000000000000000  0000000000000000           0     0     0
   [ 1] .text             PROGBITS         0000000080020000  00001000
         000000000000001a  0000000000000000  AX       0     0     2
   [ 2] .bss              NOBITS           0000000080021000  00002000
         0000000000010000  0000000000000000  WA       0     0     1
   [ 3] .riscv.attributes RISCV_ATTRIBUTE  0000000000000000  00002000
         000000000000006a  0000000000000000           0     0     1
   [ 4] .comment          PROGBITS         0000000000000000  0000206a
         0000000000000013  0000000000000001  MS       0     0     1
   [ 5] .symtab           SYMTAB           0000000000000000  00002080
         00000000000001c8  0000000000000018           7     4     8
   [ 6] .shstrtab         STRTAB           0000000000000000  00002248
         0000000000000041  0000000000000000           0     0     1
   [ 7] .strtab           STRTAB           0000000000000000  00002289
         00000000000000ab  0000000000000000           0     0     1
   Key to Flags:
   W (write), A (alloc), X (execute), M (merge), S (strings), I (info),
   L (link order), O (extra OS processing required), G (group), T (TLS),
   C (compressed), x (unknown), o (OS specific), E (exclude),
   p (processor specific)

   There are no section groups in this file.

每个 section header 则描述一个段的元数据。

其中，我们看到了代码段 ``.text`` 被放在可执行文件的 4096 字节处，大小 0x1a=26 字节，需要被加载到地址 ``0x80020000``。
它们分别由元数据的字段 Offset、 Size 和 Address 给出。同理，我们自己预留的应用程序函数调用栈在 ``.bss`` 段中，大小为 :math:`64\text{KiB}`
，需要被加载到地址 ``0x80021000`` 处。我们没有看到 ``.data/.rodata`` 等段，因为目前的 ``rust_main`` 里面没有任何东西。

我们还能够看到 ``.symtab`` 段中给出的符号表：

.. code-block::

   Symbol table '.symtab' contains 19 entries:
      Num:    Value          Size Type    Bind   Vis      Ndx Name
      0: 0000000000000000     0 NOTYPE  LOCAL  DEFAULT  UND 
      1: 0000000000000000     0 FILE    LOCAL  DEFAULT  ABS os.78wp4f2l-cgu.0
      2: 0000000000000000     0 FILE    LOCAL  DEFAULT  ABS os.78wp4f2l-cgu.1
      3: 0000000080020000     0 NOTYPE  LOCAL  DEFAULT    1 .Lpcrel_hi0
      4: 0000000080020000     0 NOTYPE  GLOBAL DEFAULT    1 _start
      5: 0000000080021000     0 NOTYPE  GLOBAL DEFAULT    2 boot_stack
      6: 0000000080031000     0 NOTYPE  GLOBAL DEFAULT    2 boot_stack_top
      7: 0000000080020010    10 FUNC    GLOBAL DEFAULT    1 rust_main
      8: 0000000080020000     0 NOTYPE  GLOBAL DEFAULT  ABS BASE_ADDRESS
      9: 0000000080020000     0 NOTYPE  GLOBAL DEFAULT    1 skernel
      10: 0000000080020000     0 NOTYPE  GLOBAL DEFAULT    1 stext
      11: 0000000080021000     0 NOTYPE  GLOBAL DEFAULT    1 etext
      12: 0000000080021000     0 NOTYPE  GLOBAL DEFAULT    1 srodata
      13: 0000000080021000     0 NOTYPE  GLOBAL DEFAULT    1 erodata
      14: 0000000080021000     0 NOTYPE  GLOBAL DEFAULT    1 sdata
      15: 0000000080021000     0 NOTYPE  GLOBAL DEFAULT    1 edata
      16: 0000000080031000     0 NOTYPE  GLOBAL DEFAULT    2 sbss
      17: 0000000080031000     0 NOTYPE  GLOBAL DEFAULT    2 ebss
      18: 0000000080031000     0 NOTYPE  GLOBAL DEFAULT    2 ekernel

里面包括了栈顶、栈底、rust_main 的地址以及我们在 ``linker.ld`` 中定义的各个段开始和结束地址。

因此，从 ELF header 中可以看出，ELF 中的内容按顺序应该是：

- ELF header
- 若干个 program header
- 程序各个段的实际数据
- 若干的 section header

当将程序加载到内存的时候，对于每个 program header 所指向的区域，我们需要将对应的数据从文件复制到内存中。这就需要解析 ELF 的元数据
才能知道数据在文件中的位置以及即将被加载到内存中的位置。但目前，我们不需要从 ELF 中解析元数据就知道程序的内存布局
（这个内存布局是我们按照需求自己指定的），我们可以手动完成加载任务。

具体的做法是利用 ``rust-objcopy`` 工具删除掉 ELF 文件中的
所有 header 只保留各个段的实际数据得到一个没有任何符号的纯二进制镜像文件，由于缺少了必要的元数据，我们的二进制工具也没有办法
对它完成解析了。而后，我们直接将这个二进制镜像文件手动载入到内存中合适位置即可。在这里，我们知道在镜像文件中，仍然是代码段 ``.text`` 
作为起始，因此我们要将这个代码段载入到 ``0x80020000`` 才能和上一级 bootloader 对接上。因此，我们只要把整个镜像文件手动载入到
内存的地址 ``0x80020000`` 处即可。在不同的硬件平台上，手动加载的方式是不同的。

qemu 平台
-------------------------

首先我们还原一下可执行文件和二进制镜像的生成流程：

.. code-block:: makefile

   # os/Makefile
   TARGET := riscv64gc-unknown-none-elf
   MODE := release
   KERNEL_ELF := target/$(TARGET)/$(MODE)/os
   KERNEL_BIN := $(KERNEL_ELF).bin

   $(KERNEL_BIN): kernel
      @$(OBJCOPY) $(KERNEL_ELF) --strip-all -O binary $@

   kernel:
      @cargo build --release

这里可以看出 ``KERNEL_ELF`` 保存最终可执行文件 ``os`` 的路径，而 ``KERNEL_BIN`` 保存只保留各个段数据的二进制镜像文件 ``os.bin`` 
的路径。目标 ``kernel`` 直接通过 ``cargo build`` 以 release 模式最终可执行文件，目标 ``KERNEL_BIN`` 依赖于目标 ``kernel``，将
可执行文件通过 ``rust-objcopy`` 工具加上适当的配置移除所有的 header 和符号得到二进制镜像。

我们可以通过 ``make run`` 直接在 qemu 上运行我们的应用程序，qemu 是一个虚拟机，它完整的模拟了一整套硬件平台，就像是一台真正的计算机
一样，我们来看运行 qemu 的具体命令：

.. code-block:: makefile
   :linenos:
   :emphasize-lines: 11,12,13,14,15

   KERNEL_ENTRY_PA := 0x80020000

   BOARD		?= qemu
   SBI			?= rustsbi
   BOOTLOADER	:= ../bootloader/$(SBI)-$(BOARD).bin

   run: run-inner

   run-inner: build
   ifeq ($(BOARD),qemu)
      @qemu-system-riscv64 \
         -machine virt \
         -nographic \
         -bios $(BOOTLOADER) \
         -device loader,file=$(KERNEL_BIN),addr=$(KERNEL_ENTRY_PA)
   else
      @cp $(BOOTLOADER) $(BOOTLOADER).copy
      @dd if=$(KERNEL_BIN) of=$(BOOTLOADER).copy bs=128K seek=1
      @mv $(BOOTLOADER).copy $(KERNEL_BIN)
      @sudo chmod 777 $(K210-SERIALPORT)
      python3 $(K210-BURNER) -p $(K210-SERIALPORT) -b 1500000 $(KERNEL_BIN)
      miniterm --eol LF --dtr 0 --rts 0 --filter direct $(K210-SERIALPORT) 115200
   endif

注意其中高亮部分给出了传给 qemu 的参数。

- ``-machine`` 告诉 qemu 使用预设的硬件配置。在整个项目中我们将一直沿用该配置。
- ``-bios`` 告诉 qemu 使用我们放在 ``bootloader`` 目录下的预编译版本作为 bootloader。
- ``-device`` 则告诉 qemu 将二进制镜像加载到内存指定的位置。

可以先输入 Ctrl+A ，再输入 X 来退出 qemu 终端。

.. warning::

   **FIXME： 使用 GDB 跟踪 qemu 的运行状态**


k210 平台
------------------------

对于 k210 平台来说，只需要将 maix 系列开发板通过数据线连接到 PC，然后 ``make run BOARD=k210`` 即可。从 Makefile 中来看：

.. code-block:: makefile
   :linenos:
   :emphasize-lines: 13,16,17

   K210-SERIALPORT	= /dev/ttyUSB0
   K210-BURNER		= ../tools/kflash.py

   run-inner: build
   ifeq ($(BOARD),qemu)
      @qemu-system-riscv64 \
         -machine virt \
         -nographic \
         -bios $(BOOTLOADER) \
         -device loader,file=$(KERNEL_BIN),addr=$(KERNEL_ENTRY_PA)
   else
      @cp $(BOOTLOADER) $(BOOTLOADER).copy
      @dd if=$(KERNEL_BIN) of=$(BOOTLOADER).copy bs=128K seek=1
      @mv $(BOOTLOADER).copy $(KERNEL_BIN)
      @sudo chmod 777 $(K210-SERIALPORT)
      python3 $(K210-BURNER) -p $(K210-SERIALPORT) -b 1500000 $(KERNEL_BIN)
      miniterm --eol LF --dtr 0 --rts 0 --filter direct $(K210-SERIALPORT) 115200
   endif

在构建目标 ``run-inner`` 的时候，根据平台 ``BOARD`` 的不同，启动运行的指令也不同。当我们传入命令行参数 ``BOARD=k210`` 时，就会进入下面
的分支。

- 第 13 行我们使用 ``dd`` 工具将 bootloader 和二进制镜像拼接到一起，这是因为 k210 平台的写入工具每次只支持写入一个文件，所以我们只能
  将二者合并到一起一并写入 k210 的内存上。这样的参数设置可以保证 bootloader 在合并后文件的开头，而二进制镜像在文件偏移量 0x20000 的
  位置处。有兴趣的读者可以输入命令 ``man dd`` 查看关于工具 ``dd`` 的更多信息。
- 第 16 行我们使用烧写工具 ``K210-BURNER`` 将合并后的镜像烧写到 k210 开发板的内存的 ``0x80000000`` 地址上。
  参数 ``K210-SERIALPORT`` 表示当前 OS 识别到的 k210 开发板的串口设备名。在 Ubuntu 平台上一般为 ``/dev/ttyUSB0``。
- 第 17 行我们打开串口终端和 k210 开发板进行通信，可以通过键盘向 k210 开发板发送字符并在屏幕上看到 k210 开发板的字符输出。

可以输入 Ctrl+] 退出 miniterm。

手动清空 .bss 段
----------------------------------

由于 ``.bss`` 段需要在程序正式开始运行之前被固定初始化为零，因此在 ELF 文件中，为了节省磁盘空间，只会记录 ``.bss`` 段的位置而并不是
有一块长度相等的全为零的数据。在内核将可执行文件加载到内存的时候，它需要负责将 ``.bss`` 所分配到的内存区域全部清零。而我们这里需要在
应用程序 ``rust_main`` 中，在访问任何 ``.bss`` 段的全局数据之前手动将其清零。

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

在程序内自己进行清零的时候，我们就不用去解析 ELF（此时也没有 ELF 可供解析）了，而是通过链接脚本 ``linker.ld`` 中给出的全局符号 
``sbss`` 和 ``ebss`` 来确定 ``.bss`` 段的位置。

.. note::

    **Rust 语法卡片：外部符号引用**

    extern "C" 可以引用一个外部的 C 函数接口（这意味着调用它的时候要遵从目标平台的 C 语言调用规范）。但我们这里只是引用位置标志
    并将其转成 usize 获取它的地址。由此可以知道 ``.bss`` 段两端的地址。

    **Rust 语法卡片：迭代器与闭包**

    代码第 7 行用到了 Rust 的迭代器与闭包的语法，它们在很多情况下能够提高开发效率。如读者感兴趣的话也可以将其改写为等价的 for 
    循环实现。

.. _term-raw-pointer:
.. _term-dereference:
.. warning::

    **Rust 语法卡片：Unsafe**

    代码第 8 行，我们将 ``.bss`` 段内的一个地址转化为一个 **裸指针** (Raw Pointer)，并将它指向的值修改为 0。这在 C 语言中是
    一种司空见惯的操作，但在 Rust 中我们需要将他包裹在 unsafe 块中。这是因为，Rust 认为对于裸指针的 **解引用** (Dereference) 
    是一种 unsafe 行为。

    相比 C 语言，Rust 进行了更多的语义约束来保证安全性（内存安全/类型安全/并发安全），这在编译期和运行期都有所体现。但在某些时候，
    尤其是与底层硬件打交道的时候，在 Rust 的语义约束之内没法满足我们的需求，这个时候我们就需要将超出了 Rust 语义约束的行为包裹
    在 unsafe 块中，告知编译器不需要对它进行完整的约束检查，而是由程序员自己负责保证它的安全性。当代码不能正常运行的时候，我们往往也是
    最先去检查 unsafe 块中的代码，因为它没有受到编译器的保护，出错的概率更大。

    C 语言中的指针相当于 Rust 中的裸指针，它无所不能但又太过于灵活，程序员对其不谨慎的使用常常会引起很多内存不安全问题，最常见的如
    悬垂指针和多次回收的问题，Rust 编译器没法确认程序员对它的使用是否安全，因此将其划到 unsafe Rust 的领域。在 safe Rust 中，我们
    有引用 ``&/&mut`` 以及各种功能各异的智能指针 ``Box<T>/RefCell<T>/Rc<T>`` 可以使用，只要按照 Rust 的规则来使用它们便可借助
    编译器在编译期就解决很多潜在的内存不安全问题。

