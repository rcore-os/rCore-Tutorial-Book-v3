内核与应用的地址空间
================================================

页表 ``PageTable`` 只能以页为单位帮助我们维护一个地址空间的地址转换关系，它对于整个地址空间并没有一个全局的掌控。本节
我们就在内核中实现地址空间的抽象。

实现地址空间抽象
------------------------------------------

我们以逻辑段 ``MemoryArea`` 为单位描述一个地址空间。所谓逻辑段，就是指地址区间中的一段实际可用（即 MMU 通过查多级页表
可以正确完成地址转换）的虚拟地址区间，该区间内包含的所有虚拟页面都以一种相同的方式映射到物理页帧。

.. code-block:: rust

    // os/src/mm/memory_set.rs

    pub struct MapArea {
        vpn_range: VPNRange,
        data_frames: BTreeMap<VirtPageNum, FrameTracker>,
        map_type: MapType,
        map_perm: MapPermission,
    }

其中 ``VPNRange`` 描述一段虚拟页号的连续区间，表示该逻辑段在地址区间中的位置和长度。它是一个迭代器，可以使用 Rust 
的语法糖 for-loop 进行迭代。有兴趣的读者可以参考 ``os/src/mm/address.rs`` 中它的实现。

.. warning::

    **Rust 语法卡片：迭代器 Iterator**

    之后有时间再补。

``MapType`` 描述该逻辑段内的所有虚拟页面映射到物理页帧的同一种方式，它是一个枚举类型，在内核当前的实现中支持两种方式：

.. code-block:: rust

    // os/src/mm/memory_set.rs

    #[derive(Copy, Clone, PartialEq, Debug)]
    pub enum MapType {
        Identical,
        Framed,
    }

其中 ``Identical`` 表示之前也有提到的恒等映射，用于在启用多级页表之后仍能够访问一个特定的物理地址指向的物理内存；而 
``Framed`` 则表示对于每个虚拟页面都需要映射到一个新分配的物理页帧。

当逻辑段采用 ``MapType::Framed`` 方式映射到物理内存的时候， ``data_frames`` 是一个保存了该逻辑段内的每个虚拟页面
和它被映射到的物理页帧 ``FrameTracker`` 的一个键值对容器 ``BTreeMap`` 中，这些物理页帧被用来实际存放数据而不是
多级页表中的节点。和之前的 ``PageTable`` 一样，这也用到了 RAII 的思想，将这些物理页帧的生命周期绑定到它所在的逻辑段 
``MapArea`` 下，当逻辑段被回收之后这些之前分配的物理页帧也会同时被回收。

``MapPermission`` 表示控制该逻辑段的访问方式，它是页表项标志位 ``PTEFlags`` 的一个子集，仅保留 U/R/W/X 
四个标志位，因为其他的标志位仅与硬件的地址转换机制细节相关，这样的设计能避免引入错误的标志位。

.. code-block:: rust

    // os/src/mm/memory_set.rs

    bitflags! {
        pub struct MapPermission: u8 {
            const R = 1 << 1;
            const W = 1 << 2;
            const X = 1 << 3;
            const U = 1 << 4;
        }
    }

地址空间则使用 ``MemorySet`` 类型来表示：

.. code-block:: rust

    // os/src/mm/memory_set.rs

    pub struct MemorySet {
        page_table: PageTable,
        areas: Vec<MapArea>,
    }

它包含了该地址空间的多级页表 ``page_table`` 和一个逻辑段 ``MapArea`` 的向量 ``areas`` 。注意 ``PageTable`` 下
挂着所有多级页表的节点被放在的物理页帧，而每个 ``MapArea`` 下则挂着对应逻辑段的数据被内核实际放在的物理页帧，这两部分
合在一起构成了一个地址空间所需的所有物理页帧。这同样是一种 RAII 风格，当一个地址空间 ``MemorySet`` 生命周期结束后，
这些物理页帧都会被回收。

地址空间 ``MemorySet`` 的方法如下：

.. code-block:: rust
    :linenos:

    // os/src/mm/memory_set.rs

    impl MemorySet {
        pub fn new_bare() -> Self {
            Self {
                page_table: PageTable::new(),
                areas: Vec::new(),
            }
        }
        fn push(&mut self, mut map_area: MapArea, data: Option<&[u8]>) {
            map_area.map(&mut self.page_table);
            if let Some(data) = data {
                map_area.copy_data(&mut self.page_table, data);
            }
            self.areas.push(map_area);
        }
        /// Assume that no conflicts.
        pub fn insert_framed_area(
            &mut self,
            start_va: VirtAddr, end_va: VirtAddr, permission: MapPermission
        ) {
            self.push(MapArea::new(
                start_va,
                end_va,
                MapType::Framed,
                permission,
            ), None);
        }
        pub fn new_kernel() -> Self;
        /// Include sections in elf and trampoline and TrapContext and user stack,
        /// also returns user_sp and entry point.
        pub fn from_elf(elf_data: &[u8]) -> (Self, usize, usize);
    }

- 第 4 行， ``new_bare`` 方法可以新建一个空的地址空间；
- 第 10 行， ``push`` 方法可以在当前地址空间插入一个新的逻辑段 ``map_area`` ，如果它是以 ``Framed`` 方式映射到
  物理内存，还可以可选地在那些被映射到的物理页帧上写入一些初始化数据 ``data`` ；
- 第 18 行， ``insert_framed_area`` 方法调用 ``push`` ，可以在当前地址空间插入一个 ``Framed`` 方式映射到
  物理内存的逻辑段；
- 第 29 行， ``new_kernel`` 可以生成内核的地址空间，而第 32 行的 ``from_elf`` 则可以应用的 ELF 格式可执行文件
  解析出各数据段并对应生成应用的地址空间。它们的实现我们将在后面讨论。

在实现 ``push`` 方法在地址空间中插入一个逻辑段 ``MapArea`` 的时候，需要同时维护地址空间的多级页表 ``page_table`` 
记录的虚拟页号到页表项的映射关系，也需要用到这个映射关系来找到向哪些物理页帧上拷贝初始数据。这用到了 ``MapArea`` 
提供的另外几个方法：

.. code-block:: rust
    :linenos:
    
    // os/src/mm/memory_set.rs

    impl MapArea {
        pub fn new( 
            start_va: VirtAddr,
            end_va: VirtAddr,
            map_type: MapType,
            map_perm: MapPermission
        ) -> Self {
            let start_vpn: VirtPageNum = start_va.floor();
            let end_vpn: VirtPageNum = end_va.ceil();
            Self {
                vpn_range: VPNRange::new(start_vpn, end_vpn),
                data_frames: BTreeMap::new(),
                map_type,
                map_perm,
            }
        }
        pub fn map(&mut self, page_table: &mut PageTable) {
            for vpn in self.vpn_range {
                self.map_one(page_table, vpn);
            }
        }
        pub fn unmap(&mut self, page_table: &mut PageTable) {
            for vpn in self.vpn_range {
                self.unmap_one(page_table, vpn);
            }
        }
        /// data: start-aligned but maybe with shorter length
        /// assume that all frames were cleared before
        pub fn copy_data(&mut self, page_table: &mut PageTable, data: &[u8]) {
            assert_eq!(self.map_type, MapType::Framed);
            let mut start: usize = 0;
            let mut current_vpn = self.vpn_range.get_start();
            let len = data.len();
            loop {
                let src = &data[start..len.min(start + PAGE_SIZE)];
                let dst = &mut page_table
                    .translate(current_vpn)
                    .unwrap()
                    .ppn()
                    .get_bytes_array()[..src.len()];
                dst.copy_from_slice(src);
                start += PAGE_SIZE;
                if start >= len {
                    break;
                }
                current_vpn.step();
            }
        }
    }

- 第 4 行的 ``new`` 方法可以新建一个逻辑段结构体，注意传入的起始/终止虚拟地址会分别被下取整/上取整为虚拟页号并传入
  迭代器 ``vpn_range`` 中；
- 第 19 行的 ``map`` 和第 24 行的 ``unmap`` 可以将当前逻辑段到物理内存的映射从传入的该逻辑段所属的地址空间的
  多级页表中加入或删除。可以看到它们的实现是遍历逻辑段中的所有虚拟页面，并以每个虚拟页面为单位依次在多级页表中进行
  键值对的插入或删除，分别对应 ``MapArea`` 的 ``map_one`` 和 ``unmap_one`` 方法，我们后面将介绍它们的实现；
- 第 31 行的 ``copy_data`` 方法将切片 ``data`` 中的数据拷贝到当前逻辑段实际被内核放置在的各物理页帧上，从而
  在地址空间中通过该逻辑段就能访问这些数据。调用它的时候需要满足：切片 ``data`` 中的数据大小不超过当前逻辑段的
  总大小，且切片中的数据会被对齐到逻辑段的开头，然后逐页拷贝到实际的物理页帧。

  从第 36 行开始的循环会遍历每一个需要拷贝数据的虚拟页面，在数据拷贝完成后会在第 48 行通过调用 ``step`` 方法，该
  方法来自于 ``os/src/mm/address.rs`` 中为 ``VirtPageNum`` 实现的 ``StepOne`` Trait，感兴趣的读者可以阅读
  代码确认其实现。

  每个页面的数据拷贝需要确定源 ``src`` 和目标 ``dst`` 两个切片并直接使用 ``copy_from_slice`` 完成复制。当确定
  目标切片 ``dst`` 的时候，第 ``39`` 行从传入的当前逻辑段所属的地址空间的多级页表中手动查找迭代到的虚拟页号被映射
  到的物理页帧，并通过 ``get_bytes_array`` 方法获取能够真正改写该物理页帧上内容的字节数组型可变引用，最后再获取它
  的切片用于数据拷贝。

接下来介绍对逻辑段中的单个虚拟页面进行映射/解映射的方法 ``map_one`` 和 ``unmap_one`` 。显然它们的实现取决于当前
逻辑段被映射到物理内存的方式：

.. code-block:: rust
    :linenos:

    // os/src/mm/memory_set.rs

    impl MemoryArea {
        pub fn map_one(&mut self, page_table: &mut PageTable, vpn: VirtPageNum) {
            let ppn: PhysPageNum;
            match self.map_type {
                MapType::Identical => {
                    ppn = PhysPageNum(vpn.0);
                }
                MapType::Framed => {
                    let frame = frame_alloc().unwrap();
                    ppn = frame.ppn;
                    self.data_frames.insert(vpn, frame);
                }
            }
            let pte_flags = PTEFlags::from_bits(self.map_perm.bits).unwrap();
            page_table.map(vpn, ppn, pte_flags);
        }
        pub fn unmap_one(&mut self, page_table: &mut PageTable, vpn: VirtPageNum) {
            match self.map_type {
                MapType::Framed => {
                    self.data_frames.remove(&vpn);
                }
                _ => {}
            }
            page_table.unmap(vpn);
        }
    }

- 对于第 4 行的 ``map_one`` 来说，在虚拟页号 ``vpn`` 已经确定的情况下，它需要知道要将一个怎么样的页表项插入多级页表。
  页表项的标志位来源于当前逻辑段的类型为 ``MapPermission`` 的统一配置，只需将其转换为 ``PTEFlags`` ；而页表项的
  物理页号则取决于当前逻辑段映射到物理内存的方式：

  - 当以恒等映射 ``Identical`` 方式映射的时候，物理页号就等于虚拟页号；
  - 当以 ``Framed`` 方式映射的时候，需要分配一个物理页帧让当前的虚拟页面可以映射过去，此时页表项中的物理页号自然就是
    这个被分配的物理页帧的物理页号。此时还需要将这个物理页帧挂在逻辑段的 ``data_frames`` 字段下。

  当确定了页表项的标志位和物理页号之后，即可调用多级页表 ``PageTable`` 的 ``map`` 接口来插入键值对。
- 对于第 19 行的 ``unmap_one`` 来说，基本上就是调用 ``PageTable`` 的 ``unmap`` 接口删除以传入的虚拟页号为键的
  键值对即可。然而，当以 ``Framed`` 映射的时候，不要忘记同时将虚拟页面被映射到的物理页帧 ``FrameTracker`` 从 
  ``data_frames`` 中移除，这样这个物理页帧才能立即被回收以备后续分配。

内核地址空间
------------------------------------------

应用地址空间
------------------------------------------

地址空间切换
------------------------------------------