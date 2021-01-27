基于地址空间的分时多任务
==============================================================

本节我们介绍如何基于地址空间抽象而不是对于物理内存的直接访问来实现第三章的分时多任务系统。

内核初始映射
------------------------------------

当 SBI 实现（本项目中基于 RustSBI）初始化完成后， CPU 将跳转到内核入口点并在 S 特权级上执行，此时还并没有开启分页模式
，内核的每一次访存仍被视为一个物理地址直接访问物理内存。而在开启分页模式之后，内核的代码在访存的时候只能看到内核地址空间，
此时每次访存将被视为一个虚拟地址且需要通过 MMU 基于内核地址空间的多级页表的地址转换。这两种模式之间的过渡在内核初始化期间
完成。

我们创建内核地址空间的全局实例：

.. code-block:: rust

    // os/src/mm/memory_set.rs

    lazy_static! {
        pub static ref KERNEL_SPACE: Arc<Mutex<MemorySet>> = Arc::new(Mutex::new(
            MemorySet::new_kernel()
        ));
    }

从之前对于 ``lazy_static!`` 宏的介绍可知， ``KERNEL_SPACE`` 在运行期间它第一次被用到时才会实际进行初始化，而它所
占据的空间则是编译期被放在全局数据段中。这里使用经典的 ``Arc<Mutex<T>>`` 组合是因为我们既需要 ``Arc<T>`` 提供的共享
引用，也需要 ``Mutex<T>`` 提供的互斥访问。在多核环境下才能体现出它的全部能力，目前在单核环境下主要是为了通过编译器检查。

在 ``rust_main`` 函数中，我们首先调用 ``mm::init`` 进行内存管理子系统的初始化：

.. code-block:: rust

    // os/src/mm/mod.rs

    pub use memory_set::KERNEL_SPACE;

    pub fn init() {
        heap_allocator::init_heap();
        frame_allocator::init_frame_allocator();
        KERNEL_SPACE.lock().activate();
    }

可以看到，我们最先进行了全局动态内存分配器的初始化，因为接下来马上就要用到 Rust 的堆数据结构。接下来我们初始化物理页帧
管理器（内含堆数据结构 ``Vec<T>`` ）使能可用物理页帧的分配和回收能力。最后我们创建内核地址空间并让 CPU 开启分页模式， 
MMU 在地址转换的时候使用内核的多级页表，这一切均在一行之内做到：

- 首先，我们引用 ``KERNEL_SPACE`` ，这是它第一次被使用，就在此时它会被初始化，调用 ``MemorySet::new_kernel`` 
  创建一个内核地址空间并使用 ``Arc<Mutex<T>>`` 包裹起来；
- 接着使用 ``.lock()`` 获取一个可变引用 ``&mut MemorySet`` 。需要注意的是这里发生了两次隐式类型转换：

  1.  我们知道 
      ``lock`` 是 ``Mutex<T>`` 的方法而不是 ``Arc<T>`` 的方法，由于 ``Arc<T>`` 实现了 ``Deref`` Trait ，当 
      ``lock`` 需要一个 ``&Mutex<T>`` 类型的参数的时候，编译器会自动将传入的 ``&Arc<Mutex<T>>`` 转换为 
      ``&Mutex<T>`` 这样就实现了类型匹配；
  2.  事实上 ``Mutex<T>::lock`` 返回的是一个 ``MutexGuard<'a, T>`` ，这同样是 
      RAII 的思想，当这个类型生命周期结束后互斥锁就会被释放。而该类型实现了 ``DerefMut`` Trait，因此当一个函数接受类型
      为 ``&mut T`` 的参数却被传入一个类型为 ``&mut MutexGuard<'a, T>`` 的参数的时候，编译器会自动进行类型转换使
      参数匹配。
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
                    llvm_asm!("sfence.vma" :::: "volatile");
                }
            }
        }

  ``PageTable::token`` 会按照 :ref:`satp CSR 格式要求 <satp-layout>` 构造一个无符号 64 位无符号整数，使得其
  分页模式为 SV39 ，且将当前多级页表的根节点所在的物理页号填充进去。在 ``activate`` 中，我们将这个值写入当前 CPU 的 
  satp CSR ，从这一刻开始 SV39 分页模式就被启用了，而且 MMU 会使用内核地址空间的多级页表进行地址转换。

  我们必须注意切换 satp CSR 是否是一个 *平滑* 的过渡：其含义是指，切换 satp 的指令及其下一条指令这两条相邻的指令的
  虚拟地址是相邻的（由于切换 satp 的指令并不是一条跳转指令， pc 只是简单的自增当前指令的字长），
  而它们所在的物理地址一般情况下也是相邻的，但是它们所经过的地址转换流程却是不同的——切换 satp 导致 MMU 查的多级页表
  是不同的。这就要求前后两个地址空间在切换 satp 的指令 *附近* 的映射满足某种意义上的连续性。

  幸运的是，我们做到了这一点。这条写入 satp 的指令及其下一条指令都在内核内存布局的代码段中，在切换之后是一个恒等映射，
  而在切换之前是视为物理地址直接取指，也可以将其看成一个恒等映射。这完全符合我们的期待：即使切换了地址空间，指令仍应该
  能够被连续的执行。

注意到在 ``activate`` 的最后，我们插入了一条汇编指令 ``sfence.vma`` ，它又起到什么作用呢？

让我们再来回顾一下多级页表：它相比线性表虽然大量节约了内存占用，但是却需要 MMU 进行更多的隐式访存。如果是一个线性表， 
MMU 仅需单次访存就能找到页表项并完成地址转换，而多级页表（以 SV39 为例，不考虑大页）最顺利的情况下也需要三次访存。这些
额外的访存和真正访问数据的那些访存在空间上并不相邻，加大了多级缓存的压力，一旦缓存缺失将带来巨大的性能惩罚。如果采用
多级页表实现，这个问题会变得更为严重，使得地址空间抽象的性能开销过大。

.. _term-tlb:

为了解决性能问题，一种常见的做法是在 CPU 中利用部分硬件资源额外加入一个 **快表** 
(TLB, Translation Lookaside Buffer) ， 它维护了部分虚拟页号到页表项的键值对。当 MMU 进行地址转换的时候，首先
会到快表中看看是否匹配，如果匹配的话直接取出页表项完成地址转换而无需访存；否则再去查页表并将键值对保存在快表中。一旦
我们修改了 satp 切换了地址空间，快表中的键值对就会失效，因为它还表示着上个地址空间的映射关系。为了 MMU 的地址转换
能够及时与 satp 的修改同步，我们可以选择立即使用 ``sfence.vma`` 指令将快表清空，这样 MMU 就不会看到快表中已经
过期的键值对了。

.. note::

    **sfence.vma 是一个屏障**

    对于一种仅含有快表的 RISC-V CPU 实现来说，我们可以认为 ``sfence.vma`` 的作用就是清空快表。事实上它在特权级
    规范中被定义为一种含义更加丰富的内存屏障，具体来说： ``sfence.vma`` 可以使得所有发生在它后面的地址转换都能够
    看到所有排在它前面的写入操作，在不同的平台上这条指令要做的事情也都是不同的。这条指令还可以被精细配置来减少同步开销，
    详情请参考 RISC-V 特权级规范。

调用 ``mm::init`` 之后我们就使能了内核动态内存分配、物理页帧管理，还启用了分页模式进入了内核地址空间。之后我们可以
通过 ``mm::remap_test`` 来检查内核地址空间的多级页表是否被正确设置：

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

其中分别通过手动查多级页表的方式验证代码段和只读数据段不允许被写入，同时不允许从数据段上取指。

加载应用程序
------------------------------------

任务控制块相比第三章也包含了更多内容：

.. code-block:: rust
    :linenos:
    :emphasize-lines: 6,7,8

    // os/src/task/task.rs

    pub struct TaskControlBlock {
        pub task_cx_ptr: usize,
        pub task_status: TaskStatus,
        pub memory_set: MemorySet,
        pub trap_cx_ppn: PhysPageNum,
        pub base_size: usize,
    }

除了应用的地址空间 ``memory_set`` 之外，还有位于应用地址空间次高页的 Trap 上下文被实际存放在物理页帧的物理页号 
``trap_cx_ppn`` ，它能够方便我们对于 Trap 上下文进行访问。此外， ``base_size`` 统计了应用数据的大小，也就是
在应用地址空间中从 :math:`\text{0x0}` 开始到用户栈结束一共包含多少字节。它后续还应该包含用于应用动态内存分配的
堆空间的大小，但我们暂不支持。

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
                .lock()
                .insert_framed_area(
                    kernel_stack_bottom.into(),
                    kernel_stack_top.into(),
                    MapPermission::R | MapPermission::W,
                );
            let task_cx_ptr = (kernel_stack_top - core::mem::size_of::<TaskContext>()) 
                as *mut TaskContext;
            unsafe { *task_cx_ptr = TaskContext::goto_trap_return(); }
            let task_control_block = Self {
                task_cx_ptr: task_cx_ptr as usize,
                task_status,
                memory_set,
                trap_cx_ppn,
                base_size: user_sp,
            };
            // prepare TrapContext in user space
            let trap_cx = task_control_block.get_trap_cx();
            *trap_cx = TrapContext::app_init_context(
                entry_point,
                user_sp,
                KERNEL_SPACE.lock().token(),
                kernel_stack_top,
                trap_handler as usize,
            );
            task_control_block
        }
    }

- 第 15 行，我们解析传入的 ELF 格式数据构造应用的地址空间 ``memory_set`` 并获得其他信息；
- 第 16 行，我们从地址空间 ``memory_set`` 中查多级页表找到应用地址空间中的 Trap 上下文实际被放在哪个物理页帧；
- 第 22 行，我们根据传入的应用 ID ``app_id`` 调用在 ``config`` 子模块中定义的 ``kernel_stack_position`` 找到
  应用的内核栈预计放在内核地址空间 ``KERNEL_SPACE`` 中的哪个位置，并通过 ``insert_framed_area`` 实际将这个逻辑段
  加入到内核地址空间中；


执行应用程序
------------------------------------

跳板的实现
------------------------------------

sys_write 的改动
------------------------------------