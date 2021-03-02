简易文件系统 easy-fs
=======================================

本节导读
---------------------------------------

本节我们介绍一个简易文件系统实现 easy-fs。作为一个文件系统而言，它的磁盘布局（为了叙述方便，我们用磁盘来指代一系列持久存储设备）体现在磁盘上各扇区的内容上，而它解析磁盘布局得到的逻辑目录树结构则是通过内存上的数据结构来访问的，这意味着它要同时涉及到对磁盘和对内存的访问。它们的访问方式是不同的，对于内存直接通过一条指令即可直接读写内存相应的位置，而磁盘的话需要用软件的方式向磁盘发出请求来间接进行读写。此外，我们也要特别注意哪些数据结构是存储在磁盘上，哪些数据结构是存储在内存中的，这样在实现的时候才不会引起混乱。

easy-fs 被从内核中分离出来，它的实现分成两个不同的 crate ：

- ``easy-fs`` 为简易文件系统的本体，它是一个库形式 crate，实现一种我们设计的简单磁盘布局；
- ``easy-fs-fuse`` 是一个能在开发环境（如 Ubuntu）中运行的应用程序，它可以对 ``easy-fs`` 进行测试，或者将为我们内核开发的应用打包为一个 easy-fs 格式的文件系统镜像。

``easy-fs`` crate 自下而上大致可以分成五个不同的层次：

1. 块设备接口层
2. 块缓存层
3. 磁盘数据结构层
4. 磁盘块管理器层
5. 索引节点层  

块设备接口层
---------------------------------------

在 ``easy-fs`` 库的最底层声明了一个块设备的抽象接口 ``BlockDevice`` ：

.. code-block:: rust

    // easy-fs/src/block_dev.rs

    pub trait BlockDevice : Send + Sync + Any {
        fn read_block(&self, block_id: usize, buf: &mut [u8]);
        fn write_block(&self, block_id: usize, buf: &[u8]);
    }

它需要实现两个抽象方法：

- ``read_block`` 可以将编号为 ``block_id`` 的块从磁盘读入内存中的缓冲区 ``buf`` ；
- ``write_block`` 可以内存中的缓冲区 ``buf`` 中的数据写入磁盘编号为 ``block_id`` 的块。

这是因为，之前提到过，块设备仅支持以块为单位进行随机读写，由此才有了这两个抽象方法。在 ``easy-fs`` 中并没有一个实现了 ``BlockDevice`` Trait 的具体类型，实际上这是需要由库的使用者提供并接入到 ``easy-fs`` 库的。这也体现了 ``easy-fs`` 的泛用性：它可以用于管理任何实现了 ``BlockDevice`` Trait 的块设备。

.. note::

    **块与扇区**

    实际上，块和扇区是两个不同的概念。 **扇区** (Sector) 是块设备随机读写的大小单位，通常每个扇区为 512 字节。而块是文件系统存储文件时的大小单位，每个块的大小等同于一个或多个扇区。之前提到过 Linux 默认文件系统的单个块大小为 4096 字节。在我们的 easy-fs 实现中一个块的大小和扇区相同为 512 字节，因此在后面的讲解中我们不再区分扇区和块的概念。

块缓存层
---------------------------------------

由于 CPU 不能直接读写磁盘块，因此常见的手段是先通过 ``read_block`` 将一个块上的数据从磁盘读到内存中的一个缓冲区中，这个缓冲区中的内容是可以直接读写的。如果对于缓冲区中的内容进行了修改，那么后续需要通过 ``write_block`` 将缓冲区中的内容写回到磁盘块中。

事实上，无论站在代码实现鲁棒性还是性能的角度，将这些缓冲区合理的管理起来都是很有必要的。一种完全不进行任何管理的模式可能是：每当要对一个磁盘块进行读写的时候，都通过 ``read_block`` 将块数据读取到一个 *临时* 创建的缓冲区，并在进行一些操作之后（可选地）将缓冲区的内容写回到磁盘块。从性能上考虑，我们需要尽可能降低真正块读写（即 ``read/write_block`` ）的次数，因为每一次调用它们都会产生大量开销。要做到这一点，关键就在于对于块读写操作进行 **合并** 。例如，如果一个块已经被读到缓冲区中了，那么我们就没有必要再读一遍，直接用已有的缓冲区就行了；同时，对于同一个块的缓冲区的多次修改没有必要每次都写回磁盘，只需等所有的修改都结束之后统一写回磁盘即可。

但是，当磁盘上的数据结构比较复杂的时候，在编程的时候我们很难手动正确的规划块读取/写入的时机。这不仅可能涉及到复杂的参数传递，稍有不慎还有可能引入同步性问题：即对于一个块缓冲区的修改在对于同一个块进行后续操作的时候不可见。它很致命但又难以调试。

因此，我们的做法是将缓冲区统一管理起来。当我们要读写一个块的时候，首先就是去全局管理器中查看这个块是否已被缓存到内存中的缓冲区中。这样，在一段连续时间内对于一个块进行的所有操作均是在同一个固定的缓冲区中进行的，这解决了同步性问题。此外，通过 ``read/write_block`` 真正进行块读写的时机完全交给全局管理器处理，我们在编程时无需操心。全局管理器仅会在必要的时机分别发起一次真正的块读写，尽可能将更多的块操作合并起来。

块缓存
+++++++++++++++++++++++++++++++++++++++++

块缓存 ``BlockCache`` 的声明如下：

.. code-block:: rust

    // easy-fs/src/lib.rs

    pub const BLOCK_SZ: usize = 512;

    // easy-fs/src/block_cache.rs

    pub struct BlockCache {
        cache: [u8; BLOCK_SZ],
        block_id: usize,
        block_device: Arc<dyn BlockDevice>,
        modified: bool,
    }

其中：

- ``cache`` 是一个 512 字节的数组，表示位于内存中的缓冲区；
- ``block_id`` 记录了这个块缓存来自于磁盘中的块的编号；
- ``block_device`` 保留一个底层块设备的引用使得可以和它打交道；
- ``modified`` 记录自从这个块缓存从磁盘载入内存之后，它有没有被修改过。

当我们创建一个 ``BlockCache`` 的时候，这将触发一次 ``read_block`` 将一个块上的数据从磁盘读到缓冲区 ``cache`` ：

.. code-block:: rust

    // easy-fs/src/block_cache.rs

    impl BlockCache {
        /// Load a new BlockCache from disk.
        pub fn new(
            block_id: usize, 
            block_device: Arc<dyn BlockDevice>
        ) -> Self {
            let mut cache = [0u8; BLOCK_SZ];
            block_device.read_block(block_id, &mut cache);
            Self {
                cache,
                block_id,
                block_device,
                modified: false,
            }
        }
    }

一旦缓冲区已经存在于内存中，CPU 就可以直接访问存储在它上面的磁盘数据结构：

.. code-block:: rust
    :linenos:

    // easy-fs/src/block_cache.rs

    impl BlockCache {
        fn addr_of_offset(&self, offset: usize) -> usize {
            &self.cache[offset] as *const _ as usize
        }

        pub fn get_ref<T>(&self, offset: usize) -> &T where T: Sized {
            let type_size = core::mem::size_of::<T>();
            assert!(offset + type_size <= BLOCK_SZ);
            let addr = self.addr_of_offset(offset);
            unsafe { &*(addr as *const T) } 
        }

        pub fn get_mut<T>(&mut self, offset: usize) -> &mut T where T: Sized {
            let type_size = core::mem::size_of::<T>();
            assert!(offset + type_size <= BLOCK_SZ);
            self.modified = true;
            let addr = self.addr_of_offset(offset);
            unsafe { &mut *(addr as *mut T) }
        }
    }

- ``addr_of_offset`` 可以得到一个 ``BlockCache`` 内部的缓冲区一个指定偏移量 ``offset`` 的字节地址；
- ``get_ref`` 是一个泛型方法，它可以获取缓冲区中的位于偏移量 ``offset`` 的一个类型为 ``T`` 的磁盘上数据结构的不可变引用。该泛型方法的 Trait Bound 限制类型 ``T`` 必须是一个编译时已知大小的类型，我们通过 ``core::mem::size_of::<T>()`` 在编译时获取类型 ``T`` 的大小并确认该数据结构被整个包含在磁盘块及其缓冲区之内。这里编译器会自动进行生命周期标注，约束返回的引用的生命周期不超过 ``BlockCache`` 自身，在使用的时候我们会保证这一点。
- ``get_mut`` 与 ``get_ref`` 的不同之处在于它会会获取磁盘上数据结构的可变引用，由此可以对数据结构进行修改。由于这些数据结构目前位于内存中的缓冲区中，我们需要将 ``BlockCache`` 的 ``modified`` 标记为 true 表示该缓冲区已经被修改，之后需要将数据写回磁盘块才能真正将修改同步到磁盘。

``BlockCache`` 的设计也体现了 RAII 思想， 它管理着一个缓冲区的生命周期。当 ``BlockCache`` 的生命周期结束之后缓冲区也会被从内存中回收，这个时候 ``modified`` 标记将会决定数据是否需要写回磁盘：

.. code-block:: rust

    // easy-fs/src/block_cache.rs

    impl BlockCache {
        pub fn sync(&mut self) {
            if self.modified {
                self.modified = false;
                self.block_device.write_block(self.block_id, &self.cache);
            }
        }
    }

    impl Drop for BlockCache {
        fn drop(&mut self) {
            self.sync()
        }
    }

在 ``BlockCache`` 被 ``drop`` 的时候，它会首先调用 ``sync`` 方法，如果自身确实被修改过的话才会将缓冲区的内容写回磁盘。事实上， ``sync`` 并不是只有在 ``drop`` 的时候才会被调用。在 Linux 中，通常有一个后台进程负责定期将内存中缓冲区的内容写回磁盘。另外有一个 ``sys_fsync`` 系统调用可以手动通知内核将一个文件的修改同步回磁盘。由于我们的实现比较简单， ``sync`` 仅会在 ``BlockCache`` 被 ``drop`` 时才会被调用。

我们可以将 ``get_ref/get_mut`` 进一步封装为更为易用的形式：

.. code-block:: rust

    // easy-fs/src/block_cache.rs

    impl BlockCache {
        pub fn read<T, V>(&self, offset: usize, f: impl FnOnce(&T) -> V) -> V {
            f(self.get_ref(offset))
        }

        pub fn modify<T, V>(&mut self, offset:usize, f: impl FnOnce(&mut T) -> V) -> V {
            f(self.get_mut(offset))
        }
    }

它们的含义是：在 ``BlockCache`` 缓冲区偏移量为 ``offset`` 的位置获取一个类型为 ``T`` 的磁盘上数据结构的不可变/可变引用（分别对应 ``read/modify`` ），并让它进行传入的闭包 ``f`` 中所定义的操作。注意 ``read/modify`` 的返回值是和传入闭包的返回值相同的，因此相当于 ``read/modify`` 构成了传入闭包 ``f`` 的一层执行环境，让它能够真正绑定到一个缓冲区开始执行。

这里我们传入闭包的类型为 ``FnOnce`` ，这是因为闭包里面的变量被捕获的方式涵盖了不可变引用/可变引用/和 move 三种可能性，故而我们需要选取范围最广的 ``FnOnce`` 。参数中的 ``impl`` 关键字体现了一种类似泛型的静态分发功能。

我们很快将展示 ``read/modify`` 接口如何在后续的开发中提供便利。

块缓存全局管理器
+++++++++++++++++++++++++++++++++++++++++

为了避免在块缓存上浪费过多内存，我们希望内存中同时只能驻留有限个磁盘块的缓冲区：

.. code-block:: rust

    // easy-fs/src/block_cache.rs

    const BLOCK_CACHE_SIZE: usize = 16;

块缓存全局管理器的功能是：当我们要对一个磁盘块进行读写从而需要获取它的缓冲区的时候，首先看它是否已经被载入到内存中了，如果已经被载入的话则直接返回，否则需要读取磁盘块的数据到内存中。此时，如果内存中驻留的磁盘块缓冲区的数量已满，则需要遵循某种缓存替换算法将某个块的缓冲区从内存中移除，再将刚刚请求的块的缓冲区加入到内存中。我们这里使用一种类 FIFO 的简单缓存替换算法，因此在管理器中只需维护一个队列：

.. code-block:: rust

    // easy-fs/src/block_cache.rs

    use alloc::collections::VecDeque;

    pub struct BlockCacheManager {
        queue: VecDeque<(usize, Arc<Mutex<BlockCache>>)>,
    }

    impl BlockCacheManager {
        pub fn new() -> Self {
            Self { queue: VecDeque::new() }
        }
    }

队列 ``queue`` 中管理的是块编号和块缓存的二元组。块编号的类型为 ``usize`` ，而块缓存的类型则是一个 ``Arc<Mutex<BlockCache>>`` 。这是一个此前频频提及到的 Rust 中的经典组合，它可以同时提供共享引用和互斥访问。这里的共享引用意义在于块缓存既需要在管理器 ``BlockCacheManager`` 保留一个引用，还需要以引用的形式返回给块缓存的请求者让它可以对块缓存进行访问。而互斥访问在单核上的意义在于提供内部可变性通过编译，在多核环境下则可以帮助我们避免可能的并发冲突。事实上，一般情况下我们需要在更上层提供保护措施避免两个线程同时对一个块缓存进行读写，因此这里只是比较谨慎的留下一层保险。

``get_block_cache`` 方法尝试从块缓存管理器中获取一个编号为 ``block_id`` 的块的块缓存，如果找不到的话会从磁盘读取到内存中，还有可能会发生缓存替换：

.. code-block:: rust
    :linenos:

    // easy-fs/src/block_cache.rs

    impl BlockCacheManager {
        pub fn get_block_cache(
            &mut self,
            block_id: usize,
            block_device: Arc<dyn BlockDevice>,
        ) -> Arc<Mutex<BlockCache>> {
            if let Some(pair) = self.queue
                .iter()
                .find(|pair| pair.0 == block_id) {
                    Arc::clone(&pair.1)
            } else {
                // substitute
                if self.queue.len() == BLOCK_CACHE_SIZE {
                    // from front to tail
                    if let Some((idx, _)) = self.queue
                        .iter()
                        .enumerate()
                        .find(|(_, pair)| Arc::strong_count(&pair.1) == 1) {
                        self.queue.drain(idx..=idx);
                    } else {
                        panic!("Run out of BlockCache!");
                    }
                }
                // load block into mem and push back
                let block_cache = Arc::new(Mutex::new(
                    BlockCache::new(block_id, Arc::clone(&block_device))
                ));
                self.queue.push_back((block_id, Arc::clone(&block_cache)));
                block_cache
            }
        }
    }

- 第 9 行会遍历整个队列试图找到一个编号相同的块缓存，如果找到了话会将块缓存管理器中保存的块缓存的引用复制一份并返回；
- 第 13 行对应找不到的情况，此时必须将块从磁盘读入内存中的缓冲区。在实际读取之前需要判断管理器保存的块缓存数量是否已经达到了上限。如果达到了上限（第 15 行）才需要执行缓存替换算法丢掉某个块的缓存空出一个空位。这里使用一种类 FIFO 算法，如果是 FIFO 算法的话，每次加入一个缓存的时候需要从队尾加入，需要替换的时候则从队头弹出。但是此时队头对应的块缓存可能仍在使用：判断的标志是其强引用计数 :math:`\geq 2` ，即除了块缓存管理器保留的一份副本之外，在外面还有若干份副本正在使用。因此，我们的做法是从队头遍历到队尾找到第一个强引用计数恰好为 1 的块缓存并将其替换出去。
  
  那么是否有可能出现队列已满且其中所有的块缓存都正在使用的情形呢？事实上，只要我们的上限 ``BLOCK_CACHE_SIZE`` 设置的足够大，超过所有线程同时访问的块总数上限，那么这种情况永远不会发生。但是，如果我们的上限设置不足，这里我们就只能 panic 。
- 第 27 行开始我们创建一个新的块缓存（会触发 ``read_block`` 进行块读取）并加入到队尾，最后返回给请求者。

接下来需要创建 ``BlockCacheManager`` 的全局实例：

.. code-block:: rust

    // easy-fs/src/block_cache.rs

    lazy_static! {
        pub static ref BLOCK_CACHE_MANAGER: Mutex<BlockCacheManager> = Mutex::new(
            BlockCacheManager::new()
        );
    }

    pub fn get_block_cache(
        block_id: usize,
        block_device: Arc<dyn BlockDevice>
    ) -> Arc<Mutex<BlockCache>> {
        BLOCK_CACHE_MANAGER.lock().get_block_cache(block_id, block_device)
    }

之后，对于其他模块而言就可以直接通过 ``get_block_cache`` 方法来请求块缓存了。这里需要指出的是，它返回的是一个 ``Arc<Mutex<BlockCache>>`` ，调用者需要通过 ``.lock()`` 获取里层互斥锁 ``Mutex`` 才能对最里面的 ``BlockCache`` 进行操作，比如通过 ``read/modify`` 访问缓冲区里面的磁盘数据结构。

磁盘布局及磁盘上数据结构
---------------------------------------

对于一个文件系统而言，最重要的功能是如何将一个逻辑上的目录树结构映射到磁盘上，决定磁盘上的每个块应该存储哪些数据。为了更容易进行管理和更新，我们需要将磁盘上的数据组织为若干种不同的磁盘上数据结构，并合理安排它们在磁盘中的位置。

easy-fs 磁盘布局概述
+++++++++++++++++++++++++++++++++++++++

在 easy-fs 磁盘布局中，按照块编号从小到大可以分成 5 个连续区域：

- 最开始的区域长度为一个块，其内容是 easy-fs **超级块** (Super Block)，超级块内以魔数的形式提供了文件系统合法性检查功能，同时还可以定位其他连续区域的位置。
- 接下来的一个区域是一个索引节点位图，长度为若干个块。它记录了后面的索引节点区域中有哪些索引节点已经被分配出去使用了，而哪些还尚未被分配出去。
- 接下来的一个区域是索引节点区域，长度为若干个块。其中的每个块都存储了若干个索引节点。
- 接下来的一个区域是一个数据块位图，长度为若干个块。它记录了后面的数据块区域中有哪些数据块已经被分配出去使用了，而哪些还尚未被分配出去。
- 最后的一个区域则是数据块区域，顾名思义，其中的每一个块的职能都是作为一个数据块实际保存文件或目录中的数据。

**索引节点** (Inode, Index Node) 是文件系统中的一种重要数据结构。逻辑目录树结构中的每个文件和目录都对应一个 inode ，我们前面提到的在文件系统实现中文件/目录的底层编号实际上就是指 inode 编号。在 inode 中不仅包含了我们通过 ``stat`` 工具能够看到的文件/目录的元数据（大小/访问权限/类型等信息），还包含它到那些实际保存文件/目录数据的数据块（位于最后的数据块区域中）的索引信息，从而能够找到文件/目录的数据被保存在哪里。从索引方式上看，同时支持直接索引和间接索引。

每个区域中均存储着不同的磁盘数据结构，它们能够对磁盘中的数据进行解释并将其结构化。下面我们分别对它们进行介绍。

easy-fs 超级块
+++++++++++++++++++++++++++++++++++++++

超级块 ``SuperBlock`` 的内容如下：

.. code-block:: rust

    // easy-fs/src/layout.rs

    #[repr(C)]
    pub struct SuperBlock {
        magic: u32,
        pub total_blocks: u32,
        pub inode_bitmap_blocks: u32,
        pub inode_area_blocks: u32,
        pub data_bitmap_blocks: u32,
        pub data_area_blocks: u32,
    }

其中， ``magic`` 是一个用于文件系统合法性验证的魔数， ``total_block`` 给出文件系统的总块数。注意这并不等同于所在磁盘的总块数，因为文件系统很可能并没有占据整个磁盘。后面的四个字段则分别给出 easy-fs 布局中后四个连续区域的长度各为多少个块。

下面是它实现的方法：

.. code-block:: rust

    // easy-fs/src/layout.rs

    impl SuperBlock {
        pub fn initialize(
            &mut self,
            total_blocks: u32,
            inode_bitmap_blocks: u32,
            inode_area_blocks: u32,
            data_bitmap_blocks: u32,
            data_area_blocks: u32,
        ) {
            *self = Self {
                magic: EFS_MAGIC,
                total_blocks,
                inode_bitmap_blocks,
                inode_area_blocks,
                data_bitmap_blocks,
                data_area_blocks,
            }
        }
        pub fn is_valid(&self) -> bool {
            self.magic == EFS_MAGIC
        }
    }

- ``initialize`` 可以在创建一个 easy-fs 的时候对超级块进行初始化，注意各个区域的块数是以参数的形式传入进来的，它们的划分是更上层的磁盘块管理器需要完成的工作。
- ``is_valid`` 则可以通过魔数判断超级块所在的文件系统是否合法。

``SuperBlock`` 是一个磁盘上数据结构，它就存放在磁盘上编号为 0 的块的开头。

位图
+++++++++++++++++++++++++++++++++++++++

在 easy-fs 布局中存在两个不同的位图，分别对于索引节点和数据块进行管理。每个位图都由若干个块组成，每个块大小为 512 字节，即 4096 个比特。每个比特都代表一个索引节点/数据块的分配状态， 0 意味着未分配，而 1 则意味着已经分配出去。位图所要做的事情是通过比特位的分配（寻找一个为 0 的比特位设置为 1）和回收（将比特位清零）来进行索引节点/数据块的分配和回收。

.. code-block:: rust

    // easy-fs/src/bitmap.rs

    pub struct Bitmap {
        start_block_id: usize,
        blocks: usize,
    }

    impl Bitmap {
        pub fn new(start_block_id: usize, blocks: usize) -> Self {
            Self {
                start_block_id,
                blocks,
            }
        }
    }

位图 ``Bitmap`` 中仅保存了它所在区域的起始块编号以及区域的长度为多少个块。通过 ``new`` 方法可以新建一个位图。注意 ``Bitmap`` 自身是驻留在内存中的，但是它能够控制它所在区域的那些磁盘块。磁盘块上的数据则是要以磁盘数据结构 ``BitmapBlock`` 的格式进行操作：

.. code-block:: rust

    // easy-fs/src/bitmap.rs

    type BitmapBlock = [u64; 64];

``BitmapBlock`` 是一个磁盘数据结构，它将位图区域中的一个磁盘块解释为长度为 64 的一个 ``u64`` 数组， 每个 ``u64`` 打包了一组 64 个比特，于是整个数组包含 :math:`64\times 64=4096` 个比特，且可以以组为单位进行操作。

首先来看 ``Bitmap`` 如何分配一个比特：

.. code-block:: rust
    :linenos:

    // easy-fs/src/bitmap.rs
    
    const BLOCK_BITS: usize = BLOCK_SZ * 8;
    
    impl Bitmap {
        pub fn alloc(&self, block_device: &Arc<dyn BlockDevice>) -> Option<usize> {
            for block_id in 0..self.blocks {
                let pos = get_block_cache(
                    block_id + self.start_block_id as usize,
                    Arc::clone(block_device),
                )
                .lock()
                .modify(0, |bitmap_block: &mut BitmapBlock| {
                    if let Some((bits64_pos, inner_pos)) = bitmap_block
                        .iter()
                        .enumerate()
                        .find(|(_, bits64)| **bits64 != u64::MAX)
                        .map(|(bits64_pos, bits64)| {
                            (bits64_pos, bits64.trailing_ones() as usize)
                        }) {
                        // modify cache
                        bitmap_block[bits64_pos] |= 1u64 << inner_pos;
                        Some(block_id * BLOCK_BITS + bits64_pos * 64 + inner_pos as usize)
                    } else {
                        None
                    }
                });
                if pos.is_some() {
                    return pos;
                }
            }
            None
        }
    }

其主要思路是遍历区域中的每个块，再在每个块中以比特组（每组 64 比特）为单位进行遍历，找到一个尚未被全部分配出去的组，最后在里面分配一个比特。它将会返回分配的比特所在的位置，等同于索引节点/数据块的编号。如果所有比特均已经被分配出去了，则返回 ``None`` 。


磁盘上索引节点
+++++++++++++++++++++++++++++++++++++++

数据块与目录项
+++++++++++++++++++++++++++++++++++++++


磁盘块管理器
---------------------------------------

索引节点
---------------------------------------

测试 easy-fs
---------------------------------------

将应用打包为 easy-fs 镜像
---------------------------------------

