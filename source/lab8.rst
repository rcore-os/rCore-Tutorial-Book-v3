Lab8实验
=========================

介绍
--------------

-  本节难度：\ **全面理解操作系统**
-  可选择：实验分为基础作业实验和扩展作业实验两项（二选一） 
  
基础作业
---------------

**在保持syscall数量和基本含义不变的情况下，通过对OS内部的改进，提升OS的质量。**

同学们通过独立完成前面7个实验后，应该对于操作系统的核心关键机制有了较好的了解，并知道如何形成一个有进程/地址空间/文件核心概念的基本功能OS。但同学自制的OS可能还需进一步完善，才能在功能/性能/可靠性上进一步进化，以通过lab8测试用例的正常运行。

第8个实验的目的是希望同学们能够在完成前7个实验的基础上，站在全局视角，分析lab2~lab8测试用例（没增加新的syscall访问，只是更加全面和深入地测试操作系统的质量和能力）的运行情况，分析和理解自己写的OS是否能比较好地满足应用需求？如果不满足应用需求，或者应用导致系统缓慢甚至崩溃，那原因出在哪里？应该如何修改？修改后的OS是否更加完善还是缺陷更多？

实验要求
~~~~~~~~

-  实现分支：ch8
-  运行测试用例，并分析ch8 中部分测试用例对lab7
   OS造成的不良影响，为何没运行通过，为何死在某处了，为何系统崩溃，为何系统缓慢导致应用没通过规定时限？
   注意:
   不一定所有的测例都会导致自己实现的OS崩溃，与语言和实现都有关系，选择出问题的测例分析即可。对于没有出错的测例，可以选择性分析自己的OS 是如何预防这些“刁钻”测例的。对于测例没有测到的，也可以分析自己觉得安全 / 高效的实现。
-  写出实验报告，结合你学到的操作系统课程知识和你的操作系统具体实践情况，分析你写的lab7OS对lab8的app支持不够的原因（至少2个，最多4个。4个(当然要写的合理)就可满分了，更多的合理分析不会加分），并说明可能的解决方法；也可更进一步改进&完成编程实现，使其可以通过一些原本fail 的测例（至少1个，最多2个。2个（要有改进的代码和分析说明）就可满分了，通过更多之前fail的测例不会加分。底线是OS不崩溃，可以通过简单杀死进程方式保证OS不会死掉。比如不支持某种corner case，就把触发该 case 的进程杀掉，如果是这样，至少完成两个。助教会根据报告综合给分。）
-  鼓励针对有趣的测例进行分析！开放思考！鼓励实现改进！（只是分析的话很简单不是吗）
   

**注0：**

lab 1~8 的分值相同，lab8截至是时间为 15周周末，基础实验属于必做实验（除非你选择做扩展作业来代替基础作业）。

**注1：**

在测例中有简明描述：想测试OS哪方面的质量。同学请量力而行，不要求通过所有lab8的测例，不要求对lab7
OS性能/功能/可靠性产生负面影响的lab8的所有测试用例进行分析。说直白点，求您别卷了。

**注2：**

对于有特殊要求的同学（比如你觉得上面的实验太难），可单独找助教或老师说出你感兴趣或力所能及的实验内容，得到老师和助教同意后，做你提出的实验。

**注3：**

**欢迎同学们贡献新测例，有意义测例经过助教检查可以写进报告充当工作量，欢迎打掉框架代码OS，也欢迎打掉其他同学的OS。**

扩展作业(可选)
--------------

给部分同学不同的OS设计与实现的实验选择。扩展作业选项(1-14)基于lab7来实现，扩展作业选项(15)是发现目标内核（ch7/lab7的ucore/rcore
os）漏洞。可选内容（有大致难度估计）如下：

1.  实现多核支持，设计多核相关测试用例，并通过已有和新的测试用例（难度：8）

    -  某学长的有bug的rcore
       tutorial参考实现\ `https://github.com/xy-plus/rCore-Tutorial-v3/tree/ch7 <https://github.com/xy-plus/rCore-Tutorial-v3/tree/ch7?fileGuid=gXqmevn42YSgQpqo>`__

2.  实现slab内存分配算法，通过相关测试用例（难度：7）

    -  `https://github.com/tokio-rs/slab <https://github.com/tokio-rs/slab?fileGuid=gXqmevn42YSgQpqo>`__

3.  实现新的调度算法，如CFS, BFS等，通过相关测试用例（难度：7）

    -  `https://en.wikipedia.org/wiki/Completely_Fair_Scheduler <https://en.wikipedia.org/wiki/Completely_Fair_Scheduler?fileGuid=gXqmevn42YSgQpqo>`__
    -  `https://www.kernel.org/doc/html/latest/scheduler/sched-design-CFS.html <https://www.kernel.org/doc/html/latest/scheduler/sched-design-CFS.html?fileGuid=gXqmevn42YSgQpqo>`__

4.  实现某种IO buffer缓存替换算法，如2Q,
    LRU-K,LIRS等，通过相关测试用例（难度：6）

    -  `LIRS:
       http://web.cse.ohio-state.edu/~zhang.574/lirs-sigmetrics-02.html <http://web.cse.ohio-state.edu/~zhang.574/lirs-sigmetrics-02.html?fileGuid=gXqmevn42YSgQpqo>`__
    -  `2Q:
       https://nyuscholars.nyu.edu/en/publications/2q-a-low-overhead-high-performance-buffer-replacement-algorithm <https://nyuscholars.nyu.edu/en/publications/2q-a-low-overhead-high-performance-buffer-replacement-algorithm?fileGuid=gXqmevn42YSgQpqo>`__
    -  `LRU-K:
       https://dl.acm.org/doi/10.1145/170036.170081 <https://dl.acm.org/doi/10.1145/170036.170081?fileGuid=gXqmevn42YSgQpqo>`__

5.  实现某种页替换算法，如Clock,
    二次机会算法等，通过相关测试用例（难度：6）
6.  实现支持日志机制的可靠文件系统，可参考OSTEP教材中对日志文件系统的描述（难度：7）
7.  支持virtio disk的中断机制，提高IO性能（难度：4）

    -  `chapter8
       https://github.com/rcore-os/rCore-Tutorial-Book-v3/tree/chy <https://github.com/rcore-os/rCore-Tutorial-Book-v3/tree/chy?fileGuid=gXqmevn42YSgQpqo>`__
    -  `https://github.com/rcore-os/virtio-drivers <https://github.com/rcore-os/virtio-drivers?fileGuid=gXqmevn42YSgQpqo>`__
    -  `https://github.com/belowthetree/TisuOS <https://github.com/belowthetree/TisuOS?fileGuid=gXqmevn42YSgQpqo>`__

8.  支持virtio framebuffer/键盘/鼠标处理，给出demo(推荐类似
    pong的graphic game)的测试用例（难度：7）

    -  code:\ `https://github.com/sgmarz/osblog/tree/pong <https://github.com/sgmarz/osblog/tree/pong?fileGuid=gXqmevn42YSgQpqo>`__
    -  code:\ `https://github.com/belowthetree/TisuOS <https://github.com/belowthetree/TisuOS?fileGuid=gXqmevn42YSgQpqo>`__
    -  `tutorial doc: Talking with our new Operating System by Handling
       Input Events and
       Devices <https://blog.stephenmarz.com/2020/08/03/risc-v-os-using-rust-input-devices/?fileGuid=gXqmevn42YSgQpqo>`__
    -  `tutorial doc: Getting Graphical Output from our Custom RISC-V
       Operating System in
       Rust <https://blog.stephenmarz.com/2020/11/11/risc-v-os-using-rust-graphics/?fileGuid=gXqmevn42YSgQpqo>`__
    -  `tutorial doc: Writing Pong Game in Rust for my OS Written in
       Rust <https://blog.stephenmarz.com/category/os/?fileGuid=gXqmevn42YSgQpqo>`__

9.  支持virtio NIC，给出测试用例（难度：7）

    -  `https://github.com/rcore-os/virtio-drivers <https://github.com/rcore-os/virtio-drivers?fileGuid=gXqmevn42YSgQpqo>`__

10. 支持 virtio fs or其他virtio虚拟外设，通过测试用例（难度：5）

    -  `https://docs.oasis-open.org/virtio/virtio/v1.1/csprd01/virtio-v1.1-csprd01.html <https://docs.oasis-open.org/virtio/virtio/v1.1/csprd01/virtio-v1.1-csprd01.html?fileGuid=gXqmevn42YSgQpqo>`__

11. 支持\ `testsuits for
    kernel <https://gitee.com/oscomp/testsuits-for-oskernel#testsuits-for-os-kernel?fileGuid=gXqmevn42YSgQpqo>`__\ 中15个以上的syscall，通过相关测试用例（难度：6）

    -  大部分与我们实验涉及的syscall类似
    -  `https://gitee.com/oscomp/testsuits-for-oskernel#testsuits-for-os-kernel <https://gitee.com/oscomp/testsuits-for-oskernel#testsuits-for-os-kernel?fileGuid=gXqmevn42YSgQpqo>`__

12. 支持新文件系统，比如fat32或ext2等，通过相关测试用例（难度：7）

    -  `https://github.com/rafalh/rust-fatfs <https://github.com/rafalh/rust-fatfs?fileGuid=gXqmevn42YSgQpqo>`__
    -  `https://github.com/pi-pi3/ext2-rs <https://github.com/pi-pi3/ext2-rs?fileGuid=gXqmevn42YSgQpqo>`__

13. 支持物理硬件（如全志哪吒开发板，K210开发板等）。（难度8）

    -  可找老师要物理硬件开发板和相关开发资料

14. 对fork/exec/spawn等进行扩展，并改进shell程序，实现“\|”这种经典的管道机制。（难度：4）

    -  参考rcore tutorial 文档中chapter7中内容

15. 向实验用操作系统发起fuzzing攻击（难度：未知）

    -  其实助教或老师写出的OS
       kernel也是漏洞百出，不堪一击。我们缺少的仅仅是一个可以方便发现bug的工具。也许同学们能独立写出或建立在已有工作的基础上写出一个os
       kernel
       fuzzing工具来发现 bugs 并crash os kernel。下面是一个类似的参考实现项目，也许能提供一些启发。
    -  `gustave fuzzer for os kernel
       tutorial <https://github.com/airbus-seclab/gustave/blob/master/doc/tutorial.md?fileGuid=gXqmevn42YSgQpqo>`__
    -  `gustave fuzzer
       project <https://github.com/airbus-seclab/gustave?fileGuid=gXqmevn42YSgQpqo>`__
    -  `paper: GUSTAVE: Fuzzing OS kernels like simple
       applications <https://airbus-seclab.github.io/GUSTAVE_thcon/GUSTAVE_thcon.pdf?fileGuid=gXqmevn42YSgQpqo>`__

16. **学生自己的想法，但需要告知老师或助教，并得到同意。**

-  支持 1~3
   人组队，如果确定并组队完成，请在5月2日前通过电子邮件告知助教。成员的具体得分可能会通过与老师和助教的当面交流综合判断给出。
   尽量减少划水与抱大腿。
-  根据老师和助教的评价，可获得额外得分，但不会超过实验
   的满分（30分）。也就是如果前面实验有失分，可以通过一个简单扩展把部分分数拿回来。
   
**注0：**

不能抄袭其他上课同学的作业，查出后，\ **所有实验成绩清零。**

**注1：**

lab8扩展作业可代替lab8基础作业。拓展实验给分要求会远低于大实验，简单的拓展也可以的得到较高的评价。在完成代码的同时，也要求写出有关设计思路，问题及解决方法，实验分析等内容的实验报告。

**注2：**

完成lab1~lab8的编程作业（基础作业）也可得满分。这个扩展作业不是必须要做的，是给有兴趣但不想选择大实验的同学一个选择。



