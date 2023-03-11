进程管理机制的设计实现
============================================

本节导读
--------------------------------------------

有了上节的数据结构和相关基本方法的介绍后，我们还需完成进程管理关键功能的实现，从而构造出一个完整的白垩纪“伤齿龙”操作系统。本节将从如下四个方面介绍如何基于上一节设计的内核数据结构来实现进程管理：

- 创建初始进程：创建第一个用户态进程 ``initproc``；
- 进程调度机制：当进程主动调用 ``sys_yield`` 交出 CPU 使用权或者内核把本轮分配的时间片用尽的进程换出且换入下一个进程；
- 进程生成机制：介绍进程相关的两个重要系统调用 ``sys_fork/sys_exec`` 的实现；
- 进程资源回收机制：当进程调用 ``sys_exit`` 正常退出或者出错被内核终止之后如何保存其退出码，其父进程通过 ``sys_waitpid`` 系统调用收集该进程的信息并回收其资源。
- 字符输入机制：为了支持shell程序-user_shell获得字符输入，介绍 ``sys_read`` 系统调用的实现；

初始进程的创建
--------------------------------------------

内核初始化完毕之后即会调用 ``task`` 子模块提供的 ``add_initproc`` 函数来将初始进程 ``initproc`` 加入任务管理器，但在这之前我们需要初始化初始进程的进程控制块 ``INITPROC`` ，这个过程基于 ``lazy_static`` 在运行时完成。

.. code-block:: rust

    // os/src/task/mod.rs

    use crate::loader::get_app_data_by_name;
    use manager::add_task;

    lazy_static! {
        pub static ref INITPROC: Arc<TaskControlBlock> = Arc::new(
            TaskControlBlock::new(get_app_data_by_name("initproc").unwrap())
        );
    }

    pub fn add_initproc() {
        add_task(INITPROC.clone());
    }

我们调用 ``TaskControlBlock::new`` 来创建一个进程控制块，它需要传入 ELF 可执行文件的数据切片作为参数，这可以通过加载器 ``loader`` 子模块提供的 ``get_app_data_by_name`` 接口查找 ``initproc`` 的 ELF 执行文件数据来获得。在初始化 ``INITPROC`` 之后，就可以在 ``add_initproc`` 中调用 ``task`` 的任务管理器 ``manager`` 子模块提供的 ``add_task`` 接口，将其加入到任务管理器。

接下来介绍 ``TaskControlBlock::new`` 是如何实现的：

.. code-block:: rust
    :linenos:

    // os/src/task/task.rs

    use super::{PidHandle, pid_alloc, KernelStack};
    use super::TaskContext;
    use crate::config::TRAP_CONTEXT;
    use crate::trap::TrapContext;

    // impl TaskControlBlock
    pub fn new(elf_data: &[u8]) -> Self {
        // memory_set with elf program headers/trampoline/trap context/user stack
        let (memory_set, user_sp, entry_point) = MemorySet::from_elf(elf_data);
        let trap_cx_ppn = memory_set
            .translate(VirtAddr::from(TRAP_CONTEXT).into())
            .unwrap()
            .ppn();
        // alloc a pid and a kernel stack in kernel space
        let pid_handle = pid_alloc();
        let kernel_stack = KernelStack::new(&pid_handle);
        let kernel_stack_top = kernel_stack.get_top();
        // push a task context which goes to trap_return to the top of kernel stack
        let task_control_block = Self {
            pid: pid_handle,
            kernel_stack,
            inner: unsafe { UPSafeCell::new(TaskControlBlockInner {
                trap_cx_ppn,
                base_size: user_sp,
                task_cx: TaskContext::goto_trap_return(kernel_stack_top),
                task_status: TaskStatus::Ready,
                memory_set,
                parent: None,
                children: Vec::new(),
                exit_code: 0,
            })},
        };
        // prepare TrapContext in user space
        let trap_cx = task_control_block.inner_exclusive_access().get_trap_cx();
        *trap_cx = TrapContext::app_init_context(
            entry_point,
            user_sp,
            KERNEL_SPACE.exclusive_access().token(),
            kernel_stack_top,
            trap_handler as usize,
        );
        task_control_block
    }

- 第 11 行我们解析应用的 ELF 执行文件得到应用地址空间 ``memory_set`` ，用户栈在应用地址空间中的位置 ``user_sp`` 以及应用的入口点 ``entry_point`` 。
- 第 12 行我们手动查页表找到位于应用地址空间中新创建的Trap 上下文被实际放在哪个物理页帧上，用来做后续的初始化。
- 第 16~19 行我们为该进程分配 PID 以及内核栈，并记录下内核栈在内核地址空间的位置 ``kernel_stack_top`` 。
- 第 20 行我们在该进程的内核栈上压入初始化的任务上下文，使得第一次任务切换到它的时候可以跳转到 ``trap_return`` 并进入用户态开始执行。
- 第 21 行我们整合之前的部分信息创建进程控制块 ``task_control_block`` 。
- 第 37 行我们初始化位于该进程应用地址空间中的 Trap 上下文，使得第一次进入用户态的时候时候能正确跳转到应用入口点并设置好用户栈，同时也保证在 Trap 的时候用户态能正确进入内核态。
- 第 44 行将 ``task_control_block`` 返回。

进程调度机制
--------------------------------------------

通过调用 ``task`` 子模块提供的 ``suspend_current_and_run_next`` 函数可以暂停当前任务并切换到下一个任务，当应用调用 ``sys_yield`` 主动交出使用权、本轮时间片用尽或者由于某些原因内核中的处理无法继续的时候，就会在内核中调用此函数触发调度机制并进行任务切换。下面给出了两种典型的使用情况：

.. code-block:: rust
    :linenos:
    :emphasize-lines: 4,18

    // os/src/syscall/process.rs

    pub fn sys_yield() -> isize {
        suspend_current_and_run_next();
        0
    }

    // os/src/trap/mod.rs

    #[no_mangle]
    pub fn trap_handler() -> ! {
        set_kernel_trap_entry();
        let scause = scause::read();
        let stval = stval::read();
        match scause.cause() {
            Trap::Interrupt(Interrupt::SupervisorTimer) => {
                set_next_trigger();
                suspend_current_and_run_next();
            }
            ...
        }
        trap_return();
    }

随着进程概念的引入， ``suspend_current_and_run_next`` 的实现也需要发生变化：

.. code-block:: rust
    :linenos:

    // os/src/task/mod.rs

    use processor::{task_current_task, schedule};
    use manager::add_task;

    pub fn suspend_current_and_run_next() {
        // There must be an application running.
        let task = take_current_task().unwrap();

        // ---- access current TCB exclusively
        let mut task_inner = task.inner_exclusive_access();
        let task_cx_ptr = &mut task_inner.task_cx as *mut TaskContext;
        // Change status to Ready
        task_inner.task_status = TaskStatus::Ready;
        drop(task_inner);
        // ---- stop exclusively accessing current PCB

        // push back to ready queue.
        add_task(task);
        // jump to scheduling cycle
        schedule(task_cx_ptr);
    }

首先通过 ``take_current_task`` 来取出当前正在执行的任务，修改其进程控制块内的状态，随后将这个任务放入任务管理器的队尾。接着调用 ``schedule`` 函数来触发调度并切换任务。注意，当仅有一个任务的时候， ``suspend_current_and_run_next`` 的效果是会继续执行这个任务。

进程的生成机制
--------------------------------------------

在内核中手动生成的进程只有初始进程 ``initproc`` ，余下所有的进程都是它直接或间接 fork 出来的。当一个子进程被 fork 出来之后，它可以调用 ``exec`` 系统调用来加载并执行另一个可执行文件。因此， ``fork/exec`` 两个系统调用提供了进程的生成机制。下面我们分别来介绍二者的实现。

fork 系统调用的实现
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

在实现 fork 的时候，最为关键且困难的是为子进程创建一个和父进程几乎完全相同的应用地址空间。我们的实现如下：

.. code-block:: rust
    :linenos:

    // os/src/mm/memory_set.rs

    impl MapArea {
        pub fn from_another(another: &MapArea) -> Self {
            Self {
                vpn_range: VPNRange::new(
                    another.vpn_range.get_start(),
                    another.vpn_range.get_end()
                ),
                data_frames: BTreeMap::new(),
                map_type: another.map_type,
                map_perm: another.map_perm,
            }
        }
    }

    impl MemorySet {
        pub fn from_existed_user(user_space: &MemorySet) -> MemorySet {
            let mut memory_set = Self::new_bare();
            // map trampoline
            memory_set.map_trampoline();
            // copy data sections/trap_context/user_stack
            for area in user_space.areas.iter() {
                let new_area = MapArea::from_another(area);
                memory_set.push(new_area, None);
                // copy data from another space
                for vpn in area.vpn_range {
                    let src_ppn = user_space.translate(vpn).unwrap().ppn();
                    let dst_ppn = memory_set.translate(vpn).unwrap().ppn();
                    dst_ppn.get_bytes_array().copy_from_slice(src_ppn.get_bytes_array());
                }
            }
            memory_set
        }
    }

这需要对内存管理子模块 ``mm`` 做一些拓展：

- 第 4 行的 ``MapArea::from_another`` 可以从一个逻辑段复制得到一个虚拟地址区间、映射方式和权限控制均相同的逻辑段，不同的是由于它还没有真正被映射到物理页帧上，所以 ``data_frames`` 字段为空。
- 第 18 行的 ``MemorySet::from_existed_user`` 可以复制一个完全相同的地址空间。首先在第 19 行，我们通过 ``new_bare`` 新创建一个空的地址空间，并在第 21 行通过 ``map_trampoline`` 为这个地址空间映射上跳板页面，这是因为我们解析 ELF 创建地址空间的时候，并没有将跳板页作为一个单独的逻辑段插入到地址空间的逻辑段向量 ``areas`` 中，所以这里需要单独映射上。
  
  剩下的逻辑段都包含在 ``areas`` 中。我们遍历原地址空间中的所有逻辑段，将复制之后的逻辑段插入新的地址空间，在插入的时候就已经实际分配了物理页帧了。接着我们遍历逻辑段中的每个虚拟页面，对应完成数据复制，这只需要找出两个地址空间中的虚拟页面各被映射到哪个物理页帧，就可转化为将数据从物理内存中的一个位置复制到另一个位置，使用 ``copy_from_slice`` 即可轻松实现。

接着，我们实现 ``TaskControlBlock::fork`` 来从父进程的进程控制块创建一份子进程的控制块：

.. code-block:: rust
    :linenos:

    // os/src/task/task.rs

    impl TaskControlBlock {
        pub fn fork(self: &Arc<TaskControlBlock>) -> Arc<TaskControlBlock> {
            // ---- access parent PCB exclusively
            let mut parent_inner = self.inner_exclusive_access();
            // copy user space(include trap context)
            let memory_set = MemorySet::from_existed_user(
                &parent_inner.memory_set
            );
            let trap_cx_ppn = memory_set
                .translate(VirtAddr::from(TRAP_CONTEXT).into())
                .unwrap()
                .ppn();
            // alloc a pid and a kernel stack in kernel space
            let pid_handle = pid_alloc();
            let kernel_stack = KernelStack::new(&pid_handle);
            let kernel_stack_top = kernel_stack.get_top();
            let task_control_block = Arc::new(TaskControlBlock {
                pid: pid_handle,
                kernel_stack,
                inner: unsafe { UPSafeCell::new(TaskControlBlockInner {
                    trap_cx_ppn,
                    base_size: parent_inner.base_size,
                    task_cx: TaskContext::goto_trap_return(kernel_stack_top),
                    task_status: TaskStatus::Ready,
                    memory_set,
                    parent: Some(Arc::downgrade(self)),
                    children: Vec::new(),
                    exit_code: 0,
                })},
            });
            // add child
            parent_inner.children.push(task_control_block.clone());
            // modify kernel_sp in trap_cx
            // **** access children PCB exclusively
            let trap_cx = task_control_block.inner_exclusive_access().get_trap_cx();
            trap_cx.kernel_sp = kernel_stack_top;
            // return
            task_control_block
            // ---- stop exclusively accessing parent/children PCB automatically
        }
    }

它基本上和新建进程控制块的 ``TaskControlBlock::new`` 是相同的，但要注意以下几点：

- 子进程的地址空间不是通过解析 ELF 文件，而是通过在第 8 行调用 ``MemorySet::from_existed_user`` 复制父进程地址空间得到的；
- 第 24 行，我们让子进程和父进程的 ``base_size`` ，也即应用数据的大小保持一致；
- 在 fork 的时候需要注意父子进程关系的维护。第 28 行我们将父进程的弱引用计数放到子进程的进程控制块中，而在第 33 行我们将子进程插入到父进程的孩子向量 ``children`` 中。

我们在子进程内核栈上压入一个初始化的任务上下文，使得内核一旦通过任务切换到该进程，就会跳转到 ``trap_return`` 来进入用户态。而在复制地址空间的时候，子进程的 Trap 上下文也是完全从父进程复制过来的，这可以保证子进程进入用户态和其父进程回到用户态的那一瞬间 CPU 的状态是完全相同的（后面我们会让它们的返回值不同从而区分两个进程）。而两个进程的应用数据由于地址空间复制的原因也是完全相同的，这是 fork 语义要求做到的。

在具体实现 ``sys_fork`` 的时候，我们需要特别注意如何体现父子进程的差异：

.. code-block:: rust
    :linenos: 
    :emphasize-lines: 11,28,33

    // os/src/syscall/process.rs

    pub fn sys_fork() -> isize {
        let current_task = current_task().unwrap();
        let new_task = current_task.fork();
        let new_pid = new_task.pid.0;
        // modify trap context of new_task, because it returns immediately after switching
        let trap_cx = new_task.inner_exclusive_access().get_trap_cx();
        // we do not have to move to next instruction since we have done it before
        // for child process, fork returns 0
        trap_cx.x[10] = 0;  //x[10] is a0 reg
        // add new task to scheduler
        add_task(new_task);
        new_pid as isize
    }

    // os/src/trap/mod.rs

    #[no_mangle]
    pub fn trap_handler() -> ! {
        set_kernel_trap_entry();
        let scause = scause::read();
        let stval = stval::read();
        match scause.cause() {
            Trap::Exception(Exception::UserEnvCall) => {
                // jump to next instruction anyway
                let mut cx = current_trap_cx();
                cx.sepc += 4;
                // get system call return value
                let result = syscall(cx.x[17], [cx.x[10], cx.x[11], cx.x[12]]);
                // cx is changed during sys_exec, so we have to call it again
                cx = current_trap_cx();
                cx.x[10] = result as usize;
            }
        ...
    }    

在调用 ``syscall`` 进行系统调用分发并具体调用 ``sys_fork`` 之前， 第28行，``trap_handler`` 已经将当前进程 Trap 上下文中的 ``sepc`` 向后移动了 4 字节，使得它回到用户态之后，会从发出系统调用的 ``ecall`` 指令的下一条指令开始执行。之后当我们复制地址空间的时候，子进程地址空间 Trap 上下文的 ``sepc``  也是移动之后的值，我们无需再进行修改。

父子进程回到用户态的瞬间都处于刚刚从一次系统调用返回的状态，但二者的返回值不同。第 8~11 行我们将子进程的 Trap 上下文中用来存放系统调用返回值的 a0 寄存器修改为 0 ；第 33 行，而父进程系统调用的返回值会在 ``trap_handler`` 中 ``syscall`` 返回之后再设置为 ``sys_fork`` 的返回值，这里我们返回子进程的 PID 。这就做到了父进程 ``fork`` 的返回值为子进程的 PID ，而子进程的返回值则为 0 。通过返回值是否为 0 可以区分父子进程。

另外，不要忘记在第 13 行，我们将生成的子进程通过 ``add_task`` 加入到任务管理器中。

exec 系统调用的实现
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

``exec`` 系统调用使得一个进程能够加载一个新应用的 ELF 可执行文件中的代码和数据替换原有的应用地址空间中的内容，并开始执行。我们先从进程控制块的层面进行修改：

.. code-block:: rust
    :linenos:

    // os/src/task/task.rs

    impl TaskControlBlock {
        pub fn exec(&self, elf_data: &[u8]) {
            // memory_set with elf program headers/trampoline/trap context/user stack
            let (memory_set, user_sp, entry_point) = MemorySet::from_elf(elf_data);
            let trap_cx_ppn = memory_set
                .translate(VirtAddr::from(TRAP_CONTEXT).into())
                .unwrap()
                .ppn();

            // **** access inner exclusively
            let mut inner = self.inner_exclusive_access();
            // substitute memory_set
            inner.memory_set = memory_set;
            // update trap_cx ppn
            inner.trap_cx_ppn = trap_cx_ppn;
            // initialize trap_cx
            let trap_cx = inner.get_trap_cx();
            *trap_cx = TrapContext::app_init_context(
                entry_point,
                user_sp,
                KERNEL_SPACE.exclusive_access().token(),
                self.kernel_stack.get_top(),
                trap_handler as usize,
            );
            // **** stop exclusively accessing inner automatically
        }
    }

它在解析传入的 ELF 格式数据之后只做了两件事情：

- 首先是从 ELF 文件生成一个全新的地址空间并直接替换进来（第 15 行），这将导致原有的地址空间生命周期结束，里面包含的全部物理页帧都会被回收；
- 然后是修改新的地址空间中的 Trap 上下文，将解析得到的应用入口点、用户栈位置以及一些内核的信息进行初始化，这样才能正常实现 Trap 机制。

这里无需对任务上下文进行处理，因为这个进程本身已经在执行了，而只有被暂停的应用才需要在内核栈上保留一个任务上下文。

有了 ``exec`` 函数后， ``sys_exec`` 就很容易实现了：

.. code-block:: rust
    :linenos:

    // os/src/mm/page_table.rs

    pub fn translated_str(token: usize, ptr: *const u8) -> String {
        let page_table = PageTable::from_token(token);
        let mut string = String::new();
        let mut va = ptr as usize;
        loop {
            let ch: u8 = *(page_table.translate_va(VirtAddr::from(va)).unwrap().get_mut());
            if ch == 0 {
                break;
            } else {
                string.push(ch as char);
                va += 1;
            }
        }
        string
    }

    // os/src/syscall/process.rs

    pub fn sys_exec(path: *const u8) -> isize {
        let token = current_user_token();
        let path = translated_str(token, path);
        if let Some(data) = get_app_data_by_name(path.as_str()) {
            let task = current_task().unwrap();
            task.exec(data);
            0
        } else {
            -1
        }
    }

应用在 ``sys_exec`` 系统调用中传递给内核的只有一个要执行的应用名字符串在当前应用地址空间中的起始地址，如果想在内核中具体获得字符串的话就需要手动查页表。第 3 行的 ``translated_str`` 便可以从内核地址空间之外的某个应用的用户态地址空间中拿到一个字符串，其原理就是针对应用的字符串中字符的用户态虚拟地址，查页表，找到对应的内核虚拟地址，逐字节地构造字符串，直到发现一个 ``\0`` 为止（第7~15行）。

..  chyyuu 这样找字符串，是否有安全隐患？？？

回到 ``sys_exec`` 的实现，它调用 ``translated_str`` 找到要执行的应用名并试图在应用加载器提供的 ``get_app_data_by_name`` 接口中找到对应的 ELF 格式的数据。如果找到，就调用 ``TaskControlBlock::exec`` 替换掉地址空间并返回 0。这个返回值其实并没有意义，因为我们在替换地址空间的时候本来就对 Trap 上下文重新进行了初始化。如果没有找到，就不做任何事情并返回 -1。在shell程序-user_shell中我们也正是通过这个返回值来判断要执行的应用是否存在。

系统调用后重新获取 Trap 上下文
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

过去的 ``trap_handler`` 实现是这样处理系统调用的：

.. code-block:: rust
    :linenos:

    // os/src/trap/mod.rs

    #[no_mangle]
    pub fn trap_handler() -> ! {
        set_kernel_trap_entry();
        let cx = current_trap_cx();
        let scause = scause::read();
        let stval = stval::read();
        match scause.cause() {
            Trap::Exception(Exception::UserEnvCall) => {
                cx.sepc += 4;
                cx.x[10] = syscall(cx.x[17], [cx.x[10], cx.x[11], cx.x[12]]) as usize;
            }
            ...
        }
        trap_return();
    }

这里的 ``cx`` 是当前应用的 Trap 上下文的可变引用，我们需要通过查页表找到它具体被放在哪个物理页帧上，并构造相同的虚拟地址来在内核中访问它。对于系统调用 ``sys_exec`` 来说，一旦调用它之后，我们会发现 ``trap_handler`` 原来上下文中的 ``cx`` 失效了——因为它是用来访问之前地址空间中 Trap 上下文被保存在的那个物理页帧的，而现在它已经被回收掉了。因此，为了能够处理类似的这种情况，我们在 ``syscall`` 分发函数返回之后需要重新获取 ``cx`` ，目前的实现如下：

.. code-block:: rust
    :linenos:

    // os/src/trap/mod.rs

    #[no_mangle]
    pub fn trap_handler() -> ! {
        set_kernel_trap_entry();
        let scause = scause::read();
        let stval = stval::read();
        match scause.cause() {
            Trap::Exception(Exception::UserEnvCall) => {
                // jump to next instruction anyway
                let mut cx = current_trap_cx();
                cx.sepc += 4;
                // get system call return value
                let result = syscall(cx.x[17], [cx.x[10], cx.x[11], cx.x[12]]);
                // cx is changed during sys_exec, so we have to call it again
                cx = current_trap_cx();
                cx.x[10] = result as usize;
            }
            ...
        }
        trap_return();
    }


shell程序 user_shell 的输入机制
--------------------------------------------

为了实现shell程序 ``user_shell`` 的输入机制，我们需要实现 ``sys_read`` 系统调用使得应用能够取得用户的键盘输入。

.. code-block:: rust
    :linenos:
    
    // os/src/syscall/fs.rs

    use crate::sbi::console_getchar;

    const FD_STDIN: usize = 0;

    pub fn sys_read(fd: usize, buf: *const u8, len: usize) -> isize {
        match fd {
            FD_STDIN => {
                assert_eq!(len, 1, "Only support len = 1 in sys_read!");
                let mut c: usize;
                loop {
                    c = console_getchar();
                    if c == 0 {
                        suspend_current_and_run_next();
                        continue;
                    } else {
                        break;
                    }
                }
                let ch = c as u8;
                let mut buffers = translated_byte_buffer(current_user_token(), buf, len);
                unsafe { buffers[0].as_mut_ptr().write_volatile(ch); }
                1
            }
            _ => {
                panic!("Unsupported fd in sys_read!");
            }
        }
    }

目前我们仅支持从标准输入 ``FD_STDIN`` 即文件描述符 0 读入，且单次读入的长度限制为 1，即每次只能读入一个字符。我们调用 ``sbi`` 子模块提供的从键盘获取输入的接口 ``console_getchar`` ，如果返回 0 则说明还没有输入，我们调用 ``suspend_current_and_run_next`` 暂时切换到其他进程，等下次切换回来的时候再看看是否有输入了。获取到输入之后，我们退出循环并手动查页表将输入的字符正确的写入到应用地址空间。

注：我们这里还没有涉及 **文件** 的概念，在后续章节中有具体的介绍。

进程资源回收机制
--------------------------------------------

进程的退出
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

.. _process-exit:

当应用调用 ``sys_exit`` 系统调用主动退出或者出错由内核终止之后，会在内核中调用 ``exit_current_and_run_next`` 函数退出当前进程并切换到下一个进程。使用方法如下：

.. code-block:: rust
    :linenos:
    :emphasize-lines: 4,29,34

    // os/src/syscall/process.rs

    pub fn sys_exit(exit_code: i32) -> ! {
        exit_current_and_run_next(exit_code);
        panic!("Unreachable in sys_exit!");
    }

    // os/src/trap/mod.rs

    #[no_mangle]
    pub fn trap_handler() -> ! {
        set_kernel_trap_entry();
        let scause = scause::read();
        let stval = stval::read();
        match scause.cause() {
            Trap::Exception(Exception::StoreFault) |
            Trap::Exception(Exception::StorePageFault) |
            Trap::Exception(Exception::InstructionFault) |
            Trap::Exception(Exception::InstructionPageFault) |
            Trap::Exception(Exception::LoadFault) |
            Trap::Exception(Exception::LoadPageFault) => {
                println!(
                    "[kernel] {:?} in application, bad addr = {:#x}, bad instruction = {:#x}, core dumped.",
                    scause.cause(),
                    stval,
                    current_trap_cx().sepc,
                );
                // page fault exit code
                exit_current_and_run_next(-2);
            }
            Trap::Exception(Exception::IllegalInstruction) => {
                println!("[kernel] IllegalInstruction in application, core dumped.");
                // illegal instruction exit code
                exit_current_and_run_next(-3);
            }
            ...
        }
        trap_return();
    }

相比前面的章节， ``exit_current_and_run_next`` 带有一个退出码作为参数。当在 ``sys_exit`` 正常退出的时候，退出码由应用传到内核中；而出错退出的情况（如第 29 行的访存错误或第 34 行的非法指令异常）则是由内核指定一个特定的退出码。这个退出码会在 ``exit_current_and_run_next`` 写入当前进程的进程控制块中：

.. code-block:: rust
    :linenos:

    // os/src/mm/memory_set.rs

    impl MemorySet {
        pub fn recycle_data_pages(&mut self) {
            self.areas.clear();
        }
    }

    // os/src/task/mod.rs

    pub fn exit_current_and_run_next(exit_code: i32) {
        // take from Processor
        let task = take_current_task().unwrap();
        // **** access current TCB exclusively
        let mut inner = task.inner_exclusive_access();
        // Change status to Zombie
        inner.task_status = TaskStatus::Zombie;
        // Record exit code
        inner.exit_code = exit_code;
        // do not move to its parent but under initproc

        // ++++++ access initproc TCB exclusively
        {
            let mut initproc_inner = INITPROC.inner_exclusive_access();
            for child in inner.children.iter() {
                child.inner_exclusive_access().parent = Some(Arc::downgrade(&INITPROC));
                initproc_inner.children.push(child.clone());
            }
        }
        // ++++++ stop exclusively accessing parent PCB

        inner.children.clear();
        // deallocate user space
        inner.memory_set.recycle_data_pages();
        drop(inner);
        // **** stop exclusively accessing current PCB
        // drop task manually to maintain rc correctly
        drop(task);
        // we do not have to save task context
        let mut _unused = TaskContext::zero_init();
        schedule(&mut _unused as *mut _);
    }

- 第 13 行我们调用 ``take_current_task`` 来将当前进程控制块从处理器监控 ``PROCESSOR`` 中取出而不是得到一份拷贝，这是为了正确维护进程控制块的引用计数；
- 第 17 行我们将进程控制块中的状态修改为 ``TaskStatus::Zombie`` 即僵尸进程，这样它后续才能被父进程在 ``waitpid`` 系统调用的时候回收；
- 第 19 行我们将传入的退出码 ``exit_code`` 写入进程控制块中，后续父进程在 ``waitpid`` 的时候可以收集；
- 第 24~26 行所做的事情是将当前进程的所有子进程挂在初始进程 ``initproc`` 下面，其做法是遍历每个子进程，修改其父进程为初始进程，并加入初始进程的孩子向量中。第 32 行将当前进程的孩子向量清空。
- 第 34 行对于当前进程占用的资源进行早期回收。在第 4 行可以看出， ``MemorySet::recycle_data_pages`` 只是将地址空间中的逻辑段列表 ``areas`` 清空（即执行 ``Vec``  向量清空），这将导致应用地址空间被回收（即进程的数据和代码对应的物理页帧都被回收），但用来存放页表的那些物理页帧此时还不会被回收（会由父进程最后回收子进程剩余的占用资源）。
- 最后在第 41 行我们调用 ``schedule`` 触发调度及任务切换，由于我们再也不会回到该进程的执行过程中，因此无需关心任务上下文的保存。

父进程回收子进程资源
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

父进程通过 ``sys_waitpid`` 系统调用来回收子进程的资源并收集它的一些信息：

.. code-block:: rust
    :linenos:
    :emphasize-lines: 15,35,37,46,47

    // os/src/syscall/process.rs

    /// If there is not a child process whose pid is same as given, return -1.
    /// Else if there is a child process but it is still running, return -2.
    pub fn sys_waitpid(pid: isize, exit_code_ptr: *mut i32) -> isize {
        let task = current_task().unwrap();
        // find a child process

        // ---- access current TCB exclusively
        let mut inner = task.inner_exclusive_access();
        if inner.children
            .iter()
            .find(|p| {pid == -1 || pid as usize == p.getpid()})
            .is_none() {
            return -1;
            // ---- stop exclusively accessing current PCB
        }
        let pair = inner.children
            .iter()
            .enumerate()
            .find(|(_, p)| {
                // ++++ temporarily access child PCB exclusively
                p.inner_exclusive_access().is_zombie() && (pid == -1 || pid as usize == p.getpid())
                // ++++ stop exclusively accessing child PCB
            });
        if let Some((idx, _)) = pair {
            let child = inner.children.remove(idx);
            // confirm that child will be deallocated after removing from children list
            assert_eq!(Arc::strong_count(&child), 1);
            let found_pid = child.getpid();
            // ++++ temporarily access child TCB exclusively
            let exit_code = child.inner_exclusive_access().exit_code;
            // ++++ stop exclusively accessing child PCB
            *translated_refmut(inner.memory_set.token(), exit_code_ptr) = exit_code;
            found_pid as isize
        } else {
            -2
        }
        // ---- stop exclusively accessing current PCB automatically
    }

    // user/src/lib.rs

    pub fn wait(exit_code: &mut i32) -> isize {
        loop {
            match sys_waitpid(-1, exit_code as *mut _) {
                -2 => { yield_(); }
                // -1 or a real pid
                exit_pid => return exit_pid,
            }
        }
    }

``sys_waitpid`` 是一个立即返回的系统调用，它的返回值语义是：如果当前的进程不存在一个进程 ID 为 pid（pid==-1 或 pid > 0）的子进程，则返回 -1；如果存在一个进程 ID 为 pid 的僵尸子进程，则正常回收并返回子进程的 pid，并更新系统调用的退出码参数为 ``exit_code``  。这里还有一个 -2 的返回值，它的含义是子进程还没退出，通知用户库 ``user_lib`` （是实际发出系统调用的地方），这样用户库看到是 -2 后，就进一步调用 ``sys_yield`` 系统调用（第46行），让当前父进程进入等待状态。

注：在编写应用的开发者看来， 位于用户库 ``user_lib`` 中的 ``wait/waitpid`` 两个辅助函数都必定能够返回一个有意义的结果，要么是 -1，要么是一个正数 PID ，是不存在 -2 这种通过等待即可消除的中间结果的。让调用 ``wait/waitpid`` 两个辅助函数的进程等待正是在用户库 ``user_lib`` 中完成。

第 11~17 行判断 ``sys_waitpid`` 是否会返回 -1 ，这取决于当前进程是否有一个符合要求的子进程。当传入的 ``pid`` 为 -1 的时候，任何一个子进程都算是符合要求；但 ``pid`` 不为 -1 的时候，则只有 PID 恰好与 ``pid`` 相同的子进程才算符合条件。我们简单通过迭代器即可完成判断。

第 18~26 行判断符合要求的子进程中是否有僵尸进程，如果有的话还需要同时找出它在当前进程控制块子进程向量中的下标。如果找不到的话直接返回 ``-2`` ，否则进入第 27~35 行的处理：

- 第 27 行我们将子进程从向量中移除并置于当前上下文中；
- 第 29 行确认这是对于该子进程控制块的唯一一次强引用，即它不会出现在某个进程的子进程向量中，更不会出现在处理器监控器或者任务管理器中。当它所在的代码块结束，这次引用变量的生命周期结束，将导致该子进程进程控制块的引用计数变为 0 ，彻底回收掉它占用的所有资源，包括：内核栈和它的 PID 还有它的应用地址空间存放页表的那些物理页帧等等。

剩下主要是将收集的子进程信息返回。

- 第 30 行得到子进程的 PID 并会在最终返回；
- 第 32 行得到了子进程的退出码；
- 第 34 行写入到当前进程的应用地址空间中。由于应用传递给内核的仅仅是一个指向应用地址空间中保存子进程返回值的内存区域的指针，我们还需要在 ``translated_refmut`` 中手动查页表找到应该写入到物理内存中的哪个位置，这样才能把子进程的退出码 ``exit_code`` 返回给父进程。其实现可以在 ``os/src/mm/page_table.rs`` 中找到，比较简单，在这里不再赘述。


到这里，“伤齿龙”操作系统就算完成了。它在启动后，会加载执行用户态的shell程序，并可以通过shell程序提供的命令行交互界面，让使用者敲入要执行的应用程序名字，就可以创建一个子进程来执行这个应用程序，实现了灵活的人机交互和进程管理的动态灵活性。

.. chyyuu 可以加入一节，描述os的执行过程？？？