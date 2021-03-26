文件与文件描述符
===========================================

本节导读
-------------------------------------------

本节我们介绍文件和文件描述符概念，并在进程中加入文件描述符表，同时将进程对于标准输入输出的访问的修改为基于文件抽象接口的实现。

文件
-------------------------------------------

.. chyyuu 可以简单介绍一下文件的起源???

在类 Unix 操作系统中，”**一切皆文件**“ (Everything is a file) 是一种重要的设计哲学。在这里，所谓的 **文件** (File) 就是指由内核管理并分配给进程让它可以与之交互的部分 I/O 资源，它大致可以分成以下几种：

- **普通文件** (Regular File) 指的是储存在磁盘/硬盘等存储介质上的文件系统中的一般意义上的文件，可以被看成一个固定的字节序列；
- **目录** (Directory) 是用来建立树形目录结构的文件系统并可以根据路径索引文件的一种特殊的文件；
- **符号链接** (Symbolic Link) 一种能够指向其他文件的特殊文件；
- **命名管道** (Named Pipe) 与我们本章将介绍的 **匿名管道** (Pipe) 有一些不同，但它们均用于单向的进程间通信；
- **套接字** (Socket) 可以支持双向的进程间通信；
- **设备文件** (Device File) 可以与系统中的 I/O 设备进行交互。这些 I/O 设备可以分成两类： **块设备** (Block Device) 和 **字符设备** (Character Device) 。块设备只能以 **块** (Block) 为单位进行读写，并支持随机访问，最典型的如一些磁盘/硬盘等；而字符设备允许发送者和接收者传输一条字节流，接收者只能按照发送者发送的顺序接收字符，最典型的如键盘/串口等。

文件虽然代表了很多种不同的软件/硬件 I/O 资源，但是在进程看来所有文件的访问都可以通过一个统一的抽象接口 ``File`` 来进行：

.. code-block:: rust

    // os/src/fs/mod.rs

    pub trait File : Send + Sync {
        fn read(&self, buf: UserBuffer) -> usize;
        fn write(&self, buf: UserBuffer) -> usize;
    }

其中 ``UserBuffer`` 是我们在 ``mm`` 子模块中定义的应用地址空间中的一段缓冲区的抽象。它本质上其实只是一个 ``&[u8]`` ，但是它位于应用地址空间中，在内核中我们无法直接通过这种方式来访问，因此需要进行封装。然而，在理解抽象接口 ``File`` 的各方法时，我们仍可以将 ``UserBuffer`` 看成一个 ``&[u8]`` 切片，它是同时给出了缓冲区的起始地址及长度的一个胖指针。

``read`` 指的是从文件中读取数据放到缓冲区中，最多将缓冲区填满（即读取缓冲区的长度那么多字节），并返回实际读取的字节数；而 ``write`` 指的是将缓冲区中的数据写入文件，最多将缓冲区中的数据全部写入，并返回直接写入的字节数。至于 ``read`` 和 ``write`` 的实现则与文件具体是哪种类型有关，它决定了数据如何被读取和写入。

回过头来再看一下用户缓冲区的抽象 ``UserBuffer`` ，它的声明如下：

.. code-block:: rust

    // os/src/mm/page_table.rs

    pub fn translated_byte_buffer(
        token: usize,
        ptr: *const u8,
        len: usize
    ) -> Vec<&'static mut [u8]>;

    pub struct UserBuffer {
        pub buffers: Vec<&'static mut [u8]>,
    }

    impl UserBuffer {
        pub fn new(buffers: Vec<&'static mut [u8]>) -> Self {
            Self { buffers }
        }
        pub fn len(&self) -> usize {
            let mut total: usize = 0;
            for b in self.buffers.iter() {
                total += b.len();
            }
            total
        }
    }

它只是将我们调用 ``translated_byte_buffer`` 获得的包含多个切片的 ``Vec`` 进一步包装起来，通过 ``len`` 方法可以得到缓冲区的长度。此外，我们还让它作为一个迭代器可以逐字节进行读写。有兴趣的读者可以参考类型 ``UserBufferIterator`` 还有 ``IntoIterator`` 和 ``Iterator`` 两个 Trait 的使用方法。

标准输入和标准输出
--------------------------------------------

我们为标准输入和标准输出实现 ``File`` Trait，使得进程可以与它们交互：

.. code-block:: rust
    :linenos:

    // os/src/fs/stdio.rs

    pub struct Stdin;

    pub struct Stdout;

    impl File for Stdin {
        fn read(&self, mut user_buf: UserBuffer) -> usize {
            assert_eq!(user_buf.len(), 1);
            // busy loop
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
            unsafe { user_buf.buffers[0].as_mut_ptr().write_volatile(ch); }
            1
        }
        fn write(&self, _user_buf: UserBuffer) -> usize {
            panic!("Cannot write to stdin!");
        }
    }

    impl File for Stdout {
        fn read(&self, _user_buf: UserBuffer) -> usize{
            panic!("Cannot read from stdout!");
        }
        fn write(&self, user_buf: UserBuffer) -> usize {
            for buffer in user_buf.buffers.iter() {
                print!("{}", core::str::from_utf8(*buffer).unwrap());
            }
            user_buf.len()
        }
    }

可以看到，标准输入 ``Stdin`` 只允许进程通过 ``read`` 从里面读入，目前每次仅支持读入一个字符，其实现与之前的 ``sys_read`` 基本相同，只是需要通过 ``UserBuffer`` 来获取具体将字节写入的位置。相反，标准输出 ``Stdout`` 只允许进程通过 ``write`` 写入到里面，实现方法是遍历每个切片，将其转化为字符串通过 ``print!`` 宏来输出。值得注意的是，如果有多核同时使用 ``print!`` 宏，将会导致两个不同的输出交错到一起造成输出混乱，后续我们还会对它做一些改进。

文件描述符与文件描述符表
--------------------------------------------

.. chyyuu 可以解释一下文件描述符的起因???

每个进程都带有一个线性的 **文件描述符表** (File Descriptor Table) 记录所有它请求内核打开并可以读写的那些文件。而 **文件描述符** (File Descriptor) 则是一个非负整数，表示文件描述符表中一个打开的文件所处的位置。通过文件描述符，进程可以在自身的文件描述符表中找到对应的文件，并进行读写。当打开一个文件的时候，如果顺利，内核会返回给应用刚刚打开的文件的文件描述符；而当应用想关闭一个文件的时候，也需要向内核提供对应的文件描述符。

当一个进程被创建的时候，内核会默认为其打开三个文件：

- 文件描述符为 0 的标准输入；
- 文件描述符为 1 的标准输出；
- 文件描述符为 2 的标准错误输出。

在我们的实现中并不区分标准输出和标准错误输出，而是会将文件描述符 1 和 2 均对应到标准输出。

这里隐含着有关文件描述符的一条重要的规则：即进程打开一个文件的时候，内核总是会将文件分配到该进程文件描述符表中 **最小的** 空闲位置。比如，当一个进程被创建以后立即打开一个文件，则内核总是会返回文件描述符 3 。当我们关闭一个打开的文件之后，它对应的文件描述符将会变得空闲并在后面可以被分配出去。

我们需要在进程控制块中加入文件描述符表的相应字段：

.. code-block:: rust
    :linenos:
    :emphasize-lines: 12

    // os/src/task/task.rs

    pub struct TaskControlBlockInner {
        pub trap_cx_ppn: PhysPageNum,
        pub base_size: usize,
        pub task_cx_ptr: usize,
        pub task_status: TaskStatus,
        pub memory_set: MemorySet,
        pub parent: Option<Weak<TaskControlBlock>>,
        pub children: Vec<Arc<TaskControlBlock>>,
        pub exit_code: i32,
        pub fd_table: Vec<Option<Arc<dyn File + Send + Sync>>>,
    }

可以看到 ``fd_table`` 的类型包含多层嵌套，我们从外到里分别说明：

- ``Vec`` 的动态长度特性使得我们无需设置一个固定的文件描述符数量上限，我们可以更加灵活的使用内存，而不必操心内存管理问题；
- ``Option`` 使得我们可以区分一个文件描述符当前是否空闲，当它是 ``None`` 的时候是空闲的，而 ``Some`` 则代表它已被占用；
- ``Arc`` 首先提供了共享引用能力。后面我们会提到，可能会有多个进程共享同一个文件对它进行读写。此外被它包裹的内容会被放到内核堆而不是栈上，于是它便不需要在编译期有着确定的大小；
- ``dyn`` 关键字表明 ``Arc`` 里面的类型实现了 ``File/Send/Sync`` 三个 Trait ，但是编译期无法知道它具体是哪个类型（可能是任何实现了 ``File`` Trait 的类型如 ``Stdin/Stdout`` ，故而它所占的空间大小自然也无法确定），需要等到运行时才能知道它的具体类型，对于一些抽象方法的调用也是在那个时候才能找到该类型实现的版本的地址并跳转过去。

.. note::

    **Rust 语法卡片：Rust 中的多态**

    在编程语言中， **多态** (Polymorphism) 指的是在同一段代码中可以隐含多种不同类型的特征。在 Rust 中主要通过泛型和 Trait 来实现多态。
    
    泛型是一种 **编译期多态** (Static Polymorphism)，在编译一个泛型函数的时候，编译器会对于所有可能用到的类型进行实例化并对应生成一个版本的汇编代码，在编译期就能知道选取哪个版本并确定函数地址，这可能会导致生成的二进制文件体积较大；而 Trait 对象（也即上面提到的 ``dyn`` 语法）是一种 **运行时多态** (Dynamic Polymorphism)，需要在运行时查一种类似于 C++ 中的 **虚表** (Virtual Table) 才能找到实际类型对于抽象接口实现的函数地址并进行调用，这样会带来一定的运行时开销，但是更为灵活。

当新建一个进程的时候，我们需要按照先前的说明为进程打开标准输入输出：

.. code-block:: rust
    :linenos:
    :emphasize-lines: 18-25

    // os/src/task/task.rs

    impl TaskControlBlock {
        pub fn new(elf_data: &[u8]) -> Self {
            ...
            let task_control_block = Self {
                pid: pid_handle,
                kernel_stack,
                inner: Mutex::new(TaskControlBlockInner {
                    trap_cx_ppn,
                    base_size: user_sp,
                    task_cx_ptr: task_cx_ptr as usize,
                    task_status: TaskStatus::Ready,
                    memory_set,
                    parent: None,
                    children: Vec::new(),
                    exit_code: 0,
                    fd_table: vec![
                        // 0 -> stdin
                        Some(Arc::new(Stdin)),
                        // 1 -> stdout
                        Some(Arc::new(Stdout)),
                        // 2 -> stderr
                        Some(Arc::new(Stdout)),
                    ],
                }),
            };
            ...
        }
    }

此外，在 fork 的时候，子进程需要完全继承父进程的文件描述符表来和父进程共享所有文件：

.. code-block:: rust
    :linenos:
    :emphasize-lines: 8-16,29

    // os/src/task/task.rs

    impl TaskControlBlock {
        pub fn fork(self: &Arc<TaskControlBlock>) -> Arc<TaskControlBlock> {
            ...
            // push a goto_trap_return task_cx on the top of kernel stack
            let task_cx_ptr = kernel_stack.push_on_top(TaskContext::goto_trap_return());
            // copy fd table
            let mut new_fd_table: Vec<Option<Arc<dyn File + Send + Sync>>> = Vec::new();
            for fd in parent_inner.fd_table.iter() {
                if let Some(file) = fd {
                    new_fd_table.push(Some(file.clone()));
                } else {
                    new_fd_table.push(None);
                }
            }
            let task_control_block = Arc::new(TaskControlBlock {
                pid: pid_handle,
                kernel_stack,
                inner: Mutex::new(TaskControlBlockInner {
                    trap_cx_ppn,
                    base_size: parent_inner.base_size,
                    task_cx_ptr: task_cx_ptr as usize,
                    task_status: TaskStatus::Ready,
                    memory_set,
                    parent: Some(Arc::downgrade(self)),
                    children: Vec::new(),
                    exit_code: 0,
                    fd_table: new_fd_table,
                }),
            });
            // add child
            ...
        }
    }

这样，即使我们仅手动为初始进程 ``initproc`` 打开了标准输入输出，所有进程也都可以访问它们。

文件读写系统调用
---------------------------------------------------

基于文件抽象接口和文件描述符表，我们终于可以让文件读写系统调用 ``sys_read/write`` 变得更加具有普适性，不仅仅局限于标准输入输出：

.. code-block:: rust

    // os/src/syscall/fs.rs

    pub fn sys_write(fd: usize, buf: *const u8, len: usize) -> isize {
        let token = current_user_token();
        let task = current_task().unwrap();
        let inner = task.acquire_inner_lock();
        if fd >= inner.fd_table.len() {
            return -1;
        }
        if let Some(file) = &inner.fd_table[fd] {
            let file = file.clone();
            // release Task lock manually to avoid deadlock
            drop(inner);
            file.write(
                UserBuffer::new(translated_byte_buffer(token, buf, len))
            ) as isize
        } else {
            -1
        }
    }

    pub fn sys_read(fd: usize, buf: *const u8, len: usize) -> isize {
        let token = current_user_token();
        let task = current_task().unwrap();
        let inner = task.acquire_inner_lock();
        if fd >= inner.fd_table.len() {
            return -1;
        }
        if let Some(file) = &inner.fd_table[fd] {
            let file = file.clone();
            // release Task lock manually to avoid deadlock
            drop(inner);
            file.read(
                UserBuffer::new(translated_byte_buffer(token, buf, len))
            ) as isize
        } else {
            -1
        }
    }

我们都是在当前进程的文件描述符表中通过文件描述符找到某个文件，无需关心文件具体的类型，只要知道它一定实现了 ``File`` Trait 的 ``read/write`` 方法即可。Trait 对象提供的运行时多态能力会在运行的时候帮助我们定位到 ``read/write`` 的符合实际类型的实现。