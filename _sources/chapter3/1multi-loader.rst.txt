多道程序放置与加载
=====================================

本节导读
--------------------------

本节我们将实现可以把多个应用放置到内存中的二叠纪“锯齿螈” [#prionosuchus]_ 操作系统，“锯齿螈”能够上陆了！能实现二叠纪“锯齿螈”操作系统的一个重要前提是计算机中物理内存容量增加了，足以容纳多个应用程序的内容。在计算机的发展史上，我们也确实看到，随着集成电路的快速发展，计算机的内存容量也越来越大了。

在本章的引言中我们提到每个应用都需要按照它的编号被分别放置并加载到内存中不同的位置。本节我们就来介绍多应用的内存放置是如何实现的。通过具体实现，可以看到多个应用程序被一次性地加载到内存中，这样在切换到另外一个应用程序执行会很快，不像前一章介绍的操作系统，还要有清空前一个应用，然后加载当前应用的过程开销。

但我们也会了解到，每个应用程序需要知道自己运行时在内存中的不同位置，这对应用程序的编写带来了一定的麻烦。而且操作系统也要知道每个应用程序运行时的位置，不能任意移动应用程序所在的内存空间，即不能在运行时根据内存空间的动态空闲情况，把应用程序调整到合适的空闲空间中。这是“锯齿螈” [#prionosuchus]_ 操作系统在动态内存管理上的不足之处。

..
  chyyuu：有一个ascii图，画出我们做的OS在本节的部分。

多道程序放置
----------------------------

与第二章相同，所有应用的 ELF 格式执行文件都经过 ``objcopy`` 工具丢掉所有 ELF header 和符号变为二进制镜像文件，随后以同样的格式通过在操作系统内核中嵌入 ``link_user.S`` 文件，在编译时直接把应用链接到内核的数据段中。不同的是，我们对相关模块进行了调整：在第二章中应用的加载和执行进度控制都交给 ``batch`` 子模块，而在第三章中我们将应用的加载这部分功能分离出来在 ``loader`` 子模块中实现，应用的执行和切换功能则交给 ``task`` 子模块。

注意，我们需要调整每个应用被构建时使用的链接脚本 ``linker.ld`` 中的起始地址 ``BASE_ADDRESS`` ，这个地址是应用被内核加载到内存中的起始地址。也就是要做到：应用知道自己会被加载到某个地址运行，而内核也确实能做到将应用加载到它指定的那个地址。这算是应用和内核在某种意义上达成的一种协议。之所以要有这么苛刻的条件，是因为目前的操作系统内核的能力还是比较弱的，对应用程序通用性的支持也不够（比如不支持加载应用到内存中的任意地址运行），这也进一步导致了应用程序编程上不够方便和通用（应用需要指定自己运行的内存地址）。事实上，目前应用程序的编址方式是基于绝对位置的，并没做到与位置无关，内核也没有提供相应的地址重定位机制。

.. note::

   对于编址方式，需要再回顾一下编译原理课讲解的后端代码生成技术，以及计算机组成原理课的指令寻址方式的内容。可以在 `这里 <https://nju-projectn.github.io/ics-pa-gitbook/ics2020/4.2.html>`_ 找到更多有关
   位置无关和重定位的说明。

由于每个应用被加载到的位置都不同，也就导致它们的链接脚本 ``linker.ld`` 中的 ``BASE_ADDRESS`` 都是不同的。实际上，我们不是直接用 ``cargo build`` 构建应用的链接脚本，而是写了一个脚本定制工具 ``build.py`` ，为每个应用定制了各自的链接脚本：

.. code-block:: python
   :linenos:

    # user/build.py

    import os

    base_address = 0x80400000
    step = 0x20000
    linker = 'src/linker.ld'

    app_id = 0
    apps = os.listdir('src/bin')
    apps.sort()
    for app in apps:
        app = app[:app.find('.')]
        lines = []
        lines_before = []
        with open(linker, 'r') as f:
            for line in f.readlines():
                lines_before.append(line)
                line = line.replace(hex(base_address), hex(base_address+step*app_id))
                lines.append(line)
        with open(linker, 'w+') as f:
            f.writelines(lines)
        os.system('cargo build --bin %s --release' % app)
        print('[build.py] application %s start with address %s' %(app, hex(base_address+step*app_id)))
        with open(linker, 'w+') as f:
            f.writelines(lines_before)
        app_id = app_id + 1

它的思路很简单，在遍历 ``app`` 的大循环里面只做了这样几件事情：

- 第 16~22 行，找到 ``src/linker.ld`` 中的 ``BASE_ADDRESS = 0x80400000;`` 这一行，并将后面的地址替换为和当前应用对应的一个地址；
- 第 23 行，使用 ``cargo build`` 构建当前的应用，注意我们可以使用 ``--bin`` 参数来只构建某一个应用；
- 第 25~26 行，将 ``src/linker.ld`` 还原。


多道程序加载
----------------------------

应用的加载方式也和上一章的有所不同。上一章中讲解的加载方法是让所有应用都共享同一个固定的加载物理地址。也是因为这个原因，内存中同时最多只能驻留一个应用，当它运行完毕或者出错退出的时候由操作系统的 ``batch`` 子模块加载一个新的应用来替换掉它。本章中，所有的应用在内核初始化的时候就一并被加载到内存中。为了避免覆盖，它们自然需要被加载到不同的物理地址。这是通过调用 ``loader`` 子模块的 ``load_apps`` 函数实现的：

.. code-block:: rust
   :linenos:

    // os/src/loader.rs

    pub fn load_apps() {
        extern "C" { fn _num_app(); }
        let num_app_ptr = _num_app as usize as *const usize;
        let num_app = get_num_app();
        let app_start = unsafe {
            core::slice::from_raw_parts(num_app_ptr.add(1), num_app + 1)
        };
        // load apps
        for i in 0..num_app {
            let base_i = get_base_i(i);
            // clear region
            (base_i..base_i + APP_SIZE_LIMIT).for_each(|addr| unsafe {
                (addr as *mut u8).write_volatile(0)
            });
            // load app from data section to memory
            let src = unsafe {
                core::slice::from_raw_parts(
                    app_start[i] as *const u8,
                    app_start[i + 1] - app_start[i]
                )
            };
            let dst = unsafe {
                core::slice::from_raw_parts_mut(base_i as *mut u8, src.len())
            };
            dst.copy_from_slice(src);
        }
        unsafe {
            asm!("fence.i");
        }
    }

可以看出，第 :math:`i` 个应用被加载到以物理地址 ``base_i`` 开头的一段物理内存上，而 ``base_i`` 的计算方式如下：

.. code-block:: rust
   :linenos:

    // os/src/loader.rs

    fn get_base_i(app_id: usize) -> usize {
        APP_BASE_ADDRESS + app_id * APP_SIZE_LIMIT
    }

我们可以在 ``config`` 子模块中找到这两个常数。从这一章开始， ``config`` 子模块用来存放内核中所有的常数。看到 ``APP_BASE_ADDRESS`` 被设置为 ``0x80400000`` ，而 ``APP_SIZE_LIMIT`` 和上一章一样被设置为 ``0x20000`` ，也就是每个应用二进制镜像的大小限制。因此，应用的内存布局就很明朗了——就是从 ``APP_BASE_ADDRESS`` 开始依次为每个应用预留一段空间。这样，我们就说清楚了多个应用是如何被构建和加载的。


执行应用程序
----------------------------

当多道程序的初始化放置工作完成，或者是某个应用程序运行结束或出错的时候，我们要调用 run_next_app 函数切换到下一个应用程序。此时 CPU 运行在 S 特权级的操作系统中，而操作系统希望能够切换到 U 特权级去运行应用程序。这一过程与上章的 :ref:`执行应用程序 <ch2-app-execution>` 一节的描述类似。相对不同的是，操作系统知道每个应用程序预先加载在内存中的位置，这就需要设置应用程序返回的不同 Trap 上下文（Trap 上下文中保存了 放置程序起始地址的 ``epc`` 寄存器内容）：

- 跳转到应用程序（编号 :math:`i` ）的入口点 :math:`\text{entry}_i` 
- 将使用的栈切换到用户栈 :math:`\text{stack}_i` 

我们的“锯齿螈”初级多道程序操作系统就算是实现完毕了。它支持把多个应用的代码和数据放置到内存中，并能够依次执行每个应用，提高了应用切换的效率，这就达到了本章对操作系统的初级需求。但“锯齿螈”操作系统在任务调度的灵活性上还有很大的改进空间，下一节我们将开始改进这方面的问题。

..
  chyyuu：有一个ascii图，画出我们做的OS。


.. [#prionosuchus] 锯齿螈身长可达9米，是迄今出现过的最大的两栖动物，是二叠纪时期江河湖泊和沼泽中的顶级掠食者。  