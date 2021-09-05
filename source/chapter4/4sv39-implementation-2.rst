实现 SV39 多级页表机制（下）
========================================================


本节导读
--------------------------


本节我们继续来实现 SV39 多级页表机制。这还需进一步了解和管理当前已经使用是或空闲的物理页帧，这样操作系统才能给应用程序动态分配或回收物理地址空间。有了有效的物理内存空间的管理，操作系统就能够在物理内存空间中建立多级页表（页表占用物理内存），为应用程序和操作系统自身建立虚实地址映射关系，从而实现虚拟内存空间，即给应用“看到”的地址空间。

物理页帧管理
-----------------------------------

从前面的介绍可以看出物理页帧的重要性：它既可以用来实际存放应用的数据，也能够用来存储某个应用多级页表中的一个节点。
目前的物理内存上已经有一部分用于放置内核的代码和数据，我们需要将剩下可用的部分以单个物理页帧为单位管理起来，
当需要存放应用数据或是应用的多级页表需要一个新节点的时候分配一个物理页帧，并在应用出错或退出的时候回收它占有
的所有物理页帧。

可用物理页的分配与回收
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

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
    使得同一时间最多只有一条 Trap 控制流并发访问内核的各数据结构，此时应该是并没有任何数据竞争风险的。那么
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


分配/回收物理页帧的接口
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

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


页表基本数据结构与访问接口
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

我们知道，SV39 多级页表是以节点为单位进行管理的。每个节点恰好存储在一个物理页帧中，它的位置可以用一个物理页号来
表示。

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

每个应用的地址空间都对应一个不同的多级页表，这也就意味这不同页表的起始地址（即页表根节点的地址）是不一样的。因此 ``PageTable`` 要保存它根节点的物理页号 ``root_ppn`` 作为页表唯一的区分标志。此外，
向量 ``frames`` 以 ``FrameTracker`` 的形式保存了页表所有的节点（包括根节点）所在的物理页帧。这与物理页帧管理模块
的测试程序是一个思路，即将这些 ``FrameTracker`` 的生命周期进一步绑定到 ``PageTable`` 下面。当 ``PageTable`` 
生命周期结束后，向量 ``frames`` 里面的那些 ``FrameTracker`` 也会被回收，也就意味着存放多级页表节点的那些物理页帧
被回收了。

当我们通过 ``new`` 方法新建一个 ``PageTable`` 的时候，它只需有一个根节点。为此我们需要分配一个物理页帧 
``FrameTracker`` 并挂在向量 ``frames`` 下，然后更新根节点的物理页号 ``root_ppn`` 。

多级页表并不是被创建出来之后就不再变化的，为了 MMU 能够通过地址转换正确找到应用地址空间中的数据实际被内核放在内存中
位置，操作系统需要动态维护一个虚拟页号到页表项的映射，支持插入/删除键值对，其方法签名如下：

.. code-block:: rust

    // os/src/mm/page_table.rs

    impl PageTable {
        pub fn map(&mut self, vpn: VirtPageNum, ppn: PhysPageNum, flags: PTEFlags);
        pub fn unmap(&mut self, vpn: VirtPageNum);
    }

- 我们通过 ``map`` 方法来在多级页表中插入一个键值对，注意这里我们将物理页号 ``ppn`` 和页表项标志位 ``flags`` 作为
  不同的参数传入而不是整合为一个页表项；
- 相对的，我们通过 ``unmap`` 方法来删除一个键值对，在调用时仅需给出作为索引的虚拟页号即可。

.. _modify-page-table:

在这些操作的过程中我们自然需要访问或修改多级页表节点的内容。每个节点都被保存在一个物理页帧中，在多级页表的架构中我们是以
一个节点被存放在的物理页帧的物理页号作为指针指向该节点，这意味着，对于每个节点来说，一旦我们知道了指向它的物理页号，我们
就需要能够修改这个节点的内容。前面我们在使用 ``frame_alloc`` 分配一个物理页帧之后便立即将它上面的数据清零其实也是一样
的需求。总结一下也就是说，至少在操作某个多级页表或是管理物理页帧的时候，我们要能够自由的读写与一个给定的物理页号对应的
物理页帧上的数据。

在尚未启用分页模式之前，内核和应用的代码都可以通过物理地址直接访问内存。而在打开分页模式之后，分别运行在 S 特权级
和 U 特权级的内核和应用的访存行为都会受到影响，它们的访存地址会被视为一个当前地址空间（ ``satp`` CSR 给出当前
多级页表根节点的物理页号）中的一个虚拟地址，需要 MMU 
查相应的多级页表完成地址转换变为物理地址，也就是地址空间中虚拟地址指向的数据真正被内核放在的物理内存中的位置，然后
才能访问相应的数据。此时，如果想要访问一个特定的物理地址 ``pa`` 所指向的内存上的数据，就需要对应 **构造** 一个虚拟地址 
``va`` ，使得当前地址空间的页表存在映射 :math:`\text{va}\rightarrow\text{pa}` ，且页表项中的保护位允许这种
访问方式。于是，在代码中我们只需访问地址 ``va`` ，它便会被 MMU 通过地址转换变成 ``pa`` ，这样我们就做到了在启用
分页模式的情况下也能从某种意义上直接访问内存。

.. _term-identical-mapping:

这就需要我们提前扩充多级页表维护的映射，使得对于每一个对应于某一特定物理页帧的物理页号 ``ppn`` ，均存在一个虚拟页号 
``vpn`` 能够映射到它，而且要能够较为简单的针对一个 ``ppn`` 找到某一个能映射到它的 ``vpn`` 。这里我们采用一种最
简单的 **恒等映射** (Identical Mapping) ，也就是说对于物理内存上的每个物理页帧，我们都在多级页表中用一个与其
物理页号相等的虚拟页号映射到它。当我们想针对物理页号构造一个能映射到它的虚拟页号的时候，也只需使用一个和该物理页号
相等的虚拟页号即可。

.. _term-recursive-mapping:

.. note::

    **其他的映射方式**

    为了达到这一目的还存在其他不同的映射方式，例如比较著名的 **页表自映射** (Recursive Mapping) 等。有兴趣的同学
    可以进一步参考 `BlogOS 中的相关介绍 <https://os.phil-opp.com/paging-implementation/#accessing-page-tables>`_ 。

这里需要说明的是，在下一节中我们可以看到，应用和内核的地址空间是隔离的。而直接访问物理页帧的操作只会在内核中进行，
应用无法看到物理页帧管理器和多级页表等内核数据结构。因此，上述的恒等映射只需被附加到内核地址空间即可。


内核中访问物理页帧的方法
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

.. _access-frame-in-kernel-as:


于是，我们来看看在内核中应如何访问一个特定的物理页帧：

.. code-block:: rust

    // os/src/mm/address.rs

    impl PhysPageNum {
        pub fn get_pte_array(&self) -> &'static mut [PageTableEntry] {
            let pa: PhysAddr = self.clone().into();
            unsafe {
                core::slice::from_raw_parts_mut(pa.0 as *mut PageTableEntry, 512)
            }
        }
        pub fn get_bytes_array(&self) -> &'static mut [u8] {
            let pa: PhysAddr = self.clone().into();
            unsafe {
                core::slice::from_raw_parts_mut(pa.0 as *mut u8, 4096)
            }
        }
        pub fn get_mut<T>(&self) -> &'static mut T {
            let pa: PhysAddr = self.clone().into();
            unsafe {
                (pa.0 as *mut T).as_mut().unwrap()
            }
        }
    }

我们构造可变引用来直接访问一个物理页号 ``PhysPageNum`` 对应的物理页帧，不同的引用类型对应于物理页帧上的一种不同的
内存布局，如 ``get_pte_array`` 返回的是一个页表项定长数组的可变引用，可以用来修改多级页表中的一个节点；而 
``get_bytes_array`` 返回的是一个字节数组的可变引用，可以以字节为粒度对物理页帧上的数据进行访问，前面进行数据清零
就用到了这个方法； ``get_mut`` 是个泛型函数，可以获取一个恰好放在一个物理页帧开头的类型为 ``T`` 的数据的可变引用。

在实现方面，都是先把物理页号转为物理地址 ``PhysAddr`` ，然后再转成 usize 形式的物理地址。接着，我们直接将它
转为裸指针用来访问物理地址指向的物理内存。在分页机制开启前，这样做自然成立；而开启之后，虽然裸指针被视为一个虚拟地址，
但是上面已经提到这种情况下虚拟地址会映射到一个相同的物理地址，因此在这种情况下也成立。注意，我们在返回值类型上附加了
静态生命周期泛型 ``'static`` ，这是为了绕过 Rust 编译器的借用检查，实质上可以将返回的类型也看成一个裸指针，因为
它也只是标识数据存放的位置以及类型。但与裸指针不同的是，无需通过 ``unsafe`` 的解引用访问它指向的数据，而是可以像一个
正常的可变引用一样直接访问。

.. note::
    
    **unsafe 真的就是“不安全”吗？**

    下面是笔者关于 ``unsafe`` 一点可能不太正确的理解，不感兴趣的读者可以跳过。

    当我们在 Rust 中使用 unsafe 的时候，并不仅仅是为了绕过编译器检查，更是为了告知编译器和其他看到这段代码的程序员：
    “ **我保证这样做是安全的** ” 。尽管，严格的 Rust 编译器暂时还不能确信这一点。从规范 Rust 代码编写的角度，
    我们需要尽可能绕过 unsafe ，因为如果 Rust 编译器或者一些已有的接口就可以提供安全性，我们当然倾向于利用它们让我们
    实现的功能仍然是安全的，可以避免一些无谓的心智负担；反之，就只能使用 unsafe ，同时最好说明如何保证这项功能是安全的。

    这里简要从内存安全的角度来分析一下 ``PhysPageNum`` 的 ``get_*`` 系列方法的实现中 ``unsafe`` 的使用。为了方便
    解释，我们可以将 ``PhysPageNum`` 也看成一种 RAII 的风格，即它控制着一个物理页帧资源的访问。首先，这不会导致 
    use-after-free 的问题，因为在内核运行全期整块物理内存都是可以访问的，它不存在被释放后无法访问的可能性；其次，
    也不会导致并发冲突。注意这不是在 ``PhysPageNum`` 这一层解决的，而是 ``PhysPageNum`` 的使用层要保证任意两个线程
    不会同时对一个 ``PhysPageNum`` 进行操作。读者也应该可以感觉出这并不能算是一种好的设计，因为这种约束从代码层面是很
    难直接保证的，而是需要系统内部的某种一致性。虽然如此，它对于我们这个极简的内核而言算是很合适了。

.. chyyuu 上面一段提到了线程？？？

建立和拆除虚实地址映射关系
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

接下来介绍建立和拆除虚实地址映射关系的 ``map`` 和 ``unmap`` 方法是如何实现的。它们都依赖于一个很重要的过程，也即在多级页表中找到一个虚拟地址对应的页表项。
找到之后，只要修改页表项的内容即可完成键值对的插入和删除。在寻找页表项的时候，可能出现页表的中间级节点还未被创建的情况，
这个时候我们需要手动分配一个物理页帧来存放这个节点，并将这个节点接入到当前的多级页表的某级中。


.. code-block:: rust
    :linenos:

    // os/src/mm/address.rs

    impl VirtPageNum {
        pub fn indexes(&self) -> [usize; 3] {
            let mut vpn = self.0;
            let mut idx = [0usize; 3];
            for i in (0..3).rev() {
                idx[i] = vpn & 511;
                vpn >>= 9;
            }
            idx
        }
    }

    // os/src/mm/page_table.rs

    impl PageTable {
        fn find_pte_create(&mut self, vpn: VirtPageNum) -> Option<&mut PageTableEntry> {
            let idxs = vpn.indexes();
            let mut ppn = self.root_ppn;
            let mut result: Option<&mut PageTableEntry> = None;
            for i in 0..3 {
                let pte = &mut ppn.get_pte_array()[idxs[i]];
                if i == 2 {
                    result = Some(pte);
                    break;
                }
                if !pte.is_valid() {
                    let frame = frame_alloc().unwrap();
                    *pte = PageTableEntry::new(frame.ppn, PTEFlags::V);
                    self.frames.push(frame);
                }
                ppn = pte.ppn();
            }
            result
        }
    }

- ``VirtPageNum`` 的 ``indexes`` 可以取出虚拟页号的三级页索引，并按照从高到低的顺序返回。注意它里面包裹的 
  usize 可能有 :math:`27` 位，也有可能有 :math:`64-12=52` 位，但这里我们是用来在多级页表上进行遍历，因此
  只取出低 :math:`27` 位。
- ``PageTable::find_pte_create`` 在多级页表找到一个虚拟页号对应的页表项的可变引用方便后续的读写。如果在
  遍历的过程中发现有节点尚未创建则会新建一个节点。

  变量 ``ppn`` 表示当前节点的物理页号，最开始指向多级页表的根节点。随后每次循环通过 ``get_pte_array`` 将
  取出当前节点的页表项数组，并根据当前级页索引找到对应的页表项。如果当前节点是一个叶节点，那么直接返回这个页表项
  的可变引用；否则尝试向下走。走不下去的话就新建一个节点，更新作为下级节点指针的页表项，并将新分配的物理页帧移动到
  向量 ``frames`` 中方便后续的自动回收。注意在更新页表项的时候，不仅要更新物理页号，还要将标志位 V 置 1，
  不然硬件在查多级页表的时候，会认为这个页表项不合法，从而触发 Page Fault 而不能向下走。

于是， ``map/unmap`` 就非常容易实现了：

.. code-block:: rust

    // os/src/mm/page_table.rs

    impl PageTable {
        pub fn map(&mut self, vpn: VirtPageNum, ppn: PhysPageNum, flags: PTEFlags) {
            let pte = self.find_pte_create(vpn).unwrap();
            assert!(!pte.is_valid(), "vpn {:?} is mapped before mapping", vpn);
            *pte = PageTableEntry::new(ppn, flags | PTEFlags::V);
        }
        pub fn unmap(&mut self, vpn: VirtPageNum) {
            let pte = self.find_pte_create(vpn).unwrap();
            assert!(pte.is_valid(), "vpn {:?} is invalid before unmapping", vpn);
            *pte = PageTableEntry::empty();
        }
    }

只需根据虚拟页号找到页表项，然后修改或者直接清空其内容即可。

.. warning::

    目前的实现方式并不打算对物理页帧耗尽的情形做任何处理而是直接 ``panic`` 退出。因此在前面的代码中能够看到
    很多 ``unwrap`` ，这种使用方式并不为 Rust 所推荐，只是由于简单起见暂且这样做。

为了方便后面的实现，我们还需要 ``PageTable`` 提供一种不经过 MMU 而是手动查页表的方法：

.. code-block:: rust
    :linenos:

    // os/src/mm/page_table.rs

    impl PageTable {
        /// Temporarily used to get arguments from user space.
        pub fn from_token(satp: usize) -> Self {
            Self {
                root_ppn: PhysPageNum::from(satp & ((1usize << 44) - 1)),
                frames: Vec::new(),
            }
        }
        fn find_pte(&self, vpn: VirtPageNum) -> Option<&PageTableEntry> {
            let idxs = vpn.indexes();
            let mut ppn = self.root_ppn;
            let mut result: Option<&PageTableEntry> = None;
            for i in 0..3 {
                let pte = &ppn.get_pte_array()[idxs[i]];
                if i == 2 {
                    result = Some(pte);
                    break;
                }
                if !pte.is_valid() {
                    return None;
                }
                ppn = pte.ppn();
            }
            result
        }
        pub fn translate(&self, vpn: VirtPageNum) -> Option<PageTableEntry> {
            self.find_pte(vpn)
                .map(|pte| {pte.clone()})
        }
    }

- 第 5 行的 ``from_token`` 可以临时创建一个专用来手动查页表的 ``PageTable`` ，它仅有一个从传入的 ``satp`` token 
  中得到的多级页表根节点的物理页号，它的 ``frames`` 字段为空，也即不实际控制任何资源；
- 第 11 行的 ``find_pte`` 和之前的 ``find_pte_create`` 不同之处在于它不会试图分配物理页帧。一旦在多级页表上遍历
  遇到空指针它就会直接返回 ``None`` 表示无法正确找到传入的虚拟页号对应的页表项；
- 第 28 行的 ``translate`` 调用 ``find_pte`` 来实现，如果能够找到页表项，那么它会将页表项拷贝一份并返回，否则就
  返回一个 ``None`` 。

.. chyyuu 没有提到from_token的作用???