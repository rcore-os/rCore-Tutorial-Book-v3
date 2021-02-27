训练
=====================================================

.. toctree::
   :hidden:
   :maxdepth: 4

- 本节难度： **低** 

简单安全检查
-------------------------------

lab2 中，我们实现了第一个系统调用 ``sys_write``，这使得我们可以在用户态输出信息。但是 os 在提供服务的同时，还有保护 os 本身以及其他用户程序不受错误或者恶意程序破坏的功能。

由于还没有实现虚拟内存，我们可以在用户程序中指定一个属于其他程序字符串，并将它输出，这显然是不合理的，因此我们要对 sys_write 做检查：

- sys_write 仅能输出位于程序本身内存空间内的数据，否则报错。

实验要求
-------------------------------
- 实现分支: ch2。
- 完成实验指导书中的内容，能运行用户态程序并执行 sys_write 系统调用。
- 通过 `Rust测例 <https://github.com/DeathWish5/rCore_tutorial_tests>`_ 或者 `C测例 <https://github.com/DeathWish5/riscvos-c-tests>`_ 中 chapter2 对应的所有测例，测例详情见对应仓库。

实验检查
-------------------------------

- 实验目录要求(Rust)

.. code-block::

   ├── os(内核实现)
   │   ├── Cargo.toml(配置文件)
   │   ├── Makefile (要求 make run 可以正确执行，尽量不输出调试信息)
   │   ├── src(所有内核的源代码放在 os/src 目录下)
   │       ├── main.rs(内核主函数)
   │       ├── ...
   ├── reports
   │   ├── lab1.md/pdf
   │   └── ...
   ├── build.rs (在这里实现用户程序的打包)
   ├── README.md（其他必要的说明）
   ├── ...

参考示例目录结构。目标用户目录 ``../user/build/bin``。

- 检查

.. code-block:: console

   $ cd os
   $ git checkout ch2
   $ make run

可以正确执行正确执行目标用户测例，并得到预期输出（详见测例注释）。

注意：如果设置默认 log 等级，从 lab2 开始关闭所有 log 输出。