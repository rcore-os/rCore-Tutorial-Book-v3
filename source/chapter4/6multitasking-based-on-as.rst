基于地址空间的分时多任务
==============================================================


本节导读
--------------------------




本节我们介绍如何基于地址空间抽象而不是对于物理内存的直接访问来实现支持地址空间隔离的分时多任务系统 -- “头甲龙” [#tutus]_ 操作系统 。这样，我们的应用编写会更加方便，应用与操作系统内核的空间隔离性增强了，应用程序和操作系统自身的安全性也得到了加强。为此，需要对现有的操作系统进行如下的功能扩展：

- 创建内核页表，使能分页机制，建立内核的虚拟地址空间；
- 扩展Trap上下文，在保存与恢复Trap上下文的过程中切换页表（即切换虚拟地址空间）；
- 建立用于内核地址空间与应用地址空间相互切换所需的跳板空间；
- 扩展任务控制块包括虚拟内存相关信息，并在加载执行创建基于某应用的任务时，建立应用的虚拟地址空间；
- 改进Trap处理过程和sys_write等系统调用的实现以支持分离的应用地址空间和内核地址空间。

在扩展了上述功能后，应用与应用之间，应用与操作系统内核之间通过硬件分页机制实现了内存空间隔离，且应用和内核之间还是能有效地进行相互访问，而且应用程序的编写也会更加简单通用。


建立并开启基于分页模式的虚拟地址空间
--------------------------------------------

当 SBI 实现（本项目中基于 RustSBI）初始化完成后， CPU 将跳转到内核入口点并在 S 特权级上执行，此时还并没有开启分页模式，内核的每次访存是直接的物理内存访问。而在开启分页模式之后，内核代码在访存时只能看到内核地址空间，此时每次访存需要通过 MMU 的地址转换。这两种模式之间的过渡在内核初始化期间完成。

创建内核地址空间
^^^^^^^^^^^^^^^^^^^^^^^^


我们创建内核地址空间的全局实例：

.. code-block:: rust

    // os/src/mm/memory_set.rs

    lazy_static! {
        pub static ref KERNEL_SPACE: Arc<UPSafeCell<MemorySet>> = Arc::new(unsafe {
            UPSafeCell::new(MemorySet::new_kernel()
        )});
    }

从之前对于 ``lazy_static!`` 宏的介绍可知， ``KERNEL_SPACE`` 在运行期间它第一次被用到时才会实际进行初始化，而它所
占据的空间则是编译期被放在全局数据段中。这里使用 ``Arc<UPSafeCell<T>>`` 组合是因为我们既需要 ``Arc<T>`` 提供的共享
引用，也需要 ``UPSafeCell<T>`` 提供的内部可变引用访问。

在 ``rust_main`` 函数中，我们首先调用 ``mm::init`` 进行内存管理子系统的初始化：

.. code-block:: rust

    // os/src/mm/mod.rs

    pub use memory_set::KERNEL_SPACE;

    pub fn init() {
        heap_allocator::init_heap();
        frame_allocator::init_frame_allocator();
        KERNEL_SPACE.exclusive_access().activate();
    }

可以看到，我们最先进行了全局动态内存分配器的初始化，因为接下来马上就要用到 Rust 的堆数据结构。接下来我们初始化物理页帧管理器（内含堆数据结构 ``Vec<T>`` ）使能可用物理页帧的分配和回收能力。最后我们创建内核地址空间并让 CPU 开启分页模式， MMU 在地址转换的时候使用内核的多级页表，这一切均在一行之内做到：

- 首先，我们引用 ``KERNEL_SPACE`` ，这是它第一次被使用，就在此时它会被初始化，调用 ``MemorySet::new_kernel`` 创建一个内核地址空间并使用 ``Arc<Mutex<T>>`` 包裹起来；
- 接着使用 ``.exclusive_access()`` 获取一个可变引用 ``&mut MemorySet`` 。需要注意的是这里发生了两次隐式类型转换：

  1.  我们知道 ``exclusive_access`` 是 ``UPSafeCell<T>`` 的方法而不是 ``Arc<T>`` 的方法，由于 ``Arc<T>`` 实现了 ``Deref`` Trait ，当 ``exclusive_access`` 需要一个 ``&UPSafeCell<T>`` 类型的参数的时候，编译器会自动将传入的 ``Arc<UPSafeCell<T>>`` 转换为 ``&UPSafeCell<T>`` 这样就实现了类型匹配；
  2.  事实上 ``UPSafeCell<T>::exclusive_access`` 返回的是一个 ``RefMut<'_, T>`` ，这同样是 RAII 的思想，当这个类型生命周期结束后互斥锁就会被释放。而该类型实现了 ``DerefMut`` Trait，因此当一个函数接受类型为 ``&mut T`` 的参数却被传入一个类型为 ``&mut RefMut<'_, T>`` 的参数的时候，编译器会自动进行类型转换使参数匹配。
- 最后，我们调用 ``MemorySet::activate`` ：

    .. code-block:: rust 
        :linenos:

        // os/src/mm/page_table.rs

        pub fn token(&self) -> usize {
            8usize << 60 | self.root_ppn.0
        }

        // os/src/mm/memory_set.rs

        impl MemorySet {
            pub fn activate(&self) {
                let satp = self.page_table.token();
                unsafe {
                    satp::write(satp);
                    asm!("sfence.vma" :::: "volatile");
                }
            }
        }

  ``PageTable::token`` 会按照 :ref:`satp CSR 格式要求 <satp-layout>` 构造一个无符号 64 位无符号整数，使得其分页模式为 SV39 ，且将当前多级页表的根节点所在的物理页号填充进去。在 ``activate`` 中，我们将这个值写入当前 CPU 的 satp CSR ，从这一刻开始 SV39 分页模式就被启用了，而且 MMU 会使用内核地址空间的多级页表进行地址转换。

  我们必须注意切换 satp CSR 是否是一个 *平滑* 的过渡：其含义是指，切换 satp 的指令及其下一条指令这两条相邻的指令的虚拟地址是相邻的（由于切换 satp 的指令并不是一条跳转指令， pc 只是简单的自增当前指令的字长），而它们所在的物理地址一般情况下也是相邻的，但是它们所经过的地址转换流程却是不同的——切换 satp 导致 MMU 查的多级页表是不同的。这就要求前后两个地址空间在切换 satp 的指令 *附近* 的映射满足某种意义上的连续性。

  幸运的是，我们做到了这一点。这条写入 satp 的指令及其下一条指令都在内核内存布局的代码段中，在切换之后是一个恒等映射，而在切换之前是视为物理地址直接取指，也可以将其看成一个恒等映射。这完全符合我们的期待：即使切换了地址空间，指令仍应该能够被连续的执行。

注意到在 ``activate`` 的最后，我们插入了一条汇编指令 ``sfence.vma`` ，它又起到什么作用呢？

让我们再来回顾一下多级页表：它相比线性表虽然大量节约了内存占用，但是却需要 MMU 进行更多的隐式访存。如果是一个线性表， MMU 仅需单次访存就能找到页表项并完成地址转换，而多级页表（以 SV39 为例，不考虑大页）最顺利的情况下也需要三次访存。这些额外的访存和真正访问数据的那些访存在空间上并不相邻，加大了多级缓存的压力，一旦缓存缺失将带来巨大的性能惩罚。如果采用多级页表实现，这个问题会变得更为严重，使得地址空间抽象的性能开销过大。

.. _term-tlb:

为了解决性能问题，一种常见的做法是在 CPU 中利用部分硬件资源额外加入一个 **快表** (TLB, Translation Lookaside Buffer) ， 它维护了部分虚拟页号到页表项的键值对。当 MMU 进行地址转换的时候，首先会到快表中看看是否匹配，如果匹配的话直接取出页表项完成地址转换而无需访存；否则再去查页表并将键值对保存在快表中。一旦我们修改 satp 就会切换地址空间，快表中的键值对就会失效（因为快表保存着老地址空间的映射关系，切换到新地址空间后，老的映射关系就没用了）。为了确保 MMU 的地址转换能够及时与 satp 的修改同步，我们需要立即使用 ``sfence.vma`` 指令将快表清空，这样 MMU 就不会看到快表中已经过期的键值对了。

.. note::

    **sfence.vma 是一个屏障(Barrier)**

    对于一种含有快表的 RISC-V CPU 实现来说，我们可以认为 ``sfence.vma`` 的作用就是清空快表。事实上它在特权级规范中被定义为一种含义更加丰富的内存屏障，具体来说： ``sfence.vma`` 可以使得所有发生在它后面的地址转换都能够看到所有排在它前面的写入操作。在不同的硬件配置上这条指令要做的具体事务是有差异的。这条指令还可以被精细配置来减少同步开销，详情请参考 RISC-V 特权级规范。


检查内核地址空间的多级页表设置
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

调用 ``mm::init`` 之后我们就使能了内核动态内存分配、物理页帧管理，还启用了分页模式进入了内核地址空间。之后我们可以通过 ``mm::remap_test`` 来检查内核地址空间的多级页表是否被正确设置：

.. code-block:: rust

    // os/src/mm/memory_set.rs

    pub fn remap_test() {
        let mut kernel_space = KERNEL_SPACE.lock();
        let mid_text: VirtAddr = ((stext as usize + etext as usize) / 2).into();
        let mid_rodata: VirtAddr = ((srodata as usize + erodata as usize) / 2).into();
        let mid_data: VirtAddr = ((sdata as usize + edata as usize) / 2).into();
        assert_eq!(
            kernel_space.page_table.translate(mid_text.floor()).unwrap().writable(),
            false
        );
        assert_eq!(
            kernel_space.page_table.translate(mid_rodata.floor()).unwrap().writable(),
            false,
        );
        assert_eq!(
            kernel_space.page_table.translate(mid_data.floor()).unwrap().executable(),
            false,
        );
        println!("remap_test passed!");
    }

在上述函数的实现中，分别通过手动查内核多级页表的方式验证代码段和只读数据段不允许被写入，同时不允许从数据段上取指执行。

.. _term-trampoline:

跳板机制的实现
------------------------------------

上一小节我们看到无论是内核还是应用的地址空间，最高的虚拟页面都是一个跳板。同时应用地址空间的次高虚拟页面还被设置为用来存放应用的 Trap 上下文。那么跳板究竟起什么作用呢？为何不直接把 Trap 上下文仍放到应用的内核栈中呢？

回忆曾在第二章介绍过的 :ref:`Trap 上下文保存与恢复 <trap-context-save-restore>` 。当一个应用 Trap 到内核时，``sscratch`` 已指向该应用的内核栈栈顶，我们用一条指令即可从用户栈切换到内核栈，然后直接将 Trap 上下文压入内核栈栈顶。当 Trap 处理完毕返回用户态的时候，将 Trap 上下文中的内容恢复到寄存器上，最后将保存着应用用户栈顶的 ``sscratch`` 与 sp 进行交换，也就从内核栈切换回了用户栈。在这个过程中， ``sscratch`` 起到了非常关键的作用，它使得我们可以在不破坏任何通用寄存器的情况下，完成用户栈与内核栈的切换，以及位于内核栈顶的 Trap 上下文的保存与恢复。

然而，一旦使能了分页机制，一切就并没有这么简单了，我们必须在这个过程中同时完成地址空间的切换。具体来说，当 ``__alltraps`` 保存 Trap 上下文的时候，我们必须通过修改 satp 从应用地址空间切换到内核地址空间，因为 trap handler 只有在内核地址空间中才能访问；同理，在 ``__restore`` 恢复 Trap 上下文的时候，我们也必须从内核地址空间切换回应用地址空间，因为应用的代码和数据只能在它自己的地址空间中才能访问，应用是看不到内核地址空间的。这样就要求地址空间的切换不能影响指令的连续执行，即要求应用和内核地址空间在切换地址空间指令附近是平滑的。

.. _term-meltdown:

.. note::

    **内核与应用地址空间的隔离**

    目前我们的设计思路 A 是：对内核建立唯一的内核地址空间存放内核的代码、数据，同时对于每个应用维护一个它们自己的用户地址空间，因此在 Trap 的时候就需要进行地址空间切换，而在任务切换的时候无需进行（因为这个过程全程在内核内完成）。

    另外的一种设计思路 B 是：让每个应用都有一个包含应用和内核的地址空间，并将其中的逻辑段分为内核和用户两部分，分别映射到内核/用户的数据和代码，且分别在 CPU 处于 S/U 特权级时访问。此设计中并不存在一个单独的内核地址空间。

    设计方式 B 的优点在于： Trap 的时候无需切换地址空间，而在任务切换的时候才需要切换地址空间。相对而言，设计方式B比设计方式A更容易实现，在应用高频进行系统调用的时候，采用设计方式B能够避免频繁地址空间切换的开销，这通常源于快表或 cache 的失效问题。但是设计方式B也有缺点：即内核的逻辑段需要在每个应用的地址空间内都映射一次，这会带来一些无法忽略的内存占用开销，并显著限制了嵌入式平台（如我们所采用的 K210 ）的任务并发数。此外，设计方式 B 无法防御针对处理器电路设计缺陷的侧信道攻击（如 `熔断 (Meltdown) 漏洞 <https://cacm.acm.org/magazines/2020/6/245161-meltdown/fulltext>`_ ），使得恶意应用能够以某种方式间接“看到”内核地址空间中的数据，使得用户隐私数据有可能被泄露。将内核与地址空间隔离便是修复此漏洞的一种方法。

    经过权衡，在本教程中我们参考 MIT 的教学 OS `xv6 <https://github.com/mit-pdos/xv6-riscv>`_ ，采用内核和应用地址空间隔离的设计。

我们为何将应用的 Trap 上下文放到应用地址空间的次高页面而不是内核地址空间中的内核栈中呢？原因在于，在保存 Trap 上下文到内核栈中之前，我们必须完成两项工作：1）必须先切换到内核地址空间，这就需要将内核地址空间的 token 写入 satp 寄存器；2）之后还需要保存应用的内核栈栈顶的位置，这样才能以它为基址保存 Trap 上下文。这两步需要用寄存器作为临时周转，然而我们无法在不破坏任何一个通用寄存器的情况下做到这一点。因为事实上我们需要用到内核的两条信息：内核地址空间的 token ，以及应用的内核栈栈顶的位置，RISC-V却只提供一个 ``sscratch`` 寄存器可用来进行周转。所以，我们不得不将 Trap 上下文保存在应用地址空间的一个虚拟页面中，而不是切换到内核地址空间去保存。


扩展Trap 上下文
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

为了方便实现，我们在 Trap 上下文中包含更多内容（和我们关于上下文的定义有些不同，它们在初始化之后便只会被读取而不会被写入，并不是每次都需要保存/恢复）：

.. code-block:: rust
    :linenos:
    :emphasize-lines: 8,9,10

    // os/src/trap/context.rs

    #[repr(C)]
    pub struct TrapContext {
        pub x: [usize; 32],
        pub sstatus: Sstatus,
        pub sepc: usize,
        pub kernel_satp: usize,
        pub kernel_sp: usize,
        pub trap_handler: usize,
    }

在多出的三个字段中：

- ``kernel_satp`` 表示内核地址空间的 token ，即内核页表的起始物理地址；
- ``kernel_sp`` 表示当前应用在内核地址空间中的内核栈栈顶的虚拟地址；
- ``trap_handler`` 表示内核中 trap handler 入口点的虚拟地址。

它们在应用初始化的时候由内核写入应用地址空间中的 TrapContext 的相应位置，此后就不再被修改。



切换地址空间
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

让我们来看一下现在的 ``__alltraps`` 和 ``__restore`` 各是如何在保存和恢复 Trap 上下文的同时也切换地址空间的：

.. code-block:: riscv
    :linenos:

    # os/src/trap/trap.S

        .section .text.trampoline
        .globl __alltraps
        .globl __restore
        .align 2
    __alltraps:
        csrrw sp, sscratch, sp
        # now sp->*TrapContext in user space, sscratch->user stack
        # save other general purpose registers
        sd x1, 1*8(sp)
        # skip sp(x2), we will save it later
        sd x3, 3*8(sp)
        # skip tp(x4), application does not use it
        # save x5~x31
        .set n, 5
        .rept 27
            SAVE_GP %n
            .set n, n+1
        .endr
        # we can use t0/t1/t2 freely, because they have been saved in TrapContext
        csrr t0, sstatus
        csrr t1, sepc
        sd t0, 32*8(sp)
        sd t1, 33*8(sp)
        # read user stack from sscratch and save it in TrapContext
        csrr t2, sscratch
        sd t2, 2*8(sp)
        # load kernel_satp into t0
        ld t0, 34*8(sp)
        # load trap_handler into t1
        ld t1, 36*8(sp)
        # move to kernel_sp
        ld sp, 35*8(sp)
        # switch to kernel space
        csrw satp, t0
        sfence.vma
        # jump to trap_handler
        jr t1

    __restore:
        # a0: *TrapContext in user space(Constant); a1: user space token
        # switch to user space
        csrw satp, a1
        sfence.vma
        csrw sscratch, a0
        mv sp, a0
        # now sp points to TrapContext in user space, start restoring based on it
        # restore sstatus/sepc
        ld t0, 32*8(sp)
        ld t1, 33*8(sp)
        csrw sstatus, t0
        csrw sepc, t1
        # restore general purpose registers except x0/sp/tp
        ld x1, 1*8(sp)
        ld x3, 3*8(sp)
        .set n, 5
        .rept 27
            LOAD_GP %n
            .set n, n+1
        .endr
        # back to user stack
        ld sp, 2*8(sp)
        sret

- 当应用 Trap 进入内核的时候，硬件会设置一些 CSR 并在 S 特权级下跳转到 ``__alltraps`` 保存 Trap 上下文。此时 sp 寄存器仍指向用户栈，但 ``sscratch`` 则被设置为指向应用地址空间中存放 Trap 上下文的位置（实际在次高页面）。随后，就像之前一样，我们 ``csrrw`` 交换 sp 和 ``sscratch`` ，并基于指向 Trap 上下文位置的 sp 开始保存通用寄存器和一些 CSR ，这个过程在第 28 行结束。到这里，我们就全程在应用地址空间中完成了保存 Trap 上下文的工作。
  
- 接下来该考虑切换到内核地址空间并跳转到 trap handler 了。

  - 第 30 行将内核地址空间的 token 载入到 t0 寄存器中；
  - 第 32 行将 trap handler 入口点的虚拟地址载入到 t1 寄存器中；
  - 第 34 行直接将 sp 修改为应用内核栈顶的地址；

  注：这三条信息均是内核在初始化该应用的时候就已经设置好的。

  - 第 36~37 行将 satp 修改为内核地址空间的 token 并使用 ``sfence.vma`` 刷新快表，这就切换到了内核地址空间；
  - 第 39 行 最后通过 ``jr`` 指令跳转到 t1 寄存器所保存的trap handler 入口点的地址。

  注：这里我们不能像之前的章节那样直接 ``call trap_handler`` ，原因稍后解释。

- 当内核将 Trap 处理完毕准备返回用户态的时候会 *调用* ``__restore`` （符合RISC-V函数调用规范），它有两个参数：第一个是 Trap 上下文在应用地址空间中的位置，这个对于所有的应用来说都是相同的，在 a0 寄存器中传递；第二个则是即将回到的应用的地址空间的 token ，在 a1 寄存器中传递。

  - 第 44~45 行先切换回应用地址空间（注：Trap 上下文是保存在应用地址空间中）；
  - 第 46 行将传入的 Trap 上下文位置保存在 ``sscratch`` 寄存器中，这样 ``__alltraps`` 中才能基于它将 Trap 上下文保存到正确的位置；
  - 第 47 行将 sp 修改为 Trap 上下文的位置，后面基于它恢复各通用寄存器和 CSR；
  - 第 64 行最后通过 ``sret`` 指令返回用户态。


建立跳板页面
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^


接下来还需要考虑切换地址空间前后指令能否仍能连续执行。可以看到我们将 ``trap.S`` 中的整段汇编代码放置在 ``.text.trampoline`` 段，并在调整内存布局的时候将它对齐到代码段的一个页面中：

.. code-block:: diff
    :linenos:

    # os/src/linker.ld

        stext = .;
        .text : {
            *(.text.entry)
    +        . = ALIGN(4K);
    +        strampoline = .;
    +        *(.text.trampoline);
    +        . = ALIGN(4K);
            *(.text .text.*)
        }

这样，这段汇编代码放在一个物理页帧中，且 ``__alltraps`` 恰好位于这个物理页帧的开头，其物理地址被外部符号 ``strampoline`` 标记。在开启分页模式之后，内核和应用代码都只能看到各自的虚拟地址空间，而在它们的视角中，这段汇编代码都被放在它们各自地址空间的最高虚拟页面上，由于这段汇编代码在执行的时候涉及到地址空间切换，故而被称为跳板页面。

在产生trap前后的一小段时间内会有一个比较 **极端** 的情况，即刚产生trap时，CPU已经进入了内核态（即Supervisor Mode），但此时执行代码和访问数据还是在应用程序所处的用户态虚拟地址空间中，而不是我们通常理解的内核虚拟地址空间。在这段特殊的时间内，CPU指令为什么能够被连续执行呢？这里需要注意：无论是内核还是应用的地址空间，跳板的虚拟页均位于同样位置，且它们也将会映射到同一个实际存放这段汇编代码的物理页帧。也就是说，在执行 ``__alltraps`` 或 ``__restore`` 函数进行地址空间切换的时候，应用的用户态虚拟地址空间和操作系统内核的内核态虚拟地址空间对切换地址空间的指令所在页的映射方式均是相同的，这就说明了这段切换地址空间的指令控制流仍是可以连续执行的。

现在可以说明我们在创建用户/内核地址空间中用到的 ``map_trampoline`` 是如何实现的了：

.. code-block:: rust
    :linenos:

    // os/src/config.rs

    pub const TRAMPOLINE: usize = usize::MAX - PAGE_SIZE + 1;

    // os/src/mm/memory_set.rs

    impl MemorySet {
        /// Mention that trampoline is not collected by areas.
        fn map_trampoline(&mut self) {
            self.page_table.map(
                VirtAddr::from(TRAMPOLINE).into(),
                PhysAddr::from(strampoline as usize).into(),
                PTEFlags::R | PTEFlags::X,
            );
        }
    }

这里我们为了实现方便并没有新增逻辑段 ``MemoryArea`` 而是直接在多级页表中插入一个从地址空间的最高虚拟页面映射到跳板汇编代码所在的物理页帧的键值对，访问权限与代码段相同，即 ``RX`` （可读可执行）。

最后可以解释为何我们在 ``__alltraps`` 中需要借助寄存器 ``jr`` 而不能直接 ``call trap_handler`` 了。因为在内存布局中，这条 ``.text.trampoline`` 段中的跳转指令和 ``trap_handler`` 都在代码段之内，汇编器（Assembler）和链接器（Linker）会根据 ``linker-qemu/k210.ld`` 的地址布局描述，设定跳转指令的地址，并计算二者地址偏移量，让跳转指令的实际效果为当前 pc 自增这个偏移量。但实际上由于我们设计的缘故，这条跳转指令在被执行的时候，它的虚拟地址被操作系统内核设置在地址空间中的最高页面之内，所以加上这个偏移量并不能正确的得到 ``trap_handler`` 的入口地址。

**问题的本质可以概括为：跳转指令实际被执行时的虚拟地址和在编译器/汇编器/链接器进行后端代码生成和链接形成最终机器码时设置此指令的地址是不同的。** 

加载和执行应用程序
------------------------------------

扩展任务控制块
^^^^^^^^^^^^^^^^^^^^^^^^^^^

为了让应用在运行时有一个安全隔离且符合编译器给应用设定的地址空间布局的虚拟地址空间，操作系统需要对任务进行更多的管理，所以任务控制块相比第三章也包含了更多内容：

.. code-block:: rust
    :linenos:
    :emphasize-lines: 6,7,8

    // os/src/task/task.rs

    pub struct TaskControlBlock {
        pub task_cx: TaskContext,
        pub task_status: TaskStatus,
        pub memory_set: MemorySet,
        pub trap_cx_ppn: PhysPageNum,
        pub base_size: usize,
    }

除了应用的地址空间 ``memory_set`` 之外，还有位于应用地址空间次高页的 Trap 上下文被实际存放在物理页帧的物理页号 ``trap_cx_ppn`` ，它能够方便我们对于 Trap 上下文进行访问。此外， ``base_size`` 统计了应用数据的大小，也就是在应用地址空间中从 :math:`\text{0x0}` 开始到用户栈结束一共包含多少字节。它后续还应该包含用于应用动态内存分配的堆空间的大小，但目前暂不支持。



更新对任务控制块的管理
^^^^^^^^^^^^^^^^^^^^^^^^^^^

下面是任务控制块的创建：

.. code-block:: rust
    :linenos:

    // os/src/config.rs

    /// Return (bottom, top) of a kernel stack in kernel space.
    pub fn kernel_stack_position(app_id: usize) -> (usize, usize) {
        let top = TRAMPOLINE - app_id * (KERNEL_STACK_SIZE + PAGE_SIZE);
        let bottom = top - KERNEL_STACK_SIZE;
        (bottom, top)
    }

    // os/src/task/task.rs

    impl TaskControlBlock {
        pub fn new(elf_data: &[u8], app_id: usize) -> Self {
            // memory_set with elf program headers/trampoline/trap context/user stack
            let (memory_set, user_sp, entry_point) = MemorySet::from_elf(elf_data);
            let trap_cx_ppn = memory_set
                .translate(VirtAddr::from(TRAP_CONTEXT).into())
                .unwrap()
                .ppn();
            let task_status = TaskStatus::Ready;
            // map a kernel-stack in kernel space
            let (kernel_stack_bottom, kernel_stack_top) = kernel_stack_position(app_id);
            KERNEL_SPACE
                .exclusive_access()
                .insert_framed_area(
                    kernel_stack_bottom.into(),
                    kernel_stack_top.into(),
                    MapPermission::R | MapPermission::W,
                );
            let task_control_block = Self {
                task_status,
                task_cx: TaskContext::goto_trap_return(kernel_stack_top),
                memory_set,
                trap_cx_ppn,
                base_size: user_sp,
            };
            // prepare TrapContext in user space
            let trap_cx = task_control_block.get_trap_cx();
            *trap_cx = TrapContext::app_init_context(
                entry_point,
                user_sp,
                KERNEL_SPACE.exclusive_access().token(),
                kernel_stack_top,
                trap_handler as usize,
            );
            task_control_block
        }
    }

- 第 15 行，解析传入的 ELF 格式数据构造应用的地址空间 ``memory_set`` 并获得其他信息；
- 第 16 行，从地址空间 ``memory_set`` 中查多级页表找到应用地址空间中的 Trap 上下文实际被放在哪个物理页帧；
- 第 22 行，根据传入的应用 ID ``app_id`` 调用在 ``config`` 子模块中定义的 ``kernel_stack_position`` 找到
  应用的内核栈预计放在内核地址空间 ``KERNEL_SPACE`` 中的哪个位置，并通过 ``insert_framed_area`` 实际将这个逻辑段
  加入到内核地址空间中；

.. _trap-return-intro:

- 第 30~32 行，在应用的内核栈顶压入一个跳转到 ``trap_return`` 而不是 ``__restore`` 的任务上下文，这主要是为了能够支持对该应用的启动并顺利切换到用户地址空间执行。在构造方式上，只是将 ra 寄存器的值设置为 ``trap_return`` 的地址。 ``trap_return`` 是后面要介绍的新版的 Trap 处理的一部分。

  这里对裸指针解引用成立的原因在于：当前已经进入了内核地址空间，而要操作的内核栈也是在内核地址空间中的；
- 第 33~36 行，用上面的信息来创建并返回任务控制块实例 ``task_control_block``；
- 第 38 行，查找该应用的 Trap 上下文的内核虚地址。由于应用的 Trap 上下文是在应用地址空间而不是在内核地址空间中，我们只能手动查页表找到 Trap 上下文实际被放在的物理页帧，然后通过之前介绍的 :ref:`在内核地址空间读写特定物理页帧的能力 <access-frame-in-kernel-as>` 获得在用户空间的 Trap 上下文的可变引用用于初始化：

  .. code-block:: rust

    // os/src/task/task.rs

    impl TaskControlBlock {
        pub fn get_trap_cx(&self) -> &'static mut TrapContext {
            self.trap_cx_ppn.get_mut()
        }
    }
  
  此处需要说明的是，返回 ``'static`` 的可变引用和之前一样可以看成一个绕过 unsafe 的裸指针；而 ``PhysPageNum::get_mut`` 是一个泛型函数，由于我们已经声明了总体返回 ``TrapContext`` 的可变引用，则Rust编译器会给 ``get_mut`` 泛型函数针对具体类型 ``TrapContext`` 的情况生成一个特定版本的 ``get_mut`` 函数实现。在 ``get_trap_cx`` 函数中则会静态调用 ``get_mut`` 泛型函数的特定版本实现。
- 第 39~45 行，调用 ``TrapContext::app_init_context`` 函数，通过应用的 Trap 上下文的可变引用来对其进行初始化。具体初始化过程如下所示：

  .. code-block:: rust
      :linenos:
      :emphasize-lines: 8,9,10,18,19,20

      // os/src/trap/context.rs

      impl TrapContext {
          pub fn set_sp(&mut self, sp: usize) { self.x[2] = sp; }
          pub fn app_init_context(
              entry: usize,
              sp: usize,
              kernel_satp: usize,
              kernel_sp: usize,
              trap_handler: usize,
          ) -> Self {
              let mut sstatus = sstatus::read();
              sstatus.set_spp(SPP::User);
              let mut cx = Self {
                  x: [0; 32],
                  sstatus,
                  sepc: entry,
                  kernel_satp,
                  kernel_sp,
                  trap_handler,
              };
              cx.set_sp(sp);
              cx
          }
      }

  和之前实现相比， ``TrapContext::app_init_context`` 需要补充上让应用在 ``__alltraps`` 能够顺利进入到内核地址空间并跳转到 trap handler 入口点的相关信息。

在内核初始化的时候，需要将所有的应用加载到全局应用管理器中：

.. code-block:: rust
    :linenos:

    // os/src/task/mod.rs

    struct TaskManagerInner {
        tasks: Vec<TaskControlBlock>,
        current_task: usize,
    }

    lazy_static! {
        pub static ref TASK_MANAGER: TaskManager = {
            println!("init TASK_MANAGER");
            let num_app = get_num_app();
            println!("num_app = {}", num_app);
            let mut tasks: Vec<TaskControlBlock> = Vec::new();
            for i in 0..num_app {
                tasks.push(TaskControlBlock::new(
                    get_app_data(i),
                    i,
                ));
            }
            TaskManager {
                num_app,
                inner: RefCell::new(TaskManagerInner {
                    tasks,
                    current_task: 0,
                }),
            }
        };
    }

可以看到，在 ``TaskManagerInner`` 中我们使用向量 ``Vec`` 来保存任务控制块。在全局任务管理器 ``TASK_MANAGER`` 初始化的时候，只需使用 ``loader`` 子模块提供的 ``get_num_app`` 和 ``get_app_data`` 分别获取链接到内核的应用数量和每个应用的 ELF 文件格式的数据，然后依次给每个应用创建任务控制块并加入到向量中即可。将 ``current_task`` 设置为 0 ，表示内核将从第 0 个应用开始执行。

回过头来介绍一下应用构建器 ``os/build.rs`` 的改动：

- 首先，我们在 ``.incbin`` 中不再插入清除全部符号的应用二进制镜像 ``*.bin`` ，而是将应用的 ELF 执行文件直接链接进来；
- 其次，在链接每个 ELF 执行文件之前我们都加入一行 ``.align 3`` 来确保它们对齐到 8 字节，这是由于如果不这样做， ``xmas-elf`` crate 可能会在解析 ELF 的时候进行不对齐的内存读写，例如使用 ``ld`` 指令从内存的一个没有对齐到 8 字节的地址加载一个 64 位的值到一个通用寄存器。而在 k210 平台上，由于其硬件限制，这种情况会触发一个内存读写不对齐的异常，导致解析无法正常完成。

为了方便后续的实现，全局任务管理器还需要提供关于当前应用与地址空间有关的一些信息：

.. code-block:: rust
    :linenos:

    // os/src/task/mod.rs

    impl TaskManager {
        fn get_current_token(&self) -> usize {
            let inner = self.inner.borrow();
            let current = inner.current_task;
            inner.tasks[current].get_user_token()
        }

        fn get_current_trap_cx(&self) -> &mut TrapContext {
            let inner = self.inner.borrow();
            let current = inner.current_task;
            inner.tasks[current].get_trap_cx()
        }
    }

    pub fn current_user_token() -> usize {
        TASK_MANAGER.get_current_token()
    }

    pub fn current_trap_cx() -> &'static mut TrapContext {
        TASK_MANAGER.get_current_trap_cx()
    }

通过 ``current_user_token`` 可以获得当前正在执行的应用的地址空间的 token 。同时，该应用地址空间中的 Trap 上下文很关键，内核需要访问它来拿到应用进行系统调用的参数并将系统调用返回值写回，通过 ``current_trap_cx`` 内核可以拿到它访问这个 Trap 上下文的可变引用并进行读写。

改进 Trap 处理的实现
------------------------------------

让我们来看现在 ``trap_handler`` 的改进实现：

.. code-block:: rust
    :linenos:

    // os/src/trap/mod.rs

    fn set_kernel_trap_entry() {
        unsafe {
            stvec::write(trap_from_kernel as usize, TrapMode::Direct);
        }
    }

    #[no_mangle]
    pub fn trap_from_kernel() -> ! {
        panic!("a trap from kernel!");
    }

    #[no_mangle]
    pub fn trap_handler() -> ! {
        set_kernel_trap_entry();
        let cx = current_trap_cx();
        let scause = scause::read();
        let stval = stval::read();
        match scause.cause() {
            ...
        }
        trap_return();
    }

由于应用的 Trap 上下文不在内核地址空间，因此我们调用 ``current_trap_cx`` 来获取当前应用的 Trap 上下文的可变引用而不是像之前那样作为参数传入 ``trap_handler`` 。至于 Trap 处理的过程则没有发生什么变化。

注意到，在 ``trap_handler`` 的开头还调用 ``set_kernel_trap_entry`` 将 ``stvec`` 修改为同模块下另一个函数 ``trap_from_kernel`` 的地址。这就是说，一旦进入内核后再次触发到 S态 Trap，则硬件在设置一些 CSR 寄存器之后，会跳过对通用寄存器的保存过程，直接跳转到 ``trap_from_kernel`` 函数，在这里直接 ``panic`` 退出。这是因为内核和应用的地址空间分离之后，U态 --> S态 与 S态 --> S态 的 Trap 上下文保存与恢复实现方式/Trap 处理逻辑有很大差别。这里为了简单起见，弱化了 S态 --> S态的 Trap 处理过程：直接 ``panic`` 。

在 ``trap_handler`` 完成 Trap 处理之后，我们需要调用 ``trap_return`` 返回用户态：

.. code-block:: rust
    :linenos:

    // os/src/trap/mod.rs

    fn set_user_trap_entry() {
        unsafe {
            stvec::write(TRAMPOLINE as usize, TrapMode::Direct);
        }
    }

    #[no_mangle]
    pub fn trap_return() -> ! {
        set_user_trap_entry();
        let trap_cx_ptr = TRAP_CONTEXT;
        let user_satp = current_user_token();
        extern "C" {
            fn __alltraps();
            fn __restore();
        }
        let restore_va = __restore as usize - __alltraps as usize + TRAMPOLINE;
        unsafe {
            asm!(
                "fence.i",
                "jr {restore_va}",
                restore_va = in(reg) restore_va,
                in("a0") trap_cx_ptr,
                in("a1") user_satp,
                options(noreturn)
            );
        }
        panic!("Unreachable in back_to_user!");
    }

- 第 11 行，在 ``trap_return`` 的开始处就调用 ``set_user_trap_entry`` ，来让应用 Trap 到 S 的时候可以跳转到 ``__alltraps`` 。注：我们把 ``stvec`` 设置为内核和应用地址空间共享的跳板页面的起始地址 ``TRAMPOLINE`` 而不是编译器在链接时看到的 ``__alltraps`` 的地址。这是因为启用分页模式之后，内核只能通过跳板页面上的虚拟地址来实际取得 ``__alltraps`` 和 ``__restore`` 的汇编代码。
- 第 12~13 行，准备好 ``__restore`` 需要两个参数：分别是 Trap 上下文在应用地址空间中的虚拟地址和要继续执行的应用地址空间的 token 。
  
  最后我们需要跳转到 ``__restore`` ，以执行：切换到应用地址空间、从 Trap 上下文中恢复通用寄存器、 ``sret`` 继续执行应用。它的关键在于如何找到 ``__restore`` 在内核/应用地址空间中共同的虚拟地址。

- 第 18 行，展示了计算 ``__restore`` 虚地址的过程：由于 ``__alltraps`` 是对齐到地址空间跳板页面的起始地址 ``TRAMPOLINE`` 上的， 则 ``__restore`` 的虚拟地址只需在 ``TRAMPOLINE`` 基础上加上 ``__restore`` 相对于 ``__alltraps`` 的偏移量即可。这里 ``__alltraps`` 和 ``__restore`` 都是指编译器在链接时看到的内核内存布局中的地址。


- 第 20-27 行，首先需要使用 ``fence.i`` 指令清空指令缓存 i-cache 。这是因为，在内核中进行的一些操作可能导致一些原先存放某个应用代码的物理页帧如今用来存放数据或者是其他应用的代码，i-cache 中可能还保存着该物理页帧的错误快照。因此我们直接将整个 i-cache 清空避免错误。接着使用 ``jr`` 指令完成了跳转到 ``__restore`` 的任务。  

当每个应用第一次获得 CPU 使用权即将进入用户态执行的时候，它的内核栈顶放置着我们在 :ref:`内核加载应用的时候 <trap-return-intro>` 构造的一个任务上下文：

.. code-block:: rust

    // os/src/task/context.rs

    impl TaskContext {
        pub fn goto_trap_return() -> Self {
            Self {
                ra: trap_return as usize,
                s: [0; 12],
            }
        }
    }

在 ``__switch`` 切换到该应用的任务上下文的时候，内核将会跳转到 ``trap_return`` 并返回用户态开始该应用的启动执行。

改进 sys_write 的实现
------------------------------------

类似Trap处理的改进，由于内核和应用地址空间的隔离， ``sys_write`` 不再能够直接访问位于应用空间中的数据，而需要手动查页表才能知道那些数据被放置在哪些物理页帧上并进行访问。

为此，页表模块 ``page_table`` 提供了将应用地址空间中一个缓冲区转化为在内核空间中能够直接访问的形式的辅助函数：

.. code-block:: rust
    :linenos:

    // os/src/mm/page_table.rs

    pub fn translated_byte_buffer(
        token: usize,
        ptr: *const u8,
        len: usize
    ) -> Vec<&'static [u8]> {
        let page_table = PageTable::from_token(token);
        let mut start = ptr as usize;
        let end = start + len;
        let mut v = Vec::new();
        while start < end {
            let start_va = VirtAddr::from(start);
            let mut vpn = start_va.floor();
            let ppn = page_table
                .translate(vpn)
                .unwrap()
                .ppn();
            vpn.step();
            let mut end_va: VirtAddr = vpn.into();
            end_va = end_va.min(VirtAddr::from(end));
            if end_va.page_offset() == 0 {
                v.push(&mut ppn.get_bytes_array()[start_va.page_offset()..]);
            } else {
                v.push(&mut ppn.get_bytes_array()[start_va.page_offset()..end_va.page_offset()]);
            }
            start = end_va.into();
        }
        v
    }

参数中的 ``token`` 是某个应用地址空间的 token ， ``ptr`` 和 ``len`` 则分别表示该地址空间中的一段缓冲区的起始地址和长度(注：这个缓冲区的应用虚拟地址范围是连续的)。 ``translated_byte_buffer`` 会以向量的形式返回一组可以在内核空间中直接访问的字节数组切片（注：这个缓冲区的内核虚拟地址范围有可能是不连续的），具体实现在这里不再赘述。

进而我们可以完成对 ``sys_write`` 系统调用的改造：

.. code-block:: rust

    // os/src/syscall/fs.rs

    pub fn sys_write(fd: usize, buf: *const u8, len: usize) -> isize {
        match fd {
            FD_STDOUT => {
                let buffers = translated_byte_buffer(current_user_token(), buf, len);
                for buffer in buffers {
                    print!("{}", core::str::from_utf8(buffer).unwrap());
                }
                len as isize
            },
            _ => {
                panic!("Unsupported fd in sys_write!");
            }
        }
    }

上述函数尝试将按应用的虚地址指向的缓冲区转换为一组按内核虚地址指向的字节数组切片构成的向量，然后把每个字节数组切片转化为字符串``&str`` 然后输出即可。



小结
-------------------------------------

这一章内容很多，讲解了 **地址空间** 这一抽象概念是如何在一个具体的“头甲龙”操作系统中实现的。这里面的核心内容是如何建立基于页表机制的虚拟地址空间。为此，操作系统需要知道并管理整个系统中的物理内存；需要建立虚拟地址到物理地址映射关系的页表；并基于页表给操作系统自身和每个应用提供一个虚拟地址空间；并需要对管理应用的任务控制块进行扩展，确保能对应用的地址空间进行管理；由于应用和内核的地址空间是隔离的，需要有一个跳板来帮助完成应用与内核之间的切换执行；并导致了对异常、中断、系统调用的相应更改。这一系列的改进，最终的效果是编写应用更加简单了，且应用的执行或错误不会影响到内核和其他应用的正常工作。为了得到这些好处，我们需要比较费劲地进化我们的操作系统。如果同学结合阅读代码，编译并运行应用+内核，读懂了上面的文档，那完成本章的实验就有了一个坚实的基础。

如果同学能想明白如何插入/删除页表；如何在 ``trap_handler`` 下处理 ``LoadPageFault`` ；以及 ``sys_get_time`` 在使能页机制下如何实现，那就会发现下一节的实验练习也许 **就和lab1一样** 。

.. [#tutus] 头甲龙最早出现在1.8亿年以前的侏罗纪中期，是身披重甲的食素恐龙，尾巴末端的尾锤，是防身武器。
