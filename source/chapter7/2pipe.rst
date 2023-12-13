管道
============================================

本节导读
--------------------------------------------

在上一节，我们实现了基于文件接口的标准输入和输出，这样一个进程可以根据不同的输入产生对应的输出。本节我们将基于上一节介绍的文件接口 ``File`` 来把不同进程的输入和输出连接起来，从而在不改变应用程序代码的情况下，让操作系统具有进程间信息交换和功能组合的能力。这需要我们实现一种父子进程间的单向进程间通信机制——管道，并为此实现两个新的系统调用 ``sys_pipe`` 和 ``sys_close`` 。

管道机制简介
--------------------------------------------

.. chyyuu 进一步介绍一下pipe的历史???

首先来介绍什么是 **管道** (Pipe) 。管道是一种进程间通信机制，由操作系统提供，并可通过直接编程或在shell程序的帮助下轻松地把不同进程（目前是父子进程之间或子子进程之间）的输入和输出对接起来。我们也可以将管道看成一个有一定缓冲区大小的字节队列，它分为读和写两端，需要通过不同的文件描述符来访问。读端只能用来从管道中读取，而写端只能用来将数据写入管道。由于管道是一个队列，读取数据的时候会从队头读取并弹出数据，而写入数据的时候则会把数据写入到队列的队尾。由于管道的缓冲区大小是有限的，一旦整个缓冲区都被填满就不能再继续写入，就需要等到读端读取并从队列中弹出一些数据之后才能继续写入。当缓冲区为空的时候，读端自然也不能继续从里面读取数据，需要等到写端写入了一些数据之后才能继续读取。

一般在shell程序中， ``“|”`` 是管道符号，即两个命令之间的一道竖杠。我们通过管道符号组合的命令，就可以了解登录Linux的用户的各种情况：

.. code-block:: shell

    who                     # 登录Linux的用户信息
    who | grep chyyuu       # 是否用户ID为chyyuu的用户登录了
    who | grep chyyuu | wc  # chyyuu用户目前在线登录的个数


管道的系统调用原型及使用方法
--------------------------------------------

接下来，我们将逐步尝试实现上面描述的管道的初步效果。我们新增一个系统调用来为当前进程打开一个代表管道的文件集（包含一个只读文件，一个只写文件）：

.. code-block:: rust

    /// 功能：为当前进程打开一个管道。
    /// 参数：pipe 表示应用地址空间中的一个长度为 2 的 usize 数组的起始地址，内核需要按顺序将管道读端
    /// 和写端的文件描述符写入到数组中。
    /// 返回值：如果出现了错误则返回 -1，否则返回 0 。可能的错误原因是：传入的地址不合法。
    /// syscall ID：59
    pub fn sys_pipe(pipe: *mut usize) -> isize;

在用户库中会将其包装为 ``pipe`` 函数：

.. code-block:: rust

    // user/src/syscall.rs

    const SYSCALL_PIPE: usize = 59;

    pub fn sys_pipe(pipe: &mut [usize]) -> isize {
        syscall(SYSCALL_PIPE, [pipe.as_mut_ptr() as usize, 0, 0])
    }

    // user/src/lib.rs

    pub fn pipe(pipe_fd: &mut [usize]) -> isize { sys_pipe(pipe_fd) }

只有当一个管道的所有读端文件/写端文件都被关闭之后，管道占用的资源才会被回收，因此我们需要通过关闭文件的系统调用 ``sys_close`` （它会在用户库中被包装为 ``close`` 函数。） ，来尽可能早的关闭之后不再用到的读端的文件和写端的文件。

.. image:: pipe-syscall.png
   :align: center
   :scale: 50 %
   :name: Pipe System Call
   :alt: 管道的系统调用原型及使用方法示意图

我们来从简单的管道测例 ``pipetest`` 中介绍管道的使用方法：

.. code-block:: rust
    :linenos:

    // user/src/bin/pipetest.rs

    #![no_std]
    #![no_main]

    #[macro_use]
    extern crate user_lib;

    use user_lib::{fork, close, pipe, read, write, wait};

    static STR: &str = "Hello, world!";

    #[no_mangle]
    pub fn main() -> i32 {
        // create pipe
        let mut pipe_fd = [0usize; 2];
        pipe(&mut pipe_fd);
        // read end
        assert_eq!(pipe_fd[0], 3);
        // write end
        assert_eq!(pipe_fd[1], 4);
        if fork() == 0 {
            // child process, read from parent
            // close write_end
            close(pipe_fd[1]);
            let mut buffer = [0u8; 32];
            let len_read = read(pipe_fd[0], &mut buffer) as usize;
            // close read_end
            close(pipe_fd[0]);
            assert_eq!(core::str::from_utf8(&buffer[..len_read]).unwrap(), STR);
            println!("Read OK, child process exited!");
            0
        } else {
            // parent process, write to child
            // close read end
            close(pipe_fd[0]);
            assert_eq!(write(pipe_fd[1], STR.as_bytes()), STR.len() as isize);
            // close write end
            close(pipe_fd[1]);
            let mut child_exit_code: i32 = 0;
            wait(&mut child_exit_code);
            assert_eq!(child_exit_code, 0);
            println!("pipetest passed!");
            0
        }
    }

在父进程中，我们通过 ``pipe`` 打开一个管道文件数组，其中 ``pipe_fd[0]`` 保存了管道读端的文件描述符，而 ``pipe_fd[1]`` 保存了管道写端的文件描述符。在 ``fork`` 之后，子进程会完全继承父进程的文件描述符表，于是子进程也可以通过同样的文件描述符来访问同一个管道的读端和写端。之前提到过管道是单向的，在这个测例中我们希望管道中的数据从父进程流向子进程，也即父进程仅通过管道的写端写入数据，而子进程仅通过管道的读端读取数据。

因此，在第 25 和第 36 行，分别第一时间在子进程中关闭管道的写端和在父进程中关闭管道的读端。父进程在第 37 行将字符串 ``STR`` 写入管道的写端，随后在第 39 行关闭管道的写端；子进程在第 27 行从管道的读端读取字符串，并在第 29 行关闭。

如果想在父子进程之间实现双向通信，我们就必须创建两个管道。有兴趣的同学可以参考测例 ``pipe_large_test`` 。

基于文件的管道
--------------------------------------------

我们将管道的一端（读端或写端）抽象为 ``Pipe`` 类型：

.. code-block:: rust

    // os/src/fs/pipe.rs

    pub struct Pipe {
        readable: bool,
        writable: bool,
        buffer: Arc<Mutex<PipeRingBuffer>>,
    }

``readable`` 和 ``writable`` 分别指出该管道端可否支持读取/写入，通过 ``buffer`` 字段还可以找到该管道端所在的管道自身。后续我们将为它实现 ``File`` Trait ，之后它便可以通过文件描述符来访问。

而管道自身，也就是那个带有一定大小缓冲区的字节队列，我们抽象为 ``PipeRingBuffer`` 类型：

.. code-block:: rust

    // os/src/fs/pipe.rs

    const RING_BUFFER_SIZE: usize = 32;

    #[derive(Copy, Clone, PartialEq)]
    enum RingBufferStatus {
        FULL,
        EMPTY,
        NORMAL,
    }

    pub struct PipeRingBuffer {
        arr: [u8; RING_BUFFER_SIZE],
        head: usize,
        tail: usize,
        status: RingBufferStatus,
        write_end: Option<Weak<Pipe>>,
    }

- ``RingBufferStatus`` 记录了缓冲区目前的状态：``FULL`` 表示缓冲区已满不能再继续写入； ``EMPTY`` 表示缓冲区为空无法从里面读取；而 ``NORMAL`` 则表示除了 ``FULL`` 和 ``EMPTY`` 之外的其他状态。
- ``PipeRingBuffer`` 的 ``arr/head/tail`` 三个字段用来维护一个循环队列，其中 ``arr`` 为存放数据的数组， ``head`` 为循环队列队头的下标， ``tail`` 为循环队列队尾的下标。
- ``PipeRingBuffer`` 的 ``write_end`` 字段还保存了它的写端的一个弱引用计数，这是由于在某些情况下需要确认该管道所有的写端是否都已经被关闭了，通过这个字段很容易确认这一点。

从内存管理的角度，每个读端或写端中都保存着所属管道自身的强引用计数，且我们确保这些引用计数只会出现在管道端口 ``Pipe`` 结构体中。于是，一旦一个管道所有的读端和写端均被关闭，便会导致它们所属管道的引用计数变为 0 ，循环队列缓冲区所占用的资源被自动回收。虽然 ``PipeRingBuffer`` 中保存了一个指向写端的引用计数，但是它是一个弱引用，也就不会出现循环引用的情况导致内存泄露。

.. chyyuu 介绍弱引用???

管道创建
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

通过 ``PipeRingBuffer::new`` 可以创建一个新的管道：

.. code-block:: rust

    // os/src/fs/pipe.rs

    impl PipeRingBuffer {
        pub fn new() -> Self {
            Self {
                arr: [0; RING_BUFFER_SIZE],
                head: 0,
                tail: 0,
                status: RingBufferStatus::EMPTY,
                write_end: None,
            }
        }
    }

``Pipe`` 的 ``read/write_end_with_buffer`` 方法可以分别从一个已有的管道创建它的读端和写端：

.. code-block:: rust

    // os/src/fs/pipe.rs

    impl Pipe {
        pub fn read_end_with_buffer(buffer: Arc<Mutex<PipeRingBuffer>>) -> Self {
            Self {
                readable: true,
                writable: false,
                buffer,
            }
        }
        pub fn write_end_with_buffer(buffer: Arc<Mutex<PipeRingBuffer>>) -> Self {
            Self {
                readable: false,
                writable: true,
                buffer,
            }
        }
    }

可以看到，读端和写端的访问权限进行了相应设置：不允许向读端写入，也不允许从写端读取。

通过 ``make_pipe`` 方法可以创建一个管道并返回它的读端和写端：

.. code-block:: rust
    
    // os/src/fs/pipe.rs

    impl PipeRingBuffer {
        pub fn set_write_end(&mut self, write_end: &Arc<Pipe>) {
            self.write_end = Some(Arc::downgrade(write_end));
        }
    }

    /// Return (read_end, write_end)
    pub fn make_pipe() -> (Arc<Pipe>, Arc<Pipe>) {
        let buffer = Arc::new(Mutex::new(PipeRingBuffer::new()));
        let read_end = Arc::new(
            Pipe::read_end_with_buffer(buffer.clone())
        );
        let write_end = Arc::new(
            Pipe::write_end_with_buffer(buffer.clone())
        );
        buffer.lock().set_write_end(&write_end);
        (read_end, write_end)
    }

注意，我们调用 ``PipeRingBuffer::set_write_end`` 在管道中保留它的写端的弱引用计数。

现在来实现创建管道的系统调用 ``sys_pipe`` ：

.. code-block:: rust
    :linenos:

    // os/src/task/task.rs

    impl TaskControlBlockInner {
        pub fn alloc_fd(&mut self) -> usize {
            if let Some(fd) = (0..self.fd_table.len())
                .find(|fd| self.fd_table[*fd].is_none()) {
                fd
            } else {
                self.fd_table.push(None);
                self.fd_table.len() - 1
            }
        }
    }

    // os/src/syscall/fs.rs

    pub fn sys_pipe(pipe: *mut usize) -> isize {
        let task = current_task().unwrap();
        let token = current_user_token();
        let mut inner = task.acquire_inner_lock();
        let (pipe_read, pipe_write) = make_pipe();
        let read_fd = inner.alloc_fd();
        inner.fd_table[read_fd] = Some(pipe_read);
        let write_fd = inner.alloc_fd();
        inner.fd_table[write_fd] = Some(pipe_write);
        *translated_refmut(token, pipe) = read_fd;
        *translated_refmut(token, unsafe { pipe.add(1) }) = write_fd;
        0
    }

``TaskControlBlockInner::alloc_fd`` 可以在进程控制块中分配一个最小的空闲文件描述符来访问一个新打开的文件。它先从小到大遍历所有曾经被分配过的文件描述符尝试找到一个空闲的，如果没有的话就需要拓展文件描述符表的长度并新分配一个。

在 ``sys_pipe`` 中，第 21 行我们调用 ``make_pipe`` 创建一个管道并获取其读端和写端，第 22~25 行我们分别为读端和写端分配文件描述符并将它们放置在文件描述符表中的相应位置中。第 26~27 行我们则是将读端和写端的文件描述符写回到应用地址空间。

管道读写
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

首先来看如何为 ``Pipe`` 实现 ``File`` Trait 的 ``read`` 方法，即从管道的读端读取数据。在此之前，我们需要对于管道循环队列进行封装来让它更易于使用：

.. code-block:: rust
    :linenos:

    // os/src/fs/pipe.rs

    impl PipeRingBuffer {
        pub fn read_byte(&mut self) -> u8 {
            self.status = RingBufferStatus::NORMAL;
            let c = self.arr[self.head];
            self.head = (self.head + 1) % RING_BUFFER_SIZE;
            if self.head == self.tail {
                self.status = RingBufferStatus::EMPTY;
            }
            c
        }
        pub fn available_read(&self) -> usize {
            if self.status == RingBufferStatus::EMPTY {
                0
            } else {
                if self.tail > self.head {
                    self.tail - self.head
                } else {
                    self.tail + RING_BUFFER_SIZE - self.head
                }
            }
        }
        pub fn all_write_ends_closed(&self) -> bool {
            self.write_end.as_ref().unwrap().upgrade().is_none()
        }
    }

``PipeRingBuffer::read_byte`` 方法可以从管道中读取一个字节，注意在调用它之前需要确保管道缓冲区中不是空的。它会更新循环队列队头的位置，并比较队头和队尾是否相同，如果相同的话则说明管道的状态变为空 ``EMPTY`` 。仅仅通过比较队头和队尾是否相同不能确定循环队列是否为空，因为它既有可能表示队列为空，也有可能表示队列已满。因此我们需要在 ``read_byte`` 的同时进行状态更新。

``PipeRingBuffer::available_read`` 可以计算管道中还有多少个字符可以读取。我们首先需要判断队列是否为空，因为队头和队尾相等可能表示队列为空或队列已满，两种情况 ``available_read`` 的返回值截然不同。如果队列为空的话直接返回 0，否则根据队头和队尾的相对位置进行计算。

``PipeRingBuffer::all_write_ends_closed`` 可以判断管道的所有写端是否都被关闭了，这是通过尝试将管道中保存的写端的弱引用计数升级为强引用计数来实现的。如果升级失败的话，说明管道写端的强引用计数为 0 ，也就意味着管道所有写端都被关闭了，从而管道中的数据不会再得到补充，待管道中仅剩的数据被读取完毕之后，管道就可以被销毁了。

下面是 ``Pipe`` 的 ``read`` 方法的实现：

.. code-block:: rust
    :linenos:

    // os/src/fs/pipe.rs

    impl File for Pipe {
        fn read(&self, buf: UserBuffer) -> usize {
            assert!(self.readable());
            let want_to_read = buf.len();
            let mut buf_iter = buf.into_iter();
            let mut already_read = 0usize;
            loop {
                let mut ring_buffer = self.buffer.exclusive_access();
                let loop_read = ring_buffer.available_read();
                if loop_read == 0 {
                    if ring_buffer.all_write_ends_closed() {
                        return already_read;
                    }
                    drop(ring_buffer);
                    suspend_current_and_run_next();
                    continue;
                }
                for _ in 0..loop_read {
                    if let Some(byte_ref) = buf_iter.next() {
                        unsafe {
                            *byte_ref = ring_buffer.read_byte();
                        }
                        already_read += 1;
                        if already_read == want_to_read {
                            return want_to_read;
                        }
                    } else {
                        return already_read;
                    }
                }
            }
        }
    }


- 第 7 行的 ``buf_iter`` 将传入的应用缓冲区 ``buf`` 转化为一个能够逐字节对于缓冲区进行访问的迭代器，每次调用 ``buf_iter.next()`` 即可按顺序取出用于访问缓冲区中一个字节的裸指针。
- 第 8 行的 ``already_read`` 用来维护实际有多少字节从管道读入应用的缓冲区。
- ``File::read`` 的语义是要从文件中最多读取应用缓冲区大小那么多字符。这可能超出了循环队列的大小，或者由于尚未有进程从管道的写端写入足够的字符，因此我们需要将整个读取的过程放在一个循环中，当循环队列中不存在足够字符的时候暂时进行任务切换，等待循环队列中的字符得到补充之后再继续读取。
  
  这个循环从第 9 行开始，第 11 行我们用 ``loop_read`` 来表示循环这一轮次中可以从管道循环队列中读取多少字符。如果管道为空则会检查管道的所有写端是否都已经被关闭，如果是的话，说明我们已经没有任何字符可以读取了，这时可以直接返回；否则我们需要等管道的字符得到填充之后再继续读取，因此我们调用 ``suspend_current_and_run_next`` 切换到其他任务，等到切换回来之后回到循环开头再看一下管道中是否有字符了。在调用之前我们需要手动释放管道自身的锁，因为切换任务时候的 ``__switch`` 跨越了正常函数调用的边界。

  如果 ``loop_read`` 不为 0 ，在这一轮次中管道中就有 ``loop_read`` 个字节可以读取。我们可以迭代应用缓冲区中的每个字节指针，并调用 ``PipeRingBuffer::read_byte`` 方法来从管道中进行读取。如果这 ``loop_read`` 个字节均被读取之后还没有填满应用缓冲区，就需要进入循环的下一个轮次，否则就可以直接返回了。在具体实现的时候注意边界条件的判断。

``Pipe`` 的 ``write`` 方法 -- 即通过管道的写端向管道中写入数据的实现和 ``read`` 的原理类似，篇幅所限在这里不再赘述，感兴趣的同学可自行参考其实现。

这样我们就为管道 ``Pipe`` 实现了上节中的通用文件接口 ``File`` trait，并将其顺利整合到了文件子系统中。上一节我们提到子进程会继承父进程的所有文件描述符，管道自然也包括在内，使得父子进程可以使用共享的单向管道进行通信了。


小结
--------------------------------------------

这一章讲述的重点是一种有趣的进程间通信的机制--管道。通过管道，能够把不同进程的输入和输出连接在一起，实现进程功能的组合。为了能够统一表示输入，输出，以及管道，我们给出了与 **地址空间** 、 **进程** 齐名的操作系统抽象 **文件** ，并基于文件重构了操作系统的输入/输出机制。目前，仅仅实现了非常简单的基于父子进程的管道机制。在操作系统层面，还缺乏对命令行参数的支持，在应用层面，还缺少I/O重定向和shell程序中基于 "|" 管道符号的支持。但我们已经建立了基本的进程通信机制，实现了支持协作的白垩纪“迅猛龙”操作系统的大部分功能，使得应用程序之间可以合作完成更复杂的工作。
但如果要让相互独立的应用程序之间也能合作，还需要对应用的执行参数进行一定的扩展，支持进程执行的命令行参数。这样才能在应用程序的层面，完善I/O重定向，并在shell中支持基于 "|" 管道符号，形成更加灵活的独立进程间的通信能力和shell命令行支持。
