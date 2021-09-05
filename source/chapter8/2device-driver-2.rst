驱动程序（下）
=========================================

本节导读
-----------------------------------------

本节主要介绍了QMU模拟的RISC-V计算机中的virtio设备的架构和重要组成部分，以及面向virtio设备的驱动程序的主要功能；并对virtio-blk设备及其驱动程序，virtio-gpu设备及其驱动程序进行了比较深入的分析。

virtio设备
-----------------------------------------

virtio设备是虚拟外设，存在于QEMU模拟的RISC-V 64 virt 计算机中，而我们要在操作系统中实现的virtio驱动程序，以能够管理和控制这些virtio虚拟设备。每一类virtio设备都有自己的virtio接口，virtio接口包括了数据结构和相关API的定义。这些定义中，很多在内容上都是一致的，只是在特定设备中，会根据设备的类型特征设定具体的属性内容。

virtio架构
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

总体上看，virtio 架构可以分为四层，包括运行在QEMU模拟器上的前端操作系统中各种驱动程序模块，在QEMU中模拟的各种后端 Device，中间用于前后端通信的 virtio 层，这一层是虚拟队列（virtqueue），是前后端通信的接口，表示驱动程序与设备间的数据传输机制，不过这不涉及具体实现。虚拟队列的下层是 virtio-ring，是数据传输机制的具体实现，主要由环形缓冲区和相关操作组成，用于保存前端驱动程序和后端虚拟设备之间进行命令和数据交互的信息。

.. image:: virtio-arch.png
   :align: center
   :name: virtio-arch


virtio设备
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

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

- ACKNOWLEDGE（1）：驱动程序发现了这个设备，并且认为这是一个有效的virtio设备；
- DRIVER (2) : 驱动程序知道该如何驱动这个设备；
- FAILED (128) : 由于某种错误原因，驱动程序无法正常驱动这个设备；
- FEATURES_OK (8) : 驱动程序认识设备的特征，并且与设备就设备特征协商达成一致；
- DRIVER_OK (4) : 驱动程序加载完成，设备可以正常工作了；
- DEVICE_NEEDS_RESET (64) ：设备触发了错误，需要重置才能继续工作。


**特征位** 

特征位用于表示VirtIO设备具有的各种特性。其中bit0-bit23是特定设备可以使用的feature bits， bit24-bit37预给队列和feature协商机制，bit38以上保留给未来其他用途。驱动程序与设备就设备的各种特性需要协商，形成一致的共识，这样才能正确的管理设备。


**通知**

驱动程序和设备在交互中，需要互通通知对方，驱动程序组织好相关命令/信息要通知设备去处理I/O事务，设备处理完I/O事务后，要通知驱动程序进行后续事务，如回收内存，向用户进程反馈I/O事务的处理结果等。

驱动程序通知设备可用``门铃 doorbell``机制，即写PIO或MMIO方式的设备特定寄存器，QEMU进行拦截再通知其模拟的设备。设备通知驱动程序一般用中断机制，即在QEMU中进行中断注入，让CPU响应并执行中断处理例程，来完成对I/O执行结果的处理。

**设备配置空间**

设备配置空间通常用于配置不常变动的设备参数（属性），或者初始化阶段需要时设置的设备参数。设备的特征位中包含表示配置空间是否存在的bit位，并可通过在特征位的末尾新添新的bit位来扩展配置空间。

.. _term-virtqueue:

**virtqueue虚拟队列**
~~~~~~~~~~~~~~~~~~~~~~~~~

在virtio设备上进行批量数据传输的机制被称为虚拟队列（virtqueue），virtio设备的虚拟队列（virtqueue）可以由各种数据结构（如数组、环形队列等）来具体实现。每个virtio设备可以拥有零个或多个virtqueue，每个virtqueue占用2个或者更多个4K的物理页。 virtqueue有Split Virtqueues（向下兼容的一种组织方式）和Packed Virtqueues（更高效的一种组织方式）两种模式。在Split virtqueues模式下，virtqueue被分成若干个部分， 每个部分都是前端驱动或者后端设备单向可写。 每个virtqueue都有一个16bit的 ``Queue Size`` 参数，表示队列的总长度。virtqueue由三部分地址连续的物理内存块组成：

- 描述符表 Descriptor Table：IO传输请求信息（描述符）的数组，每个描述符都是对某buffer 的address/length描述。buffer中包含IO传输请求的命令/数据/返回结果等。
- 可用环 Available Ring：记录了描述符表中被驱动程序更新的描述符的索引集合，需要后端的设备进行读取并完成相关I/O操作；
- 已用环 Used Ring：记录了描述符表中被设备更新的描述符的索引集合，需要前端的驱动程序进行读取并完成对I/O操作结果的响应；

**描述符表**

描述符表用来指向I/O传输请求的信息，即是驱动程序与设备进行交互的缓冲区（buffer），由 ``Queue Size`` 个Descriptor（描述符）组成。描述符中包括buffer的物理地址 -- addr字段，buffer的长度 -- len字段，可以链接到 ``next Descriptor`` 的next指针（用于把多个描述符链接成描述符链）。buffer所在物理地址空间需要操作系统或运行时在初始化时分配好，并在后续由驱动程序在其中填写IO传输相关的命令/数据，或者是设备返回I/O操作的结果。多个描述符（I/O操作命令，I/O操作数据块，I/O操作的返回结果）形成的描述符链可以表示一个完整的I/O操作请求。

**可用环** 

可用环中的条目是一个描述符链的头部描述符的索引值，并有头尾指针表示其可用条目范围，形成一个环形队列。它仅由驱动程序写入，并由设备读出。virtio设备通过读取可以环中的条目可获取驱动程序发出的I/O操作请求对应的描述符链，然后就可以进行进一步的处理了。描述符指向的缓冲区具有可读写属性，可读的缓冲区用于Driver发送数据，可写的缓冲区用于接收数据。比如对于（I/O操作命令 -- “读磁盘块”，I/O操作数据块 -- “数据缓冲区”，I/O操作的返回结果 --“结果缓冲区”）这三个描述符形成的链，可通过读取第一个描述符指向的缓冲区了解到是“读磁盘块”操作，这样就可把磁盘块数据通过DMA操作放到第二个描述符指向的“数据缓冲区”中，然后把“OK”写入到第三个描述符指向的“结果缓冲区”中。

**已用环**

已用环中的条目也一个是描述符链的头部描述符的索引值，并有头尾指针表示其已用条目的范围，形成一个环形队列。这个描述符是Device完成相应I/O处理后，将可用环中的对应“I/O操作的返回结果”的描述符索引值移入到已用环中，并通过轮询或中断机制来通知virtio驱动程序，并让virtio驱动程序读取已用环中的这个描述符，从而进行对设备完成I/O操作后的进一步处理。


基于MMIO方式的virtio设备
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

基于MMIO方式的virtio设备没有基于总线的设备探测机制。 所以操作系统采用Device Tree的方式来探测各种基于MMIO方式的virtio设备，从而操作系统能知道与设备相关的寄存器和所用的中断。基于MMIO方式的virtio设备提供了一组内存映射的控制寄存器，后跟一个设备特定的配置空间，在形式上是位于一个特定地址上的内存区域。一旦操作系统找到了这个内存区域，就可以获得与这个设备相关的各种寄存器信息。比如，我们在 `virtio-drivers` crate 中就定义了基于MMIO方式的virtio设备的寄存器区域：

.. _term-virtio-mmio-regs:

.. code-block:: Rust

   //virtio-drivers/src/header.rs Line 8
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

这里列出了部分关键寄存器和它的基本功能描述。在后续的设备初始化以及设备I/O操作中，会访问这里列出的寄存器。

接下来，我们将分析virtio驱动程序如何管理virtio设备来完成初始化和I/O操作的。

virtio驱动程序
-----------------------------------

这部分内容是各种virtio驱动程序的共性部分，主要包括驱动程序与设备的交互步骤，初始化设备，以及驱动程序执行过程中的一些实现细节。

驱动程序与设备之间的交互
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

.. https://rootw.github.io/2019/09/firecracker-virtio/

对于驱动程序和外设之间采用virtio机制（也可称为协议）进行交互的原理如下图所示。


.. image:: virtio-cpu-device-io2.png
   :align: center
   :name: virtio-cpu-device-io2


驱动程序与外设可以共同访问约定的物理内存。这些物理内存将保存具体的I/O请求和I/O响应。当驱动程序想要向设备发送命令/数据时，它会在约定的物理内存中填充命令/数据，各个物理内存块所在的起始地址和大小信息放在描述符表的描述符中，再把这些描述符链接在一起，形成描述符链。

而描述符链的起始描述符的索引信息会放入一个称为环形队列的数据结构，该队列可分为包含I/O请求的起始描述符的项组成的请求队列(可用环 Available Ring)和由包含I/O响应的描述符的项组成的响应队列(已用环 Used Ring)。

一个用户进程发起的I/O操作的处理过程大致可以分成如下四步：

1. 用户进程发出I/O请求，经过层层下传给到驱动程序，驱动程序将I/O请求的信息位置放入请求队列中并通过某种通知机制（如写某个设备寄存器）通知设备；
2. 设备收到通知后，从请求队列中的位置描述取出I/O请求并在内部进行实际I/O处理；
3. 设备完成I/O处理或出错后，将结果作为I/O响应的位置放入响应队列(已用环 Used Ring)并以某种通知机制（如外部中断）通知CPU；
4. 驱动程序根据响应队列(已用环 Used Ring)中的位置描述取出I/O处理结果并最终返回给用户进程。


.. image:: vring.png
   :align: center
   :name: vring


virtio驱动程序的执行过程
~~~~~~~~~~~~~~~~~~~~~~~~~~~~

**设备的初始化**

操作系统通过某种方式（设备发现，基于设备树的查找等）找到virtio设备后，驱动程序进行设备初始化的常规步骤如下所示：

1. 重启设备状态，设置设备状态域为0
2. 设置设备状态域为 ``ACKNOWLEDGE`` ，表明当前已经识别到了设备
3. 设置设备状态域为 ``DRIVER`` ，表明驱动程序知道如何驱动当前设备
4. 进行设备特定的安装和配置，包括协商特征位，建立virtqueue，访问设备配置空间等, 设置设备状态域为 ``FEATURES_OK``
5. 设置设备状态域为 ``DRIVER_OK`` 或者 ``FAILED`` （如果中途出现错误）

注意，上述的步骤不是必须都要做到的，但最终需要设置设备状态域为 ``DRIVER_OK`` ，这样驱动程序才能正常访问设备。


**虚拟队列的相关操作**

虚拟队列的相关操作包括两个部分：向设备提供新的可用缓冲区（可用环-->描述符-->缓冲区），以及处理设备使用的已用缓冲区（已用环-->描述符-->缓冲区）。 比如，最简单的virtio网络设备具有两个虚拟队列：发送虚拟队列和接收虚拟队列。驱动程序将发出（设备可读）的数据包（位于缓冲区中）添加到传输虚拟队列中，然后在数据包被设备使用后将其释放。接收（设备可写）缓冲区被添加到接收虚拟队列中，缓冲区中的数据包会被驱动程序处理。

这两部分的具体操作如下：

**向设备提供缓冲区**

驱动程序给设备的虚拟队列提供缓冲区的地址和长度信息，具体步骤如下所示：


1. 驱动程序将缓冲区的地址和长度信息放入描述符表中的空闲描述符中，并根据需要把多个描述符进行链接，形成一个描述符链（表示一个I/O操作请求）；
2. 驱动程序将描述符链头的索引放入可用环的下一个环条目中；
3. 如果可以进行批处理（batching），则可以重复执行步骤1和2，这样通过（可用环-->描述符-->缓冲区）来找到缓冲区；
4. 驱动程序执行适当的内存屏障操作，以确保设备能看到更新的描述符表和可用环，并追踪找到可用缓冲区；
5. 根据添加到可用环中的描述符链头的数量，增加 ``available idx`` ；
6. 驱动程序执行适当的内存屏障操作，以确保在检查通知前更新 ``available idx`` ；
7. 驱动程序会将"有可用的缓冲区"的通知发送给设备，这样设备根据它内部的idx信息与 ``available idx`` 的差值知道有多少个缓冲区要处理。


**将缓冲区放入描述符表**

缓冲区用于表示一个I/O请求的具体内容，由零个或多个设备可读/可写的物理地址连续的内存块组成（一般前面是可读的内存块，后续跟着可写的内存块）。我们把构成缓冲区的内存块称为缓冲区元素，把缓冲区映射到描述符表中以形成描述符链的具体步骤：

对于每个缓冲区元素 ``b`` ：

1. 获取下一个空闲描述符表条目 ``d`` ；
2. 将 ``d.addr`` 设置为 ``b`` 的的起始物理地址；
3. 将 ``d.len`` 设置为 ``b`` 的长度；
4. 如果 ``b`` 是设备可写的，则将 ``d.flags`` 设置为 ``VIRTQ_DESC_F_WRITE`` ，否则设置为0；
5. 如果 ``b`` 之后还有一个缓冲元素 ``c`` ：
   
   5.1 将 ``d.next`` 设置为下一个空闲描述符元素的索引；

   5.2 将 ``d.flags`` 中的 ``VIRTQ_DESC_F_NEXT`` 位置1；

**更新可用环**

描述符链头是上述步骤中的第一个 ``d`` ，即。描述符表条目的索引，指向缓冲区的第一部分。一个驱动程序实现可以执行以下的伪码操作（假定在与小端字节序之间进行适当的转换）来更新可用环：

.. code-block:: Rust

   avail.ring[avail.idx % qsz] = head;


但是，通常驱动程序可以在更新idx之前添加许多描述符链 （这时它们对于设备是可见的），因此通常要对驱动程序已添加的数目进行计数：

.. code-block:: Rust

   avail.ring[(avail.idx + added++) % qsz] = head;

idx总是递增，并在到达65536（2^16）后又回到0：

.. code-block:: Rust

   avail.idx += added;

一旦驱动程序更新了 ``avail.idx`` ，这表示描述符及其它指向的缓冲区能够被设备看到。这样设备就可以访问驱动程序创建的描述符链和它们指向的内存。驱动程序必须在idx更新之前执行合适的内存屏障操作，以确保设备看到最新的buffer内容。

**通知设备**

设备一般都是挂接在总线上，所以通知设备的实际方法是特定于总线的，且通常开销比较大。但在包含virtio设备的虚拟计算机中，我们不用太担心性能问题。驱动程序必须在设备读取标志或 ``avail_event`` 之前执行适当的内存屏障，以避免丢失通知。

从设备接收 ``已用缓冲区``

一旦设备使用（可以是读或写，取决于设备和虚拟队列的属性）了描述符所指向的缓冲区，设备便会向驱动程序发送 ``已用缓冲区通知（used buffer notification）`` 。

为了优化性能，驱动程序可以在处理已用环（used ring）时禁用 ``已用缓冲区通知`` ，但是要注意在清空环和重新启用通知之间丢失通知的问题。这通常可以通过在重新启用通知后重新检查更多的 ``已用缓冲区`` 的方法来解决，相关的伪代码如下所示：

.. code-block:: Rust

   //禁用 已用缓冲区通知
   virtq_disable_used_buffer_notifications(vq); 
   
   loop {
         //设备是否使用了描述符所指向的缓冲区
         if (vq.last_seen_used != le16_to_cpu(virtq.used.idx)) {
                  //使能 ``已用缓冲区通知``
                  virtq_enable_used_buffer_notifications(vq); 
                  mb(); //内存屏障操作
                  //设备是否使用了描述符所指向的缓冲区
                  if (vq.last_seen_used != le16_to_cpu(virtq.used.idx)) 
                     break; //设备使用了描述符所指向的缓冲区
                  //禁用 已用缓冲区通知
                  virtq_disable_used_buffer_notifications(vq); 
         } 
         //驱动程序开始响应和处理设备使用的缓冲区
         struct virtq_used_elem *e = virtq.used.ring[vq.last_seen_used%vsz]; 
         process_buffer(e); 
         vq.last_seen_used++; 
   }

virtio-blk驱动程序
------------------------------------------

virtio-blk设备是一种virtio存储设备，在QEMU模拟的RISC-V 64计算机中，以MMIO的方式来与驱动程序进行交互。

virtio-blk设备的关键数据结构
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

这里我们首先需要定义virtio-blk设备的结构：

.. code-block:: Rust

   pub struct VirtIOBlk<'a> {
      header: &'static mut VirtIOHeader,
      queue: VirtQueue<'a>,
      capacity: usize,
   }


其中的 ``VirtIOHeader`` 数据结构的内存布局与上一节描述 :ref:`virt-mmio设备的寄存器内存布局 <term-virtio-mmio-regs>` 是一致的。而 ``VirtQueue`` 数据结构与上一节描述的 :ref:`virtqueue <term-virtqueue>` 在表达的含义上基本一致的。

.. code-block:: Rust

   #[repr(C)]
   pub struct VirtQueue<'a> {
      dma: DMA, // DMA guard
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

其中成员变量 ``free_head`` 指空闲描述符链表头，初始时所有描述符通过 ``next`` 指针依次相连形成空闲链表，成员变量 ``last_used_idx`` 是指设备上次已取的已用环元素位置。成员变量 ``avail_idx`` 是指设备上次已取的已用环元素位置。

初始化virtio-blk设备
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
   
在 ``virtio-drivers`` crate的 ``examples\riscv\src\main.rs`` 文件中的 ``virtio_probe`` 函数识别出virtio-blk设备后，会调用 ``virtio_blk(header)`` 来完成对virtio-blk设备的初始化过程。其实具体的初始化过程与virtio规范中描述的一般virtio设备的初始化过程大致一样，步骤（实际实现可以简化）如下：
   
1. （忽略）通过将0写入状态寄存器来复位器件；
2. 将状态寄存器的ACKNOWLEDGE状态位置1；
3. 将状态寄存器的DRIVER状态位置1；
4. 从host_features寄存器读取设备功能；
5. 协商功能集并将接受的内容写如guest_features寄存器；
6. 将状态寄存器的FEATURES_OK状态位置1；
7. （忽略）重新读取状态寄存器，以确认设备已接受您的功能；
8. 执行特定于设备的设置：读取设备配置空间，建立虚拟队列；
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
- ``VirtIOHeader.queue_set`` 函数把VirtQueue实例的信息写到virtio-blk设备的MMIO寄存器中；
- 初始化VirtQueue实例中各个成员变量（主要是 ``dma`` ， ``desc`` ，``avail`` ，``used`` ）的值。

这时，对virtio-blk设备的初始化算是完成了，这时执行最后的第九步，将virtio-blk设备设置为活跃可用状态。

virtio-blk设备的I/O操作
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~


virtio-blk驱动程序发起的I/O请求包含操作类型(读或写)、起始扇区(块设备的最小访问单位的一个扇区的长度512字节)、内存地址、访问长度；请求处理完成后返回的I/O响应仅包含结果状态(成功或失败，读操作请求的读出扇区内容)。系统产生的一个I/O请求在内存中的数据结构分为三个部分：Header（请求头部，包含操作类型和起始扇区）；Data（数据区，包含地址和长度）；Status（结果状态）。

virtio-blk设备使用 ``VirtQueue`` 数据结构来表示虚拟队列进行数据传输，此数据结构主要由三段连续内存组成：描述符表 ``Descriptor[]`` 、环形队列结构的 ``AvailRing`` 和 ``UsedRing``  。驱动程序和virtio-blk设备都能访问到此数据结构。
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

可用环 ``AvailRing`` 的结构为：

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

可用环由头部的 ``flags`` 和 ``idx`` 域及 ``ring`` 数组组成： ``flags`` 与通知机制相关； ``idx`` 代表最新放入IO请求的编号，从零开始单调递增，将其对队列长度取余即可得该I/O请求在可用环数组中的索引；可用环数组元素用来存放I/O请求占用的首个描述符在描述符表中的索引，数组长度等于可用环的长度(不开启event_idx特性)。

已用环 ``UsedRing`` 的结构为：

.. code-block:: Rust

   #[repr(C)]
   #[derive(Debug)]
   struct UsedRing {
      flags: Volatile<u16>,
      idx: Volatile<u16>,
      ring: [UsedElem; 32],       // actual size: queue_size
      avail_event: Volatile<u16>, // unused
   }


已用环由头部的 ``flags`` 和 ``idx`` 域及 ``ring`` 数组组成： ``flags`` 与通知机制相关； ``idx`` 代表最新放入I/O响应的编号，从零开始单调递增，将其对队列长度取余即可得该I/O响应在已用环数组中的索引；已用环数组元素主要用来存放I/O响应占用的首个描述符在描述符表中的索引， 数组长度等于已用环的长度(不开启event_idx特性)。



针对用户进程发出的I/O请求，经过系统调用，文件系统等一系列处理后，最终会形成对virtio-blk驱动程序的调用。对于写操作，具体实现如下：


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

1. 一个完整的virtio-blk的I/O写请求由三部分组成，包括表示I/O写请求信息的结构 ``BlkReq`` ，要传输的数据块 ``buf``，一个表示设备响应信息的结构 ``BlkResp``  。这三部分需要三个描述符来表示；
2. （驱动程序处理）接着调用 ``VirtQueue.add`` 函数，从描述符表中申请三个空闲描述符，每项指向一个内存块，填写上述三部分的信息，并将三个描述符连接成一个描述符链表；
3. （驱动程序处理）接着调用 ``VirtQueue.notify`` 函数，写MMIO模式的 ``queue_notify`` 寄存器，即向 virtio-blk设备发出通知；
4. （设备处理）virtio-blk设备收到通知后，通过比较 ``last_avail`` (初始为0)和 ``AvailRing`` 中的 ``idx`` 判断是否有新的请求待处理(如果 ``last_vail`` 小于 ``AvailRing`` 中的 ``idx`` ，则表示有新请求)。如果有，则 ``last_avail`` 加1，并以 ``last_avail`` 为索引从描述符表中找到这个I/O请求对应的描述符链来获知完整的请求信息，并完成存储块的I/O写操作；
5. （设备处理）设备完成I/O写操作后(包括更新包含 ``BlkResp`` 的Descriptor)，将已完成I/O的描述符放入UsedRing对应的ring项中，并更新idx,代表放入一个响应；如果设置了中断机制，还会产生中断来通知操作系统响应中断；
6. （驱动程序处理）驱动程序可用轮询机制查看设备是否有响应（持续调用  ``VirtQueue.can_pop`` 函数），通过比较内部的 ``VirtQueue.last_used_idx`` 和 ``VirtQueue.used.idx`` 判断是否有新的响应。如果有，则取出响应(并更新 ``last_used_idx`` )，将完成响应对应的三项Descriptor回收，最后将结果返回给用户进程。当然，也可通过中断机制来响应。


I/O读请求的处理过程与I/O写请求的处理过程几乎一样，这里就不在详细说明了。具体可以看看 ``virtio-drivers/src/blk.rs`` 文件中的 ``VirtIOBlk.read_block`` 函数的实现。


virtio-gpu驱动程序
------------------------------------------

让操作系统能够显示图形是我们的想要完成的有趣目标。这可以通过在QEMU或带显示屏的开发板上写显示驱动程序来完成。这里我们主要介绍如何驱动基于QEMU的virtio-gpu虚拟显示设备。我们看到的图形显示屏幕其实是由一个一个的像素点来组成的。显示驱动程序的主要目标就是把每个像素点用内存单元来表示，并把代表所有这些像素点的内存区域（也称显示内存，显存， frame buffer）“通知”显示I/O控制器（也称图形适配器，graphics adapter），然后显示I/O控制器会根据内存内容渲染到图形显示屏上。

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

``header`` 结构是virtio设备的共有属性，包括版本号、设备id、设备特征等信息。显存区域 ``frame_buffer_dma`` 是一块要由操作系统或运行时分配的内存，后续的像素点的值就会写在这个区域中。virtio-gpu驱动程序与virtio-gpu设备之间通过两个 virtqueue 来进行交互访问，``control_queue`` 用于驱动程序发送显示相关控制命令， ``cursor_queue`` 用于驱动程序发送显示鼠标更新的相关控制命令（这里暂时不用）。 ``queue_buf_dma`` 是存放控制命令和返回结果的内存， ``queue_buf_send`` 和 ``queue_buf_recv`` 是 ``queue_buf_dma`` 的切片。

初始化virtio-gpu设备
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

在 ``virtio-drivers`` crate的 ``examples\riscv\src\main.rs`` 文件中的 ``virtio_probe`` 函数识别出virtio-gpu设备后，会调用 ``virtio_gpu(header)`` 函数来完成对virtio-gpu设备的初始化过程。virtio-gpu设备初始化的工作主要是查询显示设备的信息（如分辨率等），并将该信息用于初始显示扫描（scanout）设置。具体过程如下：

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

虽然virtio-gpu初始化完毕，但它目前还不能进行显示。为了能够进行正常的显示，我们还需建立显存区域 frame buffer，并绑定在virtio-gpu设备上。这主要是通过 ``VirtIOGpu.setp_framebuffer`` 函数来完成的。

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


上面的函数主要完成的工作有如下几个步骤，其实就是驱动程序给virtio-gpu设备发控制命令，建立好显存区域：

1. 发出 ``GetDisplayInfo`` 命令，获得virtio-gpu设备的显示分辨率;
1. 发出 ``ResourceCreate2D`` 命令，让设备以分辨率大小（ ``width *height`` ），像素信息（ ``Red/Green/Blue/Alpha`` 各占1字节大小，即一个像素占4字节），来配置设备显示资源；
1. 分配 ``width *height * 4`` 字节的连续物理内存空间作为显存， 发出 ``ResourceAttachBacking`` 命令，让设备把显存附加到设备显示资源上；
1. 发出 ``SetScanout`` 命令，把设备显示资源链接到显示扫描输出上，这样才能让显存的像素信息显示出来；

到这一步，才算是把virtio-gpu设备初始化完成了。


virtio-gpu设备的I/O操作
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

接下来的显示操作比较简单，就是在显存中更新像素信息，然后给设备发出刷新指令，就可以显示了，具体的示例代码如下：

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


测试virtio设备
-------------------------------   

在 ``virtio-drivers`` crate的 ``examples\riscv\src\main.rs`` 文件是一个可让virtio-blk设备读写磁盘，让virtio-gpu设备显示图像的测试用例，我们可以通过执行如下命令来尝试这些virtio设备：

.. code:: shell

   $ cd virtio-driver/examples/riscv64
   $ make run   

.. image:: virtio-test-example.png
   :align: center
   :name: virtio-test-example

目前virtio-blk驱动程序已经包含在第七章实现的操作系统中，有兴趣的同学可以参考这个例子，把virtio-gpu驱动程序也包含在本章的操作系统中。当然也鼓励设计实现其他更多的virtio设备的驱动程序，让操作系统有更有趣的I/O交互能力。