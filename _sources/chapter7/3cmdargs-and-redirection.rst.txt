命令行参数与标准 I/O 重定向
=================================================

本节导读
-------------------------------------------------

虽然我们已经支持从文件系统中加载应用，还实现了文件的创建和读写，但是目前我们在应用中只能硬编码要操作的文件，这就使得应用的功能大大受限，shell程序对于文件的交互访问能力也很弱。为了解决这些问题，我们需要在shell程序和内核中支持命令行参数的解析和传递。而且我们可以把应用的命令行参数的扩展，管道以及标准 I/O 重定向功能综合在一起，来让两个甚至多个互不相干的应用也能合作。

命令行参数
-------------------------------------------------

在使用 C/C++ 语言开发 Linux 应用的时候，我们可以使用标准库提供的 ``argc/argv`` 来获取命令行参数，它们是直接被作为参数传给 ``main`` 函数的。下面来看一个打印命令行参数的例子：

.. code-block:: c
    :linenos:

    // a.c

    #include <stdio.h>

    int main(int argc, char* argv[]) {
        printf("argc = %d\n", argc);
        for (int i = 0; i < argc; i++) {
            printf("argv[%d] = %s\n", i, argv[i]);
        }
        return 0;
    }

其中 ``argc`` 表示命令行参数的个数，而 ``argv`` 是一个长度为 ``argc`` 的字符串数组，数组中的每个字符串都是一个命令行参数。我们可以在 Linux 系统上运行这个程序：

.. code-block:: console

    $ gcc a.c -oa -g -Wall
    $ ./a aa bb 11 22 cc
    argc = 6
    argv[0] = ./a
    argv[1] = aa
    argv[2] = bb
    argv[3] = 11
    argv[4] = 22
    argv[5] = cc

为了支持后续的一些功能，我们希望在内核和shell程序上支持这个功能。为了对实现正确性进行测试，在本章中我们编写了一个名为 ``cmdline_args`` 的应用，它是用 Rust 编写的，并只能在我们的内核上执行，但是它的功能是和 ``a.c`` 保持一致的。我们可以在我们的内核上运行该应用来看看效果：

.. code-block::

    Rust user shell
    >> cmdline_args aa bb 11 22 cc
    argc = 6
    argv[0] = cmdline_args
    argv[1] = aa
    argv[2] = bb
    argv[3] = 11
    argv[4] = 22
    argv[5] = cc
    Shell: Process 2 exited with code 0
    >> 

可以看到二者的输出是基本相同的。

但是，要实现这个看似简单的功能，需要内核和用户态应用的共同努力。为了支持命令行参数， ``sys_exec`` 的系统调用接口需要发生变化：

.. code-block:: rust
    :linenos:

    // user/src/syscall.rs

    pub fn sys_exec(path: &str, args: &[*const u8]) -> isize;

可以看到，它的参数多出了一个 ``args`` 数组，数组中的每个元素都是一个命令行参数字符串的起始地址。由于我们是以引用的形式传递这个数组，实际传递给内核的是这个数组的起始地址：

.. code-block:: rust
    :linenos:

    // user/src/syscall.rs

    pub fn sys_exec(path: &str, args: &[*const u8]) -> isize {
        syscall(SYSCALL_EXEC, [path.as_ptr() as usize, args.as_ptr() as usize, 0])
    }

    // user/src/lib.rs

    pub fn exec(path: &str, args: &[*const u8]) -> isize { sys_exec(path, args) }

接下来我们分析一下，一行带有命令行参数的命令从输入到它的命令行参数被打印出来中间经历了哪些过程。

shell程序的命令行参数分割
+++++++++++++++++++++++++++++++++++++++++++++++++

回忆一下，之前在shell程序 ``user_shell`` 中，一旦接收到一个回车，我们就会将当前行的内容 ``line`` 作为一个名字并试图去执行同名的应用。但是现在 ``line`` 还可能包含一些命令行参数，只有最开头的一个才是要执行的应用名。因此我们要做的第一件事情就是将 ``line`` 用空格进行分割：

.. code-block:: rust
    :linenos:

    // user/src/bin/user_shell.rs

    let args: Vec<_> = line.as_str().split(' ').collect();
    let mut args_copy: Vec<String> = args
    .iter()
    .map(|&arg| {
        let mut string = String::new();
        string.push_str(arg);
        string
    })
    .collect();

    args_copy
    .iter_mut()
    .for_each(|string| {
        string.push('\0');
    });

经过分割， ``args`` 中的 ``&str`` 都是 ``line`` 中的一段子区间，它们的结尾并没有包含 ``\0`` ，因为 ``line`` 是我们输入得到的，中间本来就没有 ``\0`` 。由于在向内核传入字符串的时候，我们只能传入字符串的起始地址，因此我们必须保证其结尾为 ``\0`` 。从而我们用 ``args_copy`` 将 ``args`` 中的字符串拷贝一份到堆上并在末尾手动加入 ``\0`` 。这样就可以安心的将 ``args_copy`` 中的字符串传入内核了。我们用 ``args_addr`` 来收集这些字符串的起始地址：

.. code-block:: rust
    :linenos:

    // user/src/bin/user_shell.rs

    let mut args_addr: Vec<*const u8> = args_copy
    .iter()
    .map(|arg| arg.as_ptr())
    .collect();
    args_addr.push(0 as *const u8);

向量 ``args_addr`` 中的每个元素都代表一个命令行参数字符串的起始地址。由于我们要传递给内核的是这个向量的起始地址，为了让内核能够获取到命令行参数的个数，我们需要在 ``args_addr`` 的末尾放入一个 0 ，这样内核看到它的时候就能知道命令行参数已经获取完毕了。

在 ``fork`` 出来的子进程里面我们需要这样执行应用：

.. code-block:: rust
    :linenos:

    // user/src/bin/user_shell.rs

    // child process
    if exec(args_copy[0].as_str(), args_addr.as_slice()) == -1 {
        println!("Error when executing!");
        return -4;
    }

sys_exec 将命令行参数压入用户栈
+++++++++++++++++++++++++++++++++++++++++++++++++

在 ``sys_exec`` 中，首先需要将应用传进来的命令行参数取出来：

.. code-block:: rust
    :linenos:
    :emphasize-lines: 6-14,19

    // os/src/syscall/process.rs

    pub fn sys_exec(path: *const u8, mut args: *const usize) -> isize {
        let token = current_user_token();
        let path = translated_str(token, path);
        let mut args_vec: Vec<String> = Vec::new();
        loop {
            let arg_str_ptr = *translated_ref(token, args);
            if arg_str_ptr == 0 {
                break;
            }
            args_vec.push(translated_str(token, arg_str_ptr as *const u8));
            unsafe { args = args.add(1); }
        }
        if let Some(app_inode) = open_file(path.as_str(), OpenFlags::RDONLY) {
            let all_data = app_inode.read_all();
            let task = current_task().unwrap();
            let argc = args_vec.len();
            task.exec(all_data.as_slice(), args_vec);
            // return argc because cx.x[10] will be covered with it later
            argc as isize
        } else {
            -1
        }
    }

这里的 ``args`` 指向命令行参数字符串起始地址数组中的一个位置，每次我们都可以从一个起始地址通过 ``translated_str`` 拿到一个字符串，直到 ``args`` 为 0 就说明没有更多命令行参数了。在第 19 行调用 ``TaskControlBlock::exec`` 的时候，我们需要将获取到的 ``args_vec`` 传入进去并将里面的字符串压入到用户栈上。

.. code-block:: rust
    :linenos:
    :emphasize-lines: 11-34,45,50,51

    // os/src/task/task.rs

    impl TaskControlBlock {
        pub fn exec(&self, elf_data: &[u8], args: Vec<String>) {
            // memory_set with elf program headers/trampoline/trap context/user stack
            let (memory_set, mut user_sp, entry_point) = MemorySet::from_elf(elf_data);
            let trap_cx_ppn = memory_set
                .translate(VirtAddr::from(TRAP_CONTEXT).into())
                .unwrap()
                .ppn();
            // push arguments on user stack
            user_sp -= (args.len() + 1) * core::mem::size_of::<usize>();
            let argv_base = user_sp;
            let mut argv: Vec<_> = (0..=args.len())
                .map(|arg| {
                    translated_refmut(
                        memory_set.token(),
                        (argv_base + arg * core::mem::size_of::<usize>()) as *mut usize
                    )
                })
                .collect();
            *argv[args.len()] = 0;
            for i in 0..args.len() {
                user_sp -= args[i].len() + 1;
                *argv[i] = user_sp;
                let mut p = user_sp;
                for c in args[i].as_bytes() {
                    *translated_refmut(memory_set.token(), p as *mut u8) = *c;
                    p += 1;
                }
                *translated_refmut(memory_set.token(), p as *mut u8) = 0;
            }
            // make the user_sp aligned to 8B for k210 platform
            user_sp -= user_sp % core::mem::size_of::<usize>();

            // **** hold current PCB lock
            let mut inner = self.acquire_inner_lock();
            // substitute memory_set
            inner.memory_set = memory_set;
            // update trap_cx ppn
            inner.trap_cx_ppn = trap_cx_ppn;
            // initialize trap_cx
            let mut trap_cx = TrapContext::app_init_context(
                entry_point,
                user_sp,
                KERNEL_SPACE.lock().token(),
                self.kernel_stack.get_top(),
                trap_handler as usize,
            );
            trap_cx.x[10] = args.len();
            trap_cx.x[11] = argv_base;
            *inner.get_trap_cx() = trap_cx;
            // **** release current PCB lock
        }
    }

第 11-34 行所做的主要工作是将命令行参数以某种格式压入用户栈。具体的格式可以参考下图（比如应用传入了两个命令行参数 ``aa`` 和 ``bb`` ）：

.. image:: user-stack-cmdargs.png
    :align: center

- 首先需要在用户栈上分配一个字符串指针数组，也就是蓝色区域。数组中的每个元素都指向一个用户栈更低处的命令行参数字符串的起始地址。在第 12~24 行可以看到，最开始我们只是分配空间，具体的值要等到字符串被放到用户栈上之后才能确定更新。
- 第 23~32 行，我们逐个将传入的 ``args`` 中的字符串压入到用户栈中，对应于图中的橙色区域。为了实现方便，我们在用户栈上预留空间之后逐字节进行复制。注意 ``args`` 中的字符串是通过 ``translated_str`` 从应用地址空间取出的，它的末尾不包含 ``\0`` 。为了应用能知道每个字符串的长度，我们需要手动在末尾加入 ``\0`` 。
- 第 34 行将 ``user_sp`` 以 8 字节对齐，即图中的绿色区域。这是因为命令行参数的长度不一，很有可能压入之后 ``user_sp`` 没有对齐到 8 字节，那么在 K210 平台上在访问用户栈的时候就会触发访存不对齐的异常。在 Qemu 平台上则并不存在这个问题。

我们还需要对应修改 Trap 上下文。首先是第 45 行，我们的 ``user_sp`` 相比之前已经发生了变化，它上面已经压入了命令行参数。同时，我们还需要修改 Trap 上下文中的 ``a0/a1`` 寄存器，让 ``a0`` 表示命令行参数的个数，而 ``a1`` 则表示图中 ``argv_base`` 即蓝色区域的起始地址。这两个参数在第一次进入对应应用的用户态的时候会被接收并用于还原命令行参数。

用户库从用户栈上还原命令行参数
+++++++++++++++++++++++++++++++++++++++++++++++++

在应用第一次进入用户态的时候，我们放在 Trap 上下文 a0/a1 两个寄存器中的内容可以被用户库中的入口函数以参数的形式接收：

.. code-block:: rust
    :linenos:
    :emphasize-lines: 10-24

    // user/src/lib.rs

    #[no_mangle]
    #[link_section = ".text.entry"]
    pub extern "C" fn _start(argc: usize, argv: usize) -> ! {
        unsafe {
            HEAP.lock()
                .init(HEAP_SPACE.as_ptr() as usize, USER_HEAP_SIZE);
        }
        let mut v: Vec<&'static str> = Vec::new();
        for i in 0..argc {
            let str_start = unsafe {
                ((argv + i * core::mem::size_of::<usize>()) as *const usize).read_volatile()
            };
            let len = (0usize..).find(|i| unsafe {
                ((str_start + *i) as *const u8).read_volatile() == 0
            }).unwrap();
            v.push(
                core::str::from_utf8(unsafe {
                    core::slice::from_raw_parts(str_start as *const u8, len)
                }).unwrap()
            );
        }
        exit(main(argc, v.as_slice()));
    }

可以看到，在入口 ``_start`` 中我们就接收到了命令行参数个数 ``argc`` 和字符串数组的起始地址 ``argv`` 。但是这个起始地址不太好用，我们希望能够将其转化为编写应用的时候看到的 ``&[&str]`` 的形式。转化的主体在第 10~23 行，就是分别取出 ``argc`` 个字符串的起始地址（基于字符串数组的 base 地址 ``argv`` ），从它向后找到第一个 ``\0`` 就可以得到一个完整的 ``&str`` 格式的命令行参数字符串并加入到向量 ``v`` 中。最后通过 ``v.as_slice`` 就得到了我们在 ``main`` 主函数中看到的 ``&[&str]`` 。

通过命令行工具 cat 输出文件内容
+++++++++++++++++++++++++++++++++++++++++++++++++

有了之前的命令行参数支持，我们就可以编写命令行工具 ``cat`` 来输出指定文件的内容了。它的使用方法如下：

.. code-block::

    >> filetest_simple
    file_test passed!
    Shell: Process 2 exited with code 0
    >> cat filea
    Hello, world!
    Shell: Process 2 exited with code 0
    >> 

``filetest_simple`` 会将 ``Hello, world!`` 输出到文件 ``filea`` 中。之后我们就可以通过 ``cat filea`` 来打印文件 ``filea`` 中的内容。

``cat`` 本身也是一个应用，且很容易实现：

.. code-block:: rust
    :linenos:

    // user/src/bin/cat.rs

    #![no_std]
    #![no_main]

    #[macro_use]
    extern crate user_lib;
    extern crate alloc;

    use user_lib::{
        open,
        OpenFlags,
        close,
        read,
    };
    use alloc::string::String;

    #[no_mangle]
    pub fn main(argc: usize, argv: &[&str]) -> i32 {
        assert!(argc == 2);
        let fd = open(argv[1], OpenFlags::RDONLY);
        if fd == -1 {
            panic!("Error occurred when opening file");
        }
        let fd = fd as usize;
        let mut buf = [0u8; 16];
        let mut s = String::new();
        loop {
            let size = read(fd, &mut buf) as usize;
            if size == 0 { break; }
            s.push_str(core::str::from_utf8(&buf[..size]).unwrap());
        }
        println!("{}", s);
        close(fd);
        0
    }


标准输入输出重定向
-------------------------------------------------

为了进一步增强shell程序使用文件系统时的灵活性，我们需要新增标准输入输出重定向功能。这个功能在我们使用 Linux 内核的时候很常用，我们在自己的内核中举个例子：

.. code-block::

    >> yield > fileb
    Shell: Process 2 exited with code 0
    >> cat fileb
    Hello, I am process 2.
    Back in process 2, iteration 0.
    Back in process 2, iteration 1.
    Back in process 2, iteration 2.
    Back in process 2, iteration 3.
    Back in process 2, iteration 4.
    yield pass.

    Shell: Process 2 exited with code 0
    >> 

通过 ``>`` 我们可以将应用 ``yield`` 的输出重定向到文件 ``fileb`` 中。我们也可以注意到在屏幕上暂时看不到 ``yield`` 的输出了。在应用 ``yield`` 退出之后，我们可以使用 ``cat`` 工具来查看文件 ``fileb`` 的内容，可以看到里面的确是 ``yield`` 的输出。同理，通过 ``<`` 则可以将一个应用的输入重定向到某个指定文件而不是从键盘输入。

注意重定向功能对于应用来说是透明的。在应用中除非明确指出了数据要从指定的文件输入或者输出到指定的文件，否则数据默认都是输入自进程文件描述表位置 0 （即 ``fd=0`` ）处的标准输入，并输出到进程文件描述符表位置 1 （即  ``fd=1`` ）处的标准输出。这是由于内核在执行 ``sys_exec`` 系统调用创建基于新应用的进程时，会直接把文件描述符表位置 0 放置标准输入文件，位置 1 放置标准输出文件，位置 2 放置标准错误输出文件。标准输入/输出文件其实是把设备当成文件，标准输入文件就是串口的输入或键盘，而标准输出文件就是串口的输出或显示器。

因此，在应用执行之前，我们就要对应用进程的文件描述符表进行某种替换。以输出为例，我们需要提前打开文件并用这个文件来替换掉应用文件描述符表位置 1 处的标准输出文件，这就完成了所谓的重定向。在重定向之后，应用认为自己输出到  ``fd=1`` 的标准输出文件，但实际上是输出到我们指定的文件中。我们能够做到这一点还是得益于文件的抽象，因为在进程看来无论是标准输出还是常规文件都是一种文件，可以通过同样的接口来读写。

为了实现重定向功能，我们需要引入一个新的系统调用 ``sys_dup`` ：

.. code-block:: rust
    :linenos:

    // user/src/syscall.rs

    /// 功能：将进程中一个已经打开的文件复制一份并分配到一个新的文件描述符中。
    /// 参数：fd 表示进程中一个已经打开的文件的文件描述符。
    /// 返回值：如果出现了错误则返回 -1，否则能够访问已打开文件的新文件描述符。
    /// 可能的错误原因是：传入的 fd 并不对应一个合法的已打开文件。
    /// syscall ID：24
    pub fn sys_dup(fd: usize) -> isize;

这个系统调用的实现非常简单：

.. code-block:: rust
    :linenos:

    // os/src/syscall/fs.rs

    pub fn sys_dup(fd: usize) -> isize {
        let task = current_task().unwrap();
        let mut inner = task.acquire_inner_lock();
        if fd >= inner.fd_table.len() {
            return -1;
        }
        if inner.fd_table[fd].is_none() {
            return -1;
        }
        let new_fd = inner.alloc_fd();
        inner.fd_table[new_fd] = Some(Arc::clone(inner.fd_table[fd].as_ref().unwrap()));
        new_fd as isize
    }

在 ``sys_dup`` 函数中，首先检查传入 ``fd`` 的合法性。然后在文件描述符表中分配一个新的文件描述符，并保存 ``fd`` 指向的已打开文件的一份拷贝即可。

那么我们应该在什么时候进行替换，又应该如何利用 ``sys_dup`` 进行替换呢？

答案是在shell程序 ``user_shell`` 中进行处理。在分割命令行参数的时候，我们要检查是否存在通过 ``<`` 或 ``>`` 进行输入输出重定向的情况，如果存在的话则需要将它们从命令行参数中移除，并记录匹配到的输入文件名或输出文件名到字符串 ``input`` 或 ``output`` 中。注意，为了实现方便，我们这里假设输入shell程序的命令一定合法：即 ``<`` 或 ``>`` 最多只会出现一次，且后面总是会有一个参数作为重定向到的文件。

.. code-block:: rust
    :linenos:

    // user/src/bin/user_shell.rs

    // redirect input
    let mut input = String::new();
    if let Some((idx, _)) = args_copy
    .iter()
    .enumerate()
    .find(|(_, arg)| arg.as_str() == "<\0") {
        input = args_copy[idx + 1].clone();
        args_copy.drain(idx..=idx + 1);
    }

    // redirect output
    let mut output = String::new();
    if let Some((idx, _)) = args_copy
    .iter()
    .enumerate()
    .find(|(_, arg)| arg.as_str() == ">\0") {
        output = args_copy[idx + 1].clone();
        args_copy.drain(idx..=idx + 1);
    }

打开文件和替换的过程则发生在 ``fork`` 之后的子进程分支中：

.. code-block:: rust
    :linenos:

    // user/src/bin/user_shell.rs

    let pid = fork();
    if pid == 0 {
        // input redirection
        if !input.is_empty() {
            let input_fd = open(input.as_str(), OpenFlags::RDONLY);
            if input_fd == -1 {
                println!("Error when opening file {}", input);
                return -4;
            }
            let input_fd = input_fd as usize;
            close(0);
            assert_eq!(dup(input_fd), 0);
            close(input_fd);
        }
        // output redirection
        if !output.is_empty() {
            let output_fd = open(
                output.as_str(),
                OpenFlags::CREATE | OpenFlags::WRONLY
            );
            if output_fd == -1 {
                println!("Error when opening file {}", output);
                return -4;
            }
            let output_fd = output_fd as usize;
            close(1);
            assert_eq!(dup(output_fd), 1);
            close(output_fd);
        }
        // child process
        if exec(args_copy[0].as_str(), args_addr.as_slice()) == -1 {
            println!("Error when executing!");
            return -4;
        }
        unreachable!();
    } else {
        let mut exit_code: i32 = 0;
        let exit_pid = waitpid(pid as usize, &mut exit_code);
        assert_eq!(pid, exit_pid);
        println!("Shell: Process {} exited with code {}", pid, exit_code);
    }

- 输入重定向发生在第 6~16 行。我们尝试打开输入文件 ``input`` 到 ``input_fd`` 中。之后，首先通过 ``close`` 关闭标准输入所在的文件描述符 0 。之后通过 ``dup`` 来分配一个新的文件描述符来访问 ``input_fd`` 对应的输入文件。这里用到了文件描述符分配的重要性质：即必定分配可用描述符中编号最小的一个。由于我们刚刚关闭了描述符 0 ，那么在 ``dup`` 的时候一定会将它分配出去，于是现在应用进程的文件描述符 0 就对应到输入文件了。最后，因为应用进程的后续执行不会用到输入文件原来的描述符 ``input_fd`` ，所以就将其关掉。
- 输出重定向则发生在 18~31 行。它的原理和输入重定向几乎完全一致，只是通过 ``open`` 打开文件的标志不太相同。

实现到这里，就可以通过 ``exec`` 来执行应用了。

小结
-------------------------------------------------

虽然 ``fork/exec/waitpid`` 三个经典的系统调用自它们于古老的 UNIX 时代诞生以来已经过去了太长时间，从某种程度上来讲已经不太适合新的内核环境了。人们也已经提出了若干种替代品并已经在进行实践，比如POSIX标准中的 ``posix_spawn`` 或者 Linux 上的 ``clone`` 系统调用。但是它们迄今为止仍然存在就证明在它们的设计中还能够找到可取之处。从本节介绍的重定向就可以看出它们的灵活性以及强大的功能性：我们能够进行重定向恰恰是因为创建新应用进程分为 ``fork`` 和 ``exec`` 两个系统调用，那么在这两个系统调用之间我们就能够进行一些类似重定向的处理。在实现的过程中，我们还用到了 ``fork`` 出来的子进程会和父进程共享文件描述符表的性质。
