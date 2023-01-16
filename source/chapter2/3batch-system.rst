
.. _term-batchos:

实现批处理操作系统
==============================

.. toctree::
   :hidden:
   :maxdepth: 5

本节导读
-------------------------------

.. 目前本章主要介绍的批处理操作系统--泥盆纪“邓式鱼”操作系统。虽然操作系统实现了批处理执行应用程序的功能，但应用程序和操作系统还是紧耦合在一个单一的执行文件中，还缺少一种类似文件系统那样的松耦合灵活放置应用程序和加载执行应用程序的机制。这就需要在单一执行文件的情况下，设计一种尽量简洁的程序放置和加载方式，能够在批处理操作系统与应用程序之间建立起联系的纽带。这主要包括两个方面：

从本节开始我们将着手实现批处理操作系统——即泥盆纪“邓式鱼”操作系统。在批处理操作系统中，每当一个应用执行完毕，我们都需要将下一个要执行的应用的代码和数据加载到内存。在具体实现其批处理执行应用程序功能之前，本节我们首先实现该应用加载机制，也即：在操作系统和应用程序需要被放置到同一个可执行文件的前提下，设计一种尽量简洁的应用放置和加载方式，使得操作系统容易找到应用被放置到的位置，从而在批处理操作系统和应用程序之间建立起联系的纽带。具体而言，应用放置采用“静态绑定”的方式，而操作系统加载应用则采用“动态加载”的方式：

- 静态绑定：通过一定的编程技巧，把多个应用程序代码和批处理操作系统代码“绑定”在一起。
- 动态加载：基于静态编码留下的“绑定”信息，操作系统可以找到每个应用程序文件二进制代码的起始地址和长度，并能加载到内存中运行。

这里与硬件相关且比较困难的地方是如何让在内核态的批处理操作系统启动应用程序，且能让应用程序在用户态正常执行。本节会讲大致过程，而具体细节将放到下一节具体讲解。

将应用程序链接到内核
--------------------------------------------

在本章中，我们把应用程序的二进制镜像文件（从 ELF 格式可执行文件剥离元数据，参考 :ref:`前面章节 <content-binary-from-elf>` ）作为内核的数据段链接到内核里面，因此内核需要知道内含的应用程序的数量和它们的位置，这样才能够在运行时对它们进行管理并能够加载到物理内存。

.. 前面章节讲过了

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
        .quad 5
        .quad app_0_start
        .quad app_1_start
        .quad app_2_start
        .quad app_3_start
        .quad app_4_start
        .quad app_4_end

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

        .section .data
        .global app_3_start
        .global app_3_end
    app_3_start:
        .incbin "../user/target/riscv64gc-unknown-none-elf/release/03priv_inst.bin"
    app_3_end:

        .section .data
        .global app_4_start
        .global app_4_end
    app_4_start:
        .incbin "../user/target/riscv64gc-unknown-none-elf/release/04priv_csr.bin"
    app_4_end:

可以看到第 15 行开始的五个数据段分别插入了五个应用程序的二进制镜像，并且各自有一对全局符号 ``app_*_start, app_*_end`` 指示它们的开始和结束位置。而第 3 行开始的另一个数据段相当于一个 64 位整数数组。数组中的第一个元素表示应用程序的数量，后面则按照顺序放置每个应用程序的起始地址，最后一个元素放置最后一个应用程序的结束位置。这样每个应用程序的位置都能从该数组中相邻两个元素中得知。这个数组所在的位置同样也由全局符号 ``_num_app`` 所指示。

这个文件是在 ``cargo build`` 的时候，由脚本 ``os/build.rs`` 控制生成的。有兴趣的同学可以参考其代码。

找到并加载应用程序二进制码
-----------------------------------------------

能够找到并加载应用程序二进制码的应用管理器 ``AppManager`` 是“邓式鱼”操作系统的核心组件。我们在 ``os`` 的 ``batch`` 子模块中实现一个应用管理器，它的主要功能是：

- 保存应用数量和各自的位置信息，以及当前执行到第几个应用了。
- 根据应用程序位置信息，初始化好应用所需内存空间，并加载应用执行。

应用管理器 ``AppManager`` 结构体定义如下：

.. code-block:: rust
    
    // os/src/batch.rs

    struct AppManager {
        num_app: usize,
        current_app: usize,
        app_start: [usize; MAX_APP_NUM + 1],
    }


这里我们可以看出，上面提到的应用管理器需要保存和维护的信息都在 ``AppManager`` 里面。这样设计的原因在于：我们希望将 ``AppManager`` 实例化为一个全局变量，使得任何函数都可以直接访问。但是里面的 ``current_app`` 字段表示当前执行的是第几个应用，它是一个可修改的变量，会在系统运行期间发生变化。因此在声明全局变量的时候，采用 ``static mut`` 是一种比较简单自然的方法。但是在 Rust 中，任何对于 ``static mut`` 变量的访问控制都是 unsafe 的，而我们要在编程中尽量避免使用 unsafe ，这样才能让编译器负责更多的安全性检查。因此，我们需要考虑如何在尽量避免触及 unsafe 的情况下仍能声明并使用可变的全局变量。 

.. _rust-ownership-model:

.. note::

    **Rust Tips：Rust 所有权模型和借用检查**

    我们这里简单介绍一下 Rust 的所有权模型。它可以用一句话来概括： **值** （Value）在同一时间只能被绑定到一个 **变量** （Variable）上。这里，“值”指的是储存在内存中固定位置，且格式属于某种特定类型的数据；而变量就是我们在 Rust 代码中通过 ``let`` 声明的局部变量或者函数的参数等，变量的类型与值的类型相匹配。在这种情况下，我们称值的 **所有权** （Ownership）属于它被绑定到的变量，且变量可以作为访问/控制绑定到它上面的值的一个媒介。变量可以将它拥有的值的所有权转移给其他变量，或者当变量退出其作用域之后，它拥有的值也会被销毁，这意味着值占用的内存或其他资源会被回收。

    有些场景下，特别是在函数调用的时候，我们并不希望将当前上下文中的值的所有权转移到其他上下文中，因此类似于 C/C++ 中的按引用传参， Rust 可以使用 ``&`` 或 ``&mut`` 后面加上值被绑定到的变量的名字来分别生成值的不可变引用和可变引用，我们称这些引用分别不可变/可变 **借用** (Borrow) 它们引用的值。顾名思义，我们可以通过可变引用来修改它借用的值，但通过不可变引用则只能读取而不能修改。这些引用同样是需要被绑定到变量上的值，只是它们的类型是引用类型。在 Rust 中，引用类型的使用需要被编译器检查，但在数据表达上，和 C 的指针一样它只记录它借用的值所在的地址，因此在内存中它随平台不同仅会占据 4 字节或 8 字节空间。
    
    无论值的类型是否是引用类型，我们都定义值的 **生存期** （Lifetime）为代码执行期间该值必须持续合法的代码区域集合（见 [#rust-nomicon-lifetime]_ ），大概可以理解为该值在代码中的哪些地方被用到了：简单情况下，它可能等同于拥有它的变量的作用域，也有可能是从它被绑定开始直到它的拥有者变量最后一次出现或是它被解绑。
    
    当我们使用 ``&`` 和 ``&mut`` 来借用值的时候，则我们编写的代码必须满足某些约束条件，不然无法通过编译：

    - 不可变/可变引用的生存期不能 **超出** （Outlive）它们借用的值的生存期，也即：前者必须是后者的子集；
    - 同一时间，借用同一个值的不可变和可变引用不能共存；
    - 同一时间，借用同一个值的不可变引用可以存在多个，但可变引用只能存在一个。

    这是为了 Rust 内存安全而设计的重要约束条件。第一条很好理解，如果值的生存期未能完全覆盖借用它的引用的生存期，就会在某一时刻发生值已被销毁而我们仍然尝试通过引用来访问该值的情形。反过来说，显然当值合法时引用才有意义。最典型的例子是 **悬垂指针** （Dangling Pointer）问题：即我们尝试在一个函数中返回函数中声明的局部变量的引用，并在调用者函数中试图通过该引用访问已被销毁的局部变量，这会产生未定义行为并导致错误。第二、三条的主要目的则是为了避免通过多个引用对同一个值进行的读写操作产生冲突。例如，当对同一个值的读操作和写操作在时间上相互交错时（即不可变/可变引用的生存期部分重叠），读操作便有可能读到被修改到一半的值，通常这会是一个不合法的值从而导致程序无法正确运行。这可能是由于我们在编程上的疏忽，使得我们在读取一个值的时候忘记它目前正处在被修改到一半的状态，一个可能的例子是在 C++ 中正对容器进行迭代访问的时候修改了容器本身。也有可能被归结为 **别名** （Aliasing）问题，例如在 C 函数中有两个指针参数，如果它们指向相同的地址且编译器没有注意到这一点就进行过激的优化，将会使得编译结果偏离我们期望的语义。
    
    上述约束条件要求借用同一个值的不可变引用和不可变/可变引用的生存期相互隔离，从而能够解决这些问题。Rust 编译器会在编译时使用 **借用检查器** （Borrow Checker）检查这些约束条件是否被满足：其具体做法是尽可能精确的估计引用和值的生存期并将它们进行比较。随着 Rust 语言的愈发完善，其估计的精确度也会越来越高，使得程序员能够更容易通过借用检查。引用相关的借用检查发生在编译期，因此我们可以称其为编译期借用检查。

    相对的，对值的借用方式运行时可变的情况下，我们可以使用 Rust 内置的数据结构将借用检查推迟到运行时，这可以称为运行时借用检查，它的约束条件和编译期借用检查一致。当我们想要发起借用或终止借用时，只需调用对应数据结构提供的接口即可。值的借用状态会占用一部分额外内存，运行时还会有额外的代码对借用合法性进行检查，这是为满足借用方式的灵活性产生的必要开销。当无法通过借用检查时，将会产生一个不可恢复错误，导致程序打印错误信息并立即退出。具体来说，我们通常使用 ``RefCell`` 包裹可被借用的值，随后调用 ``borrow`` 和 ``borrow_mut`` 便可发起借用并获得一个对值的不可变/可变借用的标志，它们可以像引用一样使用。为了终止借用，我们只需手动销毁这些标志或者等待它们被自动销毁。 ``RefCell`` 的详细用法请参考 [#rust-refcell]_ 。

.. _term-interior-mutability:

如果单独使用 ``static`` 而去掉 ``mut`` 的话，我们可以声明一个初始化之后就不可变的全局变量，但是我们需要 ``AppManager`` 里面的内容在运行时发生变化。这涉及到 Rust 中的 **内部可变性** （Interior Mutability），也即在变量自身不可变或仅在不可变借用的情况下仍能修改绑定到变量上的值。我们可以通过用上面提到的 ``RefCell`` 来包裹 ``AppManager`` ，这样 ``RefCell`` 无需被声明为 ``mut`` ，同时被包裹的 ``AppManager`` 也能被修改。但是，我们能否将 ``RefCell`` 声明为一个全局变量呢？让我们写一小段代码试一试：

.. code-block:: rust

    // https://play.rust-lang.org/?version=stable&mode=debug&edition=2021&gist=18b0f956b83e6a8a408215edcfcb6d01
    use std::cell::RefCell;
    static A: RefCell<i32> = RefCell::new(3);
    fn main() {
        *A.borrow_mut() = 4;
        println!("{}", A.borrow());
    }

这段代码无法通过编译，其错误是：

.. code-block::

    error[E0277]: `RefCell<i32>` cannot be shared between threads safely
    --> src/main.rs:2:1
    |
    2 | static A: RefCell<i32> = RefCell::new(3);
    | ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^ `RefCell<i32>` cannot be shared between threads safely
    |
    = help: the trait `Sync` is not implemented for `RefCell<i32>`
    = note: shared static variables must have a type that implements `Sync`

    For more information about this error, try `rustc --explain E0277`.

Rust 编译器提示我们 ``RefCell<i32>`` 未被标记为 ``Sync`` ，因此 Rust 编译器认为它不能被安全的在线程间共享，也就不能作为全局变量使用。这可能会令人迷惑，这只是一个单线程程序，因此它不会有任何线程间共享数据的行为，为什么不能通过编译呢？事实上，Rust 对于并发安全的检查较为粗糙，当声明一个全局变量的时候，编译器会默认程序员会在多线程上使用它，而并不会检查程序员是否真的这样做。如果一个变量实际上仅会在单线程上使用，那 Rust 会期待我们将变量分配在栈上作为局部变量而不是全局变量。目前我们的内核仅支持单核，也就意味着只有单线程，那么我们可不可以使用局部变量来绕过这个错误呢？

很可惜，在这里和后面章节的很多场景中，有些变量无法作为局部变量使用。这是因为后面内核会并发执行多条控制流，这些控制流都会用到这些变量。如果我们最初将变量分配在某条控制流的栈上，那么我们就需要考虑如何将变量传递到其他控制流上，由于控制流的切换等操作并非常规的函数调用，我们很难将变量传递出去。因此最方便的做法是使用全局变量，这意味着在程序的任何地方均可随意访问它们，自然也包括这些控制流。

除了 ``Sync`` 的问题之外，看起来 ``RefCell`` 已经非常接近我们的需求了，因此我们在 ``RefCell`` 的基础上再封装一个 ``UPSafeCell`` ，它名字的含义是：允许我们在 *单核* 上安全使用可变全局变量。

.. code-block:: rust
    
    // os/src/sync/up.rs

    pub struct UPSafeCell<T> {
        /// inner data
        inner: RefCell<T>,
    }

    unsafe impl<T> Sync for UPSafeCell<T> {}

    impl<T> UPSafeCell<T> {
        /// User is responsible to guarantee that inner struct is only used in
        /// uniprocessor.
        pub unsafe fn new(value: T) -> Self {
            Self { inner: RefCell::new(value) }
        }
        /// Panic if the data has been borrowed.
        pub fn exclusive_access(&self) -> RefMut<'_, T> {
            self.inner.borrow_mut()
        }
    }

``UPSafeCell`` 对于 ``RefCell`` 简单进行封装，它和 ``RefCell`` 一样提供内部可变性和运行时借用检查，只是更加严格：调用 ``exclusive_access`` 可以得到它包裹的数据的独占访问权。因此当我们要访问数据时（无论读还是写），需要首先调用 ``exclusive_access`` 获得数据的可变借用标记，通过它可以完成数据的读写，在操作完成之后我们需要销毁这个标记，此后才能开始对该数据的下一次访问。相比 ``RefCell`` 它不再允许多个读操作同时存在。

这段代码里面出现了两个 ``unsafe`` ：

- 首先 ``new`` 被声明为一个 ``unsafe`` 函数，是因为我们希望使用者在创建一个 ``UPSafeCell`` 的时候保证在访问 ``UPSafeCell`` 内包裹的数据的时候始终不违背上述模式：即访问之前调用 ``exclusive_access`` ，访问之后销毁借用标记再进行下一次访问。这只能依靠使用者自己来保证，但我们提供了一个保底措施：当使用者违背了上述模式，比如访问之后忘记销毁就开启下一次访问时，程序会 panic 并退出。
- 另一方面，我们将 ``UPSafeCell`` 标记为 ``Sync`` 使得它可以作为一个全局变量。这是 unsafe 行为，因为编译器无法确定我们的 ``UPSafeCell`` 能否安全的在多线程间共享。而我们能够向编译器做出保证，第一个原因是目前我们内核仅运行在单核上，因此无需在意任何多核引发的数据竞争/同步问题；第二个原因则是它基于 ``RefCell`` 提供了运行时借用检查功能，从而满足了 Rust 对于借用的基本约束进而保证了内存安全。

.. chyyuu  这里还是要提提为何sync吧？

.. chyyuu     **为什么对于 static mut 的访问是 unsafe 的**     **为什么要将 AppManager 标记为 Sync**     可以参考附录A：Rust 快速入门的并发章节。

.. 为了解决上述矛盾，我们设计实现了 ``UPSafeCell<T>`` ，通过封装 ``RefCell<T>`` 来提供 **内部可变性** (Interior Mutability)，所谓的内部可变性就是指在我们只能拿到 ``<T>`` 类型变量的不可变借用的情况下（即同样也只能拿到其中的字段 ``current_app`` 的不可变借用），依然可以通过 ``RefCell`` 来修改 ``AppManager`` 里面的字段。使用 ``RefCell::borrow_mut`` 可以拿到 ``RefCell`` 里面内容的可变借用， ``RefCell`` 会在运行时维护当前它管理的对象的已有借用状态，并在访问对象时进行运行时借用检查。所以 ``RefCell::borrow_mut`` 就是我们实现内部可变性的关键。此外，为了让 ``AppManager`` 能被直接全局实例化，我们需要将其通过 ``UPSafeCell<T>`` 标记为 ``Sync`` 。 ``UPSafeCell<T>`` 的实现如下所示：

这样，我们就以尽量少的 unsafe code 来初始化 ``AppManager`` 的全局实例 ``APP_MANAGER`` ：

.. code-block:: rust

    // os/src/batch.rs

    lazy_static! {
        static ref APP_MANAGER: UPSafeCell<AppManager> = unsafe { UPSafeCell::new({
            extern "C" { fn _num_app(); }
            let num_app_ptr = _num_app as usize as *const usize;
            let num_app = num_app_ptr.read_volatile();
            let mut app_start: [usize; MAX_APP_NUM + 1] = [0; MAX_APP_NUM + 1];
            let app_start_raw: &[usize] =  core::slice::from_raw_parts(
                num_app_ptr.add(1), num_app + 1
            );
            app_start[..=num_app].copy_from_slice(app_start_raw);
            AppManager {
                num_app,
                current_app: 0,
                app_start,
            }
        })};
    }

初始化的逻辑很简单，就是找到 ``link_app.S`` 中提供的符号 ``_num_app`` ，并从这里开始解析出应用数量以及各个应用的起始地址。注意其中对于切片类型的使用能够很大程度上简化编程。

这里我们使用了外部库 ``lazy_static`` 提供的 ``lazy_static!`` 宏。要引入这个外部库，我们需要加入依赖：

.. code-block:: toml

    # os/Cargo.toml

    [dependencies]
    lazy_static = { version = "1.4.0", features = ["spin_no_std"] }

``lazy_static!`` 宏提供了全局变量的运行时初始化功能。一般情况下，全局变量必须在编译期设置一个初始值，但是有些全局变量依赖于运行期间才能得到的数据作为初始值。这导致这些全局变量需要在运行时发生变化，即需要重新设置初始值之后才能使用。如果我们手动实现的话有诸多不便之处，比如需要把这种全局变量声明为 ``static mut`` 并衍生出很多 unsafe 代码 。这种情况下我们可以使用 ``lazy_static!`` 宏来帮助我们解决这个问题。这里我们借助 ``lazy_static!`` 声明了一个 ``AppManager`` 结构的名为 ``APP_MANAGER`` 的全局实例，且只有在它第一次被使用到的时候，才会进行实际的初始化工作。

因此，借助我们设计的 ``UPSafeCell<T>`` 和外部库 ``lazy_static!``，我们就能使用尽量少的 unsafe 代码完成可变全局变量的声明和初始化，且一旦初始化完成，在后续的使用过程中便不再触及 unsafe 代码。

``AppManager`` 的方法中， ``print_app_info/get_current_app/move_to_next_app`` 都相当简单直接，需要说明的是 ``load_app``：

.. code-block:: rust
    :linenos:

    unsafe fn load_app(&self, app_id: usize) {
        if app_id >= self.num_app {
            panic!("All applications completed!");
        }
        println!("[kernel] Loading app_{}", app_id);
        // clear app area
        core::slice::from_raw_parts_mut(
            APP_BASE_ADDRESS as *mut u8,
            APP_SIZE_LIMIT
        ).fill(0);
        let app_src = core::slice::from_raw_parts(
            self.app_start[app_id] as *const u8,
            self.app_start[app_id + 1] - self.app_start[app_id]
        );
        let app_dst = core::slice::from_raw_parts_mut(
            APP_BASE_ADDRESS as *mut u8,
            app_src.len()
        );
        app_dst.copy_from_slice(app_src);
        // memory fence about fetching the instruction memory
        asm!("fence.i");
    }


这个方法负责将参数 ``app_id`` 对应的应用程序的二进制镜像加载到物理内存以 ``0x80400000`` 起始的位置，这个位置是批处理操作系统和应用程序之间约定的常数地址，回忆上一小节中，我们也调整应用程序的内存布局以同一个地址开头。第 7 行开始，我们首先将一块内存清空，然后找到待加载应用二进制镜像的位置，并将它复制到正确的位置。它本质上是把数据从一块内存复制到另一块内存，从批处理操作系统的角度来看，是将操作系统数据段的一部分数据（实际上是应用程序）复制到了一个可以执行代码的内存区域。在这一点上也体现了冯诺依曼计算机的 *代码即数据* 的特征。

.. _term-dcache:
.. _term-icache:

注意在第 21 行我们在加载完应用代码之后插入了一条奇怪的汇编指令 ``fence.i`` ，它起到什么作用呢？我们知道缓存是存储层级结构中提高访存速度的很重要一环。而 CPU 对物理内存所做的缓存又分成 **数据缓存** (d-cache) 和 **指令缓存** (i-cache) 两部分，分别在 CPU 访存和取指的时候使用。在取指的时候，对于一个指令地址， CPU 会先去 i-cache 里面看一下它是否在某个已缓存的缓存行内，如果在的话它就会直接从高速缓存中拿到指令而不是通过总线访问内存。通常情况下， CPU 会认为程序的代码段不会发生变化，因此 i-cache 是一种只读缓存。但在这里，OS 将修改会被 CPU 取指的内存区域，这会使得 i-cache 中含有与内存中不一致的内容。因此， OS 在这里必须使用取指屏障指令 ``fence.i`` ，它的功能是保证 **在它之后的取指过程必须能够看到在它之前的所有对于取指内存区域的修改** ，这样才能保证 CPU 访问的应用代码是最新的而不是 i-cache 中过时的内容。至于硬件是如何实现 ``fence.i`` 这条指令的，这一点每个硬件的具体实现方式都可能不同，比如直接清空 i-cache 中所有内容或者标记其中某些内容不合法等等。

.. warning:: 

   **模拟器与真机的不同之处**

   至少在 Qemu 模拟器的默认配置下，各类缓存如 i-cache/d-cache/TLB 都处于机制不完全甚至完全不存在的状态。目前在 Qemu 平台上，即使我们不加上刷新 i-cache 的指令，大概率也是能够正常运行的。但在 K210 物理计算机上，如果没有执行汇编指令 ``fence.i`` ，就会产生由于指令缓存的内容与对应内存中指令不一致导致的错误异常。

``batch`` 子模块对外暴露出如下接口：

- ``init`` ：调用 ``print_app_info`` 的时候第一次用到了全局变量 ``APP_MANAGER`` ，它也是在这个时候完成初始化；
- ``run_next_app`` ：批处理操作系统的核心操作，即加载并运行下一个应用程序。当批处理操作系统完成初始化或者一个应用程序运行结束或出错之后会调用该函数。我们下节再介绍其具体实现。

.. [#rust-nomicon-lifetime] https://doc.rust-lang.org/nomicon/lifetimes.html
.. [#rust-refcell] https://doc.rust-lang.org/stable/std/cell/struct.RefCell.html
