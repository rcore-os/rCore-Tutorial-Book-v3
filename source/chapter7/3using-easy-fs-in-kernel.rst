在内核中使用 easy-fs
===============================================

本节导读
-----------------------------------------------

上节实现了 ``easy-fs`` 文件系统，并能在用户态来进行测试，但还没有放入到内核中来。本节我们介绍如何将 ``easy-fs`` 文件系统接入内核中从而在内核中支持常规文件和目录。为此，在操作系统内核中需要有对接 ``easy-fs`` 文件系统的各种结构，它们自下而上可以分成这样几个层次：

- 块设备驱动层。针对内核所要运行在的 qemu 或 k210 平台，我们需要将平台上的块设备驱动起来并实现 ``easy-fs`` 所需的 ``BlockDevice`` Trait ，这样 ``easy-fs`` 才能将该块设备用作 easy-fs 镜像的载体。
- ``easy-fs`` 层。我们在上一节已经介绍了 ``easy-fs`` 文件系统内部的层次划分。这里是站在内核的角度，只需知道它接受一个块设备 ``BlockDevice`` ，并可以在上面打开文件系统 ``EasyFileSystem`` ，进而获取 ``Inode`` 核心数据结构，进行各种文件系统操作即可。
- 内核索引节点层。在内核中需要将 ``easy-fs`` 提供的 ``Inode`` 进一步封装成 ``OSInode`` ，以表示进程中一个打开的常规文件。由于有很多种不同的打开方式，因此在 ``OSInode`` 中要维护一些额外的信息。
- 文件描述符层。常规文件对应的 ``OSInode`` 是文件的内核内部表示，因此需要为它实现 ``File`` Trait 从而能够可以将它放入到进程文件描述符表中并通过 ``sys_read/write`` 系统调用进行读写。
- 系统调用层。由于引入了常规文件这种文件类型，导致一些系统调用以及相关的内核机制需要进行一定的修改。

块设备驱动层
-----------------------------------------------

在 ``drivers`` 子模块中的 ``block/mod.rs`` 中，我们可以找到内核访问的块设备实例 ``BLOCK_DEVICE`` ：

.. code-block:: rust

    // os/drivers/block/mod.rs

    #[cfg(feature = "board_qemu")]
    type BlockDeviceImpl = virtio_blk::VirtIOBlock;

    #[cfg(feature = "board_k210")]
    type BlockDeviceImpl = sdcard::SDCardWrapper;

    lazy_static! {
        pub static ref BLOCK_DEVICE: Arc<dyn BlockDevice> = Arc::new(BlockDeviceImpl::new());
    }

qemu 和 k210 平台上的块设备是不同的。在 qemu 上，我们使用 ``VirtIOBlock`` 访问 VirtIO 块设备；而在 k210 上，我们使用 ``SDCardWrapper`` 来访问插入 k210 开发板上真实的 microSD 卡，它们都实现了 ``easy-fs`` 要求的 ``BlockDevice`` Trait 。通过 ``#[cfg(feature)]`` 可以在编译的时候根据编译参数调整 ``BlockDeviceImpl`` 具体为哪个块设备，之后将它全局实例化为 ``BLOCK_DEVICE`` 使得内核的其他模块可以访问。

Qemu 模拟器平台
+++++++++++++++++++++++++++++++++++++++++++++++

在启动 Qemu 模拟器的时候，我们可以配置参数来添加一块 VirtIO 块设备：

.. code-block:: makefile
    :linenos:
    :emphasize-lines: 12-13

    # os/Makefile

    FS_IMG := ../user/target/$(TARGET)/$(MODE)/fs.img

    run-inner: build
    ifeq ($(BOARD),qemu)
        @qemu-system-riscv64 \
            -machine virt \
            -nographic \
            -bios $(BOOTLOADER) \
            -device loader,file=$(KERNEL_BIN),addr=$(KERNEL_ENTRY_PA) \
            -drive file=$(FS_IMG),if=none,format=raw,id=x0 \
            -device virtio-blk-device,drive=x0,bus=virtio-mmio-bus.0

- 第 12 行，我们为虚拟机添加一块虚拟硬盘，内容为我们之前通过 ``easy-fs-fuse`` 工具打包的包含应用 ELF 的 easy-fs 镜像，并命名为 ``x0`` 。
- 第 13 行，我们将硬盘 ``x0`` 作为一个 VirtIO 总线中的一个块设备接入到虚拟机系统中。 ``virtio-mmio-bus.0`` 表示 VirtIO 总线通过 MMIO 进行控制，且该块设备在总线中的编号为 0 。

**内存映射 I/O** (MMIO, Memory-Mapped I/O) 指的是外设的设备寄存器可以通过特定的物理内存地址来访问，每个外设的设备寄存器都分布在没有交集的一个或数个物理地址区间中，不同外设的设备寄存器所占的物理地址空间也不会产生交集，且这些外设物理地址区间也不会和RAM的物理内存所在的区间存在交集。从 RV64 平台 Qemu 的 `源码 <https://github.com/qemu/qemu/blob/master/hw/riscv/virt.c#L58>`_ 中可以找到 VirtIO 总线的 MMIO 物理地址区间为从 0x10001000 开头的 4KiB 。为了能够在内核中访问 VirtIO 总线，我们就必须在内核地址空间中对特定内存区域提前进行映射：

.. code-block:: rust

    // os/src/config.rs

    #[cfg(feature = "board_qemu")]
    pub const MMIO: &[(usize, usize)] = &[
        (0x10001000, 0x1000),
    ];

如上面一段代码所示，在 ``config`` 子模块中我们硬编码 Qemu 上的 VirtIO 总线的 MMIO 地址区间（起始地址，长度）。在创建内核地址空间的时候需要建立页表映射：

.. code-block:: rust

    // os/src/mm/memory_set.rs

    use crate::config::MMIO;

    impl MemorySet {
        /// Without kernel stacks.
        pub fn new_kernel() -> Self {
            ...
            println!("mapping memory-mapped registers");
            for pair in MMIO {
                memory_set.push(MapArea::new(
                    (*pair).0.into(),
                    ((*pair).0 + (*pair).1).into(),
                    MapType::Identical,
                    MapPermission::R | MapPermission::W,
                ), None);
            }
            memory_set
        }
    }

这里我们进行的是透明的恒等映射，从而让内核可以兼容于直接访问物理地址的设备驱动库。

由于设备驱动的开发过程比较琐碎，我们这里直接使用已有的 `virtio-drivers <https://github.com/rcore-os/virtio-drivers>`_ crate ，它已经支持 VirtIO 总线架构下的块设备、网络设备、GPU 等设备。关于VirtIO 相关驱动的内容，将放在后续章节中介绍。

.. code-block:: rust

    // os/src/drivers/block/virtio_blk.rs

    use virtio_drivers::{VirtIOBlk, VirtIOHeader};
    const VIRTIO0: usize = 0x10001000;

    pub struct VirtIOBlock(Mutex<VirtIOBlk<'static>>);

    impl VirtIOBlock {
        pub fn new() -> Self {
            Self(Mutex::new(VirtIOBlk::new(
                unsafe { &mut *(VIRTIO0 as *mut VirtIOHeader) }
            ).unwrap()))
        }
    }

    impl BlockDevice for VirtIOBlock {
        fn read_block(&self, block_id: usize, buf: &mut [u8]) {
            self.0.lock().read_block(block_id, buf).expect("Error when reading VirtIOBlk");
        }
        fn write_block(&self, block_id: usize, buf: &[u8]) {
            self.0.lock().write_block(block_id, buf).expect("Error when writing VirtIOBlk");
        }
    }

上面的代码中，我们将 ``virtio-drivers`` crate 提供的 VirtIO 块设备抽象 ``VirtIOBlk`` 包装为我们自己的 ``VirtIOBlock`` ，实质上只是加上了一层互斥锁，生成一个新的类型来实现 ``easy-fs`` 需要的 ``BlockDevice`` Trait 。注意在 ``VirtIOBlk::new`` 的时候需要传入一个 ``&mut VirtIOHeader`` 的参数， ``VirtIOHeader`` 实际上就代表以 MMIO 方式访问 VirtIO 设备所需的一组设备寄存器。因此我们从 ``qemu-system-riscv64`` 平台上的 Virtio MMIO 区间左端 ``VIRTIO0`` 开始转化为一个 ``&mut VirtIOHeader`` 就可以在该平台上访问这些设备寄存器了。

很容易为 ``VirtIOBlock`` 实现 ``BlockDevice`` Trait ，因为它内部来自 ``virtio-drivers`` crate 的 ``VirtIOBlk`` 类型已经实现了 ``read/write_block`` 方法，我们进行转发即可。

VirtIO 设备需要占用部分内存作为一个公共区域从而更好的和 CPU 进行合作。这就像 MMU 需要在内存中保存多级页表才能和 CPU 共同实现分页机制一样。在 VirtIO 架构下，需要在公共区域中放置一种叫做 VirtQueue 的环形队列，CPU 可以向此环形队列中向 VirtIO 设备提交请求，也可以从队列中取得请求的结果，详情可以参考 `virtio 文档 <https://docs.oasis-open.org/virtio/virtio/v1.1/csprd01/virtio-v1.1-csprd01.pdf>`_ 。对于 VirtQueue 的使用涉及到物理内存的分配和回收，但这并不在 VirtIO 驱动 ``virtio-drivers`` 的职责范围之内，因此它声明了数个相关的接口，需要库的使用者自己来实现：

.. code-block:: rust
    
    // https://github.com/rcore-os/virtio-drivers/blob/master/src/hal.rs#L57

    extern "C" {
        fn virtio_dma_alloc(pages: usize) -> PhysAddr;
        fn virtio_dma_dealloc(paddr: PhysAddr, pages: usize) -> i32;
        fn virtio_phys_to_virt(paddr: PhysAddr) -> VirtAddr;
        fn virtio_virt_to_phys(vaddr: VirtAddr) -> PhysAddr;
    }

由于我们已经实现了基于分页内存管理的地址空间，实现这些功能自然不在话下：

.. code-block:: rust

    // os/src/drivers/block/virtio_blk.rs

    lazy_static! {
        static ref QUEUE_FRAMES: Mutex<Vec<FrameTracker>> = Mutex::new(Vec::new());
    }

    #[no_mangle]
    pub extern "C" fn virtio_dma_alloc(pages: usize) -> PhysAddr {
        let mut ppn_base = PhysPageNum(0);
        for i in 0..pages {
            let frame = frame_alloc().unwrap();
            if i == 0 { ppn_base = frame.ppn; }
            assert_eq!(frame.ppn.0, ppn_base.0 + i);
            QUEUE_FRAMES.lock().push(frame);
        }
        ppn_base.into()
    }

    #[no_mangle]
    pub extern "C" fn virtio_dma_dealloc(pa: PhysAddr, pages: usize) -> i32 {
        let mut ppn_base: PhysPageNum = pa.into();
        for _ in 0..pages {
            frame_dealloc(ppn_base);
            ppn_base.step();
        }
        0
    }

    #[no_mangle]
    pub extern "C" fn virtio_phys_to_virt(paddr: PhysAddr) -> VirtAddr {
        VirtAddr(paddr.0)
    }

    #[no_mangle]
    pub extern "C" fn virtio_virt_to_phys(vaddr: VirtAddr) -> PhysAddr {
        PageTable::from_token(kernel_token()).translate_va(vaddr).unwrap()
    }

这里有一些细节需要注意：

- ``virtio_dma_alloc/dealloc`` 需要分配/回收数个 *连续* 的物理页帧，而我们的 ``frame_alloc`` 是逐个分配，严格来说并不保证分配的连续性。幸运的是，这个过程只会发生在内核初始化阶段，因此能够保证连续性。
- 在 ``virtio_dma_alloc`` 中通过 ``frame_alloc`` 得到的那些物理页帧 ``FrameTracker`` 都会被保存在全局的向量 ``QUEUE_FRAMES`` 以延长它们的生命周期，避免提前被回收。


K210 真实硬件平台
+++++++++++++++++++++++++++++++++++++++++++++++

在 K210 开发板上，我们可以插入 microSD 卡并将其作为块设备。相比 VirtIO 块设备来说，想要将 microSD 驱动起来是一件比较困难的事情。microSD 自身的通信规范比较复杂，且还需考虑在 K210 中microSD挂在 **串行外设接口** (SPI, Serial Peripheral Interface) 总线上的情况。此外还需要正确设置 GPIO 的管脚映射并调整各锁相环的频率。实际上，在一块小小的芯片中除了 K210 CPU 之外，还集成了很多不同种类的外设和控制模块，它们内在的关联比较紧密，不能像 VirtIO 设备那样容易地从系统中独立出来。

好在目前 Rust 嵌入式的生态正高速发展，针对 K210 平台也有比较成熟的封装了各类外设接口的库可以用来开发上层应用。但是其功能往往分散为多个 crate ，在使用的时候需要开发者根据需求自行进行组装。这属于 Rust 的特点之一，和 C 语言提供一个一站式的板级开发包风格有很大的不同。在开发的时候，笔者就从社区中选择了一些 crate 并进行了微量修改最终变成 ``k210-hal/k210-pac/k210-soc`` 三个能够运行在 S 特权级（它们的原身仅支持运行在 M 特权级）的 crate ，它们可以更加便捷的实现 microSD 的驱动。关于 microSD 的驱动 ``SDCardWrapper`` 的实现，有兴趣的读者可以参考 ``os/src/drivers/block/sdcard.rs`` 。

.. note::

    **感谢相关 crate 的原身**

    - `k210-hal <https://github.com/riscv-rust/k210-hal>`_
    - `k210-pac <https://github.com/riscv-rust/k210-pac>`_
    - `k210-sdk-stuff <https://github.com/laanwj/k210-sdk-stuff>`_

要在 K210 上启用 microSD ，执行的时候无需任何改动，只需在 ``make run`` 之前将 microSD 插入 PC 再通过 ``make sdcard`` 将 easy-fs 镜像烧写进去即可。而后，将 microSD 插入 K210 开发板，连接到 PC 再 ``make run`` 。

在对 microSD 进行操作的时候，会涉及到 K210 内置的各种外设，正所谓”牵一发而动全身“。因此 K210 平台上的 MMIO 包含很多区间：

.. code-block:: rust

    // os/src/config.rs

    #[cfg(feature = "board_k210")]
    pub const MMIO: &[(usize, usize)] = &[
        // we don't need clint in S priv when running
        // we only need claim/complete for target0 after initializing
        (0x0C00_0000, 0x3000),      /* PLIC      */
        (0x0C20_0000, 0x1000),      /* PLIC      */
        (0x3800_0000, 0x1000),      /* UARTHS    */
        (0x3800_1000, 0x1000),      /* GPIOHS    */
        (0x5020_0000, 0x1000),      /* GPIO      */
        (0x5024_0000, 0x1000),      /* SPI_SLAVE */
        (0x502B_0000, 0x1000),      /* FPIOA     */
        (0x502D_0000, 0x1000),      /* TIMER0    */
        (0x502E_0000, 0x1000),      /* TIMER1    */
        (0x502F_0000, 0x1000),      /* TIMER2    */
        (0x5044_0000, 0x1000),      /* SYSCTL    */
        (0x5200_0000, 0x1000),      /* SPI0      */
        (0x5300_0000, 0x1000),      /* SPI1      */
        (0x5400_0000, 0x1000),      /* SPI2      */
    ];

内核索引节点层
-----------------------------------------------

在本章的第一小节我们介绍过，站在用户的角度看来，在一个进程中可以使用多种不同的标志来打开一个文件，这会影响到打开的这个文件可以用何种方式被访问。此外，在连续调用 ``sys_read/write`` 读写一个文件的时候，我们知道进程中也存在着一个文件读写的当前偏移量，它也随着文件读写的进行而被不断更新。这些用户视角中的文件系统抽象特征需要内核来实现，与进程有很大的关系，而 ``easy-fs`` 文件系统不必涉及这些与进程结合紧密的属性。因此，我们需要将 ``easy-fs`` 提供的 ``Inode`` 加上上述信息，进一步封装为 OS 中的索引节点 ``OSInode`` ：

.. code-block:: rust

    // os/src/fs/inode.rs

    pub struct OSInode {
        readable: bool,
        writable: bool,
        inner: Mutex<OSInodeInner>,
    }

    pub struct OSInodeInner {
        offset: usize,
        inode: Arc<Inode>,
    }

    impl OSInode {
        pub fn new(
            readable: bool,
            writable: bool,
            inode: Arc<Inode>,
        ) -> Self {
            Self {
                readable,
                writable,
                inner: Mutex::new(OSInodeInner {
                    offset: 0,
                    inode,
                }),
            }
        }
    }

``OSInode`` 就表示进程中一个被打开的常规文件或目录。 ``readable/writable`` 分别表明该文件是否允许通过 ``sys_read/write`` 进行读写。至于在 ``sys_read/write`` 期间被维护偏移量 ``offset`` 和它在 ``easy-fs`` 中的 ``Inode`` 则加上一把互斥锁丢到 ``OSInodeInner`` 中。这在提供内部可变性的同时，也可以简单应对多个进程同时读写一个文件的情况。


文件描述符层
-----------------------------------------------

因为 ``OSInode`` 也是要一种要放到进程文件描述符表中，并通过 ``sys_read/write`` 系统调用进行读写的文件，因此我们也需要为它实现 ``File`` Trait ：

.. code-block:: rust

    // os/src/fs/inode.rs

    impl File for OSInode {
        fn readable(&self) -> bool { self.readable }
        fn writable(&self) -> bool { self.writable }
        fn read(&self, mut buf: UserBuffer) -> usize {
            let mut inner = self.inner.lock();
            let mut total_read_size = 0usize;
            for slice in buf.buffers.iter_mut() {
                let read_size = inner.inode.read_at(inner.offset, *slice);
                if read_size == 0 {
                    break;
                }
                inner.offset += read_size;
                total_read_size += read_size;
            }
            total_read_size
        }
        fn write(&self, buf: UserBuffer) -> usize {
            let mut inner = self.inner.lock();
            let mut total_write_size = 0usize;
            for slice in buf.buffers.iter() {
                let write_size = inner.inode.write_at(inner.offset, *slice);
                assert_eq!(write_size, slice.len());
                inner.offset += write_size;
                total_write_size += write_size;
            }
            total_write_size
        }
    }

本章我们为 ``File`` Trait 新增了 ``readable/writable`` 两个抽象接口从而在 ``sys_read/sys_write`` 的时候进行简单的访问权限检查。 ``read/write`` 的实现也比较简单，只需遍历 ``UserBuffer`` 中的每个缓冲区片段，调用 ``Inode`` 写好的 ``read/write_at`` 接口就好了。注意 ``read/write_at`` 的起始位置是在 ``OSInode`` 中维护的 ``offset`` ，这个 ``offset`` 也随着遍历的进行被持续更新。在 ``read/write`` 的全程需要获取 ``OSInode`` 的互斥锁，保证两个进程无法同时访问同个文件。

文件系统相关内核机制实现
-----------------------------------------------

文件系统初始化
+++++++++++++++++++++++++++++++++++++++++++++++

在上一小节我们介绍过，为了使用 ``easy-fs`` 提供的抽象，我们需要进行一些初始化操作才能成功将 ``easy-fs`` 接入到我们的内核中。按照前面总结的步骤：

1. 打开块设备。从本节前面可以看出，我们已经打开并可以访问装载有 easy-fs 文件系统镜像的块设备 ``BLOCK_DEVICE`` 。
2. 从块设备 ``BLOCK_DEVICE`` 上打开文件系统。
3. 从文件系统中获取根目录的 inode 。

2-3 步我们在这里完成：

.. code-block:: rust

    // os/src/fs/inode.rs

    lazy_static! {
        pub static ref ROOT_INODE: Arc<Inode> = {
            let efs = EasyFileSystem::open(BLOCK_DEVICE.clone());
            Arc::new(EasyFileSystem::root_inode(&efs))
        };
    }

这之后就可以使用根目录的 inode ``ROOT_INODE`` ，在内核中进行各种  ``easy-fs`` 的相关操作了。例如，在文件系统初始化完毕之后，在内核主函数 ``rust_main`` 中调用 ``list_apps`` 函数来列举文件系统中可用的应用的文件名：

.. code-block:: rust

    // os/src/fs/inode.rs

    pub fn list_apps() {
        println!("/**** APPS ****");
        for app in ROOT_INODE.ls() {
            println!("{}", app);
        }
        println!("**************/")
    }


通过 sys_open 打开文件
+++++++++++++++++++++++++++++++++++++++++++++++

我们需要在内核中也定义一份打开文件的标志 ``OpenFlags`` ：

.. code-block:: rust

    // os/src/fs/inode.rs

    bitflags! {
        pub struct OpenFlags: u32 {
            const RDONLY = 0;
            const WRONLY = 1 << 0;
            const RDWR = 1 << 1;
            const CREATE = 1 << 9;
            const TRUNC = 1 << 10;
        }
    }

    impl OpenFlags {
        /// Do not check validity for simplicity
        /// Return (readable, writable)
        pub fn read_write(&self) -> (bool, bool) {
            if self.is_empty() {
                (true, false)
            } else if self.contains(Self::WRONLY) {
                (false, true)
            } else {
                (true, true)
            }
        }
    }

它的 ``read_write`` 方法可以根据标志的情况返回要打开的文件是否允许读写。简单起见，这里假设标志自身一定合法。

接着，我们实现 ``open_file`` 内核函数，可根据文件名打开一个根目录下的文件：

.. code-block:: rust

    // os/src/fs/inode.rs

    pub fn open_file(name: &str, flags: OpenFlags) -> Option<Arc<OSInode>> {
        let (readable, writable) = flags.read_write();
        if flags.contains(OpenFlags::CREATE) {
            if let Some(inode) = ROOT_INODE.find(name) {
                // clear size
                inode.clear();
                Some(Arc::new(OSInode::new(
                    readable,
                    writable,
                    inode,
                )))
            } else {
                // create file
                ROOT_INODE.create(name)
                    .map(|inode| {
                        Arc::new(OSInode::new(
                            readable,
                            writable,
                            inode,
                        ))
                    })
            }
        } else {
            ROOT_INODE.find(name)
                .map(|inode| {
                    if flags.contains(OpenFlags::TRUNC) {
                        inode.clear();
                    }
                    Arc::new(OSInode::new(
                        readable,
                        writable,
                        inode
                    ))
                })
        }
    }

这里主要是实现了 ``OpenFlags`` 各标志位的语义。例如只有 ``flags`` 参数包含 `CREATE` 标志位才允许创建文件；而如果文件已经存在，则清空文件的内容。另外我们将从 ``OpenFlags`` 解析得到的读写相关权限传入 ``OSInode`` 的创建过程中。

在其基础上， ``sys_open`` 也就很容易实现了：

.. code-block:: rust

    // os/src/syscall/fs.rs

    pub fn sys_open(path: *const u8, flags: u32) -> isize {
        let task = current_task().unwrap();
        let token = current_user_token();
        let path = translated_str(token, path);
        if let Some(inode) = open_file(
            path.as_str(),
            OpenFlags::from_bits(flags).unwrap()
        ) {
            let mut inner = task.acquire_inner_lock();
            let fd = inner.alloc_fd();
            inner.fd_table[fd] = Some(inode);
            fd as isize
        } else {
            -1
        }
    }

通过 sys_exec 加载并执行应用
+++++++++++++++++++++++++++++++++++++++++++++++

在有了文件系统支持之后，我们在 ``sys_exec`` 所需的表示应用的 ELF 文件格式的数据就不再需要通过应用加载器从内核的数据段获取，而是从文件系统中获取即可：

.. code-block:: rust
    :linenos:
    :emphasize-lines: 15-24

    // os/src/syscall/process.rs

    pub fn sys_exec(path: *const u8, mut args: *const usize) -> isize {
        let token = current_user_token();
        let path = translated_str(token, path);
        let mut args_vec: Vec<String> = Vec::new();
        loop {
            let arg_str_ptr = *translated_ref(token, args);
            if arg_str_ptr == 0 {
                break;
            }
            args_vec.push(translated_str(token, arg_str_ptr as *const u8));
            unsafe { args = args.add(1); }
        }
        if let Some(app_inode) = open_file(path.as_str(), OpenFlags::RDONLY) {
            let all_data = app_inode.read_all();
            let task = current_task().unwrap();
            let argc = args_vec.len();
            task.exec(all_data.as_slice(), args_vec);
            // return argc because cx.x[10] will be covered with it later
            argc as isize
        } else {
            -1
        }
    }

注意上面代码片段中的高亮部分。当执行获取应用的 ELF 数据的操作时，首先调用 ``open_file`` 函数，以只读的方式在内核中打开应用文件并获取它对应的 ``OSInode`` 。接下来可以通过 ``OSInode::read_all`` 将该文件的数据全部读到一个向量 ``all_data`` 中：

.. code-block:: rust

    // os/src/fs/inode.rs

    impl OSInode {
        pub fn read_all(&self) -> Vec<u8> {
            let mut inner = self.inner.lock();
            let mut buffer = [0u8; 512];
            let mut v: Vec<u8> = Vec::new();
            loop {
                let len = inner.inode.read_at(inner.offset, &mut buffer);
                if len == 0 {
                    break;
                }
                inner.offset += len;
                v.extend_from_slice(&buffer[..len]);
            }
            v
        }
    }

之后，就可以从向量 ``all_data`` 中拿到应用中的 ELF 数据，当解析完毕并创建完应用地址空间后该向量将会被回收。

同样的，我们在内核中创建初始进程 ``initproc`` 也需要替换为基于文件系统的实现：

.. code-block:: rust

    // os/src/task/mod.rs

    lazy_static! {
        pub static ref INITPROC: Arc<TaskControlBlock> = Arc::new({
            let inode = open_file("initproc", OpenFlags::RDONLY).unwrap();
            let v = inode.read_all();
            TaskControlBlock::new(v.as_slice())
        });
    }