多任务加载器
=====================================

在本章的引言中我们提到每个应用都需要按照它的编号被分别加载到内存中不同的位置。本节我们就来介绍它是如何实现的。

与第二章相同，所有应用的 ELF 都经过 strip 丢掉所有 ELF header 和符号变为二进制镜像文件，随后以同样的格式通过 
``link_user.S`` 在编译的时候直接链接到内核的数据段中。不同的是，我们对相关模块进行了调整：在第二章中
应用的加载和进度控制都交给 ``batch`` 子模块，而在第三章中我们将应用的加载这部分功能分离出来在 ``loader`` 
子模块中实现，应用的执行和切换则交给 ``task`` 子模块。

应用的加载方式也和上一章不同。上一章的时候所有应用都被加载到一个固定的物理地址，也是因为这个原因，内存中同时
最多只能驻留一个应用，当它运行完毕或者出错退出的时候由 ``batch`` 子模块加载一个新的应用来替换掉它。本章中，
所有的应用在内核初始化的时候就一并被加载到内存中。为了避免覆盖，它们自然需要被加载到不同的物理地址。这是通过
调用 ``loader`` 子模块的 ``load_apps`` 函数实现的：

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
        // clear i-cache first
        unsafe { llvm_asm!("fence.i" :::: "volatile"); }
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
    }

可以看出，第 :math:`i` 个应用被加载到以物理地址 ``base_i`` 开头的一段物理内存上，而 ``base_i`` 的
计算方式如下：

.. code-block:: rust
   :linenos:

    // os/src/loader.rs

    fn get_base_i(app_id: usize) -> usize {
        APP_BASE_ADDRESS + app_id * APP_SIZE_LIMIT
    }

我们可以在 ``config`` 子模块中找到这两个常数。从这一章开始， ``config`` 子模块用来存放内核中所有的常数。看到 
``APP_BASE_ADDRESS`` 被设置为 ``0x80100000`` ，而 ``APP_SIZE_LIMIT`` 和上一章一样被设置为 
``0x20000`` ，也就是每个应用二进制镜像的大小限制。因此，应用的内存布局就很明朗了——就是从 
``APP_BASE_ADDRESS`` 开始依次为每个应用预留一段空间。

注意，我们需要调整每个应用被构建时候使用的链接脚本 ``linker.ld`` 中的起始地址 ``BASE_ADDRESS`` 为它实际
会被内核加载并运行的地址。也就是要做到：应用知道自己会被加载到某个地址运行，而内核也确实能做到将它加载到那个
地址。这算是应用和内核在某种意义上达成的一种协议。之所以要有这么苛刻的条件，是因为应用和内核的能力都很弱，泛用性很低。
事实上，目前我们的应用是绝对位置而并不是位置无关的，内核也没有提供相应的重定位机制。

.. note::

   可以在 `这里 <https://nju-projectn.github.io/ics-pa-gitbook/ics2020/4.2.html>`_ 找到更多有关
   位置无关和重定位的说明。

由于每个应用被加载到的位置都不同，也就导致它们 ``linker.ld`` 中的 ``BASE_ADDRESS`` 都是不同的。实际上，
我们写了一个脚本 ``build.py`` 而不是直接 ``cargo build`` 构建应用：

.. code-block:: python
   :linenos:

    # user/build.py

    import os

    base_address = 0x80100000
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

- 第 16~22 行，找到 ``src/linker.ld`` 中的 ``BASE_ADDRESS = 0x80100000;`` 这一行，并将后面的地址
  替换为和当前应用对应的一个地址；
- 第 23 行，使用 ``cargo build`` 构建当前的应用，注意我们可以使用 ``--bin`` 参数来只构建某一个应用；
- 第 25~26 行，将 ``src/linker.ld`` 还原。

这样，我们就说明了多个应用是如何被构建和加载的。
