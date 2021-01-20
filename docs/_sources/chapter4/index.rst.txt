第四章：地址空间（施工中）
==============================================

.. toctree::
   :hidden:
   :maxdepth: 4

   1address-space
   2rust-dynamic-allocation
   3sv39-implementation-1
   4sv39-implementation-2
   5kernel-app-spaces

.. _term-illusion:
.. _term-time-division-multiplexing:
.. _term-transparent:

上一章，我们分别实现了多道程序和分时多任务系统，它们的核心机制都是任务切换。由于它们的设计初衷不同，它们切换
的时机和策略也不同。有趣的一点是，任务切换机制对于应用是完全 **透明** (Transparent) 的，应用可以不对内核
实现该机制的策略做任何假定
（除非要进行某些针对性优化），甚至可以完全不知道这机制的存在。在大多数应用（也就是应用开发者）的视角中，它们会独占
一整个 CPU 直到执行完毕。当然，通过上一章的学习，我们知道在现代操作系统中，出于公平性的考虑，我们极少会让这种情况
发生。所以应用自认为的独占只是内核想让应用看到的一种 **幻象** (Illusion) ，而 CPU 计算资源被 **时分复用** 
(TDM, Time-Division Multiplexing) 的实质被内核通过恰当的抽象隐藏了起来，对应用不可见。

与之相对，我们目前还没有对内存管理功能进行抽象。在上一章中，出于任务切换的需要，所有的应用都在初始化阶段被加载到
内存中并同时驻留下去直到它们全部运行结束。而且，所有的应用都直接通过物理地址访问物理内存。这会带来以下问题：

- 首先，内核提供给应用的内存访问接口不够透明，也不好用。由于应用直接访问物理内存，
  这需要它在构建的时候就需要规划自己需要被加载到哪个地址运行。为了避免冲突可能还需要应用的开发者们对此进行协商，
  这显然是一件在今天看来不可理喻且极端麻烦的事情。
- 其次，内核并没有对应用的访存行为进行任何保护措施，每个应用都有整块物理内存的读写权力。即使应用被限制在 U 特权级
  下运行，它还是能够造成很多麻烦：比如它可以读写其他应用的数据来窃取信息或者破坏它的正常运行；甚至它还可以修改内核
  的代码段来替换掉原本的 ``trap_handler`` 来挟持内核执行恶意代码。总之，这造成系统既不安全、也不稳定。

因此，为了防止应用胡作非为，本章我们将更好的管理物理内存，并提供给应用一个抽象出来的更加透明易用、也更加安全的访存
接口，就和上一章我们对 CPU 资源所做的事情一样。

本章的应用和上一章相同，只不过由于内核提供给应用的访存接口被替换，应用的构建方式发生了变化，这方面在下面会深入介绍。
因此应用运行起来的话效果是和上一章保持一致的。

获取本章代码：

.. code-block:: console

   $ git clone https://github.com/rcore-os/rCore-Tutorial-v3.git
   $ cd rCore-Tutorial-v3
   $ git checkout ch4

在 qemu 模拟器上运行本章代码：

.. code-block:: console

   $ cd os
   $ make run

将 Maix 系列开发版连接到 PC，并在上面运行本章代码：

.. code-block:: console

   $ cd os
   $ make run BOARD=k210

如果顺利的话，我们将看到和上一章相同的运行结果（以 K210 平台为例）：

.. code-block::

   [rustsbi] Version 0.1.0
   .______       __    __      _______.___________.  _______..______   __
   |   _  \     |  |  |  |    /       |           | /       ||   _  \ |  |
   |  |_)  |    |  |  |  |   |   (----`---|  |----`|   (----`|  |_)  ||  |
   |      /     |  |  |  |    \   \       |  |      \   \    |   _  < |  |
   |  |\  \----.|  `--'  |.----)   |      |  |  .----)   |   |  |_)  ||  |
   | _| `._____| \______/ |_______/       |__|  |_______/    |______/ |__|

   [rustsbi] Platform: K210
   [rustsbi] misa: RV64ACDFIMSU
   [rustsbi] mideleg: 0x222
   [rustsbi] medeleg: 0x1ab
   [rustsbi] Kernel entry: 0x80020000
   [kernel] Hello, world!
   .text [0x80020000, 0x8002b000)
   .rodata [0x8002b000, 0x8002e000)
   .data [0x8002e000, 0x8004d000)
   .bss [0x8004d000, 0x8035e000)
   mapping .text section
   mapping .rodata section
   mapping .data section
   mapping .bss section
   mapping physical memory
   [kernel] back to world!
   remap_test passed!
   init TASK_MANAGER
   num_app = 4
   power_3 [10000/300000]
   power_3 [20000/300000]
   power_3 [power_5 [10000/210000]
   power_5 [20000/210000]
   power_5 [30000/210000]
   power_5 [40000/210000]
   power_5 [50000/210000power_7 [10000/240000]
   power_7 [20000/240000]
   power_7 [30000/240000]
   power_7 [40000/240000]
   power_7 [5000030000/300000]
   power_3 [40000/300000]
   power_3 [50000/300000]
   power_3 [60000/300000]
   power_3 [70000/300000]
   ]
   power_5 [60000/210000]
   power_5 [70000/210000]
   power_5 [80000/210000]
   power_5 [90000/210000]
   power_5 [100000//240000]
   power_7 [60000/240000]
   power_7 [70000/240000]
   power_7 [80000/240000]
   power_7 [90000/240000]
   power_3 [80000/300000]
   power_3 [90000/300000]
   power_3 [100000/300000]
   power_3 [110000/300000]
   power_3 [120000/300000]
   210000]
   power_5 [110000/210000]
   power_5 [120000/210000]
   power_5 [130000/210000]
   power_5 [140000/210000]
   power_7 [100000/240000]
   power_7 [110000/240000]
   power_7 [120000/240000]
   power_7 [130000/240000]
   power_7 [140000/240000power_3 [130000/300000]
   power_3 [140000/300000]
   power_3 [150000/300000]
   power_3 [160000/300000]
   power_3 [170000power_5 [150000/210000]
   power_5 [160000/210000]
   power_5 [170000/210000]
   power_5 [180000/210000]
   power_5 [190000/210000]
   power_7 [150000/240000]
   power_7 [160000/240000]
   power_7 [170000/240000]
   power_7 [180000/240000]
   power_7 [/300000]
   power_3 [180000/300000]
   power_3 [190000/300000]
   power_3 [200000/300000]
   power_3 [210000/300000]
   ]
   power_5 [200000/210000]
   power_5 [210000/210000]
   5^210000 = 527227302(mod 998244353)
   Test power_5 OK!
   [kernel] Application exited with code 0
   power_3 [220000/300000]
   power_3 [230000/300000]
   power_3 [240000/300000]
   power_3 [250000/300000]
   power_3 [260000/300000190000/240000]
   power_7 [200000/240000]
   power_7 [210000/240000]
   power_7 [220000/240000]
   power_7 [230000/240000]
   ]
   power_3 [270000/300000]
   power_3 [280000/300000]
   power_3 [290000/300000]
   power_3 [300000/300000]
   3^300000 = 612461288power_7 [240000/240000]
   7^240000 = 304164893(mod 998244353)
   Test power_7 OK!
   [kernel] Application exited with code 0
   (mod 998244353)
   Test power_3 OK!
   [kernel] Application exited with code 0
   Test sleep OK!
   [kernel] Application exited with code 0
   [kernel] Panicked at src/task/mod.rs:112 All applications completed!
   [rustsbi] reset triggered! todo: shutdown all harts on k210; program halt