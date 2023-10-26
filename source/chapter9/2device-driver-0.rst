外设平台
=========================================

本节导读
-----------------------------------------

现在我们有了对设备的基本了解，接下来就要考虑如何编写驱动程序来控制各种外设了。本节首先讲述了驱动程序要完成的主要功能，包括初始化设备，接收用户进程的I/O请求并给设备发出I
/O命令，响应设备发出的通知，完成用户进程的I/O请求。然后介绍了计算机硬件系统中除了CPU/内存之外的其他重要的外设和相关I/O控制器，以及如何通过编程来获取外设相关信息。

驱动程序概述
----------------------------------------

很难为驱动程序提供一个精确的定义。基本而言，驱动程序是一种软件组件，是操作系统与机外设之间的接口，可让操作系统和设备彼此通信。从操作系统架构上看，驱动程序与I/O设备靠的更近，离应用程序更远，这使得驱动程序需要站在协助所有进程的全局角度来处理各种I/O操作。这也就意味着在驱动程序的设计实现中，尽量不要与单个进程建立直接的联系，而是在全局角度对I/O设备进行统一处理。

上面只是介绍了CPU和I/O设备之间的交互手段。如果从操作系统角度来看，我们还需要对特定设备编写驱动程序。它一般需包括如下一些操作：

1. 定义设备相关的数据结构，包括设备信息、设备状态、设备操作标识等
2. 设备初始化，即完成对设备的初始配置，分配I/O操作所需的内存，设置好中断处理例程
3. 如果设备会产生中断，需要有处理这个设备中断的中断处理例程（Interrupt Handler）
4. 根据操作系统上层模块（如文件系统）的要求（如读磁盘数据），给I/O设备发出命令，检测和处理设备出现的错误
5. 与操作系统上层模块或应用进行交互，完成上层模块或应用的要求（如上传读出的磁盘数据）

从驱动程序I/O操作的执行模式上看，主要有两种模式的I/O操作：异步和同步。同步模式下的处理逻辑类似函数调用，从应用程序发出I/O请求，通过同步的系统调用传递到操作系统内核中，操作系统内核的各个层级进行相应处理，并最终把相关的I/O操作命令转给了驱动程序。一般情况下，驱动程序完成相应的I/O操作会比较慢（相对于CPU而言），所以操作系统会让代表应用程序的进程进入等待状态，进行进程切换。但相应的I/O操作执行完毕后（操作系统通过轮询或中断方式感知），操作系统会在合适的时机唤醒等待的进程，从而进程能够继续执行。

异步I/O操作是一个效率更高的执行模式，即应用程序发出I/O请求后，并不会等待此I/O操作完成，而是继续处理应用程序的其它任务（这个任务切换会通过运行时库或操作系统来完成）。调用异步I/O操作的应用程序需要通过某种方式（比如某种异步通知机制）来确定I/O操作何时完成。注：这部分可以通过协程技术来实现，但目前我们不会就此展开讨论。

编写驱动程序代码其实需要的知识储备还是比较多的，需要注意如下的一些内容：

1. 了解硬件规范：从而能够正确地与硬件交互，并能处理访问硬件出错的情况；
2. 了解操作系统，由于驱动程序与它所管理的设备会同时执行，也可能与操作系统其他模块并行/并发访问相关共享资源，所以需要考虑同步互斥的问题（后续会深入讲解操作系统同步互斥机制），并考虑到申请资源失败后的处理；
3. 理解驱动程序执行中所在的可能的上下文环境：如果是在进行中断处理（如在执行 ``trap_handler`` 函数），那是在中断上下文中执行；如果是在代表进程的内核线程中执行后续的I/O操作（如收发TCP包），那是在内核线程上下文执行。这样才能写出正确的驱动程序。


硬件系统架构
-----------------------------------------

设备树
~~~~~~~~~~~~~~~~~~~~~~~

首先，我们需要了解OS管理的计算机硬件系统-- ``QEMU riscv-64 virt machine`` ，特别是其中的各种外部设备。 `virt` 表示了一台虚拟的RISC-V 64计算机，CPU的个数是可以通过参数 ``-cpu num`` 配置的，内存也是可通过参数 ``-m numM/G`` 来配置。这台虚拟计算机还有很多外设信息，每个设备在物理上连接到了父设备上最后再通过总线等连接起来构成一整个设备树。QEMU 可以把它模拟的机器细节信息全都导出到dtb格式的二进制文件中，并可通过 ``dtc`` （Device Tree Compiler）工具转成可理解的文本文件。如想详细了解这个文件的格式说明可以参考  `Devicetree Specification <https://www.devicetree.org/specifications/>`_ 。

.. code-block:: console

   $ qemu-system-riscv64 -machine virt -machine dumpdtb=riscv64-virt.dtb -bios default
      qemu-system-riscv64: info: dtb dumped to riscv64-virt.dtb. Exiting.
   $ dtc -I dtb -O dts -o riscv64-virt.dts riscv64-virt.dtb
   $ less riscv64-virt.dts
   #就可以看到QEMU RV64 virt计算机的详细硬件（包括各种外设）细节，包括CPU，内存，串口，时钟和各种virtio设备的信息。
   

一个典型的设备树如下图所示：

.. image:: device-tree.png
   :align: center
   :name: device-tree

.. note::

   **设备树与设备节点属性**

   设备树（Device Tree）是一种数据结构，用于表示硬件系统的结构和功能。 它是一个文本文件，描述了硬件系统的结构和功能，并将这些信息提供给操作系统。设备树包含了关于硬件系统的信息，如：

   - 处理器的类型和数量
   - 板载设备（如存储器、网卡、显卡等）的类型和数量
   - 硬件接口（如 I2C、SPI、UART 等）的类型和地址信息

   设备树中的节点是用来描述硬件设备的信息的。 一个设备树节点包含了一个或多个属性，每个属性都是一个键-值对，用来描述设备的某一特定信息。而操作系统就是通过这些节点上的信息来实现对设备的识别和初始化。具体而言，一个设备节点上会有一些常见的属性：

   - compatible：表示设备的类型，可以是设备的厂商名、产品名等，如 "virtio,mmio" 指的是这个设备通过 virtio 协议、MMIO（内存映射 I/O）方式来驱动
   - reg：表示设备在系统中的地址空间位置
   - interrupts：表示设备支持的中断信号

   设备树在很多嵌入式系统中都得到了广泛应用，它是一种常用的方法，用于将硬件（特别是外设）信息传递给操作系统。在桌面和服务器系统中，PCI总线可以起到设备树的作用，通过访问PCI总线上特定地址空间，也可以遍历出具有挂在PCI总线上的各种PCI设备。



我们可以运行 ``virtio_drivers`` crate中的一个在裸机环境下的测试用例，来动态查看 `qemu-system-riscv64` 模拟的 `virt` 计算机的设备树信息：

.. code-block:: console

   # 获取virto_driver git仓库源码
   $ git clone https://github.com/rcore-os/virtio-drivers.git
   # 在 qemu 模拟器上运行测试用例：
   $ cd virtio-drivers/examples/riscv
   $ make qemu
   # qemu命令行参数
      qemu-system-riscv64 \
        -machine virt \
        -serial mon:stdio \
        -bios default \
        -kernel target/riscv64imac-unknown-none-elf/release/riscv \
        -global virtio-mmio.force-legacy=false \
        -drive file=target/riscv64imac-unknown-none-elf/release/img,if=none,format=raw,id=x0 \
        -device virtio-blk-device,drive=x0 \
        -device virtio-gpu-device \
        -device virtio-mouse-device \
        -device virtio-net-device
   ...


在上面的 `qemu` 命令行参数中，可以看到 `virt` 计算机中配置了基于virtio协议的存储块设备 `virtio-blk-device` 、图形显示设备 `virtio-gpu-device` 、 鼠标设备 `virtio-mouse-device` 和 网卡设备 `virtio-net-device` 。 通过看到测试用例扫描出的设备树信息，且可以看到通过 `virtio_gpu` 显示的漂亮的图形：

.. code-block:: console

   [ INFO] device tree @ 0x87000000
   [ INFO] walk dt addr=0x10008000, size=0x1000
   [ INFO] Device tree node virtio_mmio@10008000: Some("virtio,mmio")
   [ INFO] Detected virtio MMIO device with vendor id 0x554D4551, device type Block, version Modern
   [ INFO] device features: SEG_MAX | GEOMETRY | BLK_SIZE | FLUSH | TOPOLOGY | CONFIG_WCE | DISCARD | WRITE_ZEROES | RING_INDIRECT_DESC | RING_EVENT_IDX | VERSION_1
   [ INFO] config: 0x10008100
   [ INFO] found a block device of size 16KB
   [ INFO] virtio-blk test finished
   [ INFO] walk dt addr=0x10007000, size=0x1000
   [ INFO] Device tree node virtio_mmio@10007000: Some("virtio,mmio")
   [ INFO] Detected virtio MMIO device with vendor id 0x554D4551, device type GPU, version Modern
   [ INFO] Device features EDID | RING_INDIRECT_DESC | RING_EVENT_IDX | VERSION_1
   [ INFO] events_read: 0x0, num_scanouts: 0x1
   [ INFO] GPU resolution is 1280x800
   [ INFO] => RespDisplayInfo { header: CtrlHeader { hdr_type: OkDisplayInfo, flags: 0, fence_id: 0, ctx_id: 0, _padding: 0 }, rect: Rect { x: 0, y: 0, width: 1280, height: 800 }, enabled: 1, flags: 0 }
   [ INFO] virtio-gpu test finished
   [ INFO] walk dt addr=0x10006000, size=0x1000
   [ INFO] Device tree node virtio_mmio@10006000: Some("virtio,mmio")
   [ INFO] Detected virtio MMIO device with vendor id 0x554D4551, device type Input, version Modern
   [ INFO] Device features: RING_INDIRECT_DESC | RING_EVENT_IDX | VERSION_1
   [ INFO] walk dt addr=0x10005000, size=0x1000
   [ INFO] Device tree node virtio_mmio@10005000: Some("virtio,mmio")
   [ INFO] Detected virtio MMIO device with vendor id 0x554D4551, device type Network, version Modern
   [ INFO] Device features CTRL_GUEST_OFFLOADS | MAC | MRG_RXBUF | STATUS | CTRL_VQ | CTRL_RX | CTRL_VLAN | CTRL_RX_EXTRA | GUEST_ANNOUNCE | CTL_MAC_ADDR | RING_INDIRECT_DESC | RING_EVENT_IDX | VERSION_1


.. image:: virtio-test-example2.png
   :align: center
   :scale: 30 %
   :name: virtio-test-example2

在上述输出中，我们看到了 `type` 为 `Block` 、 `GPU` 、`Input` 和 `Network` 的设备，所以我们的测例确实通过发现了这些设备，还通过 `GPU` 设备进行操作，让我们终于可以看到图形了。


传递设备树信息
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

操作系统在启动后需要了解计算机系统中所有接入的设备，这就要有一个读取全部已接入设备信息的能力，而设备信息放在哪里，又是谁帮我们来做的呢？在 RISC-V 中，这个一般是由 bootloader，即 OpenSBI or RustSBI 固件完成的。它来完成对于包括物理内存在内的各外设的探测，将探测结果以 **设备树二进制对象（DTB，Device Tree Blob）** 的格式保存在物理内存中的某个地方。然后bootloader会启动操作系统，即把放置DTB的物理地址将放在 ``a1`` 寄存器中，而将会把 HART ID （**HART，Hardware Thread，硬件线程，可以理解为执行的 CPU 核**）放在 ``a0`` 寄存器上，然后跳转到操作系统的入口地址处继续执行。

在 ``virtio_drivers/examples/riscv`` 目录下，我们可以看到 ``main.rs`` 文件，它是一个裸机环境下的测试用例，它会在启动后打印出设备树信息：

.. code-block:: Rust
   :linenos:

   //virtio_drivers/examples/riscv/src/main.rs
   #[no_mangle]
   extern "C" fn main(_hartid: usize, device_tree_paddr: usize) {
      ...
      init_dt(device_tree_paddr);
      ...
   }

   fn init_dt(dtb: usize) {
      info!("device tree @ {:#x}", dtb);
      // Safe because the pointer is a valid pointer to unaliased memory.
      let fdt = unsafe { Fdt::from_ptr(dtb as *const u8).unwrap() };
      walk_dt(fdt);
   }

   fn walk_dt(fdt: Fdt) {
      for node in fdt.all_nodes() {
         if let Some(compatible) = node.compatible() {
               if compatible.all().any(|s| s == "virtio,mmio") {
                  virtio_probe(node);
               }
         }
      }
   }


我们只需要给 `main` 函数增加两个参数（即 ``a0`` 和 ``a1`` 寄存器中的值 ）即可，这样测试用例就获得了bootloader传来的放置DTB的物理地址。然后 ``init_dt`` 函数会将这个地址转换为 ``Fdt`` 类型，然后遍历整个设备树，找到所有的 ``virtio,mmio`` 设备（其实就是 QEMU 模拟的各种virtio设备），然后调用 ``virtio_probe`` 函数来显示设备信息并初始化这些设备。

解析设备树信息
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

`virtio_probe` 函数会进一步查找virtio设备节点中的`reg` 属性，从而可以找到virtio设备的具体类型（如 `DeviceType::Block` 块设备类型）等参数。这样我们就可以对具体的virtio设备进行初始化和进行具体I/O操作了。``virtio_probe`` 函数的主体部分如下所示：

.. code-block:: Rust
   :linenos:

   fn virtio_probe(node: FdtNode) {
      //分析 reg 信息
      if let Some(reg) = node.reg().and_then(|mut reg| reg.next()) {
         let paddr = reg.starting_address as usize;
         let size = reg.size.unwrap();
         let vaddr = paddr;
         info!("walk dt addr={:#x}, size={:#x}", paddr, size);
         info!(
               "Device tree node {}: {:?}",
               node.name,
               node.compatible().map(Compatible::first),
         );
         let header = NonNull::new(vaddr as *mut VirtIOHeader).unwrap();
         //判断virtio设备类型
         match unsafe { MmioTransport::new(header) } {
               Err(e) => warn!("Error creating VirtIO MMIO transport: {}", e),
               Ok(transport) => {
                  info!(
                     "Detected virtio MMIO device with vendor id {:#X}, device type {:?}, version {:?}",
                     transport.vendor_id(),
                     transport.device_type(),
                     transport.version(),
                  );
                  virtio_device(transport);
               }
         }
      }
   }
   // 对不同的virtio设备进行进一步的初始化工作
   fn virtio_device(transport: impl Transport) {
      match transport.device_type() {
         DeviceType::Block => virtio_blk(transport),
         DeviceType::GPU => virtio_gpu(transport),
         DeviceType::Input => virtio_input(transport),
         DeviceType::Network => virtio_net(transport),
         t => warn!("Unrecognized virtio device: {:?}", t),
      }
   }

显示图形的操作其实很简单，都在 ``virtio_gpu`` 函数中：

.. code-block:: Rust
   :linenos:

   fn virtio_gpu<T: Transport>(transport: T) {
      let mut gpu = VirtIOGpu::<HalImpl, T>::new(transport).expect("failed to create gpu driver");
      // 获得显示设备的长宽信息
      let (width, height) = gpu.resolution().expect("failed to get resolution");
      let width = width as usize;
      let height = height as usize;
      info!("GPU resolution is {}x{}", width, height);
      // 设置显示缓冲区
      let fb = gpu.setup_framebuffer().expect("failed to get fb");
      // 设置显示设备中的每个显示点的红、绿、蓝分量值，形成丰富色彩的图形
      for y in 0..height {
         for x in 0..width {
               let idx = (y * width + x) * 4;
               fb[idx] = x as u8;
               fb[idx + 1] = y as u8;
               fb[idx + 2] = (x + y) as u8;
         }
      }
      gpu.flush().expect("failed to flush");
      info!("virtio-gpu test finished");
   }

可以发现，对各种设备的控制，大部分都是基于对特定内存地址的读写来完成的，这就是MMIO的I/O访问方式。看到这，也许你会觉得查找、初始化和控制计算机中的设备其实没有特别复杂，前提是你对外设的硬件规范有比较深入的了解。不过当与操作系统结合在一起后，还需要和操作系统内部的其他内核模块（如文件系统等）进行交互，复杂性就会增加。我们会逐步展开这方面的讲解。

平台级中断控制器
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

在之前的操作系统中，已经涉及到中断处理，但还没有处理外设（时钟中断时RISC-V 处理器产生的）产生的中断。如果要让操作系统处理外设中断，就需要对中断控制器进行初始化设置。在RISC-V中，与外设连接的I/O控制器的一个重要组成是平台级中断控制器（Platform-Level Interrupt Controller，PLIC），它的一端汇聚了各种外设的中断信号，另一端连接到CPU的外部中断引脚上。当一个外部设备发出中断请求时，PLIC 会将其转发给 RISC-V CPU, CPU 会执行对应的中断处理程序来响应中断。通过RISC-V的 ``mie`` 寄存器中的 ``meie`` 位，可以控制这个引脚是否接收外部中断信号。当然，通过RISC-V中M Mode的中断委托机制，也可以在RISC-V的S Mode下，通过 ``sie`` 寄存器中的 ``seie`` 位，对中断信号是否接收进行控制。

.. note::

   **中断控制器（Interrupt Controller）**

   计算机中的中断控制器是一种硬件，可帮助处理器处理来自多个不同I/O设备的中断请求（Interrupt Request，简称IRQ）。这些中断请求可能同时发生，并首先经过中断控制器的处理，即中断控制器根据 IRQ 的优先级对同时发生的中断进行排序，然后把优先级最高的IRQ传给处理器，让操作系统执行相应的中断处理例程 （Interrupt Service Routine，简称ISR）。

CPU可以通过MMIO方式来对PLIC进行管理，下面是一些与PLIC相关的寄存器：

.. code-block:: console

    寄存器	        地址    	功能描述
    Priority      0x0c00_0000	 设置特定中断源的优先级
    Pending	  0x0c00_1000    包含已触发（正在处理）的中断列表
    Enable	  0x0c00_2000	 启用/禁用某些中断源
    Threshold     0x0c20_0000	 设置中断能够触发的阈值
    Claim         0x0c20_0004	 按优先级顺序返回下一个中断
    Complete      0x0c20_0004	 写操作表示完成对特定中断的处理

在QEMU ``qemu/include/hw/riscv/virt.h`` 的源码中，可以看到

.. code-block:: C
   :linenos:

   enum {
        UART0_IRQ = 10,
        RTC_IRQ = 11,
        VIRTIO_IRQ = 1, /* 1 to 8 */
        VIRTIO_COUNT = 8,
        PCIE_IRQ = 0x20, /* 32 to 35 */
        VIRTIO_NDEV = 0x35 /* Arbitrary maximum number of interrupts */
   };


可以看到串口UART0的中断号是10，virtio设备的中断号是1~8。通过 ``dtc`` （Device Tree Compiler）工具生成的文本文件，我们也可以发现上述中断信号信息，以及基于MMIO的外设寄存器信息。在后续的驱动程序中，这些信息我们可以用到。


操作系统如要响应外设的中断，需要做两方面的初始化工作。首先是完成第三章讲解的中断初始化过程，并需要把 ``sie`` 寄存器中的 ``seie`` 位设置为1，让CPU能够接收通过PLIC传来的外部设备中断信号。然后还需要通过MMIO方式对PLIC的寄存器进行初始设置，才能让外设产生的中断传到CPU处。其主要操作包括：

- 设置外设中断的优先级
- 设置外设中断的阈值，优先级小于等于阈值的中断会被屏蔽
- 激活外设中断，即把 ``Enable`` 寄存器的外设中断编号为索引的位设置为1

上述操作的具体实现，可以参考 `ch9` 分支中的内核开发板初始化代码 ``qemu.rs`` 中的 ``device_init()`` 函数：

.. code-block:: Rust
   :linenos:

   // os/src/boards/qemu.rs
   pub fn device_init() {
      use riscv::register::sie;
      let mut plic = unsafe { PLIC::new(VIRT_PLIC) };
      let hart_id: usize = 0;
      let supervisor = IntrTargetPriority::Supervisor;
      let machine = IntrTargetPriority::Machine;
      // 设置PLIC中外设中断的阈值
      plic.set_threshold(hart_id, supervisor, 0);
      plic.set_threshold(hart_id, machine, 1);
      // 使能PLIC在CPU处于S-Mode下传递键盘/鼠标/块设备/串口外设中断
      // irq nums: 5 keyboard, 6 mouse, 8 block, 10 uart
      for intr_src_id in [5usize, 6, 8, 10] {
         plic.enable(hart_id, supervisor, intr_src_id);
         plic.set_priority(intr_src_id, 1);
      }
      // 设置S-Mode CPU使能中断
      unsafe {
         sie::set_sext();
      }
   }

但外设产生中断后，CPU并不知道具体是哪个设备传来的中断，这可以通过读PLIC的 ``Claim`` 寄存器来了解。 ``Claim`` 寄存器会返回PLIC接收到的优先级最高的中断；如果没有外设中断产生，读 ``Claim`` 寄存器会返回 0。

操作系统在收到中断并完成中断处理后，还需通知PLIC中断处理完毕。CPU需要在PLIC的 ``Complete`` 寄存器中写入对应中断号为索引的位，来通知PLIC中断已处理完毕。

上述操作的具体实现，可以参考 `ch9` 分支的开发板初始化代码 ``qemu.rs`` 中的 ``irq_handler()`` 函数：


.. code-block:: Rust
   :linenos:

   // os/src/boards/qemu.rs
   pub fn irq_handler() {
      let mut plic = unsafe { PLIC::new(VIRT_PLIC) };
      // 读PLIC的 ``Claim`` 寄存器获得外设中断号
      let intr_src_id = plic.claim(0, IntrTargetPriority::Supervisor);
      match intr_src_id {
         5 => KEYBOARD_DEVICE.handle_irq(),
         6 => MOUSE_DEVICE.handle_irq(),
         8 => BLOCK_DEVICE.handle_irq(),
         10 => UART.handle_irq(),
         _ => panic!("unsupported IRQ {}", intr_src_id),
      }
      // 通知PLIC中断已处理完毕
      plic.complete(0, IntrTargetPriority::Supervisor, intr_src_id);
   }

这样同学们就大致了解了计算机中外设的发现、初始化、I/O处理和中断响应的基本过程。不过大家还没有在操作系统中实现面向具体外设的设备驱动程序。接下来，我们就会分析串口设备驱动、块设备设备驱动和显示设备驱动的设计与实现。

