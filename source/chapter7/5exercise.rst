chapter7练习
================================================

- 本节难度： **理解文件系统比较费事，编程难度适中** 

编程作业
-------------------------------------------------

硬链接
++++++++++++++++++++++++++++++++++++++++++++++++++

你的电脑桌面是咋样的？是放满了图标吗？反正我的 windows 是这样的。显然很少人会真的把可执行文件放到桌面上，桌面图标其实都是一些快捷方式。或者用 unix 的术语来说：软链接。为了减少工作量，我们今天来实现软链接的兄弟： `硬链接 <https://en.wikipedia.org/wiki/Hard_link>`_ 。

硬链接要求两个不同的目录项指向同一个文件，在我们的文件系统中也就是两个不同名称目录项指向同一个磁盘块。本节要求实现三个系统调用 ``sys_linkat、sys_unlinkat、sys_stat`` 。注意在测例中 ``sys_open`` 的接口定义也发生了变化。

**open**

    - syscall ID: 56
    - 功能：打开一个文件，并返回可以访问它的文件描述符。
    - C 接口： ``int open(int dirfd, char* path, unsigned int flags, unsigned int mode);``
    - Rust 接口： ``fn open(dirfd: usize, path: *const u8, flags: u32, mode: u32);``
    - 参数：
        - **dirfd** : 仅为了兼容性考虑，本次实验中始终为 AT_FDCWD (-100)。可以忽略。
        - **path** 描述要打开的文件的文件名（简单起见，文件系统不需要支持目录，所有的文件都放在根目录 ``/`` 下）
        - **flags** 描述打开文件的标志，具体含义（其他参数不考虑）：
          
          .. code-block:: c

                #define O_RDONLY  0x000
                #define O_WRONLY  0x001
                #define O_RDWR    0x002		// 可读可写
                #define O_CREATE  0x200

        - **mode** 仅在创建文件时有用，表示创建文件的访问权限，为了简单，本次实验中中统一为 *O_RDWR* 。
    - 说明：
        - 有 create 标志但文件存在时，忽略 create 标志，直接打开文件。
    - 返回值：如果出现了错误则返回 -1，否则返回可以访问给定文件的文件描述符。
    - 可能的错误：
        - 文件不存在且无 create 标志。
        - 标志非法（低两位为 0x3）
        - 打开文件数量达到上限。
  
**linkat**：

    * syscall ID: 37
    * 功能：创建一个文件的一个硬链接， `linkat标准接口 <https://linux.die.net/man/2/linkat>`_ 。
    * Ｃ接口： ``int linkat(int olddirfd, char* oldpath, int newdirfd, char* newpath, unsigned int flags)``
    * Rust 接口： ``fn linkat(olddirfd: i32, oldpath: *const u8, newdirfd: i32, newpath: *const u8, flags: u32) -> i32``
    * 参数：
        * olddirfd，newdirfd: 仅为了兼容性考虑，本次实验中始终为 AT_FDCWD (-100)，可以忽略。
        * flags: 仅为了兼容性考虑，本次实验中始终为 0，可以忽略。
        * oldpath：原有文件路径
        * newpath: 新的链接文件路径。
    * 说明：
        * 为了方便，不考虑新文件路径已经存在的情况（属于未定义行为），除非链接同名文件。
        * 返回值：如果出现了错误则返回 -1，否则返回 0。
    * 可能的错误
        * 链接同名文件。

**unlinkat**:

    * syscall ID: 35
    * 功能：取消一个文件路径到文件的链接, `unlinkat标准接口 <https://linux.die.net/man/2/unlinkat>`_ 。
    * Ｃ接口： ``int unlinkat(int dirfd, char* path, unsigned int flags)``
    * Rust 接口： ``fn unlinkat(dirfd: i32, path: *const u8, flags: u32) -> i32``
    * 参数：
        * dirfd: 仅为了兼容性考虑，本次实验中始终为 AT_FDCWD (-100)，可以忽略。
        * flags: 仅为了兼容性考虑，本次实验中始终为 0，可以忽略。
        * path：文件路径。
    * 说明：
        * 为了方便，不考虑使用 unlink 彻底删除文件的情况。
    * 返回值：如果出现了错误则返回 -1，否则返回 0。
    * 可能的错误
        * 文件不存在。

**fstat**:

    * syscall ID: 80
    * 功能：获取文件状态。
    * Ｃ接口： ``int fstat(int fd, struct Stat* st)``
    * Rust 接口： ``fn fstat(fd: i32, st: *mut Stat) -> i32``
    * 参数：
        * fd: 文件描述符
        * st: 文件状态结构体

        .. code-block:: rust

            #[repr(C)]
            #[derive(Debug)]
            pub struct Stat {
                /// 文件所在磁盘驱动器号
                pub dev: u64,
                /// inode 文件所在 inode 编号
                pub ino: u64,
                /// 文件类型
                pub mode: StatMode,
                /// 硬链接数量，初始为1
                pub nlink: u32,
                /// 无需考虑，为了兼容性设计
                pad: [u64; 7],
            }
            
            /// StatMode 定义：
            bitflags! {
                pub struct StatMode: u32 {
                    const NULL  = 0;
                    /// directory
                    const DIR   = 0o040000;
                    /// ordinary regular file
                    const FILE  = 0o100000;
                }
            }
        

实验要求
+++++++++++++++++++++++++++++++++++++++++++++++++++++

- 实现分支：ch7。
- 完成实验指导书中的内容，实现基本的文件操作。
- 实现硬链接及相关系统调用，并通过 `Rust测例 <https://github.com/DeathWish5/rCore_tutorial_tests>`_ 中 chapter7 对应的所有测例。

challenge: 支持多核。

.. note::

    **如何调试 easy-fs**

    如果你在第一章练习题中已经借助 ``log`` crate 实现了日志功能，那么你可以直接在 ``easy-fs`` 中引入 ``log`` crate，通过 ``log::info!/debug!`` 等宏即可进行调试并在内核中看到日志输出。具体来说，在 ``easy-fs`` 中的修改是：在 ``easy-fs/Cargo.toml`` 的依赖中加入一行 ``log = "0.4.0"``，然后在 ``easy-fs/src/lib.rs`` 中加入一行 ``extern crate log`` 。

    你也可以完全在用户态进行调试。仿照 ``easy-fs-fuse`` 建立一个在当前操作系统中运行的应用程序，将测试逻辑写在 ``main`` 函数中。这个时候就可以将它引用的 ``easy-fs`` 的 ``no_std`` 去掉并使用 ``println!`` 进行调试。

实验检查
+++++++++++++++++++++++++++++++++++++++++++++++++++++++

- 实验目录要求

    目录要求不变（参考 lab1 目录或者示例代码目录结构）。同样在 os 目录下 `make run` 之后可以正确加载用户程序并执行。

    加载的用户测例位置： `../user/build/bin`。

- 检查

    可以正确 `make run` 执行，可以正确执行目标用户测例，并得到预期输出（详见测例注释）。


Tips
++++++++++++++++++++++++++++++++++++++++++++++++++++++++

- 注意 ``sys_linkat`` 有 5 个参数，而原有的系统调用分发函数 ``syscall`` （位于 ``os/src/syscall/mod.rs`` 中）最多仅支持 3 个参数，因此我们需要进行拓展。这需要将 ``syscall`` 的函数签名中的 ``args`` 拓展为 ``[usize; 5]`` ，还需要对应调整 ``trap_handler`` 中对 ``syscall`` 的调用，从 Trap 上下文中获取更多通用寄存器放入参数 ``args`` 中。


问答作业
----------------------------------------------------------

1. 目前的文件系统只有单级目录，假设想要支持多级文件目录，请描述你设想的实现方式，描述合理即可。

2. 在有了多级目录之后，我们就也可以为一个目录增加硬链接了。在这种情况下，文件树中是否可能出现环路(软硬链接都可以，鼓励多尝试)？你认为应该如何解决？请在你喜欢的系统上实现一个环路，描述你的实现方式以及系统提示、实际测试结果。

报告要求
-----------------------------------------------------------
* 简单总结本次实验与上个实验相比你增加的东西。（控制在5行以内，不要贴代码）
* 完成问答问题
* (optional) 你对本次实验设计及难度的看法。