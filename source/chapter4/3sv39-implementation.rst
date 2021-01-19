实现 SV39 多级页表机制
========================================================

在本章第一小节中我们简单介绍了分页的内存管理策略，本节我们在 RV64 架构提供的 SV39 分页机制的基础上完成内核中的
软件对应实现。

虚拟地址和物理地址
------------------------------------------------------

默认情况下 MMU 未被使能，此时无论 CPU 位于哪个特权级，访存的地址都会作为一个物理地址交给对应的内存控制单元来直接
访问物理内存。我们可以通过修改 S 特权级的一个名为 ``satp`` 的 CSR 来启用分页模式，在这之后 S 和 U 特权级的访存
地址会被视为一个虚拟地址，它需要经过 MMU 的地址转换变为一个物理地址，再通过它来访问物理内存；而 M 特权级的访存地址
被视为一个物理地址还是一个需要经历和 S/U 特权级相同的地址转换的虚拟地址则取决于配置，在这里我们并不深入。

.. image:: satp.png

上图是 RV64 架构下 ``satp`` 的字段分布。当 ``MODE`` 设置为 0 的时候，代表所有访存都被视为物理地址；而设置为 8 
的时候，SV39 分页机制被启用，所有 S/U 特权级的访存被视为一个 39 位的虚拟地址，它们需要先经过 MMU 的地址转换流程，
如果顺利的话，则会变成一个 56 位的物理地址来访问物理内存；否则则会触发异常，这体现了该机制的内存保护能力。

虚拟地址和物理地址都是字节地址，39 位的虚拟地址可以用来访问理论上最大 :math:`512\text{GiB}` 的地址空间，
而 56 位的物理地址在理论上甚至可以访问一块大小比这个地址空间的还高出几个数量级的物理内存。但是实际上无论是
虚拟地址还是物理地址，真正有意义、能够通过 MMU 的地址转换或是 CPU 内存控制单元的检查的地址仅占其中的很小
一部分，因此它们的理论容量上限在目前都没有实际意义。

.. image:: sv39-va-pa.png

.. _term-page-offset:

我们采用分页管理，单个页面的大小设置为 :math:`4\text{KiB}` ，每个虚拟页面和物理页帧都对齐到这个页面大小，也就是说
虚拟/物理地址区间 :math:`[0,4\text{KiB})` 为第 :math:`0` 个虚拟页面/物理页帧，而 
:math:`[4\text{KiB},8\text{KiB})` 为第 :math:`1` 个，以此类推。 :math:`4\text{KiB}` 需要用 12 位字节地址
来表示，因此虚拟地址和物理地址都被分成两部分：它们的低 12 位，即 :math:`[11:0]` 被称为 **页内偏移** 
(Page Offset) ，它描述一个地址指向的字节在它所在页面中的相对位置。而虚拟地址的高 27 位，即 :math:`[38:12]` 为
它的虚拟页号 VPN，同理物理地址的高 44 位，即 :math:`[55:12]` 为它的物理页号 VPN，页号可以用来定位一个虚拟/物理地址
属于哪一个虚拟页面/物理页帧。

地址转换是以页为单位进行的，在地址转换的前后地址的页内偏移部分不变。可以认为 MMU 只是从虚拟地址中取出 27 位虚拟页号，
在页表中查到其对应的物理页号（如果存在的话），最后将得到的物理页号与虚拟地址的页内偏移依序拼接到一起就变成了物理地址。

.. note::

    **RV64 架构中虚拟地址为何只有 39 位？**

    在 64 位架构上虚拟地址长度确实应该和位宽一致为 64 位，但是在启用 SV39 分页模式下，只有后 39 位是真正有意义的。
    SV39 分页模式规定 64 位虚拟地址的 :math:`[63:39]` 这 25 位必须和第 38 位相同，否则 MMU 会直接认定它是一个
    不合法的虚拟地址。通过这个检查之后 MMU 再取出后 39 位尝试将其转化为一个 56 位的物理地址。
    
    也就是说，所有 :math:`2^{64}` 个虚拟地址中，只有最低的 :math:`256\text{GiB}` （当第 38 位为 0 时）
    以及最高的 :math:`256\text{GiB}` （当第 38 位为 1 时）是可能通过 MMU 检查的。当我们写软件代码的时候，一个
    地址的位宽毋庸置疑就是 64 位，我们要清楚可用的只有最高和最低这两部分，尽管它们已经巨大的超乎想象了；而本节中
    我们专注于介绍 MMU 的机制，强调 MMU 看到的真正用来地址转换的虚拟地址，这只有 39 位。

正如本章第一小节所说，在分页内存管理中，地址转换的核心任务在于如何维护虚拟页号到物理页号的映射——也就是页表。不过在具体
实现它之前，我们先将地址和页号的概念抽象为 Rust 中的类型，借助 Rust 的类型安全特性来确保它们被正确实现。

首先是这些类型的定义：

.. code-block:: rust

    // os/src/mm/address.rs

    #[derive(Copy, Clone, Ord, PartialOrd, Eq, PartialEq)]
    pub struct PhysAddr(pub usize);

    #[derive(Copy, Clone, Ord, PartialOrd, Eq, PartialEq)]
    pub struct VirtAddr(pub usize);

    #[derive(Copy, Clone, Ord, PartialOrd, Eq, PartialEq)]
    pub struct PhysPageNum(pub usize);

    #[derive(Copy, Clone, Ord, PartialOrd, Eq, PartialEq)]
    pub struct VirtPageNum(pub usize);

.. _term-type-convertion:

上面分别给出了物理地址、虚拟地址、物理页号、虚拟页号的 Rust 类型声明，它们都是 Rust 的元组式结构体，可以看成 
usize 的一种简单包装。我们刻意将它们各自抽象出来而不是都使用 usize 保存，就是为了在 Rust 编译器的帮助下进行
多种方便且安全的 **类型转换** (Type Convertion) 。

首先，这些类型本身可以和 usize 之间互相转换，以物理地址 ``PhysAddr`` 为例，我们需要：

.. code-block:: rust

    // os/src/mm/address.rs

    impl From<usize> for PhysAddr {
        fn from(v: usize) -> Self { Self(v) }
    }

    impl From<PhysAddr> for usize {
        fn from(v: PhysAddr) -> Self { v.0 }
    }

前者允许我们从一个 ``usize`` 来生成 ``PhysAddr`` ，即 ``PhysAddr::from(_: usize)`` 将得到一个 ``PhysAddr`` 
；反之亦然。其实由于我们在声明结构体的时候将字段公开了出来，从物理地址变量 ``pa`` 得到它的 usize 表示的更简便方法
是直接 ``pa.0`` 。

.. note::

    **Rust 语法卡片：类型转换之 From 和 Into**

    一般而言，当我们为类型 ``U`` 实现了 ``From<T>`` Trait 之后，可以使用 ``U::from(_: T)`` 来从一个 ``T`` 
    类型的实例来构造一个 ``U`` 类型的实例；而当我们为类型 ``U`` 实现了 ``Into<T>`` Trait 之后，对于一个 ``U`` 
    类型的实例 ``u`` ，可以使用 ``u.into()`` 来将其转化为一个类型为 ``T`` 的实例。

    当我们为 ``U`` 实现了 ``From<T>`` 之后，Rust 会自动为 ``T`` 实现 ``Into<U>`` Trait，
    因为它们两个本来就是在做相同的事情。因此我们只需相互实现 ``From`` 就可以相互 ``From/Into`` 了。

    需要注意的是，当我们使用 ``From`` Trait 的 ``from`` 方法来构造一个转换后类型的实例的时候，``from`` 的参数
    已经指明了转换前的类型，因而 Rust 编译器知道该使用哪个实现；而使用 ``Into`` Trait 的 ``into`` 方法来将当前
    类型转化为另一种类型的时候，它并没有参数，因而函数签名中并没有指出要转化为哪一个类型，则我们必须在其他地方 *显式* 
    指出目标类型。比如，当我们要将 ``u.into()`` 绑定到一个新变量 ``t`` 的时候，必须通过 ``let t: T`` 显式声明 
    ``t`` 的类型；又或是将 ``u.into()`` 的结果作为参数传给某一个函数，那么这个函数的函数签名中一定指出了传入位置
    的参数的类型，Rust 编译器也就明确知道转换的类型。

    请注意，解引用 ``Deref`` Trait 是 Rust 编译器唯一允许的一种隐式类型转换，而对于其他的类型转换，我们必须手动
    调用类型转化方法或者是显式给出转换前后的类型。这体现了 Rust 的类型安全特性，在 C/C++ 中并不是如此，比如两个
    不同的整数/浮点数类型进行二元运算的时候，编译器经常要先进行隐式类型转换使两个操作数类型相同，而后再进行运算，导致
    了很多数值溢出或精度损失问题。Rust 不会进行这种隐式类型转换，它会在编译期直接报错，提示两个操作数类型不匹配。

其次，地址和页号之间可以相互转换。我们这里仍以物理地址和物理页号之间的转换为例：

.. code-block:: rust
    :linenos:

    // os/src/mm/address.rs

    impl PhysAddr {
        pub fn page_offset(&self) -> usize { self.0 & (PAGE_SIZE - 1) }
    }

    impl From<PhysAddr> for PhysPageNum {
        fn from(v: PhysAddr) -> Self {
            assert_eq!(v.page_offset(), 0);
            v.floor()
        }
    }

    impl From<PhysPageNum> for PhysAddr {
        fn from(v: PhysPageNum) -> Self { Self(v.0 << PAGE_SIZE_BITS) }
    }

其中 ``PAGE_SIZE`` 为 :math:`4096` ， ``PAGE_SIZE_BITS`` 为 :math:`12` ，它们均定义在 ``config`` 子模块
中，分别表示每个页面的大小和页内偏移的位宽。从物理页号到物理地址的转换只需左移 :math:`12` 位即可，但是物理地址需要
保证它与页面大小对齐才能通过右移转换为物理页号。

对于不对齐的情况，物理地址不能通过 ``From/Into`` 转换为物理页号，而是需要通过它自己的 ``floor`` 或 ``ceil`` 方法来
进行下取整或上取整的转换。

.. code-block:: rust

    // os/src/mm/address.rs

    impl PhysAddr {
        pub fn floor(&self) -> PhysPageNum { PhysPageNum(self.0 / PAGE_SIZE) }
        pub fn ceil(&self) -> PhysPageNum { PhysPageNum((self.0 + PAGE_SIZE - 1) / PAGE_SIZE) }
    }

我们暂时先介绍这两种最简单的类型转换。

页表项
-----------------------------------------

第一小节中我们提到，在页表中以虚拟页号作为索引不仅能够查到物理页号，还能查到一组保护位，它控制了应用对地址空间每个
虚拟页面的访问权限。但实际上还有更多的标志位，物理页号和全部的标志位以某种固定的格式保存在一个结构体中，它被称为 
**页表项** (PTE, Page Table Entry) ，是利用虚拟页号在页表中查到的结果。

.. image:: sv39-pte.png

上图为 SV39 分页模式下的页表项，其中 :math:`[53:10]` 这 :math:`44` 位是物理页号，最低的 :math:`8` 位 
:math:`[7:0]` 则是标志位，它们的含义如下（请注意，为方便说明，下文我们用 *页表项的对应虚拟页面* 来表示索引到
一个页表项的虚拟页号对应的虚拟页面）：

- 仅当 V(Valid) 位为 1 时，页表项才是合法的；
- R/W/X 分别控制索引到这个页表项的对应虚拟页面是否允许读/写/取指；
- U 控制索引到这个页表项的对应虚拟页面是否在 CPU 处于 U 特权级的情况下是否被允许访问；
- G 我们暂且不理会；
- A(Accessed) 记录自从页表项上的这一位被清零之后，页表项的对应虚拟页面是否被访问过；
- D(Dirty) 则记录自从页表项上的这一位被清零之后，页表项的对应虚拟页表是否被修改过。

让我们先来实现页表项中的标志位 ``PTEFlags`` ：

.. code-block:: rust

    // os/src/main.rs

    #[macro_use]
    extern crate bitflags;

    // os/src/mm/page_table.rs

    use bitflags::*;

    bitflags! {
        pub struct PTEFlags: u8 {
            const V = 1 << 0;
            const R = 1 << 1;
            const W = 1 << 2;
            const X = 1 << 3;
            const U = 1 << 4;
            const G = 1 << 5;
            const A = 1 << 6;
            const D = 1 << 7;
        }
    }

`bitflags <https://docs.rs/bitflags/1.2.1/bitflags/>`_ 是一个 Rust 中常用来比特标志位的 crate 。它提供了
一个 ``bitflags!`` 宏，如上面的代码段所展示的那样，可以将一个 ``u8`` 封装成一个标志位的集合类型，支持一些常见的集合
运算。它的一些使用细节这里不展开，请读者自行参考它的官方文档。注意，在使用之前我们需要引入该 crate 的依赖：

.. code-block:: toml

    # os/Cargo.toml

    [dependencies]
    bitflags = "1.2.1"

接下来我们实现页表项 ``PageTableEntry`` ：

.. code-block:: rust
    :linenos:

    // os/src/mm/page_table.rs

    #[derive(Copy, Clone)]
    #[repr(C)]
    pub struct PageTableEntry {
        pub bits: usize,
    }

    impl PageTableEntry {
        pub fn new(ppn: PhysPageNum, flags: PTEFlags) -> Self {
            PageTableEntry {
                bits: ppn.0 << 10 | flags.bits as usize,
            }
        }
        pub fn empty() -> Self {
            PageTableEntry {
                bits: 0,
            }
        }
        pub fn ppn(&self) -> PhysPageNum {
            (self.bits >> 10 & ((1usize << 44) - 1)).into()
        }
        pub fn flags(&self) -> PTEFlags {
            PTEFlags::from_bits(self.bits as u8).unwrap()
        }
    }

- 第 3 行我们让编译器自动为 ``PageTableEntry`` 实现 ``Copy/Clone`` Trait，来让这个类型以值语义赋值/传参的时候
  不会发生所有权转移，而是拷贝一份新的副本。从这一点来说 ``PageTableEntry`` 就和 usize 一样，因为它也只是后者的
  一层简单包装，解释了 usize 各个比特段的含义。
- 第 10 行使得我们可以从一个物理页号 ``PhysPageNum`` 和一个页表项标志位 ``PTEFlags`` 生成一个页表项 
  ``PageTableEntry`` 实例；而第 20 行和第 23 行则分别可以从一个页表项将它们两个取出。
- 第 15 行中，我们也可以通过 ``empty`` 方法生成一个全零的页表项，注意这隐含着该页表项的 V 标志位为 0 ，
  因此这是一个不合法的页表项。

后面我们还为 ``PageTableEntry`` 实现了一些工具函数，可以快速判断一个页表项的 V/R/W/X 标志位是否为 1，以 V 
标志位的判断为例：

.. code-block:: rust

    // os/src/mm/page_table.rs

    impl PageTableEntry {
        pub fn is_valid(&self) -> bool {
            (self.flags() & PTEFlags::V) != PTEFlags::empty()
        }
    }

这里相当于判断两个集合的交集是否为空集，部分说明了 ``bitflags`` crate 的使用方法。

多级页表
-------------------------------