设备驱动程序（下）
=========================================

本节导读
-----------------------------------------

virtio设备驱动程序
-----------------------------------------

virtio设备是虚拟外设，存在于QEMU模拟的RISC-V 64 virt 计算机中，而我们要在操作系统中实现的virtio设备驱动程序，以能够管理和控制这些virtio虚拟设备。每一类virtio设备都有自己的virtio接口，virtio接口包括了数据结构和相关API的定义。这些定义中，很多在内容上都是一致的，只是在特定设备中，会根据设备的类型特征设定具体的属性内容。

virtio架构
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

总体上看，virtio 架构可以分为四层，包括运行在QEMU模拟器上的前端操作系统中各种驱动程序模块，在QEMU中模拟的各种后端 Device，中间用于前后端通信的 virtio 层，这一层是虚拟队列（virtqueue），是前后端通信的接口，表示设备驱动程序与设备间的数据传输机制，不过这不涉及具体实现。虚拟队列的下层是 virtio-ring，是数据传输机制的具体实现，主要由环形缓冲区和相关操作组成，用于保存前端驱动程序和后端虚拟设备之间进行命令和数据交互的信息。

.. image:: virtio-arch.png
   :align: center
   :name: virtio-arch


**virtio设备** 

virtio设备支持三种设备呈现模式：

- Virtio Over MMIO，虚拟设备直接挂载到系统总线上，我们实验中的虚拟计算机就是这种呈现模式；
- Virtio Over PCI BUS，遵循PCI规范，挂在到PCI总线上，作为virtio-pci设备呈现，在QEMU虚拟的x86计算机上采用的是这种模式；
- Virtio Over Channel I/O：主要用在虚拟IBM s390计算机上，virtio-ccw使用这种基于channel I/O的机制。

virtio设备的基本组成要素如下：

- 设备状态域（Device status field）
- 特征位（Feature bits）
- 通知（Notifications）
- 设备配置空间（Device Configuration space）
- 一个或多个虚拟队列（virtqueue）

**设备状态域**

其中设备状态域包含对设备初始化过程中设备具有的6种状态：

- ACKNOWLEDGE（1）：设备驱动程序发现了这个设备，并且认为这是一个有效的virtio设备；
- DRIVER (2) : 设备驱动程序知道该如何驱动这个设备；
- FAILED (128) : 由于某种错误原因，设备驱动程序无法正常驱动这个设备；
- FEATURES_OK (8) : 设备驱动程序认识设备的特征，并且与设备就设备特征协商达成一致；
- DRIVER_OK (4) : 设备驱动程序加载完成，设备可以正常工作了；
- DEVICE_NEEDS_RESET (64) ：设备触发了错误，需要重置才能继续工作。


**特征位** 

特征位用于表示VirtIO设备具有的各种特性。其中bit0-bit23是特定设备可以使用的feature bits， bit24-bit37预给队列和feature协商机制，bit38以上保留给未来其他用途。设备驱动程序与设备就设备的各种特性需要协商，形成一致的共识，这样才能正确的管理设备。


**通知**

设备驱动程序和设备在交互中，需要互通通知对方，设备驱动程序组织好相关命令/信息要通知设备去处理I/O事务，设备处理完I/O事务后，要通知设备驱动程序进行后续事务，如回收内存，向用户进程反馈I/O事务的处理结果等。

设备驱动程序通知设备用doorbell机制，即写特定寄存器，QEMU进行拦截再通知其模拟的设备。设备通知设备驱动程序一般用中断机制，即在QEMU中进行中断注入，让CPU响应并执行中断处理例程，来完成对I/O执行结果的处理。

**设备配置空间**

设备配置空间通常用于配置不常变动的设备参数（属性），或者初始化阶段需要时设置的设备参数。设备的特征位中包含表示配置空间是否存在的bit位，并可通过在特征位的末尾新添新的bit位来扩展配置空间。

.. _term-virtqueue:

**虚拟队列（virtqueue）** 与 **virtio-ring**

在virtio设备上进行批量数据传输的机制被称为virtqueue，virtio设备的虚拟队列（virtqueue）可以由virtio-ring（一种环形队列）来具体实现。每个virtio设备可以拥有零个或多个virtqueue，每个virtqueue占用2个或者更多个4K的物理页。 virtqueue有Split Virtqueues和Packed Virtqueues两种模式。在Split virtqueues模式下，virtqueue被分成若干个部分， 每个部分都是前端驱动或者后端设备单向可写。 每个virtqueue都有一个16bit的 ``Queue Size`` 参数，表示队列的总长度。每个virtqueue由三部分组成：

- Descriptor Table
- Available Ring：记录了Descriptor Table表中的哪些项被更新了，前端Driver可写但后端只读；
- Used Ring

Descriptor Table用来存放IO传输请求信息，即是virtio设备驱动程序与virtio设备进行数据交互的缓冲区，由 ``Queue Size`` 个Descriptor（描述符）组成。Descriptor中包括表示数据buffer的物理地址 -- addr字段，数据buffer的长度 -- len字段，可以链接到 ``next Descriptor`` 的next指针并形成描述符链。

Available Ring中的每个条目是一个是描述符链的头部。它仅由virtio设备驱动程序写入，并由virtio设备读出。virtio设备获取Descriptor后，Descriptor对应的缓冲区具有可读写属性，可读的缓冲区用于Driver发送数据，可写的缓冲区用于接收数据。

Used Ring中的每个条目也一个是描述符链的头部。这个描述符是Device完成相应I/O处理后，将Available Ring中的Descriptor移入到Used Ring中来，并通过轮询或中断机制来通知virtio设备驱动程序I/O完成，并让virtio设备驱动程序回收这个描述符。







.. image:: vring.png
   :align: center
   :name: vring


当virtio设备驱动程序想要向virtio设备发送数据时，它会填充Descriptor Table中的一项或几项链接在一起，形成描述符链，并将描述符索引写入Available Ring中，然后它通知virtio设备（向queue notify寄存器写入队列index）。当virtio设备收到通知，并完成I/O操作后，virtio设备将描述符索引写入Used Ring中并发送中断，让操作系统进行进一步处理并回收描述符。


virtio 设备的相关操作
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

.. https://rootw.github.io/2019/09/firecracker-virtio/

对于设备驱动和外设之间采用virtio协议进行交互的原理如下图所示。


.. image:: virtio-cpu-device-io2.png
   :align: center
   :name: virtio-cpu-device-io2


设备驱动与外设可以共同访问内存，内存中存在一个称为环形队列的数据结构，该队列可分成由I/O请求组成的请求队列(Available Ring)和由I/O响应组成的响应队列(Used Ring)。一个IO的处理过程可以分成如下四步：

1. 用户进程发出I/O请求时，设备驱动将I/O请求放入请求队列(Available Ring)中并通知设备；
2. 设备收到通知后从请求队列中取出I/O请求并在内部进行实际处理；
3. 设备将IO处理完成后，将结果作为I/O响应放入响应队列(Used Ring)并以中断方式通知CPU；
4. 设备驱动从响应队列中取出I/O处理结果并最终返回给用户进程。

**设备的初始化**

1. 重启设备状态，状态位写入 0
2. 设置状态为 ACKNOWLEDGE，guest(driver)端当前已经识别到了设备
3. 设置状态为 Driver，guest 知道如何驱动当前设备
4. 设备特定的安装和配置：特征位的协商，virtqueue 的安装，读写设备专属的配置空间等
5. 设置状态为 Driver_OK 或者 Failed（如果中途出现错误）
6. 当前设备初始化完毕，可以进行配置和使用

**设备的安装和配置**

设备操作包括两个部分：driver提供 buffers 给设备，处理 device使用过的 buffers。

**初始化 virtqueue**

该部分代码的实现具体为：

1. 选择 virtqueue 的索引，写入 Queue Select 寄存器
2. 读取 queue size 寄存器获得 virtqueue 的可用数目
3. 分配并清零连续物理内存用于存放 virtqueue。把内存地址除以 4096 写入 Queue Address 寄存器

**Guest 向设备提供 buffer**

1. 把 buffer 添加到 description table 中,填充 addr,len,flags
2. 更新 available ring head
3. 更新 available ring 中的 index
4. 通知 device，通过写入 virtqueue index 到 Queue Notify 寄存器

**Device 使用 buffer 并填充 used ring**

device 端使用 buffer 后填充 used ring 的过程如下：

1. 从描述符表格（descriptor table）中找到 available ring 中添加的 buffers，映射内存
2. 从分散-聚集的 buffer 读取数据
3. 取消内存映射,更新 ring[idx]中的 id 和 len 字段
4. 更新响应队列 vring_used 中的 idx
5. 如果设置了使能中断，产生中断并通知操作系统描述符已经使用
6. 设备驱动从响应队列 vring_used 中取出IO处理结果并返回给应用程序



基于MMIO方式的virtio设备
-----------------------------------------

基于MMIO方式的virtio设备没有基于总线的设备探测机制。 所以操作系统采用Device Tree的方式来探测各种基于MMIO方式的virtio设备，从而操作系统能知道与设备相关的寄存器和所用的中断。基于MMIO方式的virtio设备提供了一组内存映射的控制寄存器，后跟一个设备特定的配置空间，在形式上是位于一个特点地址上的内存区域。一旦操作系统找到了这个内存区域，就可以获得与这个设备相关的各种寄存器信息。比如，我们在 `virtio-drivers` crate 中就定义了基于MMIO方式的virtio设备的寄存器区域：

.. _term-virtio-mmio-regs:

.. code-block:: Rust

   //virtio-drivers/src/header.rs L8
   #[repr(C)]
   #[derive(Debug)]
   pub struct VirtIOHeader {
      magic: ReadOnly<u32>,  //魔数 Magic value
      version: ReadOnly<u32>, //设备版本号
      device_id: ReadOnly<u32>, // Virtio子系统设备ID 
      vendor_id: ReadOnly<u32>, // Virtio子系统供应商ID
      device_features: ReadOnly<u32>, //设备支持的功能
      device_features_sel: WriteOnly<u32>,//设备选择的功能
      driver_features: WriteOnly<u32>, //驱动程序理解的设备功能
      driver_features_sel: WriteOnly<u32>, //驱动程序选择的设备功能
      guest_page_size: WriteOnly<u32>, //OS中页的大小（应为2的幂）
      queue_sel: WriteOnly<u32>, //虚拟队列索引号
      queue_num_max: ReadOnly<u32>,//虚拟队列最大容量值
      queue_num: WriteOnly<u32>, //虚拟队列当前容量值
      queue_align: WriteOnly<u32>,//虚拟队列的对齐边界（以字节为单位）
      queue_pfn: Volatile<u32>, //虚拟队列所在的物理页号
      queue_ready: Volatile<u32>, // new interface only
      queue_notify: WriteOnly<u32>, //队列通知
      interrupt_status: ReadOnly<u32>, //中断状态
      interrupt_ack: WriteOnly<u32>, //中断确认
      status: Volatile<DeviceStatus>, //设备状态
      config_generation: ReadOnly<u32>, //配置空间
   }

这里列出了部分的关键的寄存器和它的基本功能描述。在后续的设备初始化，设备I/O操作中，都会用到这里列出的寄存器。

接下来，我们将分析virtio设备驱动程序如何管理这些设备来完成I/O操作的。


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


