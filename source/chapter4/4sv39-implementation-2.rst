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
  左端点 ``current`` ，同时将管理器内部维护的 ``current`` 加一代表 ``current`` 此前已经被分配过了。

  注意极端情况下可能出现内存耗尽分配失败的情况：即 ``recycled`` 为空且 :math:`\text{current}==\text{end}` 。
  为了涵盖这种情况， ``alloc`` 的返回值被 ``Option`` 包裹，我们返回 ``None`` 即可。
- 再回收 ``dealloc`` 的时候，我们需要检查回收页面的合法性，然后将其压入 ``recycled`` 栈中。回收页面合法有两个
  条件：

  - 该页面之前一定被分配出去过，因此它的物理页号一定 :math:`<\text{current}` ；
  - 该页面没有正处在回收状态，即它的物理页号不能在栈 ``recycled`` 中找到。

  我们通过 ``recycled.iter()`` 获取栈上内容的迭代器，然后通过迭代器的 ``find`` 方法试图
  寻找一个与输入物理页号相同的元素。其返回值是一个 ``Option`` ，如果找到了就会是一个 ``Option::Some`` ，
  这种情况说明我们内核其他部分实现有误，直接报错退出。

下面我们来创建 ``StackFrameAllocator`` 的全局实例：


多级页表实现
-----------------------------------