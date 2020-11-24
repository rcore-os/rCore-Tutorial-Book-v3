第一章：RV64 裸机应用
==============================================

.. toctree::
   :hidden:
   :maxdepth: 4

   1app-ee-platform
   2remove-std
   3minimal-rt
   4load-manually
   5sbi-print
   6practice

大多数程序员的第一行代码都从 ``Hello, world!`` 开始，当我们满怀着好奇心在编辑器内键入仅仅数个字节，再经过几行命令编译、运行，终于
在黑洞洞的终端窗口中看到期望中的结果的时候，一扇通往编程世界的大门已经打开。时至今日，我们能够隐约意识到编程工作能够如此方便简洁并不是
理所当然的，实际上有着多层硬件、软件隐藏在它背后，才让我们不必付出那么多努力就能够创造出功能强大的应用程序。

本章我们的目标仍然只是输出 ``Hello, world!`` ，但这一次，我们将离开舒适区，基于一个几乎空无一物的平台从零开始搭建我们自己的高楼大厦，
而不是仅仅通过一行语句就完成任务。

获取本章代码：

.. code-block:: console

   $ git clone https://github.com/rcore-os/rCore-Tutorial-v3.git
   $ cd rCore-Tutorial-v3
   $ git checkout ch1

在 qemu 模拟器上运行本章代码：

.. code-block:: console

   $ cd os
   $ make run

将 Maix 系列开发版连接到 PC，并在上面运行本章代码：

.. code-block:: console

   $ cd os
   $ make run BOARD=k210

.. warning::

   **FIXME: 提供 wsl/macOS 等更多平台支持**

如果顺利的话，以 qemu 平台为例，将输出：

.. code-block::

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

除了 ``Hello, world!`` 之外还有一些额外的信息，最后关机。