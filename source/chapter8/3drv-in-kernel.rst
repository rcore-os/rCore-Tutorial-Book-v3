在内核中实现设备驱动程序
=========================================

本节导读
-----------------------------------------


设备树
------------------------------------------

既然我们要实现把数据放在某个存储设备上并让操作系统来读取，首先操作系统就要有一个读取全部已接入设备信息的能力，而设备信息放在哪里又是谁帮我们来做的呢？在 RISC-V 中，这个一般是由 bootloader，即 OpenSBI or RustSBI 固件完成的。它来完成对于包括物理内存在内的各外设的扫描，将扫描结果以 **设备树二进制对象（DTB，Device Tree Blob）** 的格式保存在物理内存中的某个地方。而在我们的虚拟计算机中，QEMU会把这些信息准备好，而这个放置DTB的物理地址将放在 `a1` 寄存器中，而将会把 HART ID （**HART，Hardware Thread，硬件线程，可以理解为执行的 CPU 核**）放在 `a0` 寄存器上。

在我们之前的函数中并没有使用过这两个参数，如果要使用，我们不需要修改任何入口汇编的代码，只需要给 `rust_main` 函数增加两个参数即可：

.. code-block:: Rust

   #[no_mangle]
   extern "C" fn main(_hartid: usize, device_tree_paddr: usize) {
      ...
      init_dt(device_tree_paddr);
      ...
   }

上面提到 OpenSBI 固件会把设备信息以设备树的格式放在某个地址上，哪设备树格式究竟是怎样的呢？在各种操作系统中，我们打开设备管理器（Windows）和系统报告（macOS）等内置的系统软件就可以看到我们使用的电脑的设备树，一个典型的设备树如下图所示：

.. image:: device-tree.png
   :align: center
   :name: device-tree

每个设备在物理上连接到了父设备上最后再通过总线等连接起来构成一整个设备树，在每个节点上都描述了对应设备的信息，如支持的协议是什么类型等等。而操作系统就是通过这些节点上的信息来实现对设备的识别的。   

**[info] 设备节点属性**

具体而言，一个设备节点上会有几个标准属性，这里简要介绍我们需要用到的几个：

  - compatible：该属性指的是该设备的编程模型，一般格式为 "manufacturer,model"，分别指一个出厂标签和具体模型。如 "virtio,mmio" 指的是这个设备通过 virtio 协议、MMIO（内存映射 I/O）方式来驱动
  - model：指的是设备生产商给设备的型号
  - reg：当一些很长的信息或者数据无法用其他标准属性来定义时，可以用 reg 段来自定义存储一些信息

设备树是一个比较复杂的标准，更多细节可以参考 `Device Tree Reference <https://elinux.org/Device_Tree_Reference>`_ 。


解析设备树
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

对于上面的属性，我们不需要自己来实现这件事情，可以直接调用 `rCore 中 device_tree 库 <https://github.com/rcore-os/device_tree-rs">`_ ，然后遍历树上节点即可：

.. code-block:: Rust

   // 遍历设备树并初始化设备
   fn init_dt(dtb: usize) {
      info!("device tree @ {:#x}", dtb);
      // 整个设备树的 Headers（用于验证和读取）
      #[repr(C)]
      struct DtbHeader {
         be_magic: u32,
         be_size: u32,
      }
      let header = unsafe { &*(dtb as *const DtbHeader) };
      // from_be 是大小端序的转换（from big endian）
      let magic = u32::from_be(header.be_magic);
      const DEVICE_TREE_MAGIC: u32 = 0xd00dfeed;
      // 验证 Device Tree Magic Number
      assert_eq!(magic, DEVICE_TREE_MAGIC);
      let size = u32::from_be(header.be_size);
      // 拷贝dtb数据
      let dtb_data = unsafe { core::slice::from_raw_parts(dtb as *const u8, size as usize) };
      // 加载dtb数据
      let dt = DeviceTree::load(dtb_data).expect("failed to parse device tree");
      // 遍历dtb数据
      walk_dt_node(&dt.root);
   }

在开始的时候，有一步来验证 Magic Number，这一步是一个保证系统可靠性的要求，是为了验证这段内存到底是不是设备树。在遍历过程中，一旦发现了一个支持 "virtio,mmio" 的设备（其实就是 QEMU 模拟的各种virtio设备），就进入下一步加载驱动的逻辑。具体遍历设备树节点的实现如下：

.. code-block:: Rust

   fn walk_dt_node(dt: &Node) {
      if let Ok(compatible) = dt.prop_str("compatible") {
         if compatible == "virtio,mmio" {
            //确定是virtio设备
            virtio_probe(dt);
         }
      }
      for child in dt.children.iter() {
         walk_dt_node(child);
      }
   }

这是一个递归的过程，其中 `virtio_probe` 是分析具体virtio设备的函数，一旦找到这样的设备，就可以启动virtio设备初始化过程了。


.. code-block:: Rust

   fn virtio_probe(node: &Node) {
      if let Some(reg) = node.prop_raw("reg") {
         let paddr = reg.as_slice().read_be_u64(0).unwrap();
         ...
         let header = unsafe { &mut *(paddr as *mut VirtIOHeader) };
         ...
         match header.device_type() {
               DeviceType::Block => virtio_blk(header),
               ...
               t => warn!("Unrecognized virtio device: {:?}", t),
         }
      }
   }

`virtio_probe` 函数会进一步查找virtio设备节点中的`reg` 属性，从而可以找到virtio设备的具体类型（如 `DeviceType::Block` 块设备类型）等参数。接下来，我们就可以对具体的virtio设备进行初始化和进行具体I/O操作了。

virtio-blk设备
------------------------------------------

virtio-blk设备是一种存储设备，在QEMU模拟的RISC-V 64计算机中，以MMIO的方式来与操作系统进行交互。

virtio-blk设备的关键数据结构
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

这里我们首先需要定义virtio-blk设备的结构：

.. code-block:: Rust

   pub struct VirtIOBlk<'a> {
      header: &'static mut VirtIOHeader,
      queue: VirtQueue<'a>,
      capacity: usize,
   }


其中的 ``VirtIOHeader`` 数据结构的内存布局与上一节描述 :ref:`virt-mmio设备的寄存器内存布局 <term-virtio-mmio-regs>` 是一致的。而 ``VirtQueue`` 数据结构与上一节描述的 :ref: `virtqueue <term-virtqueue>` 在表达的含义上基本一致的。

.. code-block:: Rust

   #[repr(C)]
   pub struct VirtQueue<'a> {
      dma: DMA, // DMA guard
      desc: &'a mut [Descriptor], // 描述符表
      avail: &'a mut AvailRing, // Available ring
      used: &'a mut UsedRing, // Used ring
      queue_idx: u32, // The index of queue
      queue_size: u16, // The size of queue
      num_used: u16, // The number of used queues
      free_head: u16, // The head desc index of the free list
      avail_idx: u16,
      last_used_idx: u16,
   }


初始化virtio-blk设备
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
   
在 ``virtio_probe`` 函数识别出virtio-blk设备后，会调用 ``virtio_blk(header)`` 来完成对virtio-blk设备的初始化过程。其实具体的初始化过程与virtio规范中描述的一般virtio设备的初始化过程大致一样，常规步骤（实际实现可以简化）如下：
   
1. 通过将0写入状态寄存器来复位器件；
2. 将状态寄存器的ACKNOWLEDGE状态位置1；
3. 将状态寄存器的DRIVER状态位置1；
4. 从host_features寄存器读取设备功能；
5. 协商功能集并将接受的内容写如guest_features寄存器；
6. 将状态寄存器的FEATURES_OK状态位置1；
7. 重新读取状态寄存器，以确认设备已接受您的功能；（可选）
8. 执行特定于设备的设置；（可选）
9. 将状态寄存器的DRIVER_OK状态位置1，使得该设备处于活跃可用状态。
   

具体实现，在如下代码中：

.. code-block:: Rust

   // virtio-drivers/src/blk.rs
   impl VirtIOBlk<'_> {
      pub fn new(header: &'static mut VirtIOHeader) -> Result<Self> {
         header.begin_init(|features| {
            let features = BlkFeature::from_bits_truncate(features);
            // negotiate these flags only
            let supported_features = BlkFeature::empty();
            (features & supported_features).bits()
         });

         // read configuration space
         let config = unsafe { &mut *(header.config_space() as *mut BlkConfig) };
         let queue = VirtQueue::new(header, 0, 16)?;
         header.finish_init();

         Ok(VirtIOBlk {
            header,   queue,   capacity: config.capacity.read() as usize,
         })
      }

在 ``new`` 成员函数的实现中， ``header.begin_init`` 函数完成了常规步骤的前六步；第七步在这里被忽略；第八步是对 ``guest_page_size`` 寄存器的设置（写寄存器的值为4096），并进一步读取virtio-blk设备的配置空间的设备相关的信息：

.. code-block:: Rust

   capacity: Volatile<u64>     = 32   //32个扇区，即16KB
   seg_max: Volatile<u32>      = 254  
   cylinders: Volatile<u16>    = 2
   heads: Volatile<u8>         = 16
   sectors: Volatile<u8>       = 63  
   blk_size: Volatile<u32>     = 512 //扇区大小为512字节

了解了virtio-blk设备的扇区个数，扇区大小和总体容量后，还需调用 `` VirtQueue::new`` 成员函数来创建传输层的 ``VirtQueue`` 数据结构的实例，这样才能进行后续的磁盘读写操作。这个函数主要完成的事情是：

- 设定 ``queue_size`` （即VirtQueue实例的虚拟队列条目数）为16；
- 计算满足 ``queue_size`` 的描述符表，AvailRing和UsedRing所需的物理空间的大小 -- ``size`` ；
- 基于上面计算的 ``size`` 分配物理空间； //VirtQueue.new()
- 把VirtQueue实例的信息写到virtio-blk设备的MMIO寄存器中； //VirtIOHeader.queue_set()
- 初始化VirtQueue实例中各个成员变量（主要是 dma，desc，avail，used）的值。

这时，对virtio-blk设备的初始化算是完成了，这时执行最后的第九步，将virtio-blk设备设置为活跃可用状态。

virtio-blk设备的I/O操作
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~


virtio-blk设备驱动发起的I/O请求包含操作类型(读或写)、起始扇区(一个扇区为512字节，是块设备的存储单位)、内存地址、访问长度；请求处理完成后返回的I/O响应仅包含结果状态(成功或失败)。系统产生了一个I/O请求，它在内存上的数据结构分为三个部分：Header，即请求头部，包含操作类型和起始扇区；Data，即数据区，包含地址和长度；Status，即结果状态。

virtio-blk设备使用 ``VirtQueue`` 数据结构来进行数据传输，此数据结构主要由三段连续内存组成：描述符表 Descriptor[]、环形队列结构的AvailRing和UsedRing。设备驱动和virtio-blk设备都能访问到此数据结构。
在 virtio_probe 函数识别出virtio-blk设备后，会调用 virtio_blk(header) 来完成对virtio-blk设备的初始化过程。
描述符表由固定长度(16字节)的描述符Descriptor组成，其个数等于环形队列长度，其中每个Descriptor的结构为：

.. code-block:: Rust

   #[repr(C, align(16))]
   #[derive(Debug)]
   struct Descriptor {
      addr: Volatile<u64>,
      len: Volatile<u32>,
      flags: Volatile<DescFlags>,
      next: Volatile<u16>,
   }

包含四个域：addr代表某段内存的起始地址，长度为8个字节；len代表某段内存的长度，本身占用4个字节(因此代表的内存段最大为4GB)；flags代表内存段读写属性等，长度为2个字节；next代表下一个内存段对应的Descpriptor在描述符表中的索引，因此通过next字段可以将一个请求对应的多个内存段连接成链表。

AvailRing的结构为：

.. code-block:: Rust

   #[repr(C)]
   #[derive(Debug)]
   struct AvailRing {
      flags: Volatile<u16>,
      /// A driver MUST NOT decrement the idx.
      idx: Volatile<u16>,
      ring: [Volatile<u16>; 32], // actual size: queue_size
      used_event: Volatile<u16>, // unused
   }

由头部的flags和idx域及ring数组组成：flags与通知机制相关；idx代表最新放入IO请求的编号，从零开始单调递增，将其对队列长度取余即可得该IO请求在entry数组中的索引；ring数组元素用来存放IO请求占用的首个Descriptor在描述符表中的索引，数组长度等于环形队列长度(不开启event_idx特性)。

UsedRing的结构为：

.. code-block:: Rust

   #[repr(C)]
   #[derive(Debug)]
   struct UsedRing {
      flags: Volatile<u16>,
      idx: Volatile<u16>,
      ring: [UsedElem; 32],       // actual size: queue_size
      avail_event: Volatile<u16>, // unused
   }


由头部的flags和idx域及ring数组组成：flags与通知机制相关；idx代表最新放入I/O响应的编号，从零开始单调递增，将其对队列长度取余即可得该I/O响应在ring数组中的索引；ring数组元素主要用来存放I/O响应占用的首个Descriptor在描述符表中的索引， 数组长度等于环形队列长度(不开启event_idx特性)。

仅CPU可见变量为free_head(空闲Descriptor链表头，初始时所有Descriptor通过next指针依次相连形成空闲链表)和last_used(当前已取的used元素位置)。仅设备可见变量为last_avail(当前已取的avail元素位置)。

针对用户进程发出的I/O请求，经过系统调用，文件系统等一系列处理后，最终会形成对virtio-blk设备驱动程序的调用。对于写操作，具体实现如下：


.. code-block:: Rust

   //virtio-drivers/src/blk.rs
   pub fn write_block(&mut self, block_id: usize, buf: &[u8]) -> Result {
      assert_eq!(buf.len(), BLK_SIZE);
      let req = BlkReq {
         type_: ReqType::Out,
         reserved: 0,
         sector: block_id as u64,
      };
      let mut resp = BlkResp::default();
      self.queue.add(&[req.as_buf(), buf], &[resp.as_buf_mut()])?;
      self.header.notify(0);
      while !self.queue.can_pop() {
         spin_loop();
      }
      self.queue.pop_used()?;
      match resp.status {
         RespStatus::Ok => Ok(()),
         _ => Err(Error::IoError),
      }
   }

基本流程如下：

1. 一个完整I/O写请求，包括表示I/O写信息的结构 ``BlkReq`` ，一个表示设备响应信息的结构 ``BlkResp`` ，再加上要传输的数据块 ``buf`` 。这三部分分别需要三个Descriptor来表示；
2. 接着调用 ``VirtQueue.add`` 函数，从描述符表中申请三个Descriptor空闲项，每项指向一段内存，填写上述三部分的信息，并将三个Descriptor连接成一个描述符链表；
3. 接着调用 ``VirtQueue.notify`` 函数，写 ``queue_notify`` 寄存器，即向 virtio-blk设备发出通知；
4. （设备内部处理过程）virtio-blk设备收到通知后，通过比较设备内部的last_avail(初始为0)和AvailRing中的idx判断是否有新的请求待处理(如果last_vail小于AvailRing中的idx，则有新请求)。如果有，则取出请求(更新last_avail为1 )并以entry的值为索引从描述符表中找到请求对应的所有Descriptor来获知完整的请求信息，并完成存储块的I/O写操作；
5. （设备内部处理过程）设备完成I/O写操作后(包括更新包含 ``BlkResp`` 的Descriptor)，将已完成I/O的Descriptor放入UsedRing对应的ring项中，并更新idx,代表放入一个响应；如果设置了中断机制，还会产生中断来通知操作系统响应中断；
6. 设备驱动用的无中断的轮询机制查看设备是否有响应（持续调用  ``VirtQueue.can_pop`` 函数），通过比较内部的 ``VirtQueue.last_used_idx`` 和 ``VirtQueue.used.idx`` 判断是否有新的响应。如果有，则取出响应(并更新 ``last_used_idx`` )，将完成响应对应的三项Descriptor回收，最后将结果返回给用户进程。


I/O读请求的处理过程与I/O写请求的处理过程几乎一样，这里就不在详细说明了。具体可以看看 ``virtio-drivers/src/blk.rs`` 文件中的 ``VirtIOBlk.read_block`` 函数的实现。


virtio-gpu设备
------------------------------------------

让操作系统能够显示图形一直是我们的想要完成的目标。这可以通过在QEMU或带显示屏的开发板上写显示驱动程序来完成。这里我们主要介绍如何驱动基于QEMU的virtio-gpu虚拟显示设备。我们看到的图形显示屏幕其实是由一个一个的像素点来组成的。显示设备驱动的主要目标就是把每个像素点用内存单元来表示，并把代表所有这些像素点的内存区域（也称显示内存，显存， frame buffer）“通知”显示I/O控制器（也称图形适配器，graphics adapter），然后显示I/O控制器会根据内存内容渲染到图形显示屏上。

virtio-gpu设备的关键数据结构
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

.. code:: Rust

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

``header`` 结构是virtio设备的共有属性，包括版本号、设备id、设备特征等信息。显存区域 ``frame_buffer_dma`` 是一块要由操作系统或运行时分配的内存，后续的像素点的值就会写在这个区域中。virtio-gpu设备驱动与virtio-gpu设备之间通过两个 virtqueue 来进行交互访问，``control_queue`` 用于设备驱动发送显示相关控制命令， ``cursor_queue`` 用于设备驱动发送显示鼠标更新的相关控制命令（这里暂时不用）。 ``queue_buf_dma`` 是存放控制命令和返回结果的内存， ``queue_buf_send`` 和 ``queue_buf_recv`` 是 ``queue_buf_dma`` 的切片。

初始化virtio-gpu设备
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

在 virtio_probe 函数识别出virtio-gpu设备后，会调用 ``virtio_gpu(header)`` 来完成对virtio-gpu设备的初始化过程。virtio-gpu设备初始化的工作主要是查询显示设备的信息（如分辨率等），并将该信息用于初始显示扫描（scanout）设置。具体过程如下：

.. code:: Rust

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

这其实完成的都算是一些共性的virtio设备初始化操作。虽然virtio-gpu初始化完毕，但它目前还不能进行显示。为了能够进行正常的显示，我们还需建立显存区域 frame buffer，并绑定在virtio-gpu设备上。这主要是通过 ``VirtIOGpu.setp_framebuffer`` 函数来完成的。

.. code:: Rust

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


上面的函数主要完成的工作有如下几个步骤，其实就是给virtio-gpu设备发控制命令，建立好显存区域：

1. 发出 ``GetDisplayInfo`` 命令，获得virtio-gpu设备的显示分辨率;
1. 发出 ``ResourceCreate2D`` 命令，让设备以分辨率大小，和Red/Green/Blue/Alpha各1字节模式来配置设备显示资源；
1. 分配 ``width *height * 4`` 字节的连续物理内存空间作为显存， 发出 ``ResourceAttachBacking`` 命令，让设备把显存附加到设备显示资源上；
1. 发出 ``SetScanout`` 命令，把设备显示资源链接到显示扫描输出上，这样才能让显存的像素信息显示出来；

到这一步，才算是把virtio-gpu设备初始化完成了。


virtio-gpu设备的I/O操作
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

接下来的显示比较简单，就是在显存中更新像素信息，然后给设备发出刷新指令，就可以显示了，具体的示例代码如下：

.. code:: Rust

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


