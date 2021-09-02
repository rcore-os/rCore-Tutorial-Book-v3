
.. _term-batchos:

实现批处理操作系统
==============================

.. toctree::
   :hidden:
   :maxdepth: 5

本节导读
-------------------------------

目前本章主要介绍的批处理操作系统--泥盆纪“邓式鱼”操作系统，主要实现了批处理功能，但还缺少一种类似文件系统那样的松耦合灵活放置应用程序和加载执行应用程序的机制。这就需要设计一种简洁的程序放置和加载方式，能够在批处理操作系统与应用程序之间建立起联系的纽带。这主要包括两个方面：

- 静态绑定：通过一定的编程技巧，把应用程序代码和批处理操作系统代码“绑定”在一起。
- 动态加载：基于静态编码留下的“绑定”信息，操作系统可以找到应用程序文件二进制代码的起始地址和长度，并能加载到内存中运行。

这里与硬件相关且比较困难的地方是如何让在内核态的批处理操作系统启动应用程序，且能让应用程序在用户态正常执行。本节会讲大致过程，而具体细节将放到下一节具体讲解。

将应用程序链接到内核
--------------------------------------------

在本章中，我们把应用程序的二进制镜像文件作为内核的数据段链接到内核里面，因此内核需要知道内含的应用程序的数量和它们的位置，这样才能够在运行时
对它们进行管理并能够加载到物理内存。

.. note::

    应用程序的二进制镜像文件是指对编译器生成的执行文件进行进一步处理（一般用 ``objcopy`` 工具），去掉ELF文件管理信息后的代码段和数据段的内容。
    比如：

    .. code-block:: shell

        $ gcc -o hello.exe hell.c
        $ objcopy -O binary hello.exe hello.bin
    

在 ``os/src/main.rs`` 中能够找到这样一行：

.. code-block:: rust

    global_asm!(include_str!("link_app.S"));

这里我们引入了一段汇编代码 ``link_app.S`` ，它一开始并不存在，而是在构建操作系统时自动生成的。当我们使用 ``make run`` 让系统运行的过程中，这个汇编代码 ``link_app.S`` 就生成了。我们可以先来看一看 ``link_app.S`` 里面的内容：

.. code-block:: asm
    :linenos:
    
    # os/src/link_app.S

        .align 3
        .section .data
        .global _num_app
    _num_app:
        .quad 3
        .quad app_0_start
        .quad app_1_start
        .quad app_2_start
        .quad app_2_end
        
        .section .data
        .global app_0_start
        .global app_0_end
    app_0_start:
        .incbin "../user/target/riscv64gc-unknown-none-elf/release/00hello_world.bin"
    app_0_end:
            
        .section .data
        .global app_1_start
        .global app_1_end
    app_1_start:
        .incbin "../user/target/riscv64gc-unknown-none-elf/release/01store_fault.bin"
    app_1_end:
            
        .section .data
        .global app_2_start
        .global app_2_end
    app_2_start:
        .incbin "../user/target/riscv64gc-unknown-none-elf/release/02power.bin"
    app_2_end:

可以看到第 13 行开始的三个数据段分别插入了三个应用程序的二进制镜像，并且各自有一对全局符号 ``app_*_start, app_*_end`` 指示它们的
开始和结束位置。而第 3 行开始的另一个数据段相当于一个 64 位整数数组。数组中的第一个元素表示应用程序的数量，后面则按照顺序放置每个应用
程序的起始地址，最后一个元素放置最后一个应用程序的结束位置。这样每个应用程序的位置都能从该数组中相邻两个元素中得知。这个数组所在的位置
同样也由全局符号 ``_num_app`` 所指示。

这个文件是在 ``cargo build`` 的时候，由脚本 ``os/build.rs`` 控制生成的。有兴趣的读者可以参考其代码。

找到并加载应用程序二进制码
-----------------------------------------------

能够找到并加载应用程序二进制码的应用管理器 ``AppManager`` 是“邓式鱼”操作系统的核心组件。我们在 ``os`` 的 ``batch`` 子模块中实现一个应用管理器，它的主要功能是：

- 保存应用数量和各自的位置信息，以及当前执行到第几个应用了。
- 根据应用程序位置信息，初始化好应用所需内存空间，并加载应用执行。

应用管理器 ``AppManager`` 结构体定义
如下：

.. code-block:: rust

    struct AppManager {
        inner: RefCell<AppManagerInner>,
    }
    struct AppManagerInner {
        num_app: usize,
        current_app: usize,
        app_start: [usize; MAX_APP_NUM + 1],
    }
    unsafe impl Sync for AppManager {}

这里我们可以看出，上面提到的应用管理器需要保存和维护的信息都在 ``AppManagerInner`` 里面，而结构体 ``AppManager`` 里面只是保存了
一个指向 ``AppManagerInner`` 的 ``RefCell`` 智能指针。这样设计的原因在于：我们希望将 ``AppManager`` 实例化为一个全局变量，使得
任何函数都可以直接访问。但是里面的 ``current_app`` 字段表示当前执行的是第几个应用，它是一个可修改的变量，会在系统运行期间发生变化。因此在声明全局变量
的时候，采用 ``static mut`` 是一种比较简单自然的方法。但是在 Rust 中，任何对于 ``static mut`` 变量的访问控制都是 unsafe 的，而我们要尽可能
减少 ``unsafe code`` 的使用，这样才能让编译器负责更多的安全性检查。这样，在 ``static mut`` 变量声明与减少 ``unsafe code`` 的使用之间就产生了一定的矛盾。

此外，为了让 ``AppManager`` 能被直接全局实例化，我们需要将其标记为 ``Sync`` 。

.. chyyuu  这里还是要提提为何sync吧？

.. note::

    **为什么对于 static mut 的访问是 unsafe 的**

    **为什么要将 AppManager 标记为 Sync**

    可以参考附录A：Rust 快速入门的并发章节。

.. _term-interior-mutability:

为了解决上述矛盾，我们利用 ``RefCell`` 来提供 **内部可变性** (Interior Mutability)，
所谓的内部可变性就是指在我们只能拿到 ``AppManager`` 的不可变借用的情况下（即同样也只能
拿到其中的字段 ``AppManagerInner`` 的不可变借用），依然可以通过 ``RefCell`` 来修改 ``AppManagerInner`` 里面的字段。
使用 ``RefCell::borrow/RefCell::borrow_mut`` 分别可以拿到 ``RefCell`` 里面内容的不可变借用/可变借用， 
``RefCell`` 会在运行时维护当前它管理的对象的已有借用状态，并在访问对象时进行运行时借用检查。所以 ``RefCell::borrow_mut`` 就是我们实现内部可变性的关键。

我们可以这样来初始化 ``AppManager`` 的全局实例：

.. code-block:: rust

    lazy_static! {
        static ref APP_MANAGER: AppManager = AppManager {
            inner: RefCell::new({
                extern "C" { fn _num_app(); }
                let num_app_ptr = _num_app as usize as *const usize;
                let num_app = unsafe { num_app_ptr.read_volatile() };
                let mut app_start: [usize; MAX_APP_NUM + 1] = [0; MAX_APP_NUM + 1];
                let app_start_raw: &[usize] = unsafe {
                    core::slice::from_raw_parts(num_app_ptr.add(1), num_app + 1)
                };
                app_start[..=num_app].copy_from_slice(app_start_raw);
                AppManagerInner {
                    num_app,
                    current_app: 0,
                    app_start,
                }
            }),
        };
    }

初始化的逻辑很简单，就是找到 ``link_app.S`` 中提供的符号 ``_num_app`` ，并从这里开始解析出应用数量以及各个应用的开头地址。注意其中对于切片类型的使用能够很大程度上简化编程。

这里我们使用了外部库 ``lazy_static`` 提供的 ``lazy_static!`` 宏。要引入这个外部库，我们需要加入依赖：

.. code-block:: toml

    # os/Cargo.toml

    [dependencies]
    lazy_static = { version = "1.4.0", features = ["spin_no_std"] }

``lazy_static!`` 宏提供了全局变量的运行时初始化功能。一般情况下，全局变量必须在编译期设置一个初始值，但是有些全局变量依赖于运行期间
才能得到的数据作为初始值。这导致这些全局变量需要在运行时发生变化，也即重新设置初始值之后才能使用。如果我们手动实现的话有诸多不便之处，
比如需要把这种全局变量声明为 ``static mut`` 并衍生出很多 ``unsafe code`` 。这种情况下我们可以使用 ``lazy_static!`` 宏来帮助我们解决
这个问题。这里我们借助 ``lazy_static!`` 声明了一个 ``AppManager`` 结构的名为 ``APP_MANAGER`` 的全局实例，且只有在它第一次被使用到
的时候才会进行实际的初始化工作。

因此，借助 Rust 核心库提供的 ``RefCell`` 和外部库 ``lazy_static!``，我们就能在避免使用 ``static mut`` 声明的情况下，以更加优雅的Rust风格使用全局变量。

``AppManagerInner`` 的方法中， ``print_app_info/get_current_app/move_to_next_app`` 都相当简单直接，需要说明的是 ``load_app``：

.. code-block:: rust
    :linenos:

    unsafe fn load_app(&self, app_id: usize) {
        if app_id >= self.num_app {
            panic!("All applications completed!");
        }
        println!("[kernel] Loading app_{}", app_id);
        // clear icache
        llvm_asm!("fence.i" :::: "volatile");
        // clear app area
        (APP_BASE_ADDRESS..APP_BASE_ADDRESS + APP_SIZE_LIMIT).for_each(|addr| {
            (addr as *mut u8).write_volatile(0);
        });
        let app_src = core::slice::from_raw_parts(
            self.app_start[app_id] as *const u8,
            self.app_start[app_id + 1] - self.app_start[app_id]
        );
        let app_dst = core::slice::from_raw_parts_mut(
            APP_BASE_ADDRESS as *mut u8,
            app_src.len()
        );
        app_dst.copy_from_slice(app_src);
    }

这个方法负责将参数 ``app_id`` 对应的应用程序的二进制镜像加载到物理内存以 ``0x80400000`` 起始的位置，这个位置是批处理操作系统和应用程序
之间约定的常数地址，回忆上一小节中，我们也调整应用程序的内存布局以同一个地址开头。第 8 行开始，我们首先将一块内存清空，然后找到待加载应用
二进制镜像的位置，并将它复制到正确的位置。它本质上是把数据从一块内存复制到另一块内存，从批处理操作系统的角度来看，是将它数据段的一部分复制到了它
程序之外未知的地方。在这一点上也体现了冯诺依曼计算机的 ``代码即数据`` 的特征。

.. _term-dcache:
.. _term-icache:

注意第 7 行我们插入了一条奇怪的汇编指令 ``fence.i`` ，它是用来清理 i-cache 的。我们知道缓存是存储层级结构中提高访存速度的很重要一环。
而 CPU 对物理内存所做的缓存又分成 **数据缓存** (d-cache) 和 **指令缓存** (i-cache) 两部分，分别在 CPU 访存和取指的时候使用。在取指
的时候，对于一个指令地址， CPU 会先去 i-cache 里面看一下它是否在某个已缓存的缓存行内，如果在的话它就会直接从高速缓存中拿到指令而不是通过
总线和内存通信。通常情况下， CPU 会认为程序的代码段不会发生变化，因此 i-cache 是一种只读缓存。但在这里，我们会修改会被 CPU 取指的内存
区域，这会使得 i-cache 中含有与内存中不一致的内容。因此我们这里必须使用 ``fence.i`` 指令手动清空 i-cache ，让里面所有的内容全部失效，
才能够保证正确性。 

.. warning:: 

   **模拟器与真机的不同之处**

   至少在 Qemu 模拟器的默认配置下，各类缓存如 i-cache/d-cache/TLB 都处于机制不完全甚至完全不存在的状态。目前在 Qemu 平台上，即使我们
   不加上刷新 i-cache 的指令，大概率也是能够正常运行的。但在 K210 物理计算机上，如果没有执行汇编指令 ``fence.i`` ，就会产生由于指令缓存的内容与对应内存中指令不一致导致的错误。

``batch`` 子模块对外暴露出如下接口：

- ``init`` ：调用 ``print_app_info`` 的时候第一次用到了全局变量 ``APP_MANAGER`` ，它也是在这个时候完成初始化；
- ``run_next_app`` ：批处理操作系统的核心操作，即加载并运行下一个应用程序。当批处理操作系统完成初始化或者一个应用程序运行结束或出错之后会调用
  该函数。我们下节再介绍其具体实现。