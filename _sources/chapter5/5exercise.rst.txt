练习
==============================================

课后练习
-------------------------------

编程题
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

1. `*` 实现一个使用nice,fork,exec,spawn等与进程管理相关的系统调用的linux应用程序。
2. `*` 扩展操作系统内核，能够显示操作系统切换进程的过程。
3. `*` 请阅读下列代码，分析程序的输出 ``A`` 的数量：( 已知 ``&&`` 的优先级比 ``||`` 高)

    .. code-block:: c

      int main() {
          fork() && fork() && fork() || fork() && fork() || fork() && fork();
          printf("A");
          return 0;
      }

    如果给出一个 ``&&`` ``||`` 的序列，如何设计一个程序来得到答案？
4. `**` 在本章操作系统中实现本章提出的某一种调度算法（RR调度除外）。
5. `***` 扩展操作系统内核，支持多核处理器。
6. `***` 扩展操作系统内核，支持在内核态响应并处理中断。
 
问答题
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

1. `*` 如何查看Linux操作系统中的进程？
2. `*` 简单描述一下进程的地址空间中有哪些数据和代码。
3. `*` 进程控制块保存哪些内容？
4. `*` 进程上下文切换需要保存哪些内容？
5. `**` fork 为什么需要在父进程和子进程提供不同的返回值？
6. `**` fork + exec 的一个比较大的问题是 fork 之后的内存页/文件等资源完全没有使用就废弃了，针对这一点，有什么改进策略？
7. `**` 其实使用了6的策略之后，fork + exec 所带来的无效资源的问题已经基本被解决了，但是近年来fork 还是在被不断的批判，那么到底是什么正在"杀死"fork？可以参考 `论文 <https://www.microsoft.com/en-us/research/uploads/prod/2019/04/fork-hotos19.pdf>`_ 。
8. `**` 请阅读下列代码，并分析程序的输出，假定不发生运行错误，不考虑行缓冲，不考虑中断：

    .. code-block:: c

      int main(){
          int val = 2;

          printf("%d", 0);
          int pid = fork();
          if (pid == 0) {
              val++;
              printf("%d", val);
          } else {
              val--;
              printf("%d", val);
              wait(NULL);
          }
          val++;
          printf("%d", val);
          return 0;
      }

    如果 fork() 之后主程序先运行，则结果如何？如果 fork() 之后 child 先运行，则结果如何？
9. `**` 为什么子进程退出后需要父进程对它进行 wait，它才能被完全回收？
10. `**` 有哪些可能的时机导致进程切换？
11. `**` 请描述在本章操作系统中实现本章提出的某一种调度算法（RR调度除外）的简要实现步骤。
12.  `*` 非抢占式的调度算法，以及抢占式的调度算法，他们的优点各是什么？
13. `**` 假设我们简单的将进程分为两种：前台交互（要求短时延）、后台计算（计算量大）。下列进程/或进程组分别是前台还是后台？a) make 编译 linux; b) vim 光标移动; c) firefox 下载影片; d) 某游戏处理玩家点击鼠标开枪; e) 播放交响乐歌曲; f) 转码一个电影视频。除此以外，想想你日常应用程序的运行，它们哪些是前台，哪些是后台的？
14. `**` RR 算法的时间片长短对系统性能指标有什么影响？
15. `**` MLFQ 算法并不公平，恶意的用户程序可以愚弄 MLFQ 算法，大幅挤占其他进程的时间。（MLFQ 的规则：“如果一个进程，时间片用完了它还在执行用户计算，那么 MLFQ 下调它的优先级”）你能举出一个例子，使得你的用户程序能够挤占其他进程的时间吗？
16. `***` 多核执行和调度引入了哪些新的问题和挑战？

实验练习1
-------------------------------

实验练习包括实践作业和问答作业两部分。实验练习1和实验练习2可以选一个完成。

实践作业
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

进程创建
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

大家一定好奇过为啥进程创建要用 fork + execve 这么一个奇怪的系统调用，就不能直接搞一个新进程吗？思而不学则殆，我们就来试一试！这章的编程练习请大家实现一个完全 DIY 的系统调用 spawn，用以创建一个新进程。

spawn 系统调用定义( `标准spawn看这里 <https://man7.org/linux/man-pages/man3/posix_spawn.3.html>`_ )：

.. code-block:: rust

    fn sys_spawn(path: *const u8) -> isize

- syscall ID: 400
- 功能：新建子进程，使其执行目标程序。 
- 说明：成功返回子进程id，否则返回 -1。  
- 可能的错误： 
    - 无效的文件名。
    - 进程池满/内存不足等资源错误。  

TIPS：虽然测例很简单，但提醒读者 spawn **不必** 像 fork 一样复制父进程的地址空间。

实验要求
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
- 实现分支：ch5-lab
- 实验目录要求不变
- 通过所有测例

  在 os 目录下 ``make run TEST=1`` 加载所有测例， ``test_usertest`` 打包了所有你需要通过的测例，你也可以通过修改这个文件调整本地测试的内容。

challenge: 支持多核。

问答作业
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

(1) fork + exec 的一个比较大的问题是 fork 之后的内存页/文件等资源完全没有使用就废弃了，针对这一点，有什么改进策略？

(2) [选做，不占分]其实使用了题(1)的策略之后，fork + exec 所带来的无效资源的问题已经基本被解决了，但是近年来 fork 还是在被不断的批判，那么到底是什么正在"杀死"fork？可以参考 `论文 <https://www.microsoft.com/en-us/research/uploads/prod/2019/04/fork-hotos19.pdf>`_ 。

(3) 请阅读下列代码，并分析程序的输出，假定不发生运行错误，不考虑行缓冲：
    
    .. code-block:: c 

      int main(){
          int val = 2;
          
          printf("%d", 0);
          int pid = fork();
          if (pid == 0) {
              val++;
              printf("%d", val);
          } else {
              val--;
              printf("%d", val);
              wait(NULL);
          }
          val++;
          printf("%d", val);
          return 0;
      } 


    如果 fork() 之后主程序先运行，则结果如何？如果 fork() 之后 child 先运行，则结果如何？


(4) 请阅读下列代码，分析程序的输出 ``A`` 的数量：( 已知 ``&&`` 的优先级比 ``||`` 高)

    .. code-block:: c 

      int main() {
          fork() && fork() && fork() || fork() && fork() || fork() && fork();
          printf("A");
          return 0; 
      }

    [选做，不占分] 更进一步，如果给出一个 ``&&`` ``||`` 的序列，如何设计一个程序来得到答案？

实验练习的提交报告要求
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

* 简单总结本次实验与上个实验相比你增加的东西。（控制在5行以内，不要贴代码）
* 完成问答问题
* (optional) 你对本次实验设计及难度的看法。



实验练习2
--------------------------------------

实践作业
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

stride 调度算法
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

ch3 中我们实现的调度算法十分简单。现在我们要为我们的 os 实现一种带优先级的调度算法：stride 调度算法。

算法描述如下:

(1) 为每个进程设置一个当前 stride，表示该进程当前已经运行的“长度”。另外设置其对应的 pass 值（只与进程的优先权有关系），表示对应进程在调度后，stride 需要进行的累加值。

(2) 每次需要调度时，从当前 runnable 态的进程中选择 stride 最小的进程调度。对于获得调度的进程 P，将对应的 stride 加上其对应的步长 pass。

(3) 一个时间片后，回到上一步骤，重新调度当前 stride 最小的进程。

可以证明，如果令 P.pass = BigStride / P.priority 其中 P.priority 表示进程的优先权（大于 1），而 BigStride 表示一个预先定义的大常数，则该调度方案为每个进程分配的时间将与其优先级成正比。证明过程我们在这里略去，有兴趣的同学可以在网上查找相关资料。

其他实验细节：

- stride 调度要求进程优先级 :math:`\geq 2`，所以设定进程优先级 :math:`\leq 1` 会导致错误。
- 进程初始 stride 设置为 0 即可。
- 进程初始优先级设置为 16。

为了实现该调度算法，内核还要增加 set_prio 系统调用

.. code-block:: rust
   
   // syscall ID：140
   // 设置当前进程优先级为 prio
   // 参数：prio 进程优先级，要求 prio >= 2
   // 返回值：如果输入合法则返回 prio，否则返回 -1
   fn sys_set_priority(prio: isize) -> isize;

tips: 可以使用优先级队列比较方便的实现 stride 算法，但是我们的实验不考察效率，所以手写一个简单粗暴的也完全没问题。

实验要求
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

- 完成分支: ch3-lab

- 实验目录要求不变

- 通过所有测例
  
  lab3 有 3 类测例，在 os 目录下执行 ``make run TEST=1`` 检查基本 ``sys_write`` 安全检查的实现， ``make run TEST=2`` 检查 ``set_priority`` 语义的正确性， ``make run TEST=3`` 检查 stride 调度算法是否满足公平性要求，
  六个子程序运行的次数应该大致与其优先级呈正比，测试通过标准是 :math:`\max{\frac{runtimes}{prio}}/ \min{\frac{runtimes}{prio}} < 1.5`.

challenge: 实现多核，可以并行调度。

实验约定
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

在第三章的测试中，我们对于内核有如下仅仅为了测试方便的要求，请调整你的内核代码来符合这些要求：

- 用户栈大小必须为 4096，且按照 4096 字节对齐。这一规定可以在实验4开始删除，仅仅为通过 lab2 测例设置。

问答作业
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

stride 算法深入

    stride 算法原理非常简单，但是有一个比较大的问题。例如两个 pass = 10 的进程，使用 8bit 无符号整形储存 stride， p1.stride = 255, p2.stride = 250，在 p2 执行一个时间片后，理论上下一次应该 p1 执行。

    - 实际情况是轮到 p1 执行吗？为什么？

    我们之前要求进程优先级 >= 2 其实就是为了解决这个问题。可以证明，**在不考虑溢出的情况下**, 在进程优先级全部 >= 2 的情况下，如果严格按照算法执行，那么 STRIDE_MAX – STRIDE_MIN <= BigStride / 2。

    - 为什么？尝试简单说明（传达思想即可，不要求严格证明）。

    已知以上结论，**考虑溢出的情况下**，我们可以通过设计 Stride 的比较接口，结合 BinaryHeap 的 pop 接口可以很容易的找到真正最小的 Stride。
    
    - 请补全如下 ``partial_cmp`` 函数（假设永远不会相等）。

    .. code-block:: rust

        use core::cmp::Ordering;

        struct Stride(u64);

        impl PartialOrd for Stride {
            fn partial_cmp(&self, other: &Self) -> Option<Ordering> {
                // ...
            }
        }

        impl PartialEq for Person {
            fn eq(&self, other: &Self) -> bool {
                false
            }
        }

    例如使用 8 bits 存储 stride, BigStride = 255, 则:

    - (125 < 255) == false
    - (129 < 255) == true
    

实验练习的提交报告要求
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

- 简单总结与上次实验相比本次实验你增加的东西（控制在5行以内，不要贴代码）。
- 完成问答问题。
- (optional) 你对本次实验设计及难度/工作量的看法，以及有哪些需要改进的地方，欢迎畅所欲言。

参考信息
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
如果有兴趣进一步了解 stride 调度相关内容，可以尝试看看：

- `作者 Carl A. Waldspurger 写这个调度算法的原论文 <https://people.cs.umass.edu/~mcorner/courses/691J/papers/PS/waldspurger_stride/waldspurger95stride.pdf>`_
- `作者 Carl A. Waldspurger 的博士生答辩slide <http://www.waldspurger.org/carl/papers/phd-mit-slides.pdf>`_ 
- `南开大学实验指导中对Stride算法的部分介绍 <https://nankai.gitbook.io/ucore-os-on-risc-v64/lab6/tiao-du-suan-fa-kuang-jia#stride-suan-fa>`_
- `NYU OS课关于Stride Scheduling的Slide <https://cs.nyu.edu/~rgrimm/teaching/sp08-os/stride.pdf>`_

如果有兴趣进一步了解用户态线程实现的相关内容，可以尝试看看：

- `user-multitask in rv64 <https://github.com/chyyuu/os_kernel_lab/tree/v4-user-std-multitask>`_
- `绿色线程 in x86 <https://github.com/cfsamson/example-greenthreads>`_
- `x86版绿色线程的设计实现 <https://cfsamson.gitbook.io/green-threads-explained-in-200-lines-of-rust/>`_
- `用户级多线程的切换原理 <https://blog.csdn.net/qq_31601743/article/details/97514081?utm_medium=distribute.pc_relevant.none-task-blog-BlogCommendFromMachineLearnPai2-1.control&dist_request_id=&depth_1-utm_source=distribute.pc_relevant.none-task-blog-BlogCommendFromMachineLearnPai2-1.control>`_
