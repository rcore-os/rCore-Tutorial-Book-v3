virtio_gpu设备驱动程序
=========================================

本节导读
-----------------------------------------

本节主要介绍了QEMU模拟的RISC-V计算机中的virtio设备的架构和重要组成部分，以及面向virtio设备的驱动程序主要功能；并对virtio-blk设备及其驱动程序，virtio-gpu设备及其驱动程序进行了比较深入的分析。这里选择virtio设备来进行介绍，主要考虑基于两点考虑，首先这些设备就是QEMU模拟的高性能物理外设，操作系统可以面向这些设备编写出合理的驱动程序（如Linux等操作系统中都有virtio设备的驱动程序，并被广泛应用于云计算虚拟化场景中。）；其次，各种类型的virtio设备，如块设备（virtio-blk）、网络设备（virtio-net）、键盘鼠标类设备（virtio-input）、显示设备（virtio-gpu）具有对应外设类型的共性特征、专有特征和与具体处理器无关的设备抽象性。通过对这些设备的分析和比较，能够比较快速地掌握各类设备的核心特点，并掌握编写裸机或操作系统驱动程序的关键技术。



virtio-gpu驱动程序
------------------------------------------

让操作系统能够显示图形是一个有趣的目标。这可以通过在QEMU或带显示屏的开发板上写显示驱动程序来完成。这里我们主要介绍如何驱动基于QEMU的virtio-gpu虚拟显示设备。大家不用担心这个驱动实现很困难，其实它主要完成的事情就是对显示内存进行写操作而已。我们看到的图形显示屏幕其实是由一个一个的像素点来组成的，显示驱动程序的主要目标就是把每个像素点用内存单元来表示，并把代表所有这些像素点的内存区域（也称显示内存，显存， frame buffer）“通知”显示I/O控制器（也称图形适配器，graphics adapter），然后显示I/O控制器会根据内存内容渲染到图形显示屏上。

virtio-gpu设备的关键数据结构
------------------------------------------

.. code-block:: Rust
   :linenos:
   
   pub struct VirtIOGpu<'a> {
      header: &'static mut VirtIOHeader, 
      rect: Rect,
      /// DMA area of frame buffer.
      frame_buffer_dma: Option<DMA>, 
      /// Queue for sending control commands.
      control_queue: VirtQueue<'a>,
      /// Queue for sending cursor commands.
      cursor_queue: VirtQueue<'a>,
      /// Queue buffer DMA
      queue_buf_dma: DMA,
      /// Send buffer for queue.
      queue_buf_send: &'a mut [u8],
      /// Recv buffer for queue.
      queue_buf_recv: &'a mut [u8],
   }

``header`` 结构是virtio设备的共有属性，包括版本号、设备id、设备特征等信息。显存区域 ``frame_buffer_dma`` 是一块要由操作系统或运行时分配的内存，后续的像素点的值就会写在这个区域中。virtio-gpu驱动程序与virtio-gpu设备之间通过两个 virtqueue 来进行交互访问，``control_queue`` 用于驱动程序发送显示相关控制命令， ``cursor_queue`` 用于驱动程序发送显示鼠标更新的相关控制命令（这里暂时不用）。 ``queue_buf_dma`` 是存放控制命令和返回结果的内存， ``queue_buf_send`` 和 ``queue_buf_recv`` 是 ``queue_buf_dma`` 的切片。

初始化virtio-gpu设备
------------------------------------------

在 ``virtio-drivers`` crate的 ``examples\riscv\src\main.rs`` 文件中的 ``virtio_probe`` 函数识别出virtio-gpu设备后，会调用 ``virtio_gpu(header)`` 函数来完成对virtio-gpu设备的初始化过程。virtio-gpu设备初始化的工作主要是查询显示设备的信息（如分辨率等），并将该信息用于初始显示扫描（scanout）设置。具体过程如下：

.. code-block:: Rust
   :linenos:

   impl VirtIOGpu<'_> {
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

首先是 ``header.begin_init`` 函数完成了对virtio设备的共性初始化的常规步骤的前六步；第七步在这里被忽略；第八步完成对virtio-gpu设备的配置空间（config space）信息，不过这里面并没有我们关注的显示分辨率等信息；紧接着是创建两个虚拟队列，并分配两个 page （8KB）的内存空间用于放置虚拟队列中的控制命令和返回结果；最后的第九步，调用 ``header.finish_init`` 函数，将virtio-gpu设备设置为活跃可用状态。

虽然virtio-gpu初始化完毕，但它目前还不能进行显示。为了能够进行正常的显示，我们还需建立显存区域 frame buffer，并绑定在virtio-gpu设备上。这主要是通过 ``VirtIOGpu.setup_framebuffer`` 函数来完成的。

.. code-block:: Rust
   :linenos:

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

到这一步，才算是把virtio-gpu设备初始化完成了。


virtio-gpu设备的I/O操作
------------------------------------------

接下来的显示操作比较简单，就是在显存中更新像素信息，然后给设备发出刷新指令，就可以显示了，具体的示例代码如下：

.. code-block:: Rust
   :linenos:

   for y in 0..768 {
      for x in 0..1024 {
         let idx = (y * 1024 + x) * 4;
         fb[idx] = (0) as u8;       //Blue
         fb[idx + 1] = (0) as u8;   //Green
         fb[idx + 2] = (255) as u8; //Red
         fb[idx + 3] = (0) as u8;   //Alpha
       }
   }
   gpu.flush().expect("failed to flush"); 

