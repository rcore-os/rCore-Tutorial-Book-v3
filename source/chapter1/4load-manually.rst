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
   Start of section headers:          9032 (bytes into file)
   Flags:                             0x1, RVC, soft-float ABI
   Size of this header:               64 (bytes)
   Size of program headers:           56 (bytes)
   Number of program headers:         3
   Size of section headers:           64 (bytes)
   Number of section headers:         9
   Section header string table index: 7

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

一共有 9 个不同的 section header，它们从文件的 9032 字节开始，每个 64 字节：

.. code-block:: objdump

   Section Headers:
   [Nr] Name              Type             Address           Offset
         Size              EntSize          Flags  Link  Info  Align
   [ 0]                   NULL             0000000000000000  00000000
         0000000000000000  0000000000000000           0     0     0
   [ 1] .text             PROGBITS         0000000080020000  00001000
         0000000000000010  0000000000000000  AX       0     0     1
   [ 2] .text.rust_main   PROGBITS         0000000080020010  00001010
         000000000000000a  0000000000000000  AX       0     0     2
   [ 3] .stack            NOBITS           0000000080021000  00002000
         0000000000010000  0000000000000000  WA       0     0     1
   [ 4] .riscv.attributes RISCV_ATTRIBUTE  0000000000000000  00002000
         000000000000006a  0000000000000000           0     0     1
   [ 5] .comment          PROGBITS         0000000000000000  0000206a
         0000000000000013  0000000000000001  MS       0     0     1
   [ 6] .symtab           SYMTAB           0000000000000000  00002080
         00000000000001c8  0000000000000018           8     4     8
   [ 7] .shstrtab         STRTAB           0000000000000000  00002248
         0000000000000053  0000000000000000           0     0     1
   [ 8] .strtab           STRTAB           0000000000000000  0000229b
         00000000000000ab  0000000000000000           0     0     1
   Key to Flags:
   W (write), A (alloc), X (execute), M (merge), S (strings), I (info),
   L (link order), O (extra OS processing required), G (group), T (TLS),
   C (compressed), x (unknown), o (OS specific), E (exclude),
   p (processor specific)

   There are no section groups in this file.

每个 section header 则描述一个段的元数据。

其中，我们看到了代码段 ``.text/.text.rust_main`` 被放在可执行文件的 4096 字节处，大小 0x1a=26 字节，需要被加载到地址 ``0x80020000``。
它们分别由元数据的字段 Offset、 Size 和 Address 给出。同理，我们自己预留的应用程序函数调用栈在 ``.stack`` 段中，大小为 :math:`64\text{KiB}`
，需要被加载到地址 ``0x80021000`` 处。我们没有看到 ``.bss/.data/.rodata`` 等段，因为目前的 ``rust_main`` 里面没有任何东西。

我们还能够看到 ``.symtab`` 段中给出的符号表：

.. code-block::

   Symbol table '.symtab' contains 19 entries:
      Num:    Value          Size Type    Bind   Vis      Ndx Name
      0: 0000000000000000     0 NOTYPE  LOCAL  DEFAULT  UND 
      1: 0000000000000000     0 FILE    LOCAL  DEFAULT  ABS os.78wp4f2l-cgu.0
      2: 0000000000000000     0 FILE    LOCAL  DEFAULT  ABS os.78wp4f2l-cgu.1
      3: 0000000080020000     0 NOTYPE  LOCAL  DEFAULT    1 .Lpcrel_hi0
      4: 0000000080020000     0 NOTYPE  GLOBAL DEFAULT    1 _start
      5: 0000000080021000     0 NOTYPE  GLOBAL DEFAULT    3 boot_stack
      6: 0000000080031000     0 NOTYPE  GLOBAL DEFAULT    3 boot_stack_top
      7: 0000000080020010    10 FUNC    GLOBAL DEFAULT    2 rust_main
      8: 0000000080020000     0 NOTYPE  GLOBAL DEFAULT  ABS BASE_ADDRESS
      9: 0000000080020000     0 NOTYPE  GLOBAL DEFAULT    1 skernel
      10: 0000000080020000     0 NOTYPE  GLOBAL DEFAULT    1 stext
      11: 0000000080021000     0 NOTYPE  GLOBAL DEFAULT    2 etext
      12: 0000000080021000     0 NOTYPE  GLOBAL DEFAULT    2 srodata
      13: 0000000080021000     0 NOTYPE  GLOBAL DEFAULT    2 erodata
      14: 0000000080021000     0 NOTYPE  GLOBAL DEFAULT    2 sdata
      15: 0000000080021000     0 NOTYPE  GLOBAL DEFAULT    2 edata
      16: 0000000080021000     0 NOTYPE  GLOBAL DEFAULT    2 sbss
      17: 0000000080021000     0 NOTYPE  GLOBAL DEFAULT    2 ebss
      18: 0000000080031000     0 NOTYPE  GLOBAL DEFAULT    3 ekernel

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

.. note::

   **使用 GDB 跟踪 qemu 的运行状态**

   TODO


k210 平台
------------------------