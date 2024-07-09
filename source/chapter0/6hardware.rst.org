.. chyyuu 可以把k210相关的内容放到某个附录中

K210 开发板相关问题
=====================================================

rCore Tutorial v3 是基于 RISC-V 特权级架构 1.10 版本来开发的。我们采用的真实硬件平台 Kendryte K210 基于 RISC-V 特权级架构 1.9.1 版本（2016 年），目前已经不被当前主流编译工具链所支持了。麻烦的是，RISC-V 特权级架构 1.9.1 版本和1.10版本确实有很多不同。为此，RustSBI 做了很多兼容性工作，使得基于RISC-V 特权级架构 1.10的系统软件几乎可以被不加修改的运行在 Kendryte K210 上。在这里我们先简单介绍一些开发板相关的问题。

K210 相关 Demo 和文档
--------------------------------------------

- `K210 datasheet <https://cdn.hackaday.io/files/1654127076987008/kendryte_datasheet_20181011163248_en.pdf>`_
- `K210 官方 SDK <https://github.com/kendryte/kendryte-standalone-sdk>`_
- `K210 官方 SDK 文档 <https://canaan-creative.com/wp-content/uploads/2020/03/kendryte_standalone_programming_guide_20190311144158_en.pdf>`_
- `K210 官方 SDK Demo <https://github.com/kendryte/kendryte-standalone-demo>`_
- `K210 Demo in Rust <https://github.com/laanwj/k210-sdk-stuff>`_

K210 相关工具
--------------------------------------------

JTAG 调试
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

- `一篇 Blog <https://blog.sipeed.com/p/727.html>`_
- `Sipeed 工程师提供的详细配置文档 <https://github.com/wyfcyx/osnotes/blob/master/book/sipeed_rv_debugger_k210.pdf>`_
- `MaixDock OpenOCD 调试配置 <https://github.com/wyfcyx/osnotes/blob/master/book/openocd_ftdi.cfg>`_

烧写
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

- `kflash.py <https://github.com/sipeed/kflash.py>`_
- `kflash_gui <https://github.com/sipeed/kflash_gui>`_


K210 可用内存大小
--------------------------------------------

K210 的内存是由 CPU 和 KPU 共享使用的，如果想要 CPU 能够使用全部的 :math:`8\text{MiB}` 需要满足三个条件：

- KPU 不能处于工作状态；
- PLL1 必须被使能；
- PLL1 的 clock gate 必须处于打开状态。

否则， CPU 仅能够使用 :math:`6\text{MiB}` 内存。

我们进行如下操作即可让 CPU 使用全部 :math:`8\text{MiB}` 内存（基于官方 SDK）：

.. code-block:: c

    sysctl_pll_enable(SYSCTL_PLL1);
    sysctl_clock_enable(SYSCTL_CLOCK_PLL1);

K210 的频率
--------------------------------------------
默认情况下，K210 的 CPU 频率为 403000000 ，约 :math:`400\text{MHz}` 。而计数器 ``mtime`` CSR 增长的频率为 CPU 频率的 1/62 ，约 :math:`6.5\text{MHz}` 。


K210 的 MMU 支持
--------------------------------------------

K210 有完善的 SV39 多级页表机制，然而它是基于 1.9.1 版本特权级架构的，和我们目前使用的有一些不同。不过在 RustSBI 的帮助下，本项目中完全看不出 Qemu-5.0.0（特权级架构 1.10）和 K210（ 特权级架构 1.9.1） 两个平台在这方面的区别。详情请参考 `RustSBI 的设计与实现 <https://github.com/luojia65/DailySchedule/blob/master/2020-slides/RustSBI%E7%9A%84%E8%AE%BE%E8%AE%A1%E4%B8%8E%E5%AE%9E%E7%8E%B0.pdf>`_ 的 P11 页的内容。

K210 的外部中断支持
--------------------------------------------

K210 的 S 特权级外部中断不存在（被硬件置为零），因此任何软件/硬件代理均无法工作。为此，RustSBI 专门提供了一个新的 SBI call ，让 S 模式软件可以编写 S 特权级外部中断的 handler 并注册到 RustSBI 中，在中断触发的时候由 RustSBI 调用该 handler 处理中断。详情请参考 `RustSBI 的设计与实现 <https://github.com/luojia65/DailySchedule/blob/master/2020-slides/RustSBI%E7%9A%84%E8%AE%BE%E8%AE%A1%E4%B8%8E%E5%AE%9E%E7%8E%B0.pdf>`_ 的 P12 页的内容。