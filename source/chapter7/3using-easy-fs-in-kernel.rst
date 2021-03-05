在内核中使用 easy-fs
===============================================

本节导读
-----------------------------------------------

本节我们介绍如何将 ``easy-fs`` 文件系统接入内核中从而在内核中支持标准文件和目录。这自下而上可以分成这样几个层次：

- 块设备驱动层。针对内核所要运行在的 qemu 或 k210 平台，我们需要将平台上的块设备驱动起来并实现 ``easy-fs`` 所需的 ``BlockDevice`` Trait ，这样 ``easy-fs`` 才能将该块设备用作 easy-fs 镜像的载体。
- ``easy-fs`` 层。我们在上一节已经介绍了它内部的层次划分。这里是站在内核的角度，只需知道它接受一个块设备 ``BlockDevice`` ，并可以在上面打开文件系统 ``EasyFileSystem`` ，进而获取 ``Inode`` 进行各种文件系统操作即可。
- 内核索引节点层。在内核中需要将 ``easy-fs`` 提供的 ``Inode`` 进一步封装成 ``OSInode`` 表示进程中一个打开的标准文件。由于有很多种不同的打开方式，因此在 ``OSInode`` 中要维护一些额外的信息。
- 文件描述符层。标准文件对应的 ``OSInode`` 也是一种文件，因此也需要为它实现 ``File`` Trait 从而能够可以将它放入到进程文件描述符表中并通过 ``sys_read/write`` 系统调用进行读写。
- 系统调用层。针对标准文件这种新的文件类型的加入，一些系统调用需要进行修改。

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

**内存映射 I/O** (MMIO, Memory-Mapped I/O) 指的是外设的设备寄存器可以通过物理地址来访问，每个外设的设备寄存器都分布在一个或数个物理地址区间中，外设两两之间不会产生冲突，且这些物理地址区间也不会和物理内存所在的区间存在交集。从 RV64 平台 Qemu 的 `源码 <https://github.com/qemu/qemu/blob/master/hw/riscv/virt.c#L58>`_ 中可以找到 VirtIO 总线的 MMIO 物理地址区间为从 0x10001000 开头的 4KiB 。为了能够在内核中访问 VirtIO 总线，我们就必须在内核地址空间中提前进行映射：

.. code-block:: rust

    // os/src/config.rs

    #[cfg(feature = "board_qemu")]
    pub const MMIO: &[(usize, usize)] = &[
        (0x10001000, 0x1000),
    ];

如上面一段代码所示，在 ``config`` 子模块中我们硬编码 Qemu 上仅有一段访问 VirtIO 总线的 MMIO 区间。在创建内核地址空间的时候需要进行映射：

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

这里我们进行的是透明的恒等映射从而让内核可以兼容于直接访问物理地址的设备驱动库。

由于设备驱动的开发过程比较琐碎且与 OS 课程没有很大关系，我们这里直接使用已有的 `virtio-drivers <https://github.com/rcore-os/virtio-drivers>`_ crate ，它已经支持 VirtIO 总线架构下的块设备、网络设备、GPU 等设备。

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

在 K210 开发板上，我们可以插入 microSD 卡并将其作为块设备。相比 VirtIO 块设备来说，想要将 microSD 驱动起来是一件相当困难的事情。SD 自身的通信规范就已经非常复杂了，在 K210 上它还是挂在 **串行外设接口** (SPI, Serial Peripheral Interface) 总线下。此外还需要正确设置 GPIO 的管脚映射并调整各锁相环的频率。实际上，在一块小小的芯片中除了 K210 CPU 之外，还集成了很多不同种类的外设和控制模块，它们内在的关联比较紧密，不能像 VirtIO 设备那样从系统中独立出来。

好在目前 Rust 嵌入式的生态正高速发展，针对 K210 平台也有比较成熟的封装了各类外设接口的库可以用来开发上层应用。但是其功能往往分散为多个 crate ，在使用的时候需要开发者根据需求自行进行组装。这属于 Rust 的特点之一，和 C 语言提供一个一站式的板级开发包风格有很大的不同。在开发的时候，笔者就从社区中选择了一些 crate 并进行了微量修改最终变成 ``k210-hal/k210-pac/k210-soc`` 三个能够运行在 S 特权级（它们的原身仅支持运行在 M 特权级）的 crate ，它们可以更加便捷的实现 microSD 的驱动。关于 microSD 的驱动 ``SDCardWrapper`` 的实现，有兴趣的读者可以参考 ``os/src/drivers/block/sdcard.rs`` 。

.. note::

    **感谢相关 crate 的原身**

    - `k210-hal <https://github.com/riscv-rust/k210-hal>`_
    - `k210-pac <https://github.com/riscv-rust/k210-pac>`_
    - `k210-sdk-stuff <https://github.com/laanwj/k210-sdk-stuff>`_

要在 K210 上启用 microSD ，执行的时候无需任何改动，只需在 ``make run`` 之前将 microSD 插入 PC 再通过 ``make sdcard`` 将 easy-fs 镜像烧写进去即可。而后，将 microSD 插入 K210 开发板，连接到 PC 再 ``make run`` 。

在对 microSD 进行操作的时候，基本上要涉及到 K210 内置的所有外设，正所谓”牵一发而动全身“。因此 K210 平台上的 MMIO 包含很多区间：

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

文件描述符层
-----------------------------------------------

相关系统调用实现
-----------------------------------------------

通过 sys_exec 加载并执行应用
+++++++++++++++++++++++++++++++++++++++++++++++

通过 sys_open 打开文件
+++++++++++++++++++++++++++++++++++++++++++++++