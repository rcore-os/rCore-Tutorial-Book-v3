进程机制核心数据结构
===================================

本节导读
-----------------------------------

为了更好实现进程抽象，同时也使得整体架构更加灵活能够满足后续的一些需求，我们需要重新设计一些数据结构包含的内容及接口。本节将按照如下顺序来进行介绍：

- 基于应用名的应用链接/加载器
- 进程标识符 ``PidHandle`` 以及内核栈 ``KernelStack``
- 任务控制块 ``TaskControlBlock``
- 任务管理器 ``TaskManager``
- 处理器监视器 ``Processor``

基于应用名的应用链接/加载器
------------------------------------------------------------------------

在实现 ``exec`` 系统调用的时候，我们需要根据应用的名字而不仅仅是一个编号来获取应用的 ELF 格式数据。因此原有的链接和加载接口需要做出如下变更：

在链接器 ``os/build.rs`` 中，我们需要按顺序保存链接进来的每个应用的名字：
  
.. code-block::
    :linenos:
    :emphasize-lines: 8-13

        // os/build.rs

        for i in 0..apps.len() {
            writeln!(f, r#"    .quad app_{}_start"#, i)?;
        }
        writeln!(f, r#"    .quad app_{}_end"#, apps.len() - 1)?;

        writeln!(f, r#"
        .global _app_names
    _app_names:"#)?;
        for app in apps.iter() {
            writeln!(f, r#"    .string "{}""#, app)?;
        }

        for (idx, app) in apps.iter().enumerate() {
            ...
        }

第 8~13 行，我们按照顺序将各个应用的名字通过 ``.string`` 伪指令放到数据段中，注意链接器会自动在每个字符串的结尾加入分隔符 ``\0`` ，它们的位置则由全局符号 ``_app_names`` 指出。

而在加载器 ``loader.rs`` 中，我们用一个全局可见的 *只读* 向量 ``APP_NAMES`` 来按照顺序将所有应用的名字保存在内存中：

.. code-block:: Rust

    // os/src/loader.rs

    lazy_static! {
        static ref APP_NAMES: Vec<&'static str> = {
            let num_app = get_num_app();
            extern "C" { fn _app_names(); }
            let mut start = _app_names as usize as *const u8;
            let mut v = Vec::new();
            unsafe {
                for _ in 0..num_app {
                    let mut end = start;
                    while end.read_volatile() != '\0' as u8 {
                        end = end.add(1);
                    }
                    let slice = core::slice::from_raw_parts(start, end as usize - start as usize);
                    let str = core::str::from_utf8(slice).unwrap();
                    v.push(str);
                    start = end.add(1);
                }
            }
            v
        };
    }

使用 ``get_app_data_by_name`` 可以按照应用的名字来查找获得应用的 ELF 数据，而 ``list_apps`` 在内核初始化时被调用，它可以打印出所有可用的应用的名字。

.. code-block:: rust

    // os/src/loader.rs

    pub fn get_app_data_by_name(name: &str) -> Option<&'static [u8]> {
        let num_app = get_num_app();
        (0..num_app)
            .find(|&i| APP_NAMES[i] == name)
            .map(|i| get_app_data(i))
    }

    pub fn list_apps() {
        println!("/**** APPS ****");
        for app in APP_NAMES.iter() {
            println!("{}", app);
        }
        println!("**************/")
    }


进程标识符和内核栈
------------------------------------------------------------------------

进程标识符
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

同一时间存在的所有进程都有一个自己的进程标识符，它们是互不相同的整数。这里我们使用 RAII 的思想，将其抽象为一个 ``PidHandle`` 类型，当它的生命周期结束后对应的整数会被编译器自动回收：

.. code-block:: rust

    // os/src/task/pid.rs

    pub struct PidHandle(pub usize);

类似之前的物理页帧分配器 ``FrameAllocator`` ，我们实现一个同样使用简单栈式分配策略的进程标识符分配器 ``PidAllocator`` ，并将其全局实例化为 ``PID_ALLOCATOR`` ：

.. code-block:: rust

    // os/src/task/pid.rs

    struct PidAllocator {
        current: usize,
        recycled: Vec<usize>,
    }

    impl PidAllocator {
        pub fn new() -> Self {
            PidAllocator {
                current: 0,
                recycled: Vec::new(),
            }
        }
        pub fn alloc(&mut self) -> PidHandle {
            if let Some(pid) = self.recycled.pop() {
                PidHandle(pid)
            } else {
                self.current += 1;
                PidHandle(self.current - 1)
            }
        }
        pub fn dealloc(&mut self, pid: usize) {
            assert!(pid < self.current);
            assert!(
                self.recycled.iter().find(|ppid| **ppid == pid).is_none(),
                "pid {} has been deallocated!", pid
            );
            self.recycled.push(pid);
        }
    }

    lazy_static! {
        static ref PID_ALLOCATOR : Mutex<PidAllocator> = Mutex::new(PidAllocator::new());
    }

``PidAllocator::alloc`` 将会分配出去一个将 ``usize`` 包装之后的 ``PidHandle`` 。我们将其包装为一个全局分配进程标识符的接口 ``pid_alloc`` 提供给内核的其他子模块：

.. code-block:: rust

    // os/src/task/pid.rs

    pub fn pid_alloc() -> PidHandle {
        PID_ALLOCATOR.lock().alloc()
    }

同时我们也需要为 ``PidHandle`` 实现 ``Drop`` Trait 来允许编译器进行自动的资源回收：

.. code-block:: rust

    // os/src/task/pid.rs

    impl Drop for PidHandle {
        fn drop(&mut self) {
            PID_ALLOCATOR.lock().dealloc(self.0);
        }
    }

内核栈
~~~~~~~~~~~~~~~~~~~~~~

在前面的章节中我们介绍过 :ref:`内核地址空间布局 <kernel-as-high>` ，当时我们将每个应用的内核栈按照应用编号从小到大的顺序将它们作为逻辑段从高地址到低地址放在内核地址空间中，且两两之间保留一个守护页面使得我们能够尽可能早的发现内核栈溢出问题。从本章开始，我们将应用编号替换为进程标识符来决定每个进程内核栈在地址空间中的位置。

因此，在内核栈 ``KernelStack`` 中保存着它所属进程的 PID ：

.. code-block:: rust

    // os/src/task/pid.rs

    pub struct KernelStack {
        pid: usize,
    }

它提供以下方法：

.. code-block:: rust
    :linenos:

    // os/src/task/pid.rs

    /// Return (bottom, top) of a kernel stack in kernel space.
    pub fn kernel_stack_position(app_id: usize) -> (usize, usize) {
        let top = TRAMPOLINE - app_id * (KERNEL_STACK_SIZE + PAGE_SIZE);
        let bottom = top - KERNEL_STACK_SIZE;
        (bottom, top)
    }

    impl KernelStack {
        pub fn new(pid_handle: &PidHandle) -> Self {
            let pid = pid_handle.0;
            let (kernel_stack_bottom, kernel_stack_top) = kernel_stack_position(pid);
            KERNEL_SPACE
                .lock()
                .insert_framed_area(
                    kernel_stack_bottom.into(),
                    kernel_stack_top.into(),
                    MapPermission::R | MapPermission::W,
                );
            KernelStack {
                pid: pid_handle.0,
            }
        }
        pub fn push_on_top<T>(&self, value: T) -> *mut T where
            T: Sized, {
            let kernel_stack_top = self.get_top();
            let ptr_mut = (kernel_stack_top - core::mem::size_of::<T>()) as *mut T;
            unsafe { *ptr_mut = value; }
            ptr_mut
        }
        pub fn get_top(&self) -> usize {
            let (_, kernel_stack_top) = kernel_stack_position(self.pid);
            kernel_stack_top
        }
    }

- 第 11 行， ``new`` 方法可以从一个 ``PidHandle`` ，也就是一个已分配的进程标识符中对应生成一个内核栈 ``KernelStack`` 。它调用了第 4 行声明的 ``kernel_stack_position`` 函数来根据进程标识符计算内核栈在内核地址空间中的位置，随即在第 14 行将一个逻辑段插入内核地址空间 ``KERNEL_SPACE`` 中。
- 第 25 行的 ``push_on_top`` 方法可以将一个类型为 ``T`` 的变量压入内核栈顶并返回其裸指针，这也是一个泛型函数。它在实现的时候用到了第 32 行的 ``get_top`` 方法来获取当前内核栈顶在内核地址空间中的地址。

内核栈 ``KernelStack`` 也用到了 RAII 的思想，具体来说，实际保存它的物理页帧的生命周期被绑定到它下面，当 ``KernelStack`` 生命周期结束后，这些物理页帧也将会被编译器自动回收：

.. code-block:: rust

    // os/src/task/pid.rs

    impl Drop for KernelStack {
        fn drop(&mut self) {
            let (kernel_stack_bottom, _) = kernel_stack_position(self.pid);
            let kernel_stack_bottom_va: VirtAddr = kernel_stack_bottom.into();
            KERNEL_SPACE
                .lock()
                .remove_area_with_start_vpn(kernel_stack_bottom_va.into());
        }
    }

这仅需要为 ``KernelStack`` 实现 ``Drop`` Trait，一旦它的生命周期结束则在内核地址空间中将对应的逻辑段删除，由前面章节的介绍我们知道这也就意味着那些物理页帧被同时回收掉了。

进程控制块
------------------------------------------------------------------------

在内核中，每个进程的执行状态、资源控制等元数据均保存在一个被称为 **进程控制块** (PCB, Process Control Block) 的结构中，它是内核对进程进行管理的单位，故而是一种极其关键的内核数据结构。在内核看来，它就等价于一个进程。

承接前面的章节，我们仅需对任务控制块 ``TaskControlBlock`` 进行若干改动并让它直接承担进程控制块的功能：

.. code-block:: rust
    :linenos:

    // os/src/task/task.rs

    pub struct TaskControlBlock {
        // immutable
        pub pid: PidHandle,
        pub kernel_stack: KernelStack,
        // mutable
        inner: Mutex<TaskControlBlockInner>,
    }

    pub struct TaskControlBlockInner {
        pub trap_cx_ppn: PhysPageNum,
        pub base_size: usize,
        pub task_cx_ptr: usize,
        pub task_status: TaskStatus,
        pub memory_set: MemorySet,
        pub parent: Option<Weak<TaskControlBlock>>,
        pub children: Vec<Arc<TaskControlBlock>>,
        pub exit_code: i32,
    }

任务控制块中包含两部分：

- 在初始化之后就不再变化的作为一个字段直接放在任务控制块中。这里将进程标识符 ``PidHandle`` 和内核栈 ``KernelStack`` 放在其中；
- 在运行过程中可能发生变化的则放在 ``TaskControlBlockInner`` 中，将它再包裹上一层互斥锁 ``Mutex<T>`` 放在任务控制块中。这是因为在我们的设计中外层只能获取任务控制块的不可变引用，若想修改里面的部分内容的话这需要 ``Mutex<T>`` 所提供的内部可变性。另外，当后续真正可能有多核同时修改同一个任务控制块中的内容时， ``Mutex<T>`` 可以提供互斥从而避免数据竞争。

``TaskControlBlockInner`` 中则包含下面这些内容：

- ``trap_cx_ppn`` 指出了应用地址空间中的 Trap 上下文（详见第四章）被放在的物理页帧的物理页号。
- ``base_size`` 的含义是：应用数据仅有可能出现在应用地址空间低于 ``base_size`` 字节的区域中。借助它我们可以清楚的知道应用有多少数据驻留在内存中。
- ``task_cx_ptr`` 指出一个暂停的任务的任务上下文在内核地址空间（更确切的说是在自身内核栈）中的位置，用于任务切换。
- ``task_status`` 维护当前进程的执行状态。
- ``memory_set`` 表示应用地址空间。
- ``parent`` 指向当前进程的父进程（如果存在的话）。注意我们使用 ``Weak`` 而非 ``Arc`` 来包裹另一个任务控制块，因此这个智能指针将不会影响父进程的引用计数。
- ``children`` 则将当前进程的所有子进程的任务控制块以 ``Arc`` 智能指针的形式保存在一个向量中，这样才能够更方便的找到它们。

注意我们在维护父子进程关系的时候大量用到了引用计数 ``Arc/Weak`` 。子进程的进程控制块并不会被直接放到父进程控制块下面，因为子进程完全有可能在父进程退出后仍然存在。因此进程控制块的本体是被放到内核堆上面的，对于它的一切访问都是通过智能指针 ``Arc/Weak`` 来进行的。当且仅当它的引用计数变为 0 的时候，进程控制块以及被绑定到它上面的各类资源才会被回收。

``TaskControlBlockInner`` 提供的方法主要是对于它内部的字段的快捷访问：

.. code-block:: rust

    // os/src/task/task.rs

    impl TaskControlBlockInner {
        pub fn get_task_cx_ptr2(&self) -> *const usize {
            &self.task_cx_ptr as *const usize
        }
        pub fn get_trap_cx(&self) -> &'static mut TrapContext {
            self.trap_cx_ppn.get_mut()
        }
        pub fn get_user_token(&self) -> usize {
            self.memory_set.token()
        }
        fn get_status(&self) -> TaskStatus {
            self.task_status
        }
        pub fn is_zombie(&self) -> bool {
            self.get_status() == TaskStatus::Zombie
        }
    }

而任务控制块 ``TaskControlBlock`` 目前提供以下方法：

.. code-block:: rust

    // os/src/task/task.rs

    impl TaskControlBlock {
        pub fn acquire_inner_lock(&self) -> MutexGuard<TaskControlBlockInner> {
            self.inner.lock()
        }
        pub fn getpid(&self) -> usize {
            self.pid.0
        }
        pub fn new(elf_data: &[u8]) -> Self {...}
        pub fn exec(&self, elf_data: &[u8]) {...}
        pub fn fork(self: &Arc<TaskControlBlock>) -> Arc<TaskControlBlock> {...}
    }

- ``acquire_inner_lock`` 尝试获取互斥锁来得到一个 ``MutexGuard`` ，它可以被看成一个内层 ``TaskControlBlockInner`` 的可变引用并可以对它指向的内容进行修改。之所以要包装为一个方法而不是直接 ``self.inner.lock`` 是由于这样接口的定义更加清晰明确。
- ``getpid`` 以 ``usize`` 的形式返回当前进程的进程标识符。
- ``new`` 用来创建一个新的进程，目前仅用于内核中手动创建唯一一个初始进程 ``initproc`` 。
- ``exec`` 用来实现 ``exec`` 系统调用，即当前进程加载并执行另一个 ELF 格式可执行文件。
- ``fork`` 用来实现 ``fork`` 系统调用，即当前进程 fork 出来一个与之几乎相同的子进程。

``new/exec/fork`` 的实现我们将在下一小节再介绍。

任务管理器
------------------------------------------------------------------------

处理器监视器
------------------------------------------------------------------------