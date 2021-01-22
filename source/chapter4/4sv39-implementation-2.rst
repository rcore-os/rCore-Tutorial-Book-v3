实现 SV39 多级页表机制（下）
========================================================

本节我们继续来实现 SV39 多级页表机制。

物理页帧管理
-----------------------------------

从前面的介绍可以看出物理页帧的重要性：它既可以用来实际存放应用的数据，也能够用来存储某个应用多级页表中的一个节点。
目前的物理内存上已经有一部分用于放置内核的代码和数据，我们需要将剩下可用的部分以单个物理页帧为单位管理起来，
当需要存放应用数据或是应用的多级页表需要一个新节点的时候分配一个物理页帧，并在应用出错或退出的时候回收它占有
的所有物理页帧。

首先，我们需要知道物理内存的哪一部分是可用的。在 ``os/src/linker.ld`` 中，我们用符号 ``ekernel`` 指明了
内核数据的终止物理地址，在它之后的物理内存都是可用的。而在 ``config`` 子模块中：

.. code-block:: rust

    // os/src/config.rs

    pub const MEMORY_END: usize = 0x80800000;

我们硬编码整块物理内存的终止物理地址为 ``0x80800000`` 。 而 :ref:`之前 <term-physical-memory>` 提到过物理内存的
起始物理地址为 ``0x80000000`` ，这意味着我们将可用内存大小设置为 :math:`8\text{MiB}` 。
实际上在 Qemu 模拟器上可以通过设置使用更大的物理内存，但这里我们希望
它和真实硬件 K210 的配置保持一致，因此设置为仅使用 :math:`8\text{MiB}` 。我们用一个左闭右开的物理页号区间来表示
可用的物理内存，则：

- 区间的左端点应该是 ``ekernel`` 的物理地址以上取整方式转化成的物理页号；
- 区间的右端点应该是 ``MEMORY_END`` 以下取整方式转化成的物理页号。

这个区间将被传给我们后面实现的物理页帧管理器用于初始化。

我们声明一个 ``FrameAllocator`` Trait 来描述一个物理页帧管理器需要提供哪些功能：

.. code-block:: rust

    // os/src/mm/frame_allocator.rs

    trait FrameAllocator {
        fn new() -> Self;
        fn alloc(&mut self) -> Option<PhysPageNum>;
        fn dealloc(&mut self, ppn: PhysPageNum);
    }

即创建一个实例，还有以物理页号为单位进行物理页帧的分配和回收。

我们实现一种最简单的栈式物理页帧管理策略 ``StackFrameAllocator`` ：

.. code-block:: rust

    // os/src/mm/frame_allocator.rs

    pub struct StackFrameAllocator {
        current: usize,
        end: usize,
        recycled: Vec<usize>,
    }

其中各字段的含义是：物理页号区间 :math:`[\text{current},\text{end})` 此前均 *从未* 被分配出去过，而向量 
``recycled`` 以后入先出的方式保存了被回收的物理页号（注意我们已经自然的将内核堆用起来了）。

初始化非常简单。在通过 ``FrameAllocator`` 的 ``new`` 方法创建实例的时候，只需将区间两端均设为 :math:`0` ，
然后创建一个新的向量；而在它真正被使用起来之前，需要调用 ``init`` 方法将自身的 :math:`[\text{current},\text{end})` 
初始化为可用物理页号区间：

.. code-block:: rust

    // os/src/mm/frame_allocator.rs

    impl FrameAllocator for StackFrameAllocator {
        fn new() -> Self {
            Self {
                current: 0,
                end: 0,
                recycled: Vec::new(),
            }
        }
    }

    impl StackFrameAllocator {
        pub fn init(&mut self, l: PhysPageNum, r: PhysPageNum) {
            self.current = l.0;
            self.end = r.0;
        }
    }

接下来我们来看核心的物理页帧分配和回收如何实现：

.. code-block:: rust

    // os/src/mm/frame_allocator.rs

    impl FrameAllocator for StackFrameAllocator {
        fn alloc(&mut self) -> Option<PhysPageNum> {
            if let Some(ppn) = self.recycled.pop() {
                Some(ppn.into())
            } else {
                if self.current == self.end {
                    None
                } else {
                    self.current += 1;
                    Some((self.current - 1).into())
                }
            }
        }
        fn dealloc(&mut self, ppn: PhysPageNum) {
            let ppn = ppn.0;
            // validity check
            if ppn >= self.current || self.recycled
                .iter()
                .find(|&v| {*v == ppn})
                .is_some() {
                panic!("Frame ppn={:#x} has not been allocated!", ppn);
            }
            // recycle
            self.recycled.push(ppn);
        }
    }

- 在分配 ``alloc`` 的时候，首先会检查栈 ``recycled`` 内有没有之前回收的物理页号，如果有的话直接弹出栈顶并返回；
  否则的话我们只能从之前从未分配过的物理页号区间 :math:`[\text{current},\text{end})` 上进行分配，我们分配它的
  左端点 ``current`` ，同时将管理器内部维护的 ``current`` 加一代表 ``current`` 此前已经被分配过了。在即将返回
  的时候，我们使用 ``into`` 方法将 usize 转换成了物理页号 ``PhysPageNum`` 。

  注意极端情况下可能出现内存耗尽分配失败的情况：即 ``recycled`` 为空且 :math:`\text{current}==\text{end}` 。
  为了涵盖这种情况， ``alloc`` 的返回值被 ``Option`` 包裹，我们返回 ``None`` 即可。
- 在回收 ``dealloc`` 的时候，我们需要检查回收页面的合法性，然后将其压入 ``recycled`` 栈中。回收页面合法有两个
  条件：

  - 该页面之前一定被分配出去过，因此它的物理页号一定 :math:`<\text{current}` ；
  - 该页面没有正处在回收状态，即它的物理页号不能在栈 ``recycled`` 中找到。

  我们通过 ``recycled.iter()`` 获取栈上内容的迭代器，然后通过迭代器的 ``find`` 方法试图
  寻找一个与输入物理页号相同的元素。其返回值是一个 ``Option`` ，如果找到了就会是一个 ``Option::Some`` ，
  这种情况说明我们内核其他部分实现有误，直接报错退出。

下面我们来创建 ``StackFrameAllocator`` 的全局实例 ``FRAME_ALLOCATOR`` ：

.. code-block:: rust

    // os/src/mm/frame_allocator.rs

    use spin::Mutex;

    type FrameAllocatorImpl = StackFrameAllocator;

    lazy_static! {
        pub static ref FRAME_ALLOCATOR: Mutex<FrameAllocatorImpl> =
            Mutex::new(FrameAllocatorImpl::new());
    }

这里我们使用互斥锁 ``Mutex<T>`` 来包裹栈式物理页帧分配器。每次对该分配器进行操作之前，我们都需要先通过 
``FRAME_ALLOCATOR.lock()`` 拿到分配器的可变借用。注意 ``alloc`` 中并没有提供 ``Mutex<T>`` ，它
来自于一个我们在 ``no_std`` 的裸机环境下经常使用的名为 ``spin`` 的 crate ，它仅依赖 Rust 核心库 
``core`` 提供一些可跨平台使用的同步原语，如互斥锁 ``Mutex<T>`` 和读写锁 ``RwLock<T>`` 等。

.. note::

    **Rust 语法卡片：在单核环境下使用 Mutex<T> 的原因**

    在编写一个多线程的应用时，加锁的目的是为了避免数据竞争，使得里层的共享数据结构同一时间只有一个线程
    在对它进行访问。然而，目前我们的内核运行在单 CPU 上，且 Trap 进入内核之后并没有手动打开中断，这也就
    使得同一时间最多只有一条 Trap 执行流并发访问内核的各数据结构，此时应该是并没有任何数据竞争风险的。那么
    加锁的原因其实有两点：

    1. 在不触及 ``unsafe`` 的情况下实现 ``static mut`` 语义。如果读者还有印象， 
       :ref:`前面章节 <term-interior-mutability>` 我们使用 ``RefCell<T>`` 提供了内部可变性去掉了
       声明中的 ``mut`` ，然而麻烦的在于 ``static`` ，在 Rust 中一个类型想被实例化为一个全局变量，则
       该类型必须先告知编译器自己某种意义上是线程安全的，这个过程本身是 ``unsafe`` 的。

       因此我们直接使用 ``Mutex<T>`` ，它既通过 ``lock`` 方法提供了内部可变性，又已经在模块内部告知了
       编译器它的线程安全性。这样 ``unsafe`` 就被隐藏在了 ``spin`` crate 之内，我们无需关心。这种风格
       是 Rust 所推荐的。
    2. 方便后续拓展到真正存在数据竞争风险的多核环境下运行。

    这里引入了一些新概念，比如什么是线程，又如何定义线程安全？读者可以先不必深究，暂时有一个初步的概念即可。

我们需要添加该 crate 的依赖：

.. code-block:: toml

    # os/Cargo.toml

    [dependencies]
    spin = "0.7.0"

在正式分配物理页帧之前，我们需要将物理页帧全局管理器 ``FRAME_ALLOCATOR`` 初始化：

.. code-block:: rust

    // os/src/mm/frame_allocator.rs

    pub fn init_frame_allocator() {
        extern "C" {
            fn ekernel();
        }
        FRAME_ALLOCATOR
            .lock()
            .init(PhysAddr::from(ekernel as usize).ceil(), PhysAddr::from(MEMORY_END).floor());
    }

这里我们调用物理地址 ``PhysAddr`` 的 ``floor/ceil`` 方法分别下/上取整获得可用的物理页号区间。

然后是真正公开给其他子模块调用的分配/回收物理页帧的接口：

.. code-block:: rust

    // os/src/mm/frame_allocator.rs

    pub fn frame_alloc() -> Option<FrameTracker> {
        FRAME_ALLOCATOR
            .lock()
            .alloc()
            .map(|ppn| FrameTracker::new(ppn))
    }

    fn frame_dealloc(ppn: PhysPageNum) {
        FRAME_ALLOCATOR
            .lock()
            .dealloc(ppn);
    }

可以发现， ``frame_alloc`` 的返回值类型并不是 ``FrameAllocator`` 要求的物理页号 ``PhysPageNum`` ，而是将其
进一步包装为一个 ``FrameTracker`` 。这里借用了 RAII 的思想，将一个物理页帧的生命周期绑定到一个 ``FrameTracker`` 
变量上，当一个 ``FrameTracker`` 被创建的时候，我们需要从 ``FRAME_ALLOCATOR`` 中分配一个物理页帧：

.. code-block:: rust

    // os/src/mm/frame_allocator.rs

    pub struct FrameTracker {
        pub ppn: PhysPageNum,
    }

    impl FrameTracker {
        pub fn new(ppn: PhysPageNum) -> Self {
            // page cleaning
            let bytes_array = ppn.get_bytes_array();
            for i in bytes_array {
                *i = 0;
            }
            Self { ppn }
        }
    }

我们将分配来的物理页帧的物理页号作为参数传给 ``FrameTracker`` 的 ``new`` 方法来创建一个 ``FrameTracker`` 
实例。由于这个物理页帧之前可能被分配过并用做其他用途，我们在这里直接将这个物理页帧上的所有字节清零。这一过程并不
那么显然，我们后面再详细介绍。

当一个 ``FrameTracker`` 生命周期结束被编译器回收的时候，我们需要将它控制的物理页帧回收掉 ``FRAME_ALLOCATOR`` 中：

.. code-block:: rust

    // os/src/mm/frame_allocator.rs

    impl Drop for FrameTracker {
        fn drop(&mut self) {
            frame_dealloc(self.ppn);
        }
    }

这里我们只需为 ``FrameTracker`` 实现 ``Drop`` Trait 即可。当一个 ``FrameTracker`` 实例被回收的时候，它的 
``drop`` 方法会自动被编译器调用，通过之前实现的 ``frame_dealloc`` 我们就将它控制的物理页帧回收以供后续使用了。

.. note::

    **Rust 语法卡片：Drop Trait**

    Rust 中的 ``Drop`` Trait 是它的 RAII 内存管理风格可以被有效实践的关键。之前介绍的多种在堆上分配的 Rust 
    数据结构便都是通过实现 ``Drop`` Trait 来进行被绑定资源的自动回收的。例如：

    - ``Box<T>`` 的 ``drop`` 方法会回收它控制的分配在堆上的那个变量；
    - ``Rc<T>`` 的 ``drop`` 方法会减少分配在堆上的那个引用计数，一旦变为零则分配在堆上的那个被计数的变量自身
      也会被回收；
    - ``Mutex<T>`` 的 ``lock`` 方法会获取互斥锁并返回一个 ``MutexGuard<'a, T>`` ，它可以被当做一个 ``&mut T`` 
      来使用；而 ``MutexGuard<'a, T>`` 的 ``drop`` 方法会将锁释放，从而允许其他线程获取锁并开始访问里层的
      数据结构。锁的实现原理我们先不介绍。

    ``FrameTracker`` 的设计也是基于同样的思想，有了它之后我们就不必手动回收物理页帧了，这在编译期就解决了很多
    潜在的问题。

最后做一个小结：从其他模块的视角看来，物理页帧分配的接口是调用 ``frame_alloc`` 函数得到一个 ``FrameTracker`` 
（如果物理内存还有剩余），它就代表了一个物理页帧，当它的生命周期结束之后它所控制的物理页帧将被自动回收。下面是
一段演示该接口使用方法的测试程序：

.. code-block:: rust
    :linenos:
    :emphasize-lines: 9

    // os/src/mm/frame_allocator.rs

    #[allow(unused)]
    pub fn frame_allocator_test() {
        let mut v: Vec<FrameTracker> = Vec::new();
        for i in 0..5 {
            let frame = frame_alloc().unwrap();
            println!("{:?}", frame);
            v.push(frame);
        }
        v.clear();
        for i in 0..5 {
            let frame = frame_alloc().unwrap();
            println!("{:?}", frame);
            v.push(frame);
        }
        drop(v);
        println!("frame_allocator_test passed!");
    }

如果我们将第 9 行删去，则第一轮分配的 5 个物理页帧都是分配之后在循环末尾就被立即回收，因为循环作用域的临时变量 
``frame`` 的生命周期在那时结束了。然而，如果我们将它们 move 到一个向量中，它们的生命周期便被延长了——直到第 11 行
向量被清空的时候，这些 ``FrameTracker`` 的生命周期才结束，它们控制的 5 个物理页帧才被回收。这种思想我们立即
就会用到。

多级页表实现
-----------------------------------

我们知道，SV39 多级页表是以节点为单位进行管理的。每个节点恰好存储在一个物理页帧中，它的位置可以用一个物理页号来
表示。无论一个节点是否是叶节点，它的内存布局都是一个线性表，也就是一个长度固定 :math:`512` 的页表项数组。

.. code-block:: rust
    :linenos:

    // os/src/mm/page_table.rs

    pub struct PageTable {
        root_ppn: PhysPageNum,
        frames: Vec<FrameTracker>,
    }

    impl PageTable {
        pub fn new() -> Self {
            let frame = frame_alloc().unwrap();
            PageTable {
                root_ppn: frame.ppn,
                frames: vec![frame],
            }
        }
    }

每个应用的地址空间都对应一个不同的页表，因此 ``PageTable`` 要保存它根节点的物理页号 ``root_ppn`` 用来区分。此外，
向量 ``frames`` 以 ``FrameTracker`` 为代表保存了页表所有的节点（包括根节点）所在的物理页帧。这和物理页帧管理模块
的测试程序是一个思路，即将这些 ``FrameTracker`` 的生命周期进一步绑定到 ``PageTable`` 下面。当 ``PageTable`` 
生命周期结束后，向量 ``frames`` 里面的那些 ``FrameTracker`` 也会被回收，也就意味着存放多级页表节点的那些物理页帧
被回收了。

当我们通过 ``new`` 方法新建一个 ``PageTable`` 的时候，它只需有一个根节点。为此我们需要分配一个物理页帧 
``FrameTracker`` 并挂在向量 ``frames`` 下，然后更新根节点的物理页号 ``root_ppn`` 。

我们需要修改