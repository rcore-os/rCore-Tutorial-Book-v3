virtio_gpu设备驱动程序
=========================================

本节导读
-----------------------------------------

本节主要介绍了与操作系统无关的基本virtio_gpu设备驱动程序的设计与实现，以及如何在操作系统中封装virtio_gpu设备驱动程序，实现对丰富多彩的GUI app的支持。




virtio-gpu驱动程序
------------------------------------------

让操作系统能够显示图形是一个有趣的目标。这可以通过在QEMU或带显示屏的开发板上写显示驱动程序来完成。这里我们主要介绍如何驱动基于QEMU的virtio-gpu虚拟显示设备。大家不用担心这个驱动实现很困难，其实它主要完成的事情就是对显示内存进行写操作而已。我们看到的图形显示屏幕其实是由一个一个的像素点来组成的，显示驱动程序的主要目标就是把每个像素点用内存单元来表示，并把代表所有这些像素点的内存区域（也称显示内存，显存， frame buffer）“通知”显示I/O控制器（也称图形适配器，graphics adapter），然后显示I/O控制器会根据内存内容渲染到图形显示屏上。这里我们以Rust语言为例，给出virtio-gpu设备驱动程序的设计与实现。主要包括如下内容：

- virtio-gpu设备的关键数据结构
- 初始化virtio-gpu设备
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

在 ``virtio-drivers`` crate的 ``examples/riscv/src/main.rs`` 文件中的 ``virtio_probe`` 函数识别出virtio-gpu设备后，会调用 ``virtio_gpu(header)`` 函数来完成对virtio-gpu设备的初始化过程。virtio-gpu设备初始化的工作主要是查询显示设备的信息（如分辨率等），并将该信息用于初始显示扫描（scanout）设置。下面的命令可以看到虚拟GPU的创建和识别过程：

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

.. _term-virtio-driver-gpu-new:

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

.. _term-virtio-driver-gpu-setupfb:

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

虽然virtio-gpu设备驱动程序已经完成了，但是还需要操作系统对接virtio-gpu设备，才能真正的把virtio-gpu设备驱动程序和操作系统对接起来。这里以侏罗猎龙操作系统 --Device OS 为例，来介绍virtio-gpu设备在操作系统中的初始化过程。其初始化过程主要包括：

1. 调用virtio-drivers/gpu.rs中提供 ``VirtIOGpu::new()`` 方法，初始化virtio_gpu设备；
2. 建立显存缓冲区的可变一维数组引用，便于后续写显存来显示图形；
3. 建立显示窗口中的光标图形；
4. 设定表示virtio_gpu设备的全局变量。



先看看操作系统需要建立的表示virtio_gpu设备的全局变量 ``GPU_DEVICE`` ：

.. code-block:: Rust
   :linenos:

    // os/src/drivers/gpu/mod.rs
    pub trait GpuDevice: Send + Sync + Any {
        fn update_cursor(&self); //更新光标，目前暂时没用
        fn get_framebuffer(&self) -> &mut [u8];
        fn flush(&self);
    }
    pub struct VirtIOGpuWrapper {
        gpu: UPIntrFreeCell<VirtIOGpu<'static, VirtioHal>>,
        fb: &'static [u8],
    }
    lazy_static::lazy_static!(
        pub static ref GPU_DEVICE: Arc<dyn GpuDevice> = Arc::new(VirtIOGpuWrapper::new());
    );


从上面的代码可以看到，操作系统中表示表示virtio_gpu设备的全局变量 ``GPU_DEVICE`` 的类型是 ``VirtIOGpuWrapper`` ,封装了来自virtio_derivers 模块的 ``VirtIOGpu`` 类型，以及一维字节数组引用表示的显存缓冲区 ``fb`` 。这样，操作系统内核就可以通过 ``GPU_DEVICE`` 全局变量来访问gpu_blk设备了。而操作系统对virtio_blk设备的初始化就是调用 ``VirtIOGpuWrapper::<VirtioHal>::new()`` 。


当用户态应用程序要进行图形显示时，至少需要得到操作系统的两个基本图形显示服务。一个是得到显存在用户态可访问的的内存地址，这样应用程序可以在用户态把表示图形的像素值写入显存中；第二个是给virtio-gpu设备发出 ``flush`` 刷新指令，这样virtio-gpu设备能够更新显示器中的图形显示内容。

为此，操作系统在 ``VirtIOGpuWrapper`` 结构类型中需要实现 ``GpuDevice`` trait，该 trait需要实现两个函数来支持应用程序所需要的基本显示服务：

.. code-block:: Rust
   :linenos:

    impl GpuDevice for VirtIOGpuWrapper {
        // 通知virtio-gpu设备更新图形显示内容
        fn flush(&self) {
            self.gpu.exclusive_access().flush().unwrap();
        }
        // 得到显存的基于内核态虚地址的一维字节数组引用
        fn get_framebuffer(&self) -> &mut [u8] {
            unsafe {
                let ptr = self.fb.as_ptr() as *const _ as *mut u8;
                core::slice::from_raw_parts_mut(ptr, self.fb.len())
            }
        }
    ...

接下来，看一下操作系统对virtio-gpu设备的初始化过程：

.. code-block:: Rust
   :linenos:

    // os/src/drivers/gpu/mod.rs
    impl VirtIOGpuWrapper {
        pub fn new() -> Self {
            unsafe {
                // 1. 执行virtio-drivers的gpu.rs中virto-gpu基本初始化
                let mut virtio =
                    VirtIOGpu::<VirtioHal>::new(&mut *(VIRTIO7 as *mut VirtIOHeader)).unwrap();
                // 2. 设置virtio-gpu设备的显存，初始化显存的一维字节数组引用    
                let fbuffer = virtio.setup_framebuffer().unwrap();
                let len = fbuffer.len();
                let ptr = fbuffer.as_mut_ptr();
                let fb = core::slice::from_raw_parts_mut(ptr, len);
                // 3. 初始化光标图像的像素值
                let bmp = Bmp::<Rgb888>::from_slice(BMP_DATA).unwrap();
                let raw = bmp.as_raw();
                let mut b = Vec::new();
                for i in raw.image_data().chunks(3) {
                    let mut v = i.to_vec();
                    b.append(&mut v);
                    if i == [255, 255, 255] {
                        b.push(0x0)
                    } else {
                        b.push(0xff)
                    }
                }
                // 4. 设置virtio-gpu设备的光标图像
                virtio.setup_cursor(b.as_slice(), 50, 50, 50, 50).unwrap();
                // 5. 返回VirtIOGpuWrapper结构类型
                Self {
                    gpu: UPIntrFreeCell::new(virtio),
                    fb,
                }
        ...

在上述初始化过程中，我们先看到 ``VIRTIO7`` ，这是 Qemu模拟的virtio_gpu设备中I/O寄存器的物理内存地址， ``VirtIOGpu`` 需要这个地址来对 ``VirtIOHeader`` 数据结构所表示的virtio-gpu I/O控制寄存器进行读写操作，从而完成对某个具体的virtio-gpu设备的初始化过程。整个初始化过程的步骤如下：

1. 执行virtio-drivers的gpu.rs中virto-gpu基本初始化
2. 设置virtio-gpu设备的显存，初始化显存的一维字节数组引用
3. （可选）初始化光标图像的像素值
4. （可选）设置virtio-gpu设备的光标图像
5. 返回VirtIOGpuWrapper结构类型

上述步骤的第一步  :ref:`"virto-gpu基本初始化"<term-virtio-driver-gpu-new>` 和第二步 :ref:`设置显存<term-virtio-driver-gpu-setupfb>` 是核心内容，都由 virtio-drivers中与具体操作系统无关的virtio-gpu裸机驱动实现，极大降低本章从操作系统的代码复杂性。至此，我们已经完成了操作系统对 virtio-gpu设备的初始化过程，接下来，我们看一下操作系统对virtio-gpu设备的I/O处理过程。

操作系统对接virtio-gpu设备I/O处理
------------------------------------------

操作系统的virtio-gpu驱动的主要功能是给操作系统提供支持，让运行在用户态应用能够显示图形。为此，应用程序需要知道可读写的显存在哪里，并能把更新的像素值写入显存。另外还需要能够通知virtio-gpu设备更新显示内容。可以看出，这主要与操作系统的进程管理和虚存管理有直接的关系。

在操作系统与virtio-drivers crate中virtio-gpu裸机驱动对接的过程中，需要注意的关键问题是操作系统的virtio-gpu驱动如何封装virtio-blk裸机驱动的基本功能，完成如下服务：

1. 根据virtio-gpu裸机驱动提供的显存信息，建立应用程序访问的用户态显存地址空间；
2. 实现系统调用，把用户态显存地址空间的基址和范围发给应用程序；
3. 实现系统调用，把更新显存的命令发给virtio-gpu设备。

这里我们还是做了一些简化，即应用程序预先知道了virtio-blk的显示分辨率为 ``1280x800`` ，采用的是R/G/B/Alpha 像素显示，即一个像素点占用4个字节。这样整个显存大小为 ``1280x800x4=4096000`` 字节，即大约4000KB，近4MB。

我们先看看图形应用程序所需要的两个系统调用：

.. code-block:: Rust
   :linenos:

    // os/src/syscall/mod.rs
    const SYSCALL_FRAMEBUFFER: usize = 2000;
    const SYSCALL_FRAMEBUFFER_FLUSH: usize = 2001;
    // os/src/syscall/gui.rs
    // 显存的用户态起始虚拟地址
    const FB_VADDR: usize = 0x10000000;
    pub fn sys_framebuffer() -> isize {
        // 获得显存的起始物理页帧和结束物理页帧
        let gpu = GPU_DEVICE.clone();
        let fb = gpu.get_framebuffer();
        let len = fb.len();
        let fb_ppn = PhysAddr::from(fb.as_ptr() as usize).floor();
        let fb_end_ppn = PhysAddr::from(fb.as_ptr() as usize + len).ceil();
        // 获取当前进程的地址空间结构 mem_set
        let current_process = current_process();
        let mut inner = current_process.inner_exclusive_access();
        let mem_set = &mut inner.memory_set;
        // 把显存的物理页帧映射到起始地址为FB_VADDR的用户态虚拟地址空间
        mem_set.push_noalloc(
            MapArea::new(
                (FB_VADDR as usize).into(),
                (FB_VADDR + len as usize).into(),
                MapType::Framed,
                MapPermission::R | MapPermission::W | MapPermission::U,
            ),
            PPNRange::new(fb_ppn, fb_end_ppn),
        );
        // 返回起始地址为FB_VADDR
        FB_VADDR as isize
    }
    // 要求virtio-gpu设备刷新图形显示
    pub fn sys_framebuffer_flush() -> isize {
        let gpu = GPU_DEVICE.clone();
        gpu.flush();
        0
    }

有了这两个系统调用，就可以很容易建立图形应用程序了。下面这个应用程序，可以在Qemu模拟的屏幕上显示一个彩色的矩形。

.. code-block:: Rust
   :linenos:

   // user/src/bin/gui_simple.rs
   pub const VIRTGPU_XRES: usize = 1280; // 显示分辨率的宽度
   pub const VIRTGPU_YRES: usize = 800;  // 显示分辨率的高度
   pub fn main() -> i32 {
        // 访问sys_framebuffer系统调用，获得显存基址
        let fb_ptr =framebuffer() as *mut u8;
        // 把显存转换为一维字节数组
        let fb= unsafe {core::slice::from_raw_parts_mut(fb_ptr as *mut u8, VIRTGPU_XRES*VIRTGPU_YRES*4 as usize)};
        // 更新显存的像素值
        for y in 0..800 {
            for x in 0..1280 {
                let idx = (y * 1280 + x) * 4;
                fb[idx] = x as u8;
                fb[idx + 1] = y as u8;
                fb[idx + 2] = (x + y) as u8;
            }
        }
        // 访问sys_framebuffer_flush系统调用，要求virtio-gpu设备刷新图形显示
        framebuffer_flush();
        0
   }


到目前为止，看到的操作系统支持工作还是比较简单的，但其实我们还没分析如何给应用程序提供显存虚拟地址空间的。以前章节的操作系统支持应用程序的 :ref:`用户态地址空间<term-vm-app-addr-space>` ，都是在创建应用程序对应进程的初始化过程中建立，涉及不少工作，具体包括：

- 分配空闲 :ref:`物理页帧<term-manage-phys-frame>`
- 建立 :ref:`进程地址空间(Address Space)<term-vm-memory-set>` 中的 :ref:`逻辑段（MemArea）<term-vm-map-area>` 
- 建立映射物理页帧和虚拟页的 :ref:`页表<term-create-pagetable>` 

目前这些工作不能直接支持建立用户态显存地址空间。主要原因在于，用户态显存的物理页帧分配和物理虚地址页表映射，都是由virtio-gpu裸机设备驱动程序在设备初始化时完成。在图形应用进程的创建过程中，不需要再分配显存的物理页帧了，只需建立显存的用户态虚拟地址空间。

为了支持操作系统把用户态显存地址空间的基址发给应用程序，需要对操作系统的虚拟内存管理进行一定的扩展， 即实现 ``sys_framebuffer`` 系统调用中访问的 ``mem_set.push_noalloc`` 新函数和其它相关函数。


.. code-block:: Rust
   :linenos:

   // os/src/mm/memory_set.rs
   impl MemorySet {
     pub fn push_noalloc(&mut self, mut map_area: MapArea, ppn_range: PPNRange) {
        map_area.map_noalloc(&mut self.page_table, ppn_range);
        self.areas.push(map_area);
     }      
   impl MapArea {
     pub fn map_noalloc(&mut self, page_table: &mut PageTable,ppn_range:PPNRange) {
        for (vpn,ppn) in core::iter::zip(self.vpn_range,ppn_range) {
            self.data_frames.insert(vpn, FrameTracker::new_noalloc(ppn));
            let pte_flags = PTEFlags::from_bits(self.map_perm.bits).unwrap();
            page_table.map(vpn, ppn, pte_flags);
        }
     }
   // os/src/mm/frame_allocator.rs 
   pub struct FrameTracker {
     pub ppn: PhysPageNum,
     pub nodrop: bool,
   }
   impl FrameTracker {
     pub fn new_nowrite(ppn: PhysPageNum) -> Self {
        Self { ppn, nodrop: true }
     }
   impl Drop for FrameTracker {
        fn drop(&mut self) {
            if self.nodrop {
                return;
            }
            frame_dealloc(self.ppn);
        }
   }


这样，就可以实现把某一块已分配的物理页帧映射到进程的用户态虚拟地址空间，并且在进程退出是否地址空间的物理页帧时，不会把显存的物理页帧给释放掉。


图形化应用程序设计
----------------------------------------

现在操作系统有了显示的彩色图形显示功能，也有通过串口接收输入的功能，我们就可以设计更加丰富多彩的应用了。这里简单介绍一个 ``贪吃蛇`` 图形小游戏的设计。

.. note:: 
    
   "贪吃蛇"游戏简介

   游戏中的元素主要有蛇和食物组成，蛇的身体是由若干个格子组成的，初始化时蛇的身体只有一格，吃了食物后会增长。食物也是一个格子，代表食物的格子位置随机产生。游戏的主要运行逻辑是，蛇可以移动，通过用户输入的字母 ``asdw`` 的控制蛇的上下左右移动的方向。用户通过移动贪吃蛇，并与食物格子位置重合，来增加蛇的身体长度。用户输入回车键时，游戏结束。

为了简化设计，我们移植了 ``embedded-graphics`` 嵌入式图形库 [#EMBEDGRAPH]_ 到侏罗猎龙操作系统中，并修改了一个基于此图形库的Linux图形应用 -- embedded-snake-rs [#SNAKEGAME]_ ，让它在侏罗猎龙操作系统中能够运行。


移植 ``embedded-graphics`` 嵌入式图形库
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

``embedded-graphics`` 嵌入式图形库给出了很详细的移植说明， 主要是实现 ``embedded_graphics_core::draw_target::DrawTarget`` trait中的函数接口 ``fn draw_iter<I>(&mut self, pixels: I)`` 。为此需要为图形应用建立一个能够表示显存、像素点特征和显示区域的数据结构 ``Display`` 和创建函数 ``new()`` ：


.. code-block:: Rust
    :linenos:

    pub struct Display {
        pub size: Size,
        pub point: Point,
        pub fb: &'static mut [u8],
    }
    impl Display {
        pub fn new(size: Size, point: Point) -> Self {
            let fb_ptr = framebuffer() as *mut u8;
            println!(
                "Hello world from user mode program! 0x{:X} , len {}",
                fb_ptr as usize, VIRTGPU_LEN
            );
            let fb =
                unsafe { core::slice::from_raw_parts_mut(fb_ptr as *mut u8, VIRTGPU_LEN as usize) };
            Self { size, point, fb }
        }
    }

在这个 ``Display`` 结构的基础上，我们就可以实现 ``DrawTarget`` trait 要求的函数：

.. code-block:: Rust
    :linenos:

    impl OriginDimensions for Display {
        fn size(&self) -> Size {
            self.size
        }
    }

    impl DrawTarget for Display {
        type Color = Rgb888;
        type Error = core::convert::Infallible;

        fn draw_iter<I>(&mut self, pixels: I) -> Result<(), Self::Error>
        where
            I: IntoIterator<Item = embedded_graphics::Pixel<Self::Color>>,
        {
            pixels.into_iter().for_each(|px| {
                let idx = ((self.point.y + px.0.y) * VIRTGPU_XRES as i32 + self.point.x + px.0.x)
                    as usize
                    * 4;
                if idx + 2 >= self.fb.len() {
                    return;
                }
                self.fb[idx] = px.1.b();
                self.fb[idx + 1] = px.1.g();
                self.fb[idx + 2] = px.1.r();
            });
            framebuffer_flush();
            Ok(())
        }
    }


上述的 ``draw_iter()`` 函数实现了对一个由像素元素组成的显示区域的绘制迭代器，将迭代器中的像素元素绘制到 ``Display`` 结构中的显存中，并调用 ``framebuffer_flush()`` 函数将显存中的内容刷新到屏幕上。这样， ``embedded-graphics`` 嵌入式图形库在侏罗猎龙操作系统的移植任务就完成了。


实现贪吃蛇游戏图形应用
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

``embedded-snake-rs`` 的具体实现大约有200多行代码，提供了一系列的数据结构，主要的数据结构（包含相关方法实现）包括：

- ``ScaledDisplay`` ：封装了 ``Dislpay`` 并支持显示大小可缩放的方块
- ``Food`` ：会在随机位置产生并定期消失的"食物"方块
- ``Snake`` : "贪吃蛇"方块，长度由一系列的方块组成，可以通过键盘控制方向，碰到食物会增长
- ``SnakeGame`` ：食物和贪吃蛇的游戏显示配置和游戏状态

有了上述事先准备的数据结构，我们就可以实现贪吃蛇游戏的主体逻辑了。


.. code-block:: Rust
    :linenos:

    pub fn main() -> i32 {
        // 创建具有virtio-gpu设备显示内存虚地址的Display结构
        let mut disp = Display::new(Size::new(1280, 800), Point::new(0, 0));
        // 初始化游戏显示元素的配置：红色的蛇、黄色的食物，方格大小为20个像素点
        let mut game = SnakeGame::<20, Rgb888>::new(1280, 800, 20, 20, Rgb888::RED, Rgb888::YELLOW, 50);
        // 清屏
        let _ = disp.clear(Rgb888::BLACK).unwrap();
        // 启动游戏循环
        loop {
            if key_pressed() {
                let c = getchar();
                match c {
                    LF => break,
                    CR => break,
                    // 调整蛇行进方向
                    b'w' => game.set_direction(Direction::Up),
                    b's' => game.set_direction(Direction::Down),
                    b'a' => game.set_direction(Direction::Left),
                    b'd' => game.set_direction(Direction::Right),
                    _ => (),
                }
            }
            //绘制游戏界面
            let _ = disp.clear(Rgb888::BLACK).unwrap();
            game.draw(&mut disp);
            //暂停一小会
            sleep(10);
        }
        0
    }

这里看到，为了判断通过串口输入的用户是否按键，我们扩展了一个系统调用 ``sys_key_pressed`` ：

.. code-block:: Rust
    :linenos:

    // os/src/syscall/input.rs
    pub fn sys_key_pressed()  -> isize {
        let res =!UART.read_buffer_is_empty();
        if res {
            1
        } else {
            0
        }    
    }


这样，我们结合串口和 ``virtio-gpu`` 两种外设，并充分利用已有的Rust库，设计实现了一个 ``贪吃蛇`` 小游戏（如下图所示）。至此，基于侏罗猎龙操作系统的图形应用开发任务就完成了。

.. image:: ../../os-lectures/lec13/figs/gui-snake.png
   :align: center
   :scale: 30 %
   :name: gui-snake

.. [#EMBEDGRAPH] https://github.com/embedded-graphics/embedded-graphics
.. [#SNAKEGAME] https://github.com/libesz/embedded-snake-rs