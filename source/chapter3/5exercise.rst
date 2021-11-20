练习
=======================================

编程作业
--------------------------------------

stride 调度算法
+++++++++++++++++++++++++++++++++++++++++

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
+++++++++++++++++++++++++++++++++++++++++

- 完成分支: ch3-lab

- 实验目录要求不变

- 通过所有测例
  
  lab3 有 3 类测例，在 os 目录下执行 ``make run TEST=1`` 检查基本 ``sys_write`` 安全检查的实现， ``make run TEST=2`` 检查 ``set_priority`` 语义的正确性， ``make run TEST=3`` 检查 stride 调度算法是否满足公平性要求，
  六个子程序运行的次数应该大致与其优先级呈正比，测试通过标准是 :math:`\max{\frac{runtimes}{prio}}/ \min{\frac{runtimes}{prio}} < 1.5`.

challenge: 实现多核，可以并行调度。

实验约定
+++++++++++++++++++++++++++++++++++++++

在第三章的测试中，我们对于内核有如下仅仅为了测试方便的要求，请调整你的内核代码来符合这些要求：

- 用户栈大小必须为 4096，且按照 4096 字节对齐。这一规定可以在实验4开始删除，仅仅为通过 lab2 测例设置。

简答作业
--------------------------------------------

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
    

报告要求
-------------------------------

- 简单总结与上次实验相比本次实验你增加的东西（控制在5行以内，不要贴代码）。
- 完成问答问题。
- (optional) 你对本次实验设计及难度/工作量的看法，以及有哪些需要改进的地方，欢迎畅所欲言。

参考信息
-------------------------------
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
