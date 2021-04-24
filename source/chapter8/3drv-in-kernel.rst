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

`virtio_probe` 函数会进一步查找virtio设备节点中的`reg` 属性，从而可以找到virtio设备的具体类型（如 `DeviceType::Block` 块设备类型）等参数。接下来，我们就可以对具体的virtio设备进行初始好和进行具体I/O操作了。

virtio块设备
------------------------------------------

virtio-blk是一种存储设备，设备驱动发起的I/O请求包含操作类型(读或写)、起始扇区(一个扇区为512节节，是块设备的存储单位)、内存地址、访问长度；请求处理完成后返回的IO响应仅包含结果状态(成功或失败)。如下示例图中，系统产生了一个I/O请求，它在内存上的数据结构分为三个部分：Header，即请求头部，包含操作类型和起始扇区；Data，即数据区，包含地址和长度；Status，即结果状态。

virtio-blk设备使用一个环形队列结构(IO RING)，它由三段连续内存组成：Descriptor Table、Avail Queue和Used Queue：

Descriptor Table由固定长度(16字节)的Descriptor组成，其个数等于环形队列(IO RING)长度，其中每个Descriptor包含四个域：addr代表某段内存的起始地址，长度为8个字节；len代表某段内存的长度，本身占用4个字节(因此代表的内存段最大为4GB)；flags代表内存段读写属性等，长度为2个字节；next代表下一个内存段对应的Descpriptor在Descriptor Table中的索引，因此通过next字段可以将一个请求对应的多个内存段连接成链表。

Avail Queue由头部的flags和idx域及entry数组(entry代表数组元素)组成：flags与通知机制相关；idx代表最新放入IO请求的编号，从零开始单调递增，将其对队列长度取余即可得该IO请求在entry数组中的索引；entry数组元素用来存放IO请求占用的首个Descriptor在Descriptor Table中的索引，数组长度等于环形队列长度(不开启event_idx特性)。

Used Queue由头部的flags和idx域及entry数组(entry代表数组元素)组成：flags与通知机制相关；idx代表最新放入IO响应的编号，从零开始单调递增，将其对队列长度取余即可得该IO响应在entry数组中的索引；entry数组元素主要用来存放IO响应占用的首个Descriptor在Descriptor Table中的索引(还有一个len域，virtio-blk并不使用)， 数组长度等于环形队列长度(不开启event_idx特性)。
环形队列结构(IO RING)被CPU和设备同见。仅CPU可见变量为free_head(空闲Descriptor链表头，初始时所有Descriptor通过next指针依次相连形成空闲链表)和last_used(当前已取的used元素位置)。仅设备可见变量为last_avail(当前已取的avail元素位置)。

针对示例图中的IO请求，处理流程分析如下：

第一步，CPU放请求。由于示例IO请求在内存中由Header、Data和Status三段内存组成，因此要从Descriptor Table中申请三个空闲项，每项指向一段内存，并将三段内存连接成链表。这里假设我们申请到了前三个Descriptor(free_head更新为3，表示下一个空闲项从索引3开始，因为0、1、2已被占用)，那么会将第一个Descriptor的索引值0填入Aail Queue的第一个entry中，并将idx更新为1，代表放入1个请求；

第二步，设备取请求。设备收到通知后，通过比较设备内部的last_avail(初始为0)和Avail Queue中的idx(当前为1)判断是否有新的请求待处理(如果last_vail小于Avail Queue中的idx，则有新请求)。如果有，则取出请求(更新last_avail为1 )并以entry的值为索引从Descriptor Table中找到请求对应的所有Descriptor来获知完整的请求信息。

第三步，设备放响应。设备完成IO处理后(包括更新Status内存段内容)，将已完成IO的Descriptor Table索引放入Used Queue对应的entry中，并将idx更新为1,代表放入1个响应；

第四步，CPU取响应。CPU收到中断后，通过比较内部的last_used(初始化0)和Used Queue中的idx(当前为1)判断是否有新的响应(逻辑类似Avail Queue)。如果有，则取出响应(更新last_used为1)并将Status中断的结果返回应用，最后将完成响应对应的三项Descriptor以链表方式插入到free_head头部。


virtio显示设备
------------------------------------------