练习参考答案
=====================================================

.. toctree::
      :hidden:
      :maxdepth: 4

课后练习
-------------------------------

编程题
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

1. `*` 扩展easy-fs文件系统功能，扩大单个文件的大小，支持三级间接inode。

在修改之前，先看看原始inode的结构：

.. code:: rust

    /// The max number of direct inodes
    const INODE_DIRECT_COUNT: usize = 28;

    #[repr(C)]
    pub struct DiskInode {
        pub size: u32,
        pub direct: [u32; INODE_DIRECT_COUNT],
        pub indirect1: u32,
        pub indirect2: u32,
        type_: DiskInodeType,
    }

    #[derive(PartialEq)]
    pub enum DiskInodeType {
        File,
        Directory,
    }

一个 ``DiskInode`` 在磁盘上占据128字节的空间。我们考虑加入 ``indirect3`` 字段并缩减 ``INODE_DIRECT_COUNT`` 为27以保持 ``DiskInode`` 的大小不变。此时直接索引可索引13.5KiB的内容，一级间接索引和二级间接索引仍然能索引64KiB和8MiB的内容，而三级间接索引能索引128 * 8MiB = 1GiB的内容。当文件大小大于13.5KiB + 64KiB + 8MiB时，需要用到三级间接索引。

下面的改动都集中在 ``easy-fs/src/layout.rs`` 中。首先修改 ``DiskInode`` 和相关的常量定义。

.. code-block:: rust
    :emphasize-lines: 6

    pub struct DiskInode {
        pub size: u32,
        pub direct: [u32; INODE_DIRECT_COUNT],
        pub indirect1: u32,
        pub indirect2: u32,
        pub indirect3: u32,
        type_: DiskInodeType,
    }

在计算给定文件大小对应的块总数时，需要新增对三级间接索引的处理。三级间接索引的存在使得二级间接索引所需的块数不再计入所有的剩余数据块。

.. code-block:: rust
    :emphasize-lines: 14

    pub fn total_blocks(size: u32) -> u32 {
        let data_blocks = Self::_data_blocks(size) as usize;
        let mut total = data_blocks as usize;
        // indirect1
        if data_blocks > INODE_DIRECT_COUNT {
            total += 1;
        }
        // indirect2
        if data_blocks > INDIRECT1_BOUND {
            total += 1;
            // sub indirect1
            let level2_extra =
                (data_blocks - INDIRECT1_BOUND + INODE_INDIRECT1_COUNT - 1) / INODE_INDIRECT1_COUNT;
            total += level2_extra.min(INODE_INDIRECT1_COUNT);
        }
        // indirect3
        if data_blocks > INDIRECT2_BOUND {
            let remaining = data_blocks - INDIRECT2_BOUND;
            let level2_extra = (remaining + INODE_INDIRECT2_COUNT - 1) / INODE_INDIRECT2_COUNT;
            let level3_extra = (remaining + INODE_INDIRECT1_COUNT - 1) / INODE_INDIRECT1_COUNT;
            total += 1 + level2_extra + level3_extra;
        }
        total as u32
    }

``DiskInode`` 的 ``get_block_id`` 方法中遇到三级间接索引要额外读取三次块缓存。

.. code:: rust

    pub fn get_block_id(&self, inner_id: u32, block_device: &Arc<dyn BlockDevice>) -> u32 {
        let inner_id = inner_id as usize;
        if inner_id < INODE_DIRECT_COUNT {
            // ...
        } else if inner_id < INDIRECT1_BOUND {
            // ...
        } else if inner_id < INDIRECT2_BOUND {
            // ...
        } else { // 对三级间接索引的处理
            let last = inner_id - INDIRECT2_BOUND;
            let indirect1 = get_block_cache(self.indirect3 as usize, Arc::clone(block_device))
                .lock()
                .read(0, |indirect3: &IndirectBlock| {
                    indirect3[last / INODE_INDIRECT2_COUNT]
                });
            let indirect2 = get_block_cache(indirect1 as usize, Arc::clone(block_device))
                .lock()
                .read(0, |indirect2: &IndirectBlock| {
                    indirect2[(last % INODE_INDIRECT2_COUNT) / INODE_INDIRECT1_COUNT]
                });
            get_block_cache(indirect2 as usize, Arc::clone(block_device))
                .lock()
                .read(0, |indirect1: &IndirectBlock| {
                    indirect1[(last % INODE_INDIRECT2_COUNT) % INODE_INDIRECT1_COUNT]
                })
        }
    }

方法 ``increase_size`` 的实现本身比较繁琐，如果按照原有的一级和二级间接索引的方式实现对三级间接索引的处理，代码会比较丑陋。实际上多重间接索引是树结构，变量 ``current_blocks`` 和 ``total_blocks`` 对应着当前树的叶子数量和目标叶子数量，我们可以用递归函数来实现树的生长。先实现以下的辅助方法：

.. code:: rust

    /// Helper to build tree recursively
    /// extend number of leaves from `src_leaf` to `dst_leaf`
    fn build_tree(
        &self,
        blocks: &mut alloc::vec::IntoIter<u32>,
        block_id: u32,
        mut cur_leaf: usize,
        src_leaf: usize,
        dst_leaf: usize,
        cur_depth: usize,
        dst_depth: usize,
        block_device: &Arc<dyn BlockDevice>,
    ) -> usize {
        if cur_depth == dst_depth {
            return cur_leaf + 1;
        }
        get_block_cache(block_id as usize, Arc::clone(block_device))
            .lock()
            .modify(0, |indirect_block: &mut IndirectBlock| {
                let mut i = 0;
                while i < INODE_INDIRECT1_COUNT && cur_leaf < dst_leaf {
                    if cur_leaf >= src_leaf {
                        indirect_block[i] = blocks.next().unwrap();
                    }
                    cur_leaf = self.build_tree(
                        blocks,
                        indirect_block[i],
                        cur_leaf,
                        src_leaf,
                        dst_leaf,
                        cur_depth + 1,
                        dst_depth,
                        block_device,
                    );
                    i += 1;
                }
            });
        cur_leaf
    }

然后修改方法 ``increase_size``。不要忘记在填充二级间接索引时维护 ``current_blocks`` 的变化，并限制目标索引 ``(a1, b1)`` 的范围。

.. code:: rust

    /// Increase the size of current disk inode
    pub fn increase_size(
        &mut self,
        new_size: u32,
        new_blocks: Vec<u32>,
        block_device: &Arc<dyn BlockDevice>,
    ) {
        // ...
        // alloc indirect2
        // ...
        // fill indirect2 from (a0, b0) -> (a1, b1)
        // 不要忘记限制 (a1, b1) 的范围
        // ...
        // alloc indirect3
        if total_blocks > INODE_INDIRECT2_COUNT as u32 {
            if current_blocks == INODE_INDIRECT2_COUNT as u32 {
                self.indirect3 = new_blocks.next().unwrap();
            }
            current_blocks -= INODE_INDIRECT2_COUNT as u32;
            total_blocks -= INODE_INDIRECT2_COUNT as u32;
        } else {
            return;
        }
        // fill indirect3
        self.build_tree(
            &mut new_blocks,
            self.indirect3,
            0,
            current_blocks as usize,
            total_blocks as usize,
            0,
            3,
            block_device,
        );

对方法 ``clear_size`` 的修改与 ``increase_size`` 类似。先实现辅助方法 ``collect_tree_blocks``：

.. code:: rust

    /// Helper to recycle blocks recursively
    fn collect_tree_blocks(
        &self,
        collected: &mut Vec<u32>,
        block_id: u32,
        mut cur_leaf: usize,
        max_leaf: usize,
        cur_depth: usize,
        dst_depth: usize,
        block_device: &Arc<dyn BlockDevice>,
    ) -> usize {
        if cur_depth == dst_depth {
            return cur_leaf + 1;
        }
        get_block_cache(block_id as usize, Arc::clone(block_device))
            .lock()
            .read(0, |indirect_block: &IndirectBlock| {
                let mut i = 0;
                while i < INODE_INDIRECT1_COUNT && cur_leaf < max_leaf {
                    collected.push(indirect_block[i]);
                    cur_leaf = self.collect_tree_blocks(
                        collected,
                        indirect_block[i],
                        cur_leaf,
                        max_leaf,
                        cur_depth + 1,
                        dst_depth,
                        block_device,
                    );
                    i += 1;
                }
            });
        cur_leaf
    }

然后修改方法 ``clear_size``。

.. code:: rust

    /// Clear size to zero and return blocks that should be deallocated.
    /// We will clear the block contents to zero later.
    pub fn clear_size(&mut self, block_device: &Arc<dyn BlockDevice>) -> Vec<u32> {
        // ...
        // indirect2 block
        // ...
        // indirect2
        // 不要忘记限制 (a1, b1) 的范围
        self.indirect2 = 0;
        // indirect3 block
        assert!(data_blocks <= INODE_INDIRECT3_COUNT);
        if data_blocks > INODE_INDIRECT2_COUNT {
            v.push(self.indirect3);
            data_blocks -= INODE_INDIRECT2_COUNT;
        } else {
            return v;
        }
        // indirect3
        self.collect_tree_blocks(&mut v, self.indirect3, 0, data_blocks, 0, 3, block_device);
        self.indirect3 = 0;
        v
    }

接下来你可以在 ``easy-fs-fuse/src/main.rs`` 中测试easy-fs文件系统的修改，比如读写大小超过10MiB的文件。

2. `*` 扩展内核功能，支持stat系统调用，能显示文件的inode元数据信息。

你将在本章的编程实验中实现这个功能。

3. `**` 扩展内核功能，支持mmap系统调用，支持对文件的映射，实现基于内存读写方式的文件读写功能。

.. note:: 这里只是给出了一种参考实现。mmap本身行为比较复杂，使用你认为合理的方式实现即可。

在第四章的编程实验中你应该已经实现了mmap的匿名映射功能，这里我们要实现文件映射。
`mmap <https://man7.org/linux/man-pages/man2/mmap.2.html>`_ 的原型如下：

.. code:: c

    void *mmap(void *addr, size_t length, int prot, int flags,
                    int fd, off_t offset);

其中 ``addr`` 是一个虚拟地址的hint，在映射文件时我们不关心具体的虚拟地址（相当于传入 ``NULL`` ），这里我们的系统调用忽略这个参数。 ``prot`` 和 ``flags`` 指定了一些属性，为简单起见我们也不要这两个参数，映射的虚拟内存的属性直接继承自文件的读写属性。我们最终保留 ``length`` 、 ``fd`` 和 ``offset`` 三个参数。

考虑最简单的一种实现方式：mmap调用时随便选择一段虚拟地址空间，将它映射到一些随机的物理页面上，之后再把文件的对应部分全部读到内存里。如果这段映射是可写的，那么内核还要在合适的时机（比如调用msync、munmap、进程退出时）把内存里的东西回写到文件。

这样做的问题是被映射的文件可能很大，将映射的区域全部读入内存可能很慢，而且用户未必会访问所有的页面。这里可以应用按需分页的惰性加载策略：先不实际建立虚拟内存到物理内存的映射，当用户访问映射的区域时会触发缺页异常，我们在处理异常时分配实际的物理页面并将文件读入内存。

按照上述方式已经可以实现文件映射了，但让我们来考虑较为微妙的情况。比如以下的Linux C程序：

.. code:: c

    #include <unistd.h>
    #include <fcntl.h>
    #include <sys/mman.h>
    #include <stdio.h>

    int main()
    {
        char str[] = {"asdbasdq3423423\n"};
        int fd = open("2.txt", O_RDWR | O_CREAT | O_TRUNC, 0664);
        if (fd < 0) {
            printf("open failed\n");
            return -1;
        }

        if (write(fd, str, sizeof(str)) < 0) {
            printf("write failed\n");
            return -1;
        }

        char *p1 = mmap(NULL, sizeof(str), PROT_READ | PROT_WRITE, MAP_SHARED, fd, 0);
        char *p2 = mmap(NULL, sizeof(str), PROT_READ | PROT_WRITE, MAP_SHARED, fd, 0);
        printf("p1 = %p, p2 = %p\n", p1, p2);
        close(fd);
        
        p1[1] = '1';
        p2[2] = '2';
        p2[0] = '2';
        p1[0] = '1';
        printf("content1: %s", p1);
        printf("content2: %s", p2);
        return 0;
    }

一个可能的输出结果如下：

.. code::

    p1 = 0x7f955a3cf000, p2 = 0x7f955a3a2000
    content1: 112basdq3423423
    content2: 112basdq3423423

可以看到文件的同一段区域被映射到了两个不同的虚拟地址，对这两段虚拟内存的修改全部生效（冲突的修改也是最后的可见），修改后再读出来的内容也相同。这样的结果是符合直觉的，因为底层的文件只有一个（也与 ``MAP_SHARED`` 有关，由于设置 ``MAP_PRIVATE`` 标志不会将修改真正写入文件，我们参考 ``MAP_SHARED`` 的行为）。如果按照上面说的方式将两个虚拟内存区域映射到不同的物理页面，那么对两个区域的修改无法同时生效，我们也无法确定应该将哪个页面回写到文件。这个例子启示我们， **如果文件映射包含文件的相同部分，那么相应的虚拟页面应该映射到相同的物理页** 。

不幸的是，现有的 ``MapArea`` 类型只含 ``Identical`` 和 ``Framed`` ，不支持不同的虚拟页面共享物理页，所以我们需要手动管理一些资源。下面的 ``FileMapping`` 结构描述了一个文件的若干段映射：

.. code:: rust

    pub struct FileMapping {
        file: Arc<Inode>,
        ranges: Vec<MapRange>,
        frames: Vec<FrameTracker>,
        dirty_parts: BTreeSet<usize>, // file segments that need writing back
        map: BTreeMap<usize, PhysPageNum>, // file offset -> ppn
    }

其中 ``file`` 代表被映射的文件，你可能会好奇它的类型为什么不是一个文件描述符编号或者 ``Arc<dyn File>`` 。首先mmap之后使用的文件描述符可以立即被关闭而不会对文件映射造成任何影响，所以不适合只存放fd编号；其次mmap通常要求映射的文件是常规文件 （例：映射stdin和stdout毫无意义），这里用 ``Inode`` 来提醒我们这点。 ``ranges`` 里面存放了若干 ``MapRange`` ，每个都用于描述一段映射区域。 ``frames`` 用于管理实际分配的物理页帧。 ``dirty_parts`` 记录了需要回写的脏页，注意它实际上用文件内的偏移来表示。 ``map`` 维护文件内偏移到物理页号的映射。需要注意的是这里记录脏页的方式比较简单，而且也完全没有考虑在进程间共享物理页，你可以使用引用计数等手段进行扩展。

.. code:: rust

    #[derive(Clone)]
    struct MapRange {
        start: VirtAddr,
        len: usize,    // length in bytes
        offset: usize, // offset in file
        perm: MapPermission,
    }

``MapRange`` 描述了一段映射区域。 ``start`` 是该区域的起始虚拟地址， ``offset`` 为其在文件中的偏移， ``perm`` 记录了该区域的属性。

前面提到过，我们的mmap忽略掉作为hint的 ``addr`` 参数，那这里的虚拟地址填什么呢？一般来说64位架构具有大到用不完的虚拟地址空间，用一个简单的线性分配器随便分配虚拟地址即可。

.. code:: rust

    /// Base virtual address for mmap
    pub const MMAP_AREA_BASE: usize = 0x0000_0001_0000_0000; // 随便选的基址，挑块没人用的

    /// A naive linear virtual address space allocator
    pub struct VirtualAddressAllocator {
        cur_va: VirtAddr,
    }

    impl VirtualAddressAllocator {
        /// Create a new allocator with given base virtual address
        pub fn new(base: usize) -> Self {
            Self {
                cur_va: base.into(),
            }
        }

        /// Allocate a virtual address area
        pub fn alloc(&mut self, len: usize) -> VirtAddr {
            let start = self.cur_va;
            let end: VirtAddr = (self.cur_va.0 + len).into();
            self.cur_va = end.ceil().into();
            start
        }

        // 不必释放
    }

然后把 ``VirtualAddressAllocator`` 和 ``FileMapping`` 放进 ``TaskControlBlockInner`` 里。为简单起见，fork时不考虑这两个字段的复制和映射的共享。

.. code-block:: rust
    :caption: ``os/src/task/task.rs``
    :emphasize-lines: 11,12

    pub struct TaskControlBlockInner {
        pub trap_cx_ppn: PhysPageNum,
        pub base_size: usize,
        pub task_cx: TaskContext,
        pub task_status: TaskStatus,
        pub memory_set: MemorySet,
        pub parent: Option<Weak<TaskControlBlock>>,
        pub children: Vec<Arc<TaskControlBlock>>,
        pub exit_code: i32,
        pub fd_table: Vec<Option<Arc<dyn File + Send + Sync>>>,
        pub mmap_va_allocator: VirtualAddressAllocator,
        pub file_mappings: Vec<FileMapping>,
    }

下面来添加mmap系统调用：

.. code:: rust

    /// This is a simplified version of mmap which only supports file-backed mapping
    pub fn sys_mmap(fd: usize, len: usize, offset: usize) -> isize {
        if len == 0 {
            // invalid length
            return -1;
        }
        if (offset & (PAGE_SIZE - 1)) != 0 {
            // offset must be page size aligned
            return -1;
        }

        let task = current_task().unwrap();
        let mut tcb = task.inner_exclusive_access();
        if fd >= tcb.fd_table.len() {
            return -1;
        }
        if tcb.fd_table[fd].is_none() {
            return -1;
        }

        let fp = tcb.fd_table[fd].as_ref().unwrap();
        let opt_inode = fp.as_any().downcast_ref::<OSInode>();
        if opt_inode.is_none() {
            // must be a regular file
            return -1;
        }

        let inode = opt_inode.unwrap();
        let perm = parse_permission(inode);
        let file = inode.clone_inner_inode();
        if offset >= file.get_size() {
            // file offset exceeds size limit
            return -1;
        }

        let start = tcb.mmap_va_allocator.alloc(len);
        let mappings = &mut tcb.file_mappings;
        if let Some(m) = find_file_mapping(mappings, &file) {
            m.push(start, len, offset, perm);
        } else {
            let mut m = FileMapping::new_empty(file);
            m.push(start, len, offset, perm);
            mappings.push(m);
        }
        start.0 as isize
    }

这里面有不少无聊的参数检查和辅助函数，就不详细介绍了。总之这个系统调用实际做的事情只有维护对应的 ``FileMapping`` 结构，实际的工作被推迟到缺页异常处理例程中。

.. code-block:: rust
    :caption: ``os/src/trap/mod.rs``
    :emphasize-lines: 17

    #[no_mangle]
    /// handle an interrupt, exception, or system call from user space
    pub fn trap_handler() -> ! {
        set_kernel_trap_entry();
        let scause = scause::read();
        let stval = stval::read();
        match scause.cause() {
            Trap::Exception(Exception::UserEnvCall) => {
                // ...
            }
            Trap::Exception(Exception::StoreFault)
            | Trap::Exception(Exception::StorePageFault)
            | Trap::Exception(Exception::InstructionFault)
            | Trap::Exception(Exception::InstructionPageFault)
            | Trap::Exception(Exception::LoadFault)
            | Trap::Exception(Exception::LoadPageFault) => {
                if !handle_page_fault(stval) {
                    println!(
                        "[kernel] {:?} in application, bad addr = {:#x}, bad instruction = {:#x}, kernel killed it.",
                        scause.cause(),
                        stval,
                        current_trap_cx().sepc,
                    );
                    // page fault exit code
                    exit_current_and_run_next(-2);
                }
            }
            Trap::Exception(Exception::IllegalInstruction) => {
                // ...
            }
            Trap::Interrupt(Interrupt::SupervisorTimer) => {
                // ...
            }
            _ => {
                panic!(
                    "Unsupported trap {:?}, stval = {:#x}!",
                    scause.cause(),
                    stval
                );
            }
        }
        trap_return();
    }

我们在这里尝试处理缺页异常，如果 ``handle_page_fault`` 返回 ``true`` 表明异常已经被处理，否则内核仍然会杀死当前进程。

.. code-block:: rust
    :linenos:

    /// Try to handle page fault caused by demand paging
    /// Returns whether this page fault is fixed
    pub fn handle_page_fault(fault_addr: usize) -> bool {
        let fault_va: VirtAddr = fault_addr.into();
        let fault_vpn = fault_va.floor();
        let task = current_task().unwrap();
        let mut tcb = task.inner_exclusive_access();

        if let Some(pte) = tcb.memory_set.translate(fault_vpn) {
            if pte.is_valid() {
                return false; // fault va already mapped, we cannot handle this
            }
        }

        match tcb.file_mappings.iter_mut().find(|m| m.contains(fault_va)) {
            Some(mapping) => {
                let file = Arc::clone(&mapping.file);
                // fix vm mapping
                let (ppn, range, shared) = mapping.map(fault_va).unwrap();
                tcb.memory_set.map(fault_vpn, ppn, range.perm);

                if !shared {
                    // load file content
                    let file_size = file.get_size();
                    let file_offset = range.file_offset(fault_vpn);
                    assert!(file_offset < file_size);

                    // let va_offset = range.va_offset(fault_vpn);
                    // let va_len = range.len - va_offset;
                    // Note: we do not limit `read_len` with `va_len`
                    // consider two overlapping areas with different lengths

                    let read_len = PAGE_SIZE.min(file_size - file_offset);
                    file.read_at(file_offset, &mut ppn.get_bytes_array()[..read_len]);
                }
                true
            }
            None => false,
        }
    }

- ``handle_page_fault`` 的9~13行先检查触发异常的虚拟内存页是否已经映射到物理页面，如果是则说明此异常并非源自惰性按需分页（比如写入只读页），这个问题不归我们管，直接返回 ``false``。
- 接下来的第15行检查出错的虚拟地址是否在映射区域内，如果是我们才上手来处理。

在实际的修复过程中：
- 第19行先调用 ``FileMapping`` 的 ``map`` 方法建立目标虚拟地址到物理页面的映射；
- 第20行将新的映射关系添加到页表；
- 第22~35行处理文件读入。注意实际的文件读取只发生在物理页面的引用计数从0变为1的时候，存在共享的情况下再读取文件可能会覆盖掉用户对内存的修改。

``FileMapping`` 的 ``map`` 方法实现如下：

.. code-block:: rust
    :linenos:

    impl FileMapping {
        /// Create mapping for given virtual address
        fn map(&mut self, va: VirtAddr) -> Option<(PhysPageNum, MapRange, bool)> {
            // Note: currently virtual address ranges never intersect
            let vpn = va.floor();
            for range in &self.ranges {
                if !range.contains(va) {
                    continue;
                }
                let offset = range.file_offset(vpn);
                let (ppn, shared) = match self.map.get(&offset) {
                    Some(&ppn) => (ppn, true),
                    None => {
                        let frame = frame_alloc().unwrap();
                        let ppn = frame.ppn;
                        self.frames.push(frame);
                        self.map.insert(offset, ppn);
                        (ppn, false)
                    }
                };
                if range.perm.contains(MapPermission::W) {
                    self.dirty_parts.insert(offset);
                }
                return Some((ppn, range.clone(), shared));
            }
            None
        }
    }

- 第6~9行先找到包含目标虚拟地址的映射区域；
- 第10行计算虚拟地址对应的文件内偏移；
- 第11~20行先查询此文件偏移是否对应已分配的物理页，如果没有则分配一个物理页帧并记录映射关系；
- 第21~23行检查此映射区域是否有写入权限，如果有则将对应的物理页面标记为脏页。这个处理实际上比较粗糙，有些没有被真正写入的页面也被视为脏页，导致最后会有多余的文件回写。你也可以考虑不维护脏页信息，而是通过检查页表项中由硬件维护的 Dirty 位来确定哪些是真正的脏页。

修复后用户进程重新执行触发缺页异常的指令，此时物理页里存放了文件的内容，这样用户就实现了以读取内存的方式来读取文件。最后来处理被修改的脏页的同步，给 ``FileMapping`` 添加 ``sync`` 方法：

.. code-block:: rust
    :linenos:

    impl FileMapping {
        /// Write back all dirty pages
        pub fn sync(&self) {
            let file_size = self.file.get_size();
            for &offset in self.dirty_parts.iter() {
                let ppn = self.map.get(&offset).unwrap();
                if offset < file_size {
                    // WARNING: this can still cause garbage written
                    //  to file when sharing physical page
                    let va_len = self
                        .ranges
                        .iter()
                        .map(|r| {
                            if r.offset <= offset && offset < r.offset + r.len {
                                PAGE_SIZE.min(r.offset + r.len - offset)
                            } else {
                                0
                            }
                        })
                        .max()
                        .unwrap();
                    let write_len = va_len.min(file_size - offset);

                    self.file
                        .write_at(offset, &ppn.get_bytes_array()[..write_len]);
                }
            }
        }
    }

这个方法将所有潜在的脏物理页内容回写至文件。第10~22行的计算主要为了限制写入内容的长度，以避免垃圾被意外写入文件。

剩下的问题是何时调用 ``sync`` 。正常来说munmap、msync是同步点，你可以自行实现这两个系统调用，这里我们把它放在进程退出之前：

.. code-block:: rust
    :caption: ``os/src/task/mod.rs``
    :emphasize-lines: 10-13

    /// Exit the current 'Running' task and run the next task in task list.
    pub fn exit_current_and_run_next(exit_code: i32) {
        let task = take_current_task().unwrap();
        // ...
        let mut inner = task.inner_exclusive_access();
        // ...
        inner.children.clear();
        // deallocate user space
        inner.memory_set.recycle_data_pages();
        // write back dirty pages
        for mapping in inner.file_mappings.iter() {
            mapping.sync();
        }
        drop(inner);
        // **** release current PCB
        // drop task manually to maintain rc correctly
        drop(task);
        // ...
    }

这样我们就实现了基于内存读写方式的文件读写功能。可以看到mmap不是魔法，内核悄悄帮你完成了实际的文件读写。

4. `**` 扩展easy-fs文件系统功能，支持二级目录结构。可扩展：支持N级目录结构。

实际上easy-fs现有的代码支持目录的存在，只不过整个文件系统只有根目录一个目录，我们考虑放宽现有代码的一些限制。

原本的 ``easy-fs/src/vfs.rs`` 中有一个用于在当前目录下创建常规文件的 ``create`` 方法，我们给它加个参数并包装一下：

.. code-block:: rust
    :caption: ``easy-fs/src/vfs.rs``
    :emphasize-lines: 3,22,51-54,56-59

    impl Inode {
        /// Create inode under current inode by name
        fn create_inode(&self, name: &str, inode_type: DiskInodeType) -> Option<Arc<Inode>> {
            let mut fs = self.fs.lock();
            let op = |root_inode: &DiskInode| {
                // assert it is a directory
                assert!(root_inode.is_dir());
                // has the file been created?
                self.find_inode_id(name, root_inode)
            };
            if self.read_disk_inode(op).is_some() {
                return None;
            }
            // create a new file
            // alloc a inode with an indirect block
            let new_inode_id = fs.alloc_inode();
            // initialize inode
            let (new_inode_block_id, new_inode_block_offset) = fs.get_disk_inode_pos(new_inode_id);
            get_block_cache(new_inode_block_id as usize, Arc::clone(&self.block_device))
                .lock()
                .modify(new_inode_block_offset, |new_inode: &mut DiskInode| {
                    new_inode.initialize(inode_type);
                });
            self.modify_disk_inode(|root_inode| {
                // append file in the dirent
                let file_count = (root_inode.size as usize) / DIRENT_SZ;
                let new_size = (file_count + 1) * DIRENT_SZ;
                // increase size
                self.increase_size(new_size as u32, root_inode, &mut fs);
                // write dirent
                let dirent = DirEntry::new(name, new_inode_id);
                root_inode.write_at(
                    file_count * DIRENT_SZ,
                    dirent.as_bytes(),
                    &self.block_device,
                );
            });

            let (block_id, block_offset) = fs.get_disk_inode_pos(new_inode_id);
            block_cache_sync_all();
            // return inode
            Some(Arc::new(Self::new(
                block_id,
                block_offset,
                self.fs.clone(),
                self.block_device.clone(),
            )))
            // release efs lock automatically by compiler
        }

        /// Create regular file under current inode
        pub fn create(&self, name: &str) -> Option<Arc<Inode>> {
            self.create_inode(name, DiskInodeType::File)
        }

        /// Create directory under current inode
        pub fn create_dir(&self, name: &str) -> Option<Arc<Inode>> {
            self.create_inode(name, DiskInodeType::Directory)
        }
    }

这样我们就可以在一个目录底下调用 ``create_dir`` 创建新目录了（笑）。本质上我们什么也没改，我们再改改其它方法装装样子：

.. code-block:: rust
    :caption: ``easy-fs/src/vfs.rs``
    :emphasize-lines: 7-9,28,41

    impl Inode {
        /// List inodes under current inode
        pub fn ls(&self) -> Vec<String> {
            let _fs = self.fs.lock();
            self.read_disk_inode(|disk_inode| {
                let mut v: Vec<String> = Vec::new();
                if disk_inode.is_file() {
                    return v;
                }

                let file_count = (disk_inode.size as usize) / DIRENT_SZ;
                for i in 0..file_count {
                    let mut dirent = DirEntry::empty();
                    assert_eq!(
                        disk_inode.read_at(i * DIRENT_SZ, dirent.as_bytes_mut(), &self.block_device,),
                        DIRENT_SZ,
                    );
                    v.push(String::from(dirent.name()));
                }
                v
            })
        }

        /// Write data to current inode
        pub fn write_at(&self, offset: usize, buf: &[u8]) -> usize {
            let mut fs = self.fs.lock();
            let size = self.modify_disk_inode(|disk_inode| {
                assert!(disk_inode.is_file());

                self.increase_size((offset + buf.len()) as u32, disk_inode, &mut fs);
                disk_inode.write_at(offset, buf, &self.block_device)
            });
            block_cache_sync_all();
            size
        }

        /// Clear the data in current inode
        pub fn clear(&self) {
            let mut fs = self.fs.lock();
            self.modify_disk_inode(|disk_inode| {
                assert!(disk_inode.is_file());

                let size = disk_inode.size;
                let data_blocks_dealloc = disk_inode.clear_size(&self.block_device);
                assert!(data_blocks_dealloc.len() == DiskInode::total_blocks(size) as usize);
                for data_block in data_blocks_dealloc.into_iter() {
                    fs.dealloc_data(data_block);
                }
            });
            block_cache_sync_all();
        }
    }

对一个普通文件的inode调用 ``ls`` 方法毫无意义，但为了保持接口不变，我们返回一个空 ``Vec``。随意地清空或写入目录文件都会损坏目录结构，这里直接在 ``write_at`` 和 ``clear`` 方法中断言，你也可以改成其它的错误处理方式。

接下来是实际一点的修改（有，但不多）：我们让 ``find`` 方法支持简单的相对路径（不含“.”和“..”）。

.. code-block:: rust
    :caption: ``easy-fs/src/vfs.rs``

    impl Inode {
        /// Find inode under current inode by **path**
        pub fn find(&self, path: &str) -> Option<Arc<Inode>> {
            let fs = self.fs.lock();
            let mut block_id = self.block_id as u32;
            let mut block_offset = self.block_offset;
            for name in path.split('/').filter(|s| !s.is_empty()) {
                let inode_id = get_block_cache(block_id as usize, self.block_device.clone())
                    .lock()
                    .read(block_offset, |disk_inode: &DiskInode| {
                        if disk_inode.is_file() {
                            return None;
                        }
                        self.find_inode_id(name, disk_inode)
                    });
                if inode_id.is_none() {
                    return None;
                }
                (block_id, block_offset) = fs.get_disk_inode_pos(inode_id.unwrap());
            }
            Some(Arc::new(Self::new(
                block_id,
                block_offset,
                self.fs.clone(),
                self.block_device.clone(),
            )))
        }
    }

最后在 ``easy-fs-fuse/src/main.rs`` 里试试我们添加的新特性：

.. code-block:: rust
    :caption: ``easy-fs-fuse/src/main.rs``

    fn read_string(file: &Arc<Inode>) -> String {
        let mut read_buffer = [0u8; 512];
        let mut offset = 0usize;
        let mut read_str = String::new();
        loop {
            let len = file.read_at(offset, &mut read_buffer);
            if len == 0 {
                break;
            }
            offset += len;
            read_str.push_str(core::str::from_utf8(&read_buffer[..len]).unwrap());
        }
        read_str
    }

    fn tree(inode: &Arc<Inode>, name: &str, depth: usize) {
        for _ in 0..depth {
            print!("  ");
        }
        println!("{}", name);
        for name in inode.ls() {
            let child = inode.find(&name).unwrap();
            tree(&child, &name, depth + 1);
        }
    }

    #[test]
    fn efs_dir_test() -> std::io::Result<()> {
        let block_file = Arc::new(BlockFile(Mutex::new({
            let f = OpenOptions::new()
                .read(true)
                .write(true)
                .create(true)
                .open("target/fs.img")?;
            f.set_len(8192 * 512).unwrap();
            f
        })));
        EasyFileSystem::create(block_file.clone(), 4096, 1);
        let efs = EasyFileSystem::open(block_file.clone());
        let root = Arc::new(EasyFileSystem::root_inode(&efs));
        root.create("f1");
        root.create("f2");

        let d1 = root.create_dir("d1").unwrap();

        let f3 = d1.create("f3").unwrap();
        let d2 = d1.create_dir("d2").unwrap();

        let f4 = d2.create("f4").unwrap();
        tree(&root, "/", 0);

        let f3_content = "3333333";
        let f4_content = "4444444444444444444";
        f3.write_at(0, f3_content.as_bytes());
        f4.write_at(0, f4_content.as_bytes());

        assert_eq!(read_string(&d1.find("f3").unwrap()), f3_content);
        assert_eq!(read_string(&root.find("/d1/f3").unwrap()), f3_content);
        assert_eq!(read_string(&d2.find("f4").unwrap()), f4_content);
        assert_eq!(read_string(&d1.find("d2/f4").unwrap()), f4_content);
        assert_eq!(read_string(&root.find("/d1/d2/f4").unwrap()), f4_content);
        assert!(f3.find("whatever").is_none());
        Ok(())
    }

如果你觉得这个练习不够过瘾，可以试试下面的任务：

- 让easy-fs支持包含“.”和“..”的相对路径。你可以在目录文件里存放父目录的inode。
- 在内核里给进程加上当前路径信息，然后实现chdir和getcwd。当然，也可以顺便补上openat和mkdir。
- 在easy-fs中实现rename和mv的功能。在目录文件中删掉一些目录项也许要实现 ``decrease_size`` 或者类似删除的东西，但也可以考虑用删除标记这种常见的手段让一个目录项变得“不存在”。

问答题
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

1. `*` 文件系统的功能是什么？

   将数据以文件的形式持久化保存在存储设备上。

2. `**` 目前的文件系统只有单级目录，假设想要支持多级文件目录，请描述你设想的实现方式，描述合理即可。

   允许在目录项中存在目录（原本只能存在普通文件）即可。

3. `**` 软链接和硬链接是干什么的？有什么区别？当删除一个软链接或硬链接时分别会发生什么？

   软硬链接的作用都是给一个文件以"别名"，使得不同的多个路径可以指向同一个文件。当删除软链接时候，对文件没有任何影响，当删除硬链接时，文件的引用计数会被减一，若引用计数为0，则该文件所占据的磁盘空间将会被回收。

4. `***` 在有了多级目录之后，我们就也可以为一个目录增加硬链接了。在这种情况下，文件树中是否可能出现环路(软硬链接都可以，鼓励多尝试)？你认为应该如何解决？请在你喜欢的系统上实现一个环路，描述你的实现方式以及系统提示、实际测试结果。

   是可以出现环路的，一种可能的解决方式是在访问文件的时候检查自己遍历的路径中是否有重复的inode，并在发现环路时返回错误。

5. `*` 目录是一类特殊的文件，存放的是什么内容？用户可以自己修改目录内容吗？

   存放的是目录中的文件列表以及他们对应的inode，通常而言用户不能自己修改目录的内容，但是可以通过操作目录（如mv里面的文件）的方式间接修改。

6. `**` 在实际操作系统中，如Linux，为什么会存在大量的文件系统类型？

   因为不同的文件系统有着不同的特性，比如对于特定种类的存储设备的优化，或是快照和多设备管理等高级特性，适用于不同的使用场景。

7. `**` 可以把文件控制块放到目录项中吗？这样做有什么优缺点？

   可以，是对于小目录可以减少一次磁盘访问，提升性能，但是对大目录而言会使得在目录中查找文件的性能降低。

8. `**` 为什么要同时维护进程的打开文件表和操作系统的打开文件表？这两个打开文件表有什么区别和联系？

   多个进程可能会同时打开同一个文件，操作系统级的打开文件表可以加快后续的打开操作，但同时由于每个进程打开文件时使用的访问模式或是偏移量不同，所以还需要进程的打开文件表另外记录。

9. `**` 文件分配的三种方式是如何组织文件数据块的？各有什么特征（存储、文件读写、可靠性）？

   连续分配：实现简单、存取速度快，但是难以动态增加文件大小，长期使用后会产生大量无法使用（过小而无法放入大文件）碎片空间。

   链接分配：可以处理文件大小的动态增长，也不会出现碎片，但是只能按顺序访问文件中的块，同时一旦有一个块损坏，后面的其他块也无法读取，可靠性差。

   索引分配：可以随机访问文件中的偏移量，但是对于大文件需要实现多级索引，实现较为复杂。

10. `**` 如果一个程序打开了一个文件，写入了一些数据，但是没有及时关闭，可能会有什么后果？如果打开文件后，又进一步发出了读文件的系统调用，操作系统中各个组件是如何相互协作完成整个读文件的系统调用的？

   (若也没有flush的话）假如此时操作系统崩溃，尚处于内存缓冲区中未写入磁盘的数据将会丢失，同时也会占用文件描述符，造成资源的浪费。首先是系统调用处理的部分，将这一请求转发给文件系统子系统，文件系统子系统再将其转发给块设备子系统，最后再由块设备子系统转发给实际的磁盘驱动程序读取数据，最终返回给程序。

11. `***` 文件系统是一个操作系统必要的组件吗？是否可以将文件系统放到用户态？这样做有什么好处？操作系统需要提供哪些基本支持？

    不是，如在本章之前的rCore就没有文件系统。可以，如在Linux下就有FUSE这样的框架可以实现这一点。这样可以使得文件系统的实现更为灵活，开发与调试更为简便。操作系统需要提供一个注册用户态文件系统实现的机制，以及将收到的文件系统相关系统调用转发给注册的用户态进程的支持。

