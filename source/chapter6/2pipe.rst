管道
============================================

本节导读
--------------------------------------------

本节我们基于上一节介绍的抽象文件接口 ``File`` 实现一种父子进程间的单向进程间通信机制——管道，同时实现两个新的系统调用 ``sys_pipe`` 和 ``sys_close`` 。

管道的系统调用原型及使用方法
--------------------------------------------

首先来介绍什么是 **管道** (Pipe) 。我们可以将管道看成一个有一定缓冲区大小的字节队列，它分为读和写两端，需要通过不同的文件描述符来访问。读端只能用来从管道中读取，而写端只能用来将数据写入管道。由于管道是一个队列，读取的时候会从队头读取并弹出，而写入的时候则会写入到队列的队尾。同时，管道的缓冲区大小是有限的，一旦整个缓冲区都被填满就不能再继续写入，需要等到读端读取并从队列中弹出一些字符之后才能继续写入。当缓冲区为空的时候自然也不能继续从里面读取，需要等到写端写入了一些数据之后才能继续读取。

我们新增一个系统调用来为当前进程打开一个管道：

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

只有当一个管道的所有读端/写端都被关闭之后，管道占用的资源才会被回收，因此我们需要通过关闭文件的系统调用 ``sys_close`` 来尽可能早的关闭之后不再用到的读端和写端。

.. code-block:: rust

    /// 功能：当前进程关闭一个文件。
    /// 参数：fd 表示要关闭的文件的文件描述符。
    /// 返回值：如果成功关闭则返回 0 ，否则返回 -1 。可能的出错原因：传入的文件描述符并不对应一个打开的文件。
    /// syscall ID：57
    pub fn sys_close(fd: usize) -> isize;

它会在用户库中被包装为 ``close`` 函数。

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

在父进程中，我们通过 ``pipe`` 打开一个管道，于是 ``pipe_fd[0]`` 保存了管道读端的文件描述符，而 ``pipe_fd[1]`` 保存了管道写端的文件描述符。在 ``fork`` 之后，子进程会完全继承父进程的文件描述符表，于是子进程也可以通过同样的文件描述符来访问同一个管道的读端和写端。之前提到过管道是单向的，在这个测例中我们希望管道中的数据从父进程流向子进程，也即父进程仅通过管道的写端写入数据，而子进程仅通过管道的读端读取数据。

因此，我们分别在第 25 和第 34 行第一时间在子进程中关闭管道的写端和在父进程中关闭管道的读端。父进程在第 35 行将字符串 ``STR`` 写入管道的写端，随后在第 37 行关闭管道的写端；子进程在第 27 行从管道的读端读取字符串，并在第 29 行关闭。

如果想在父子进程之间实现双向通信，我们就必须创建两个管道。有兴趣的读者可以参考测例 ``pipe_large_test`` 。

通过 sys_close 关闭文件
--------------------------------------------

关闭文件的系统调用 ``sys_close`` 实现非常简单，我们只需将进程控制块中的文件描述符表对应的一项改为 ``None`` 代表它已经空闲即可，同时这也会导致内层的引用计数类型 ``Arc`` 被销毁，会减少一个文件的引用计数，当引用计数减少到 0 之后文件所占用的资源就会被自动回收。

.. code-block:: rust

    // os/src/syscall/fs.rs

    pub fn sys_close(fd: usize) -> isize {
        let task = current_task().unwrap();
        let mut inner = task.acquire_inner_lock();
        if fd >= inner.fd_table.len() {
            return -1;
        }
        if inner.fd_table[fd].is_none() {
            return -1;
        }
        inner.fd_table[fd].take();
        0
    }

管道的实现
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

从内存管理的角度，每个读端或写端中都保存着所属管道自身的强引用计数，且我们确保这些引用计数只会出现在 ``Pipe`` 结构体中。于是，一旦一个管道所有的读端和写端均被关闭，便会导致它们所属管道的引用计数变为 0 ，循环队列缓冲区所占用的资源被自动回收。虽然 ``PipeRingBuffer`` 中保存了一个指向写端的引用计数，但是它是一个弱引用，也就不会出现循环引用的情况导致内存泄露。