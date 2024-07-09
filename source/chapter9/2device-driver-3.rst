virtio_blk块设备驱动程序
=========================================

本节导读
-----------------------------------------

本节主要介绍了与操作系统无关的基本virtio_blk设备驱动程序的设计与实现，以及如何在操作系统中封装virtio_blk设备驱动程序，实现基于中断机制的I/O操作，提升计算机系统的整体性能。



virtio-blk驱动程序
------------------------------------------

virtio-blk设备是一种virtio存储设备，在QEMU模拟的RISC-V 64计算机中，以MMIO和中断等方式方式来与驱动程序进行交互。这里我们以Rust语言为例，给出virtio-blk设备驱动程序的设计与实现。主要包括如下内容：

- virtio-blk设备的关键数据结构
- 初始化virtio-blk设备
- 操作系统对接virtio-blk设备初始化
- virtio-blk设备的I/O操作
- 操作系统对接virtio-blk设备I/O操作

virtio-blk设备的关键数据结构
------------------------------------------

这里我们首先需要定义virtio-blk设备的结构：

.. code-block:: Rust
   :linenos:

   // virtio-drivers/src/blk.rs
   pub struct VirtIOBlk<'a, H: Hal> {
      header: &'static mut VirtIOHeader,
      queue: VirtQueue<'a, H>,
      capacity: usize,
   }


``header`` 成员对应的 ``VirtIOHeader`` 数据结构是virtio设备的共有属性，包括版本号、设备id、设备特征等信息，其内存布局和成员变量的含义与上一节描述 :ref:`virt-mmio设备的寄存器内存布局 <term-virtio-mmio-regs>` 是一致的。而 ``VirtQueue`` 数据结构与上一节描述的 :ref:`virtqueue <term-virtqueue>` 在表达的含义上基本一致的。

.. _term-virtqueue-struct:

.. code-block:: Rust
   :linenos:

   #[repr(C)]
   pub struct VirtQueue<'a, H: Hal> {
      dma: DMA<H>, // DMA guard
      desc: &'a mut [Descriptor], // 描述符表
      avail: &'a mut AvailRing, // 可用环 Available ring
      used: &'a mut UsedRing, // 已用环 Used ring
      queue_idx: u32, //虚拟队列索引值
      queue_size: u16, // 虚拟队列长度
      num_used: u16, // 已经使用的队列项目数
      free_head: u16, // 空闲队列项目头的索引值
      avail_idx: u16, //可用环的索引值
      last_used_idx: u16, //上次已用环的索引值
   }

其中成员变量 ``free_head`` 指空闲描述符链表头，初始时所有描述符通过 ``next`` 指针依次相连形成空闲链表，成员变量 ``last_used_idx`` 是指设备上次已取的已用环元素位置。成员变量 ``avail_idx`` 是可用环的索引值。

.. _term-virtio-hal:

这里出现的 ``Hal`` trait是 `virtio_drivers` 库中定义的一个trait，用于抽象出与具体操作系统相关的操作，主要与内存分配和虚实地址转换相关。这里我们只给出trait的定义，对应操作系统的具体实现在后续的章节中会给出。


.. code-block:: Rust
   :linenos:

   pub trait Hal {
      /// Allocates the given number of contiguous physical pages of DMA memory for virtio use.
      fn dma_alloc(pages: usize) -> PhysAddr;
      /// Deallocates the given contiguous physical DMA memory pages.
      fn dma_dealloc(paddr: PhysAddr, pages: usize) -> i32;
      /// Converts a physical address used for virtio to a virtual address which the program can
      /// access.
      fn phys_to_virt(paddr: PhysAddr) -> VirtAddr;
      /// Converts a virtual address which the program can access to the corresponding physical
      /// address to use for virtio.
      fn virt_to_phys(vaddr: VirtAddr) -> PhysAddr;
   }



初始化virtio-blk设备
------------------------------------------
   
.. 在 ``virtio-drivers`` crate的 ``examples\riscv\src\main.rs`` 文件中的 ``virtio_probe`` 函数识别出virtio-blk设备后，会调用 ``virtio_blk(header)`` 来完成对virtio-blk设备的初始化过程。其实具体的初始化过程与virtio规范中描述的一般virtio设备的初始化过程大致一样，步骤（实际实现可以简化）如下：
   
.. 1. （可忽略）通过将0写入状态寄存器来复位器件；
.. 2. 将状态寄存器的ACKNOWLEDGE状态位置1；
.. 3. 将状态寄存器的DRIVER状态位置1；
.. 4. 从host_features寄存器读取设备功能；
.. 5. 协商功能集并将接受的内容写入guest_features寄存器；
.. 6. 将状态寄存器的FEATURES_OK状态位置1；
.. 7. （可忽略）重新读取状态寄存器，以确认设备已接受协商的功能；
.. 8. 执行特定于设备的设置：读取设备配置空间，建立虚拟队列；
.. 9. 将状态寄存器的DRIVER_OK状态位置1，使得该设备处于活跃可用状态。
   

virtio-blk设备的初始化过程与virtio规范中描述的一般virtio设备的初始化过程大致一样，对其实现的初步分析在 :ref:`virtio-blk初始化代码 <term-virtio-blk-init>` 中。在设备初始化过程中读取了virtio-blk设备的配置空间的设备信息：

.. code-block:: Rust
   :linenos:

   capacity: Volatile<u64> = 32  //32个扇区，即16KB
   blk_size: Volatile<u32> = 512 //扇区大小为512字节

为何能看到扇区大小为 ``512`` 字节欸，容量为 ``16KB`` 大小的virtio-blk设备？这当然是我们让Qemu模拟器建立的一个虚拟硬盘。下面的命令可以看到虚拟硬盘创建和识别过程：

.. code-block:: shell
   :linenos:

   # 在virtio-drivers仓库的example/riscv目录下执行如下命令
   make run 
   # 可以看到与虚拟硬盘创建相关的具体命令
   ## 通过 dd 工具创建了扇区大小为 ``512`` 字节欸，容量为 ``16KB`` 大小的硬盘镜像（disk img）
   dd if=/dev/zero of=target/riscv64imac-unknown-none-elf/release/img bs=512 count=32
      记录了32+0 的读入
      记录了32+0 的写出
      16384字节（16 kB，16 KiB）已复制，0.000439258 s，37.3 MB/s
   ## 通过 qemu-system-riscv64 命令启动 Qemu 模拟器，创建 virtio-blk 设备   
   qemu-system-riscv64 \
        -drive file=target/riscv64imac-unknown-none-elf/release/img,if=none,format=raw,id=x0 \
        -device virtio-blk-device,drive=x0 ...
   ## 可以看到设备驱动查找到的virtio-blk设备色信息
   ...
   [ INFO] Detected virtio MMIO device with vendor id 0x554D4551, device type Block, version Modern
   [ INFO] device features: SEG_MAX | GEOMETRY | BLK_SIZE | FLUSH | TOPOLOGY | CONFIG_WCE | DISCARD | WRITE_ZEROES | RING_INDIRECT_DESC | RING_EVENT_IDX | VERSION_1
   [ INFO] config: 0x10008100
   [ INFO] found a block device of size 16KB
   ...

virtio-blk设备驱动程序了解了virtio-blk设备的扇区个数，扇区大小和总体容量后，还需调用 `` VirtQueue::new`` 成员函数来创建虚拟队列 ``VirtQueue`` 数据结构的实例，这样才能进行后续的磁盘读写操作。这个函数主要完成的事情是分配虚拟队列的内存空间，并进行初始化：

- 设定 ``queue_size`` （即虚拟队列的描述符条目数）为16；
- 计算满足 ``queue_size`` 的描述符表 ``desc`` ，可用环 ``avail`` 和已用环 ``used`` 所需的物理空间的大小 -- ``size`` ；
- 基于上面计算的 ``size`` 分配物理空间； //VirtQueue.new()
- ``VirtIOHeader.queue_set`` 函数把虚拟队列的相关信息（内存地址等）写到virtio-blk设备的MMIO寄存器中；
- 初始化VirtQueue实例中各个成员变量（主要是 ``dma`` ， ``desc`` ，``avail`` ，``used`` ）的值。

做完这一步后，virtio-blk设备和设备驱动之间的虚拟队列接口就打通了，可以进行I/O数据读写了。下面简单代码完成了对虚拟硬盘的读写操作和读写正确性检查：


.. code-block:: rust
   :linenos:

   // virtio-drivers/examples/riscv/src/main.rs
   fn virtio_blk(header: &'static mut VirtIOHeader) { {
      // 创建blk结构
      let mut blk = VirtIOBlk::<HalImpl, T>::new(header).expect("failed to create blk driver");
      // 读写缓冲区
      let mut input = vec![0xffu8; 512];
      let mut output = vec![0; 512];
      ...
      // 把input数组内容写入virtio-blk设备
      blk.write_block(i, &input).expect("failed to write");
      // 从virtio-blk设备读取内容到output数组
      blk.read_block(i, &mut output).expect("failed to read");
      // 检查virtio-blk设备读写的正确性
      assert_eq!(input, output);
   ...

操作系统对接virtio-blk设备初始化过程
--------------------------------------------------------------

但virtio_derivers 模块还没有与操作系统内核进行对接。我们还需在操作系统中封装virtio-blk设备，让操作系统内核能够识别并使用virtio-blk设备。首先分析一下操作系统需要建立的表示virtio_blk设备的全局变量 ``BLOCK_DEVICE`` ：


.. code-block:: Rust
   :linenos:

   // os/src/drivers/block/virtio_blk.rs
   pub struct VirtIOBlock {
      virtio_blk: UPIntrFreeCell<VirtIOBlk<'static, VirtioHal>>,
      condvars: BTreeMap<u16, Condvar>,
   }
   // os/easy-fs/src/block_dev.rs
   pub trait BlockDevice: Send + Sync + Any {
      fn read_block(&self, block_id: usize, buf: &mut [u8]);
      fn write_block(&self, block_id: usize, buf: &[u8]);
      fn handle_irq(&self);
   }
   // os/src/boards/qemu.rs
   pub type BlockDeviceImpl = crate::drivers::block::VirtIOBlock;
   // os/src/drivers/block/mod.rs
   lazy_static! {
      pub static ref BLOCK_DEVICE: Arc<dyn BlockDevice> = Arc::new(BlockDeviceImpl::new());
   }


从上面的代码可以看到，操作系统中表示virtio_blk设备的全局变量 ``BLOCK_DEVICE`` 的类型是 ``VirtIOBlock`` ,封装了来自virtio_derivers 模块的 ``VirtIOBlk`` 类型。这样，操作系统内核就可以通过 ``BLOCK_DEVICE`` 全局变量来访问virtio_blk设备了。而  ``VirtIOBlock`` 中的 ``condvars: BTreeMap<u16, Condvar>`` 条件变量结构，是用于进程在等待 I/O读或写操作完全前，通过条件变量让进程处于挂起状态。当virtio_blk设备完成I/O操作后，会通过中断唤醒等待的进程。而操作系统对virtio_blk设备的初始化除了封装 ``VirtIOBlk`` 类型并调用 ``VirtIOBlk::<VirtioHal>::new()`` 外，还需要初始化 ``condvars`` 条件变量结构，而每个条件变量对应着一个虚拟队列条目的编号，这意味着每次I/O请求都绑定了一个条件变量，让发出请求的线程/进程可以被挂起。


.. code-block:: Rust
   :linenos:

   impl VirtIOBlock {
      pub fn new() -> Self {
         let virtio_blk = unsafe {
               UPIntrFreeCell::new(
                  VirtIOBlk::<VirtioHal>::new(&mut *(VIRTIO0 as *mut VirtIOHeader)).unwrap(),
               )
         };
         let mut condvars = BTreeMap::new();
         let channels = virtio_blk.exclusive_access().virt_queue_size();
         for i in 0..channels {
               let condvar = Condvar::new();
               condvars.insert(i, condvar);
         }
         Self {
               virtio_blk,
               condvars,
         }
      }
   }

在上述初始化代码中，我们先看到 ``VIRTIO0`` ，这是 Qemu模拟的virtio_blk设备中I/O寄存器的物理内存地址， ``VirtIOBlk`` 需要这个地址来对 ``VirtIOHeader`` 数据结构所表示的virtio-blk I/O控制寄存器进行读写操作，从而完成对某个具体的virtio-blk设备的初始化过程。而且我们还看到了 ``VirtioHal`` 结构，它实现virtio-drivers 模块定义 ``Hal`` trait约定的方法 ，提供DMA内存分配和虚实地址映射操作，从而让virtio-drivers 模块中 ``VirtIOBlk`` 类型能够得到操作系统的服务。

.. code-block:: Rust
   :linenos:

   // os/src/drivers/bus/virtio.rs
   impl Hal for VirtioHal {
      fn dma_alloc(pages: usize) -> usize {
         //分配页帧 page-frames
         }
         let pa: PhysAddr = ppn_base.into();
         pa.0
      }

      fn dma_dealloc(pa: usize, pages: usize) -> i32 {
         //释放页帧 page-frames
         0
      }

      fn phys_to_virt(addr: usize) -> usize {
         addr
      }

      fn virt_to_phys(vaddr: usize) -> usize {
         //把虚地址转为物理地址
      }
   }


virtio-blk设备的I/O操作
--------------------------------------------------------------

操作系统的virtio-blk驱动的主要功能是给操作系统中的文件系统内核模块提供读写磁盘块的服务，并在对进程管理有一定的影响，但不用直接给应用程序提供服务。在操作系统与virtio-drivers crate中virtio-blk裸机驱动对接的过程中，需要注意的关键问题是操作系统的virtio-blk驱动如何封装virtio-blk裸机驱动的基本功能，完成如下服务：

1. 读磁盘块，挂起发起请求的进程/线程;
2. 写磁盘块，挂起发起请求的进程/线程；
3. 对virtio-blk设备发出的中断进行处理，唤醒相关等待的进程/线程。

virtio-blk驱动程序发起的I/O请求包含操作类型(读或写)、起始扇区(块设备的最小访问单位的一个扇区的长度512字节)、内存地址、访问长度；请求处理完成后返回的I/O响应仅包含结果状态(成功或失败，读操作请求的读出扇区内容)。系统产生的一个I/O请求在内存中的数据结构分为三个部分：Header（请求头部，包含操作类型和起始扇区）；Data（数据区，包含地址和长度）；Status（结果状态），这些信息分别放在三个buffer，所以需要三个描述符。

virtio-blk设备使用 ``VirtQueue`` 数据结构来表示虚拟队列进行数据传输，此数据结构主要由三段连续内存组成：描述符表 ``Descriptor[]`` 、环形队列结构的 ``AvailRing`` 和 ``UsedRing``  。驱动程序和virtio-blk设备都能访问到此数据结构。

描述符表由固定长度(16字节)的描述符Descriptor组成，其个数等于环形队列长度，其中每个Descriptor的结构为：

.. code-block:: Rust
   :linenos:

   struct Descriptor {
      addr: Volatile<u64>,
      len: Volatile<u32>,
      flags: Volatile<DescFlags>,
      next: Volatile<u16>,
   }

包含四个域：addr代表某段内存的起始地址，长度为8个字节；len代表某段内存的长度，本身占用4个字节(因此代表的内存段最大为4GB)；flags代表内存段读写属性等，长度为2个字节；next代表下一个内存段对应的Descpriptor在描述符表中的索引，因此通过next字段可以将一个请求对应的多个内存段连接成链表。

可用环 ``AvailRing`` 的结构为：

.. code-block:: Rust
   :linenos:

   struct AvailRing {
      flags: Volatile<u16>,
      /// A driver MUST NOT decrement the idx.
      idx: Volatile<u16>,
      ring: [Volatile<u16>; 32], // actual size: queue_size
      used_event: Volatile<u16>, // unused
   }

可用环由头部的 ``flags`` 和 ``idx`` 域及 ``ring`` 数组组成： ``flags`` 与通知机制相关； ``idx`` 代表最新放入IO请求的编号，从零开始单调递增，将其对队列长度取余即可得该I/O请求在可用环数组中的索引；可用环数组元素用来存放I/O请求占用的首个描述符在描述符表中的索引，数组长度等于可用环的长度(不开启event_idx特性)。

已用环 ``UsedRing`` 的结构为：

.. code-block:: Rust
   :linenos:

   struct UsedRing {
      flags: Volatile<u16>,
      idx: Volatile<u16>,
      ring: [UsedElem; 32],       // actual size: queue_size
      avail_event: Volatile<u16>, // unused
   }


已用环由头部的 ``flags`` 和 ``idx`` 域及 ``ring`` 数组组成： ``flags`` 与通知机制相关； ``idx`` 代表最新放入I/O响应的编号，从零开始单调递增，将其对队列长度取余即可得该I/O响应在已用环数组中的索引；已用环数组元素主要用来存放I/O响应占用的首个描述符在描述符表中的索引， 数组长度等于已用环的长度(不开启event_idx特性)。


针对用户进程发出的I/O请求，经过系统调用，文件系统等一系列处理后，最终会形成对virtio-blk驱动程序的调用。对于写操作，具体实现如下：


.. code-block:: Rust
   :linenos:

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

1. 一个完整的virtio-blk的I/O写请求由三部分组成，包括表示I/O写请求信息的结构 ``BlkReq`` ，要传输的数据块 ``buf``，一个表示设备响应信息的结构 ``BlkResp``  。这三部分需要三个描述符来表示；
2. （驱动程序处理）接着调用 ``VirtQueue.add`` 函数，从描述符表中申请三个空闲描述符，每项指向一个内存块，填写上述三部分的信息，并将三个描述符连接成一个描述符链表；
3. （驱动程序处理）接着调用 ``VirtQueue.notify`` 函数，写MMIO模式的 ``queue_notify`` 寄存器，即向 virtio-blk设备发出通知；
4. （设备处理）virtio-blk设备收到通知后，通过比较 ``last_avail`` (初始为0)和 ``AvailRing`` 中的 ``idx`` 判断是否有新的请求待处理(如果 ``last_vail`` 小于 ``AvailRing`` 中的 ``idx`` ，则表示有新请求)。如果有，则 ``last_avail`` 加1，并以 ``last_avail`` 为索引从描述符表中找到这个I/O请求对应的描述符链来获知完整的请求信息，并完成存储块的I/O写操作；
5. （设备处理）设备完成I/O写操作后(包括更新包含 ``BlkResp`` 的Descriptor)，将已完成I/O的描述符放入UsedRing对应的ring项中，并更新idx，代表放入一个响应；如果设置了中断机制，还会产生中断来通知操作系统响应中断；
6. （驱动程序处理）驱动程序可用轮询机制查看设备是否有响应（持续调用  ``VirtQueue.can_pop`` 函数），通过比较内部的 ``VirtQueue.last_used_idx`` 和 ``VirtQueue.used.idx`` 判断是否有新的响应。如果有，则取出响应(并更新 ``last_used_idx`` )，将完成响应对应的三项Descriptor回收，最后将结果返回给用户进程。当然，也可通过中断机制来响应。


I/O读请求的处理过程与I/O写请求的处理过程几乎一样，仅仅是 ``BlkReq`` 的内容不同，写操作中的 ``req.type_`` 是 ``ReqType::Out``，而读操作中的 ``req.type_`` 是 ``ReqType::In`` 。具体可以看看 ``virtio-drivers/src/blk.rs`` 文件中的 ``VirtIOBlk.read_block`` 函数的实现。

这种基于轮询的I/O访问方式效率比较差，为此，我们需要实现基于中断的I/O访问方式。为此在支持中断的 ``write_block_nb`` 方法：



.. code-block:: Rust
   :linenos:

   pub unsafe fn write_block_nb(
        &mut self,
        block_id: usize,
        buf: &[u8],
        resp: &mut BlkResp,
    ) -> Result<u16> {
        assert_eq!(buf.len(), BLK_SIZE);
        let req = BlkReq {
            type_: ReqType::Out,
            reserved: 0,
            sector: block_id as u64,
        };
        let token = self.queue.add(&[req.as_buf(), buf], &[resp.as_buf_mut()])?;
        self.header.notify(0);
        Ok(token)
   }

   // Acknowledge interrupt.
   pub fn ack_interrupt(&mut self) -> bool {
        self.header.ack_interrupt()
   }

与不支持中的 ``write_block`` 函数比起来， ``write_block_nb`` 函数更简单了，在发出I/O请求后，就直接返回了。 ``read_block_nb`` 函数的处理流程与此一致。而响应中断的 ``ack_interrupt`` 函数只是完成了非常基本的 virtio设备的中断响应操作。在virtio-drivers中实现的virtio设备驱动是看不到进程、条件变量等操作系统的各种关键要素，只有与操作系统内核对接，才能完整实现基于中断的I/O访问方式。




操作系统对接virtio-blk设备I/O处理
--------------------------------------------------------------

操作系统中的文件系统模块与操作系统中的块设备驱动程序 ``VirtIOBlock`` 直接交互，而操作系统中的块设备驱动程序 ``VirtIOBlock`` 封装了virtio-drivers中实现的virtio_blk设备驱动。在文件系统的介绍中，我们并没有深入分析virtio_blk设备。这里我们将介绍操作系统对接virtio_blk设备驱动并完成基于中断机制的I/O处理过程。

接下来需要扩展文件系统对块设备驱动的I/O访问要求，这体现在  ``BlockDevice`` trait的新定义中增加了 ``handle_irq`` 方法，而操作系统的virtio_blk设备驱动程序中的 ``VirtIOBlock`` 实现了这个方法，并且实现了既支持轮询方式，也支持中断方式的块读写操作。

.. code-block:: Rust
   :linenos:

   // easy-fs/src/block_dev.rs
   pub trait BlockDevice: Send + Sync + Any {
      fn read_block(&self, block_id: usize, buf: &mut [u8]);
      fn write_block(&self, block_id: usize, buf: &[u8]);
      // 更新的部分：增加对块设备中断的处理
      fn handle_irq(&self);
   }
   // os/src/drivers/block/virtio_blk.rs
   impl BlockDevice for VirtIOBlock {
      fn handle_irq(&self) {
         self.virtio_blk.exclusive_session(|blk| {
               while let Ok(token) = blk.pop_used() {
                     // 唤醒等待该块设备I/O完成的线程/进程
                  self.condvars.get(&token).unwrap().signal();
               }
         });
      }

      fn read_block(&self, block_id: usize, buf: &mut [u8]) {
         // 获取轮询或中断的配置标记
         let nb = *DEV_NON_BLOCKING_ACCESS.exclusive_access();
         if nb { // 如果是中断方式
               let mut resp = BlkResp::default();
               let task_cx_ptr = self.virtio_blk.exclusive_session(|blk| { 
                  // 基于中断方式的块读请求
                  let token = unsafe { blk.read_block_nb(block_id, buf, &mut resp).unwrap() };
                  // 将当前线程/进程加入条件变量的等待队列
                  self.condvars.get(&token).unwrap().wait_no_sched()
               });
               // 切换线程/进程
               schedule(task_cx_ptr);
               assert_eq!(
                  resp.status(),
                  RespStatus::Ok,
                  "Error when reading VirtIOBlk"
               );
         } else { // 如果是轮询方式，则进行轮询式的块读请求
               self.virtio_blk
                  .exclusive_access()
                  .read_block(block_id, buf)
                  .expect("Error when reading VirtIOBlk");
         }
      }

``write_block`` 写操作与 ``read_block`` 读操作的处理过程一致，这里不再赘述。

然后需要对操作系统整体的中断处理过程进行调整，以支持对基于中断方式的块读写操作：

.. code-block:: Rust
   :linenos:

   // os/src/trap/mode.rs
   //在用户态接收到外设中断
   pub fn trap_handler() -> ! {
      ...
      crate::board::irq_handler();
   //在内核态接收到外设中断
   pub fn trap_from_kernel(_trap_cx: &TrapContext) {
      ...
      crate::board::irq_handler();
   // os/src/boards/qemu.rs
   pub fn irq_handler() {
      let mut plic = unsafe { PLIC::new(VIRT_PLIC) };
      // 获得外设中断号
      let intr_src_id = plic.claim(0, IntrTargetPriority::Supervisor);
      match intr_src_id {
         ...
         //处理virtio_blk设备产生的中断
         8 => BLOCK_DEVICE.handle_irq(),
      }
      // 完成中断响应
      plic.complete(0, IntrTargetPriority::Supervisor, intr_src_id);
   }


``BLOCK_DEVICE.handle_irq()`` 执行的就是  ``VirtIOBlock`` 实现的中断处理方法 ``handle_irq()`` ，从而让等待在块读写的进程/线程得以继续执行。

有了基于中断方式的块读写操作后，当某个线程/进程由于块读写操作无法继续执行时，操作系统可以切换到其它处于就绪态的线程/进程执行，从而让计算机系统的整体执行效率得到提升。