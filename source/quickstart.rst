快速上手
============

.. toctree::
   :hidden:
   :maxdepth: 4
   
本节我们将完成环境配置并成功运行 rCore-Tutorial。

首先，请参考 `环境部署 <https://rcore-os.github.io/rCore-Tutorial-deploy/docs/pre-lab/env.html>`_ 安装 qemu 模拟器
和 rust。有一些小的变更如下：

- 将 ``riscv64imac-unknown-none-elf`` 改成 ``riscv64gc-unknown-none-elf``；
- 在使用文档中提供的链接下载 qemu 源码的时候，点击下载之后需要将链接中的 ``localhost`` 替换为 ``42.194.184.212:5212``。若仍然
  不行的话，可以在 `SiFive 官网 <https://www.sifive.com/software>`_ 下载预编译的 qemu，比如 
  `Ubuntu 版本 qemu <https://static.dev.sifive.com/dev-tools/riscv-qemu-4.2.0-2020.04.0-x86_64-linux-ubuntu14.tar.gz>`_ 。

此外：

- 下载安装 `macOS 平台 <https://static.dev.sifive.com/dev-tools/riscv64-unknown-elf-gcc-8.3.0-2020.04.0-x86_64-apple-darwin.tar.gz?_ga=2.230260892.1021855761.1603335606-1708912445.1603335606>`_ 
  或 `Ubuntu 平台 <https://static.dev.sifive.com/dev-tools/riscv64-unknown-elf-gcc-8.3.0-2020.04.0-x86_64-linux-ubuntu14.tar.gz?_ga=2.230260892.1021855761.1603335606-1708912445.1603335606>`_ 
  的预编译版本 ``riscv64-unknown-elf-*`` 工具链，并添加到环境变量。可以在提示找不到的情况下再进行下载。
- 下载安装 `Linux 平台 <https://musl.cc/riscv64-linux-musl-cross.tgz>`_ 预编译版本的 ``riscv64-linux-musl-*`` 工具链，并
  添加到环境变量。可以在提示找不到的情况下再进行下载。
- 如果想在 Maix 系列开发板上运行，需要安装 python 包 ``pyserial`` 和串口终端 miniterm 。

.. warning::

   **FIXME： 提供一套开箱即用的 Docker 环境**

