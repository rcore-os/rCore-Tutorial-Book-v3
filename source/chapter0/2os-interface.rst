操作系统的系统调用接口
================================================

.. toctree::
   :hidden:
   :maxdepth: 5

API与ABI
--------------------

站在使用操作系统的角度会比较容易对操作系统内核的功能产生初步的认识。操作系统内核是一个提供各种服务的软件，其服务对象是应用程序，而用户（这里可以理解为一般使用计算机的人）是通过应用程序的服务间接获得操作系统的服务的，因此操作系统内核藏在一般用户看不到的地方。但应用程序需要访问操作系统获得操作系统的服务，这就需要通过操作系统的接口才能完成。操作系统与运行在用户态软件之间的接口形式就是上一节提到的应用程序二进制接口 (ABI, Application Binary Interface)。

操作系统不能只提供面向单一编程语言的函数库的编程接口 (API, Application Programming Interface) ，它的接口需要考虑对基于各种编程语言的应用支持，以及访问安全等因素，使得应用软件不能像访问函数库一样的直接访问操作系统内部函数，更不能直接读写操作系统内部的地址空间。为此，操作系统设计了一套安全可靠的二进制接口，我们称为系统调用接口 (System Call Interface)。系统调用接口通常面向应用程序提供了 API 的描述，但在具体实现上，还需要提供 ABI 的接口描述规范。

在现代处理器的安全支持（特权级隔离，内存空间隔离等）下，应用程序就不能直接以函数调用的方式访问操作系统的函数，以及直接读写操作系统的数据变量。不同类型的应用程序可以通过符合操作系统规定的系统调用接口，发出系统调用请求，来获得操作系统的服务。操作系统提供完服务后，返回应用程序继续执行。


.. note::

   **API 与 ABI 的区别**
   
   应用程序二进制接口 ABI 是不同二进制代码片段的连接纽带。ABI 定义了二进制机器代码级别的规则，主要包括基本数据类型、通用寄存器的使用、参数的传递规则、以及堆栈的使用等等。ABI 与处理器和内存地址等硬件架构相关，是用来约束链接器 (Linker) 和汇编器 (Assembler) 的。在同一处理器下，基于不同高级语言编写的应用程序、库和操作系统，如果遵循同样的 ABI 定义，那么它们就能正确链接和执行。

   应用程序编程接口 API 是不同源代码片段的连接纽带。API 定义了一个源码级（如 C 语言）函数的参数，参数的类型，函数的返回值等。因此 API 是用来约束编译器 (Compiler) 的：一个 API 是给编译器的一些指令，它规定了源代码可以做以及不可以做哪些事。API 与编程语言相关，如 libc 是基于 C 语言编写的标准库，那么基于 C 的应用程序就可以通过编译器建立与 libc 的联系，并能在运行中正确访问 libc 中的函数。

.. chyyuu 应该给具体的例子，说明 API, ABI的区别。学生提问"一直想不出来ABI是怎么被用户空间程序调用的"

系统调用接口与功能
------------------------------

对于通用的应用程序，一般需要关注如下问题，并希望得到操作系统的支持：

- 一个运行的程序如何能输出字符信息？如何能获得输入字符信息？
- 一个运行的程序可以要求更多（或更少）的内存空间吗？
- 一个运行的程序如何持久地存储用户数据？
- 一个运行的程序如何与连接到计算机的设备通信并通过它们与物理世界通信？
- 多个运行的程序如何同步互斥地对共享资源进行访问？
- 一个运行的程序可以创建另一个程序的实例吗？需要等待另外一个程序执行完成吗？一个运行的程序能暂停或恢复另一个正在运行的程序吗？

操作系统主要通过基于 ABI 的系统调用接口来给应用程序提供上述服务，以支持应用程序的各种需求。对于实际操作系统而言，有多少操作系统，就有多少种不同类型的系统调用接口。通用操作系统为支持各种应用的服务需求，需要有相对多的系统调用服务接口，比如目前 Linux 有超过三百个的系统调用接口。下面列出了一些相对比较重要的操作系统接口或抽象，以及它们的大致功能：

* 进程（即程序运行过程）管理：复制创建进程 fork 、退出进程 exit 、执行进程 exec 等。
* 线程管理：线程（即程序的一个执行流）的创建、执行、调度切换等。
* 线程同步互斥的并发控制：互斥锁 mutex 、信号量 semaphore 、管程 monitor 、条件变量 condition variable 等。
* 进程间通信：管道 pipe 、信号 signal 、事件 event 等。
* 虚存管理：内存空间映射 mmap 、改变数据段地址空间大小 sbrk 、共享内存 shm 等。
* 文件 I/O 操作：对存储设备中的文件进行读 read 、写 write 、打开 open 、关闭 close 等操作。
* 外设 I/O 操作：外设包括键盘、显示器、串口、磁盘、时钟 ... ，主要采用文件 I/O 操作接口。

.. note::

   上述表述在某种程度上说明了操作系统对计算机硬件重要组成的抽象和虚拟化，这样会有助于应用程序开发。应用程序员只需访问统一的抽象概念（如文件、进程等），就可以使用各种复杂的计算机物理资源（处理器、内存、外设等）：

   * 文件 (File) 是外设的一种抽象和虚拟化。特别对于存储外设而言，文件是持久存储的抽象。
   * 地址空间 (Address Space) 是对内存的抽象和虚拟化。
   * 进程 (Process) 是对计算机资源的抽象和虚拟化。而其中最核心的部分是对 CPU 的抽象与虚拟化。



.. image:: run-app.png
   :align: center
   :name: run-app

有了这些系统调用接口，简单的应用程序就不用考虑底层硬件细节，可以在操作系统的服务支持和管理下简洁地完成其应用功能了。在现阶段，也许大家对进程、文件、地址空间等抽象概念还不了解，在接下来的章节会对这些概念有进一步的介绍。值得注意的是，我们设计的各种操作系统总共只用到三十个左右系统调用功能接口（如下表所示），就可以支持应用需要的上述功能。而且这些调用与最初的 UNIX 的系统调用接口类似，几乎没有变化。尽管UNIX 的系统调用最早是在 1970 年左右设计和实现的，但这些调用中的大多数仍然在今天的系统中广泛使用。

..  chyyuu 在线组织表格 https://tableconvert.com/restructuredtext-generator 再用 format current (ctrl-alt-T C)格式化



====  ====================  =============  ===============================
编号   系统调用              所在章节        功能描述
====  ====================  =============  ===============================
1     sys_exit                 2           结束执行
2     sys_write                2/6         (2)输出字符串/(6)写文件
3     sys_yield                3           暂时放弃执行
4     sys_get_time             3           获取当前时间
5     sys_getpid               5           获取进程id
6     sys_fork                 5           创建子进程
7     sys_exec                 5           执行新程序
8     sys_waitpid              5           等待子进程结束
9     sys_read                 5/6         (5)读取字符串/(6)读文件
10    sys_open                 6           打开/创建文件
11    sys_close                6           关闭文件
12    sys_dup                  7           复制文件描述符
13    sys_pipe                 7           创建管道
14    sys_kill                 7           发送信号给某进程
15    sys_sigaction            7           设立信号处理例程
16    sys_sigprocmask          7           设置要阻止的信号
17    sys_sigreturn            7           从信号处理例程返回
18    sys_sleep                8           进程休眠一段时间
19    sys_thread_create        8           创建线程
20    sys_gettid               8           获取线程id
21    sys_waittid              8           等待线程结束
22    sys_mutex_create         8           创建锁
23    sys_mutex_lock           8           获取锁
24    sys_mutex_unlock         8           释放锁
25    sys_semaphore_create     8           创建信号量
26    sys_semaphore_up         8           减少信号量的计数
27    sys_semaphore_down       8           增加信号量的计数
28    sys_condvar_create       8           创建条件变量
29    sys_condvar_signal       8           唤醒阻塞在条件变量上的线程
30    sys_condvar_wait         8           阻塞与此条件变量关联的当前线程
====  ====================  =============  ===============================


系统调用接口举例
---------------------------------------------------

.. chyyuu 可以有两个例子，体现API和ABI
   #![feature(asm)]
   let cmd = 0xd1;
   unsafe {
      asm!("out 0x64, eax", in("eax") cmd);
   }

   use std::io::{self, Write};

   fn main() -> io::Result<()> {
   io::stdout().write_all(b"hello world")?;

   Ok(())
   }

 
我们以rCore-Tutorial中的例子，一个应用程序显示一个字符串，来看看系统调用的具体内容。应用程序的代码如下：

.. code-block:: rust
   :linenos:

   // user/src/bin/hello_world.rs
   ...
   pub fn main() -> i32 {
      println!("Hello world from user mode program!");
      0
   }    

这个程序的功能就是显示一行字符串（重点看第4行的代码）。注意，这里的 `println!` 一个宏。而进一步跟踪源代码 （位于  `user/src/console.rs` ），可以看到 `println!` 会进一步展开为 `write` 函数：

.. code-block:: rust
   :linenos:

   // user/src/console.rs
   ...
   impl Write for Stdout {
      fn write_str(&mut self, s: &str) -> fmt::Result {
         write(STDOUT, s.as_bytes());
         Ok(())
      }
   }

这个write函数就是对系统调用 `sys_write` 的封装：


.. code-block:: rust
   :linenos:

   // user/src/lib.rs
   ...
   pub fn write(fd: usize, buf: &[u8]) -> isize {
    sys_write(fd, buf)
   }

   // user/src/syscall.rs
   ...
   pub fn sys_write(fd: usize, buffer: &[u8]) -> isize {
      syscall(SYSCALL_WRITE, [fd, buffer.as_ptr() as usize, buffer.len()])
   }


`sys_write` 用户库函数封装了 `sys_write`  系统调用的API接口，这个系统调用API的参数和返回值的含义如下：

- `SYSCALL_WRITE` 表示 `sys_write` 的系统调用号
- `fd` 表示待写入文件的文件描述符；
- `buf` 表示内存中缓冲区的起始地址；
- `len` 表示内存中缓冲区的长度；
- 返回值：返回成功写入的长度或错误值

而 `sys_write`  系统调用的ABI接口描述了具体用哪些寄存器来保存参数和返回值：

.. code-block:: rust
   :linenos:

   // user/src/syscall.rs
   ...
   fn syscall(id: usize, args: [usize; 3]) -> isize {
      let mut ret: isize;
      unsafe {
         asm!(
               "ecall",
               inlateout("x10") args[0] => ret,
               in("x11") args[1],
               in("x12") args[2],
               in("x17") id
         );
      }
      ret
   }

这里我们看到，API中的各个参数和返回值分别被RISC-V通用寄存器 `x17` （即存放系统调用号）、 `x10` （存放 `fd` ，也保存返回值） 、 `x11` （存放 `buf` ）和 `x12` （存放 `len` ）保存。
