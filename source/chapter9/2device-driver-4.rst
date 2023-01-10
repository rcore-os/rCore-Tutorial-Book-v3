virtio_gpu设备驱动程序
=========================================

本节导读
-----------------------------------------

本节主要介绍了与操作系统无关的基本virtio_gpu设备驱动程序的设计与实现，以及如何在操作系统中封装virtio_gpu设备驱动程序，实现对丰富多彩的GUI app的支持。




virtio-gpu驱动程序
------------------------------------------

让操作系统能够显示图形是一个有趣的目标。这可以通过在QEMU或带显示屏的开发板上写显示驱动程序来完成。这里我们主要介绍如何驱动基于QEMU的virtio-gpu虚拟显示设备。大家不用担心这个驱动实现很困难，其实它主要完成的事情就是对显示内存进行写操作而已。我们看到的图形显示屏幕其实是由一个一个的像素点来组成的，显示驱动程序的主要目标就是把每个像素点用内存单元来表示，并把代表所有这些像素点的内存区域（也称显示内存，显存， frame buffer）“通知”显示I/O控制器（也称图形适配器，graphics adapter），然后显示I/O控制器会根据内存内容渲染到图形显示屏上。这里我们以Rust语言为例，给出virtio-gpu设备驱动程序的设计与实现。主要包括如下内容：

- virtio-gpu设备的关键数据结构
- 初始化virtio-blk设备
- 操作系统对接virtio-gpu设备初始化
- virtio-gpu设备的I/O操作
- 操作系统对接virtio-gpu设备I/O操作


virtio-gpu设备的关键数据结构
------------------------------------------

.. code-block:: Rust
   :linenos:
   
   // virtio-drivers/src/gpu.rs
    pub struct VirtIOGpu<'a, H: Hal> {
        header: &'static mut VirtIOHeader,
        /// 显示区域的分辨率
        rect: Rect,
        /// 显示内存frame buffer
        frame_buffer_dma: Option<DMA<H>>,
        /// 光标图像内存cursor image buffer.
        cursor_buffer_dma: Option<DMA<H>>,
        /// Queue for sending control commands.
        control_queue: VirtQueue<'a, H>,
        /// Queue for sending cursor commands.
        cursor_queue: VirtQueue<'a, H>,
        /// Queue buffer
        queue_buf_dma: DMA<H>,
        /// Send buffer for queue.
        queue_buf_send: &'a mut [u8],
        /// Recv buffer for queue.
        queue_buf_recv: &'a mut [u8],
    }

``header`` 成员对应的 ``VirtIOHeader`` 数据结构是virtio设备的共有属性，包括版本号、设备id、设备特征等信息，其内存布局和成员变量的含义与本章前述的 :ref:`virt-mmio设备的寄存器内存布局 <term-virtio-mmio-regs>` 是一致的。而 :ref:`VirtQueue数据结构的内存布局<term-virtqueue-struct>` 和 :ref:`virtqueue的含义 <term-virtqueue>` 与本章前述内容一致。与 :ref:`具体操作系统相关的服务函数接口Hal<term-virtio-hal>` 在上一节已经介绍过，这里不再赘述。

显示内存区域 ``frame_buffer_dma`` 是一块要由操作系统或运行时分配的显示内存，当把表示像素点的值就写入这个区域后，virtio-gpu设备会在Qemu虚拟的显示器上显示出图形。光标图像内存区域 ``cursor_buffer_dma`` 用于存放光标图像的数据，当光标图像数据更新后，virtio-gpu设备会在Qemu虚拟的显示器上显示出光标图像。这两块区域与  ``queue_buf_dma`` 区域都是用于与I/O设备进行数据传输的 :ref:`DMA内存<term-dma-tech>`，都由操作系统进行分配等管理。所以在 ``virtio_drivers`` 中建立了对应的 ``DMA`` 结构，用于操作系统管理这些DMA内存。


.. code-block:: Rust
   :linenos:
   
   // virtio-drivers/src/gpu.rs
    pub struct DMA<H: Hal> {
        paddr: usize,  // DMA内存起始物理地址
        pages: usize,  // DMA内存所占物理页数量
        ...
    }
    impl<H: Hal> DMA<H> {
        pub fn new(pages: usize) -> Result<Self> {
            //操作系统分配 pages*页大小的DMA内存
            let paddr = H::dma_alloc(pages);
            ...
        }
        // DMA内存的物理地址
        pub fn paddr(&self) -> usize {
            self.paddr
        }
        // DMA内存的虚拟地址
        pub fn vaddr(&self) -> usize {
            H::phys_to_virt(self.paddr)
        }
        // DMA内存的物理页帧号
        pub fn pfn(&self) -> u32 {
            (self.paddr >> 12) as u32
        }
        // 把DMA内存转为便于Rust处理的可变一维数组切片
        pub unsafe fn as_buf(&self) -> &'static mut [u8] {
            core::slice::from_raw_parts_mut(self.vaddr() as _, PAGE_SIZE * self.pages as usize)
        ...
    impl<H: Hal> Drop for DMA<H> {
        // 操作系统释放DMA内存
        fn drop(&mut self) {
            let err = H::dma_dealloc(self.paddr as usize, self.pages as usize);
            ...


virtio-gpu驱动程序与virtio-gpu设备之间通过两个 virtqueue 来进行交互访问，``control_queue`` 用于驱动程序发送显示相关控制命令（如设置显示内存的起始地址等）给virtio-gpu设备， ``cursor_queue`` 用于驱动程序给给virtio-gpu设备发送显示鼠标更新的相关控制命令。 ``queue_buf_dma`` 是存放控制命令和返回结果的内存， ``queue_buf_send`` 和 ``queue_buf_recv`` 是 ``queue_buf_dma`` DMA内存的可变一维数组切片形式，分别用于虚拟队列的接收与发送。

初始化virtio-gpu设备
------------------------------------------

在 ``virtio-drivers`` crate的 ``examples\riscv\src\main.rs`` 文件中的 ``virtio_probe`` 函数识别出virtio-gpu设备后，会调用 ``virtio_gpu(header)`` 函数来完成对virtio-gpu设备的初始化过程。virtio-gpu设备初始化的工作主要是查询显示设备的信息（如分辨率等），并将该信息用于初始显示扫描（scanout）设置。下面的命令可以看到虚拟GPU的创建和识别过程：

.. code-block:: shell
   :linenos:

   # 在virtio-drivers仓库的example/riscv目录下执行如下命令
   make run 
   ## 通过 qemu-system-riscv64 命令启动 Qemu 模拟器，创建 virtio-gpu 设备   
   qemu-system-riscv64 \
        -device virtio-gpu-device ...
   ## 可以看到设备驱动查找到的virtio-gpu设备色信息
   ...
   [ INFO] Detected virtio MMIO device with vendor id 0x554D4551, device type GPU, version Modern
   [ INFO] Device features EDID | RING_INDIRECT_DESC | RING_EVENT_IDX | VERSION_1
   [ INFO] events_read: 0x0, num_scanouts: 0x1
   [ INFO] GPU resolution is 1280x800
   [ INFO] => RespDisplayInfo { header: CtrlHeader { hdr_type: OkDisplayInfo, flags: 0, fence_id: 0, ctx_id: 0, _padding: 0 }, rect: Rect { x: 0, y: 0, width: 1280, height: 800 }, enabled: 1, flags: 0 }


并看到Qemu输出的图形显示：

.. image:: virtio-test-example2.png
    :align: center
    :scale: 30 %
    :name: virtio-test-example2

接下来我们看看virtio-gpu设备初始化的具体过程如：

.. code-block:: Rust
   :linenos:

    // virtio-drivers/examples/riscv/src/main.rs
    fn virtio_gpu(header: &'static mut VirtIOHeader) {
        let mut gpu = VirtIOGpu::<HalImpl>::new(header).expect("failed to create gpu driver");
        let (width, height) = gpu.resolution().expect("failed to get resolution");
        info!("GPU resolution is {}x{}", width, height);
        let fb = gpu.setup_framebuffer().expect("failed to get fb");
        ...

在 ``virtio_gpu`` 函数调用创建了 ``VirtIOGpu::<HalImpl>::new(header)`` 函数，获得关于virtio-gpu设备的重要信息：显示分辨率 ``1280x800`` ；而且会建立virtio虚拟队列，并基于这些信息来创建表示virtio-gpu的 ``gpu`` 结构。然后会进一步调用 ``gpu.setup_framebuffer()`` 函数来建立和配置显示内存缓冲区，打通设备驱动与virtio-gpu设备间的显示数据传输通道。


``VirtIOGpu::<HalImpl>::new(header)`` 函数主要完成了virtio-gpu设备的初始化工作：

.. code-block:: Rust
   :linenos:

   // virtio-drivers/src/gpu.rs
   impl VirtIOGpu<'_, H> {
   pub fn new(header: &'static mut VirtIOHeader) -> Result<Self> {
        header.begin_init(|features| {
            let features = Features::from_bits_truncate(features);
            let supported_features = Features::empty();
            (features & supported_features).bits()
        });

        // read configuration space
        let config = unsafe { &mut *(header.config_space() as *mut Config) };

        let control_queue = VirtQueue::new(header, QUEUE_TRANSMIT, 2)?;
        let cursor_queue = VirtQueue::new(header, QUEUE_CURSOR, 2)?;

        let queue_buf_dma = DMA::new(2)?;
        let queue_buf_send = unsafe { &mut queue_buf_dma.as_buf()[..PAGE_SIZE] };
        let queue_buf_recv = unsafe { &mut queue_buf_dma.as_buf()[PAGE_SIZE..] };

        header.finish_init();

        Ok(VirtIOGpu {
            header,
            frame_buffer_dma: None,
            rect: Rect::default(),
            control_queue,
            cursor_queue,
            queue_buf_dma,
            queue_buf_send,
            queue_buf_recv,
        })
    }

首先是 ``header.begin_init`` 函数完成了对virtio设备的共性初始化的常规步骤的前六步；第七步在这里被忽略；第八步读取virtio-gpu设备的配置空间（config space）信息；紧接着是创建两个虚拟队列：控制命令队列、光标管理队列。并为控制命令队列分配两个 page （8KB）的内存空间用于放置虚拟队列中的控制命令和返回结果；最后的第九步，调用 ``header.finish_init`` 函数，将virtio-gpu设备设置为活跃可用状态。

虽然virtio-gpu初始化完毕，但它目前还不能进行显示。为了能够进行正常的显示，我们还需建立显存区域 frame buffer，并绑定在virtio-gpu设备上。这主要是通过 ``VirtIOGpu.setup_framebuffer`` 函数来完成的。

.. code-block:: Rust
   :linenos:

   // virtio-drivers/src/gpu.rs
   pub fn setup_framebuffer(&mut self) -> Result<&mut [u8]> {
        // get display info
        let display_info: RespDisplayInfo =
            self.request(CtrlHeader::with_type(Command::GetDisplayInfo))?;
        display_info.header.check_type(Command::OkDisplayInfo)?;
        self.rect = display_info.rect;

        // create resource 2d
        let rsp: CtrlHeader = self.request(ResourceCreate2D {
            header: CtrlHeader::with_type(Command::ResourceCreate2d),
            resource_id: RESOURCE_ID,
            format: Format::B8G8R8A8UNORM,
            width: display_info.rect.width,
            height: display_info.rect.height,
        })?;
        rsp.check_type(Command::OkNodata)?;

        // alloc continuous pages for the frame buffer
        let size = display_info.rect.width * display_info.rect.height * 4;
        let frame_buffer_dma = DMA::new(pages(size as usize))?;

        // resource_attach_backing
        let rsp: CtrlHeader = self.request(ResourceAttachBacking {
            header: CtrlHeader::with_type(Command::ResourceAttachBacking),
            resource_id: RESOURCE_ID,
            nr_entries: 1,
            addr: frame_buffer_dma.paddr() as u64,
            length: size,
            padding: 0,
        })?;
        rsp.check_type(Command::OkNodata)?;

        // map frame buffer to screen
        let rsp: CtrlHeader = self.request(SetScanout {
            header: CtrlHeader::with_type(Command::SetScanout),
            rect: display_info.rect,
            scanout_id: 0,
            resource_id: RESOURCE_ID,
        })?;
        rsp.check_type(Command::OkNodata)?;

        let buf = unsafe { frame_buffer_dma.as_buf() };
        self.frame_buffer_dma = Some(frame_buffer_dma);
        Ok(buf)
    }


上面的函数主要完成的工作有如下几个步骤，其实就是驱动程序给virtio-gpu设备发控制命令，建立好显存区域：

1. 发出 ``GetDisplayInfo`` 命令，获得virtio-gpu设备的显示分辨率;
2. 发出 ``ResourceCreate2D`` 命令，让设备以分辨率大小（ ``width *height`` ），像素信息（ ``Red/Green/Blue/Alpha`` 各占1字节大小，即一个像素占4字节），来配置设备显示资源；
3. 分配 ``width *height * 4`` 字节的连续物理内存空间作为显存， 发出 ``ResourceAttachBacking`` 命令，让设备把显存附加到设备显示资源上；
4. 发出 ``SetScanout`` 命令，把设备显示资源链接到显示扫描输出上，这样才能让显存的像素信息显示出来；

到这一步，才算是把virtio-gpu设备初始化完成了。做完这一步后，virtio-gpu设备和设备驱动之间的虚拟队列接口就打通了，显示缓冲区也建立好了，就可以进行显存数据读写了。

virtio-gpu设备的I/O操作
------------------------------------------

对初始化好的virtio-gpu设备进行图形显示其实很简单，主要就是两个步骤：

1. 把要显示的像素数据写入到显存中；
2. 发出刷新命令，让virtio-gpu在Qemu模拟的显示区上显示图形。

下面简单代码完成了对虚拟GPU的图形显示：

.. code-block:: Rust
   :linenos:

   // virtio-drivers/src/gpu.rs
   fn virtio_gpu(header: &'static mut VirtIOHeader) {
        ...
        //把像素数据写入显存
        for y in 0..height {    //height=800
            for x in 0..width { //width=1280
                let idx = (y * width + x) * 4;
                fb[idx] = x as u8;
                fb[idx + 1] = y as u8;
                fb[idx + 2] = (x + y) as u8;
            }
        }
        // 发出刷新命令
        gpu.flush().expect("failed to flush");

这里需要注意的是对virtio-gpu进行刷新操作比较耗时，所以我们尽量先把显示的图形像素值都写入显存中，再发出刷新命令，减少刷新命令的执行次数。


操作系统对接virtio-gpu设备初始化
------------------------------------------


操作系统对接virtio-gpu设备I/O处理
------------------------------------------