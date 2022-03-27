练习
============================================

课后练习
-------------------------------

编程题
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

1. `**` 使用sbrk，mmap,munmap,mprotect内存相关系统调用的linux应用程序。
2. `***` 修改本章操作系统内核，实现任务和操作系统内核共用同一张页表的单页表机制。
3. `***` 扩展内核，支持基于缺页异常机制，具有Lazy 策略的按需分页机制。
4. `***` 扩展内核，支持基于缺页异常的COW机制。（初始时，两个任务共享一个只读物理页。当一个任务执行写操作后，两个任务拥有各自的可写物理页）
5. `***` 扩展内核，实现swap in/out机制，并实现Clock置换算法或二次机会置换算法。
6. `***` 扩展内核，实现自映射机制。

问答题
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

.. chyyuu   这次的实验没有涉及到缺页有点遗憾，主要是缺页难以测试，而且更多的是一种优化，不符合这次实验的核心理念，所以这里补两道小题。

1. `*` 在使用高级语言编写用户程序的时候，手动用嵌入汇编的方法随机访问一个不在当前程序逻辑地址范围内的地址，比如向该地址读/写数据。该用户程序执行的时候可能会生什么？ 

   可能会报出缺页异常.

2. `*` 用户程序在运行的过程中，看到的地址是逻辑地址还是物理地址？从用户程序访问某一个地址，到实际内存中的对应单元被读/写，会经过什么样的过程，这个过程中操作系统有什么作用？（站在学过计算机组成原理的角度）

   逻辑地址。这个过程需要经过页表的转换，操作系统会负责建立页表映射。实际程序执行时的具体VA到PA的转换是在CPU的MMU之中进行的。

3. `*` 覆盖、交换和虚拟存储有何异同，虚拟存储的优势和挑战体现在什么地方？

   它们都是采取层次存储的思路，将暂时不用的内存放到外存中去，以此来缓解内存不足的问题。

   不同之处：覆盖是程序级的，需要程序员自行处理。交换则不同，由OS控制交换程序段。虚拟内存也由OS和CPU来负责处理，可以实现内存交换到外存的过程。
   
   虚拟存储的优势:1.与段/页式存储完美契合，方便非连续内存分配。2.粒度合适，比较灵活。兼顾了覆盖和交换的好处：可以在较小粒度上置换；自动化程度高，编程简单，受程序本身影响很小。（覆盖的粒度受限于程序模块的大小，对编程技巧要求很高。交换粒度较大，受限于程序所需内存。尤其页式虚拟存储，几乎不受程序影响，一般情况下，只要置换算法合适，表现稳定、高效）3.页式虚拟存储还可以同时解决内存外碎片。提高空间利用率。
   
   虚拟存储的挑战: 1.依赖于置换算法的性能。2.相比于覆盖和交换，需要比较高的硬件支持。3.较小的粒度在面临大规模的置换时会发生多次较小规模置换，降低效率。典型情况是程序第一次执行时的大量page fault，可配合预取技术缓解这一问题。

4. `*` 什么是局部性原理？为何很多程序具有局部性？局部性原理总是正确的吗？为何局部性原理为虚拟存储提供了性能的理论保证？

   局部性分时间局部性和空间局部性（以及分支局部性）。局部性的原理是程序经常对一块相近的地址进行访问或者是对一个范围内的指令进行操作。局部性原理不一定是一直正确的。虚拟存储以页为单位，局部性使得数据和指令的访存局限在几页之中，可以避免页的频繁换入换出的开销，同时也符合TLB和cache的工作机制。

5. `**` 一条load指令，最多导致多少次页访问异常？尝试考虑较多情况。

   考虑多级页表的情况。首先指令和数据读取都可能缺页。因此指令会有3次访存，之后的数据读取除了页表页缺失的3次访存外，最后一次还可以出现地址不对齐的异常，因此可以有7次异常。若考更加极端的情况，也就是页表的每一级都是不对齐的地址并且处在两页的交界处（straddle），此时一次访存会触发2次读取页面，如果这两页都缺页的话，会有更多的异常次数。

6. `**` 如果在页访问异常中断服务例程执行时，再次出现页访问异常，这时计算机系统（软件或硬件）会如何处理？这种情况可能出现吗？

   我们实验的os在此时不支持内核的异常中断，因此此时会直接panic掉，并且这种情况在我们的os中这种情况不可能出现。像linux系统，也不会出现嵌套的page fault。

7. `*` 全局和局部置换算法有何不同？分别有哪些算法？

8. `*` 简单描述OPT、FIFO、LRU、Clock、LFU的工作过程和特点 (不用写太多字，简明扼要即可)

9.  `**` 综合考虑置换算法的收益和开销，综合评判在哪种程序执行环境下使用何种算法比较合适？

10. `**` Clock算法仅仅能够记录近期是否访问过这一信息，对于访问的频度几乎没有记录，如何改进这一点？

11. `***` 哪些算法有belady现象？思考belady现象的成因，尝试给出说明OPT和LRU等为何没有belady现象。

   FIFO算法、Clock算法。

   页面调度算法可分为堆栈式和非堆栈式，LRU、LFU、OPT均为堆栈类算法，FIFO、Clock为非堆栈类算法，只有非堆栈类才会出现Belady现象。

12. `*` 什么是工作集？什么是常驻集？简单描述工作集算法的工作过程。

   工作集为一个进程当前正在使用的逻辑页面集合，可表示为二元函数$W(t, \Delta)$，t 为执行时刻，$\Delta$ 称为工作集窗口，即一个定长的页面访问时间窗口，$W(t, \Delta)$是指在当前时刻 t 前的 $\Delta$ 时间窗口中的所有访问页面所组成的集合，$|W(t, \Delta)|$为工作集的大小，即页面数目。

13. `*` 请列举 SV39 页`*` 页表项的组成，结合课堂内容，描述其中的标志位有何作用／潜在作用？

   [63:54]为保留项，[53:10]为44位物理页号，最低的8位[7:0]为标志位。

   - V(Valid)：仅当位 V 为 1 时，页表项才是合法的；
   - R(Read)/W(Write)/X(eXecute)：分别控制索引到这个页表项的对应虚拟页面是否允许读/写/执行；
   - U(User)：控制索引到这个页表项的对应虚拟页面是否在 CPU 处于 U 特权级的情况下是否被允许访问；
   - A(Accessed)：处理器记录自从页表项上的这一位被清零之后，页表项的对应虚拟页面是否被访问过；
   - D(Dirty)：处理器记录自从页表项上的这一位被清零之后，页表项的对应虚拟页面是否被修改过。

14. `**` 请问一个任务处理 10G 连续的内存页面，需要操作的页表实际大致占用多少内存(给出数量级即可)？

大致占用`10G/512=20M`内存。

15. `**`  缺页指的是进程访问页面时页面不在页表中或在页表中无效的现象，此时 MMU 将会返回一个中断，告知操作系统：该进程内存访问出了问题。然后操作系统可选择填补页表并重新执行异常指令或者杀死进程。操作系统基于缺页异常进行优化的两个常见策略中，其一是 Lazy 策略，也就是直到内存页面被访问才实际进行页表操作。比如，一个程序被执行时，进程的代码段理论上需要从磁盘加载到内存。但是 操作系统并不会马上这样做，而是会保存 .text 段在磁盘的位置信息，在这些代码第一次被执行时才完成从磁盘的加载操作。 另一个常见策略是 swap 页置换策略，也就是内存页面可能被换到磁盘上了，导致对应页面失效，操作系统在任务访问到该页产生异常时，再把数据从磁盘加载到内存。

    - 哪些异常可能是缺页导致的？发生缺页时，描述与缺页相关的CSR寄存器的值及其含义。
  
    - 答案：`mcause`寄存器中会保存发生中断异常的原因，其中`Exception Code`为`12`时发生指令缺页异常，为`15`时发生`store/AMO`缺页异常，为`13`时发生`load`缺页异常。

     CSR寄存器: 
    
     - `scause`: 中断/异常发生时，`CSR`寄存器`scause`中会记录其信息，`Interrupt`位记录是中断还是异常，`Exception Code`记录中断/异常的种类。  
     - `sstatus`: 记录处理器当前状态，其中`SPP`段记录当前特权等级。  
     - `stvec`: 记录处理`trap`的入口地址，现有两种模式`Direct`和`Vectored`。
     - `sscratch`: 其中的值是指向hart相关的S态上下文的指针，比如内核栈的指针  
     - `sepc`: `trap`发生时会将当前指令的下一条指令地址写入其中，用于`trap`处理完成后返回。  
     - `stval`: `trap`发生进入S态时会将异常信息写入，用于帮助处理`trap`，其中会保存导致缺页异常的虚拟地址  
 
    - Lazy 策略有哪些好处？请描述大致如何实现Lazy策略？

    - 答案：Lazy策略一定不会比直接加载策略慢，并且可能会提升性能，因为可能会有些页面被加载后并没有进行访问就被释放或替代了，这样可以避免很多无用的加载。分配内存时暂时不进行分配，只是将记录下来，访问缺页时会触发缺页异常，在`trap handler`中处理相应的异常，在此时将内存加载或分配即可。
  
    - swap 页置换策略有哪些好处？此时页面失效如何表现在页表项(PTE)上？请描述大致如何实现swap策略？

    - 答案：可以为用户程序提供比实际物理内存更大的内存空间。页面失效会将标志位`V`置为`0`。将置换出的物理页面保存在磁盘中，在之后访问再次触发缺页异常时将该页面写入内存。
  
16. `**` 为了防范侧信道攻击，本章的操作系统使用了双页表。但是传统的操作系统设计一般采用单页表，也就是说，任务和操作系统内核共用同一张页表，只不过内核对应的地址只允许在内核态访问。(备注：这里的单/双的说法仅为自创的通俗说法，并无这个名词概念，详情见 `KPTI <https://en.wikipedia.org/wiki/Kernel_page-table_isolation>`_ )

    - 单页表情况下，如何控制用户态无法访问内核页面？
  
    - 答案：将内核页面的 pte 的`U`标志位设置为0。
 
    - 相对于双页表，单页表有何优势？
 
    - 答案：在内核和用户态之间转换时不需要更换页表，也就不需要跳板，可以像之前一样直接切换上下文。
 
    - 请描述：在单页表和双页表模式下，分别在哪个时机，如何切换页表？
 
    - 答案：双页表实现下用户程序和内核转换时、用户程序转换时都需要更换页表，而对于单页表操作系统，不同用户线程切换时需要更换页表。

实验练习
-------------------------------

实验练习包括实践作业和问答作业两部分。

实践作业
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

重写 sys_get_time
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

引入虚存机制后，原来内核的 sys_get_time 函数实现就无效了。请你重写这个函数，恢复其正常功能。

mmap 和 munmap 匿名映射
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

`mmap <https://man7.org/linux/man-pages/man2/mmap.2.html>`_ 在 Linux 中主要用于在内存中映射文件，本次实验简化它的功能，仅用于申请内存。

请实现 mmap 和 munmap 系统调用，mmap 定义如下：


.. code-block:: rust

    fn sys_mmap(start: usize, len: usize, port: usize) -> isize

- syscall ID：222
- 申请长度为 len 字节的物理内存（不要求实际物理内存位置，可以随便找一块），将其映射到 start 开始的虚存，内存页属性为 port
- 参数：
    - start 需要映射的虚存起始地址，要求按页对齐
    - len 映射字节长度，可以为 0
    - port：第 0 位表示是否可读，第 1 位表示是否可写，第 2 位表示是否可执行。其他位无效且必须为 0
- 返回值：执行成功则返回 0，错误返回 -1
- 说明：
    - 为了简单，目标虚存区间要求按页对齐，len 可直接按页向上取整，不考虑分配失败时的页回收。
- 可能的错误：
    - start 没有按页大小对齐
    - port & !0x7 != 0 (port 其余位必须为0)
    - port & 0x7 = 0 (这样的内存无意义)
    - [start, start + len) 中存在已经被映射的页
    - 物理内存不足

munmap 定义如下：

.. code-block:: rust

    fn sys_munmap(start: usize, len: usize) -> isize

- syscall ID：215
- 取消到 [start, start + len) 虚存的映射
- 参数和返回值请参考 mmap
- 说明：
    - 为了简单，参数错误时不考虑内存的恢复和回收。
- 可能的错误：
    - [start, start + len) 中存在未被映射的虚存。


TIPS：注意 port 参数的语义，它与内核定义的 MapPermission 有明显不同！

实验要求
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

- 实现分支：ch4-lab
- 实验目录要求不变
- 通过所有测例

  在 os 目录下 ``make run TEST=1`` 测试 sys_get_time， ``make run TEST=2`` 测试 map 和 unmap。

challenge: 支持多核。

问答作业
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

无

实验练习的提交报告要求
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

* 简单总结本次实验与上个实验相比你增加的东西。（控制在5行以内，不要贴代码）
* 完成问答问题。
* (optional) 你对本次实验设计及难度的看法。
   