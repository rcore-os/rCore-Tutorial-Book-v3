文件与文件描述符
===========================================

文件
-------------------------------------------

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

其中 ``UserBuffer`` 是我们在 ``mm`` 子模块中定义的应用地址空间中的一段缓冲区的抽象。它本质上其实只是一个 ``&[u8]`` ，但是它位于应用地址空间中，在内核中我们无法直接通过这种方式来访问，因此需要进行封装。然而，在理解抽象接口 ``File`` 的各方法时，我们仍可以将 ``UserBuffer`` 看成一个 ``&[u8]`` ，它同时给出了缓冲区的起始地址及长度。

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