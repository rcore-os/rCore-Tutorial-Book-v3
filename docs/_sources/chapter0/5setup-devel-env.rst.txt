实验环境配置
============

.. toctree::
   :hidden:
   :maxdepth: 4
   
本节我们将完成环境配置并成功运行 rCore-Tutorial-v3 。整个流程分为下面几个部分：

- 系统环境配置
- Rust 开发环境配置
- Qemu 模拟器安装
- 其他工具安装
- 运行 rCore-Tutorial-v3

系统环境配置
-------------------------------

目前实验仅支持 Ubuntu18.04 / 20.04 + 操作系统。对于 Windows10 和 macOS 上的用户，可以使用 VMware 或 
VirtualBox 安装一台 Ubuntu18.04 / 20.04 虚拟机并在上面进行实验。

特别的，Windows10 的用户可以通过系统内置的 WSL2 虚拟机（请不要使用 WSL1）来安装 Ubuntu 18.04 / 20.04 。
步骤如下：

- 升级 Windows 10 到最新版（Windows 10 版本 18917 或以后的内部版本）。注意，如果
  不是 Windows 10 专业版，可能需要手动更新，在微软官网上下载。升级之后，
  可以在 PowerShell 中输入 ``winver`` 命令来查看内部版本号。
- 「Windows 设置 > 更新和安全 > Windows 预览体验计划」处选择加入 “Dev 开发者模式”。
- 以管理员身份打开 PowerShell 终端并输入以下命令：

  .. code-block::

     # 启用 Windows 功能：“适用于 Linux 的 Windows 子系统”
     >> dism.exe /online /enable-feature /featurename:Microsoft-Windows-Subsystem-Linux /all /norestart

     # 启用 Windows 功能：“已安装的虚拟机平台”
     >> dism.exe /online /enable-feature /featurename:VirtualMachinePlatform /all /norestart

     # <Distro> 改为对应从微软应用商店安装的 Linux 版本名，比如：`wsl --set-version Ubuntu 2`
     # 如果你没有提前从微软应用商店安装任何 Linux 版本，请跳过此步骤
     >> wsl --set-version <Distro> 2

     # 设置默认为 WSL 2，如果 Windows 版本不够，这条命令会出错
     >> wsl --set-default-version 2

-  `下载 Linux 内核安装包 <https://docs.microsoft.com/zh-cn/windows/wsl/install-win10#step-4---download-the-linux-kernel-update-package>`_
-  在微软商店（Microsoft Store）中搜索并安装 Ubuntu18.04 / 20.04。

如果你打算使用 VMware 安装虚拟机的话，我们已经配置好了一个能直接运行 rCore-Tutorial-v3 的 
Ubuntu18.04 镜像，它是一个 ``vmdk`` 格式的虚拟磁盘文件，只需要在 VMware 中新建一台虚拟机，
在设置虚拟磁盘的时候选择它即可。`百度网盘链接 <https://pan.baidu.com/s/1JzKjWivy9GZKK8rc3WMJ0g>`_ （提取码 x5mf ）
或者 `清华云盘链接 <https://cloud.tsinghua.edu.cn/d/a9b7b0a1b4724c3f9c66/>`_ 。
已经创建好用户 oslab ，密码为一个空格。它已经安装了中文输入法和 Markdown 编辑器 Typora 还有作为 Rust 集成开发环境的 
Visual Studio Code，能够更容易完成实验并撰写实验报告。

.. _link-docker-env:

.. note::

   **Docker 开发环境**

   感谢 dinghao188 和张汉东老师帮忙配置好的 Docker 开发环境，进入 Docker 开发环境之后不需要任何软件工具链的安装和配置，可以直接将 tutorial 运行起来，目前应该仅支持将 tutorial 运行在 Qemu 模拟器上。
   
   使用方法如下（以 Ubuntu18.04 为例）：

   1. 通过 ``su`` 切换到管理员账户 ``root`` ；
   2. 在 ``rCore-Tutorial-v3`` 根目录下 ``make docker`` 进入到 Docker 环境；
   3. 进入 Docker 之后，会发现当前处于根目录 ``/`` ，我们通过 ``cd mnt`` 将当前工作路径切换到 ``/mnt`` 目录；
   4. 通过 ``ls`` 可以发现 ``/mnt`` 目录下的内容和 ``rCore-Tutorial-v3`` 目录下的内容完全相同，接下来就可以在这个环境下运行 tutorial 了。例如 ``cd os && make run`` 。    


你也可以在 Windows10 或 macOS 原生系统或者其他 Linux 发行版上进行实验，基本上不会出现太大的问题。不过由于
时间问题我们主要在 Ubuntu18.04 上进行了测试，后面的配置也都是基于它的。如果遇到了问题的话，请在本节的讨论区
中留言，我们会尽量帮助解决。

Rust 开发环境配置
-------------------------------------------

首先安装 Rust 版本管理器 rustup 和 Rust 包管理器 cargo，这里我们用官方的安装脚本来安装：

.. code-block:: bash

   curl https://sh.rustup.rs -sSf | sh

如果通过官方的脚本下载失败了，可以在浏览器的地址栏中输入 `<https://sh.rustup.rs>`_ 来下载脚本，在本地运行即可。

如果官方的脚本在运行时出现了网络速度较慢的问题，可选地可以通过修改 rustup 的镜像地址
（修改为中国科学技术大学的镜像服务器）来加速：

.. code-block:: bash
   
   export RUSTUP_DIST_SERVER=https://mirrors.ustc.edu.cn/rust-static
   export RUSTUP_UPDATE_ROOT=https://mirrors.ustc.edu.cn/rust-static/rustup
   curl https://sh.rustup.rs -sSf | sh

或者使用tuna源来加速 `参见 rustup 帮助 <https://mirrors.tuna.tsinghua.edu.cn/help/rustup/>`_：

.. code-block:: bash
   
   export RUSTUP_DIST_SERVER=https://mirrors.tuna.edu.cn/rustup
   export RUSTUP_UPDATE_ROOT=https://mirrors.tuna.edu.cn/rustup/rustup
   curl https://sh.rustup.rs -sSf | sh

或者也可以通过在运行前设置命令行中的科学上网代理来实现：

.. code-block:: bash 

   # e.g. Shadowsocks 代理，请根据自身配置灵活调整下面的链接
   export https_proxy=http://127.0.0.1:1080
   export http_proxy=http://127.0.0.1:1080
   export ftp_proxy=http://127.0.0.1:1080

安装完成后，我们可以重新打开一个终端来让之前设置的环境变量生效。我们也可以手动将环境变量设置应用到当前终端，
只需要输入以下命令：

.. code-block:: bash

   source $HOME/.cargo/env

接下来，我们可以确认一下我们正确安装了 Rust 工具链：

.. code-block:: bash
   
   rustc --version

可以看到当前安装的工具链的版本。

.. code-block:: bash

   rustc 1.46.0-nightly (7750c3d46 2020-06-26)

.. warning::
   目前用于操作系统实验开发的rustc编译器的版本不局限在1.46.0这样的数字上，你可以选择更新的rustc编译器。但注意只能用rustc的nightly版本。


可通过如下命令安装rustc的nightly版本，并把该版本设置为rustc的缺省版本。

.. code-block:: bash
   
   rustup install nightly
   rustup default nightly


我们最好把软件包管理器 cargo 所用的软件包镜像地址 crates.io 也换成中国科学技术大学的镜像服务器来加速三方库的下载。
我们打开（如果没有就新建） ``~/.cargo/config`` 文件，并把内容修改为：

.. code-block:: toml

   [source.crates-io]
   registry = "https://github.com/rust-lang/crates.io-index"
   replace-with = 'ustc'
   [source.ustc]
   registry = "git://mirrors.ustc.edu.cn/crates.io-index"

同样，也可以使用tuna源 `参见 crates.io 帮助 <https://mirrors.tuna.tsinghua.edu.cn/help/crates.io-index.git/>`_：

.. code-block:: toml

   [source.crates-io]
   replace-with = 'tuna'

   [source.tuna]
   registry = "https://mirrors.tuna.tsinghua.edu.cn/git/crates.io-index.git"

接下来安装一些Rust相关的软件包

.. code-block:: bash

   rustup target add riscv64gc-unknown-none-elf
   cargo install cargo-binutils --vers ~0.2
   rustup component add llvm-tools-preview
   rustup component add rust-src

.. warning::
   如果你换了另外一个rustc编译器（必须是nightly版的），需要重新安装上述rustc所需软件包。
   rCore-Tutorial 仓库中的 ``Makefile`` 包含了这些工具的安装，如果你使用 ``make run`` 也可以不手动安装。

至于 Rust 开发环境，推荐 JetBrains Clion + Rust插件 或者 Visual Studio Code 搭配 rust-analyzer 和 RISC-V Support 插件。

.. note::

   * JetBrains Clion是付费商业软件，但对于学生和教师，只要在 JetBrains 网站注册账号，可以享受一定期限（半年左右）的免费使用的福利。
   * Visual Studio Code 是开源软件，不用付费就可使用。
   * 当然，采用 VIM，Emacs 等传统的编辑器也是没有问题的。

Qemu 模拟器安装
----------------------------------------

我们需要使用 Qemu 5.0.0 版本进行实验，而很多 Linux 发行版的软件包管理器默认软件源中的 Qemu 版本过低，因此
我们需要从源码手动编译安装 Qemu 模拟器。

首先我们安装依赖包，获取 Qemu 源代码并手动编译：

.. code-block:: bash

   # 安装编译所需的依赖包
   sudo apt install autoconf automake autotools-dev curl libmpc-dev libmpfr-dev libgmp-dev \
                 gawk build-essential bison flex texinfo gperf libtool patchutils bc \
                 zlib1g-dev libexpat-dev pkg-config  libglib2.0-dev libpixman-1-dev git tmux python3
   # 下载源码包 
   # 如果下载速度过慢可以使用我们提供的百度网盘链接：https://pan.baidu.com/s/1z-iWIPjxjxbdFS2Qf-NKxQ
   # 提取码 8woe
   wget https://download.qemu.org/qemu-5.0.0.tar.xz
   # 解压
   tar xvJf qemu-5.0.0.tar.xz
   # 编译安装并配置 RISC-V 支持
   cd qemu-5.0.0
   ./configure --target-list=riscv64-softmmu,riscv64-linux-user
   make -j$(nproc)

.. note::
   
   注意，上面的依赖包可能并不完全，比如在 Ubuntu 18.04 上：

   - 出现 ``ERROR: pkg-config binary 'pkg-config' not found`` 时，可以安装 ``pkg-config`` 包；
   - 出现 ``ERROR: glib-2.48 gthread-2.0 is required to compile QEMU`` 时，可以安装 
     ``libglib2.0-dev`` 包；
   - 出现 ``ERROR: pixman >= 0.21.8 not present`` 时，可以安装 ``libpixman-1-dev`` 包。

   另外一些 Linux 发行版编译 Qemu 的依赖包可以从 `这里 <https://risc-v-getting-started-guide.readthedocs.io/en/latest/linux-qemu.html#prerequisites>`_ 
   找到。

之后我们可以在同目录下 ``sudo make install`` 将 Qemu 安装到 ``/usr/local/bin`` 目录下，但这样经常会引起
冲突。个人来说更习惯的做法是，编辑 ``~/.bashrc`` 文件（如果使用的是默认的 ``bash`` 终端），在文件的末尾加入
几行：

.. code-block:: bash

   # 请注意，qemu-5.0.0 的父目录可以随着你的实际安装位置灵活调整
   export PATH=$PATH:/home/shinbokuow/Downloads/built/qemu-5.0.0
   export PATH=$PATH:/home/shinbokuow/Downloads/built/qemu-5.0.0/riscv64-softmmu
   export PATH=$PATH:/home/shinbokuow/Downloads/built/qemu-5.0.0/riscv64-linux-user

随后即可在当前终端 ``source ~/.bashrc`` 更新系统路径，或者直接重启一个新的终端。

此时我们可以确认 Qemu 的版本：

.. code-block:: bash

   qemu-system-riscv64 --version
   qemu-riscv64 --version

K210 真机串口通信
------------------------------

为了能在 K210 真机上运行 Tutorial，我们还需要安装基于 Python 的串口通信库和简易的串口终端。

.. code-block:: bash

   pip3 install pyserial
   sudo apt install python-serial

GDB 调试支持
------------------------------

在 ``os`` 目录下 ``make debug`` 可以调试我们的内核，这需要安装终端复用工具 ``tmux`` ，还需要基于 riscv64 平台的 gdb 调试器 ``riscv64-unknown-elf-gdb`` 。该调试器包含在 riscv64 gcc 工具链中，工具链的预编译版本可以在如下链接处下载：

- `Ubuntu 平台 <https://static.dev.sifive.com/dev-tools/riscv64-unknown-elf-gcc-8.3.0-2020.04.1-x86_64-linux-ubuntu14.tar.gz>`_
- `macOS 平台 <https://static.dev.sifive.com/dev-tools/riscv64-unknown-elf-gcc-8.3.0-2020.04.1-x86_64-apple-darwin.tar.gz>`_
- `Windows 平台 <https://static.dev.sifive.com/dev-tools/riscv64-unknown-elf-gcc-8.3.0-2020.04.1-x86_64-w64-mingw32.zip>`_
- `CentOS 平台 <https://static.dev.sifive.com/dev-tools/riscv64-unknown-elf-gcc-8.3.0-2020.04.1-x86_64-linux-centos6.tar.gz>`_

解压后在 ``bin`` 目录下即可找到 ``riscv64-unknown-elf-gdb`` 以及另外一些常用工具 ``objcopy/objdump/readelf`` 等。

运行 rCore-Tutorial-v3
------------------------------------------------------------

在 Qemu 平台上运行
++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++

如果是在 Qemu 平台上运行，只需在 ``os`` 目录下 ``make run`` 即可。在内核加载完毕之后，可以看到目前可以用的
应用程序。 ``usertests`` 打包了其中的很大一部分，所以我们可以运行它，只需输入在终端中输入它的名字即可。

.. image:: qemu-final.gif

之后，可以先按下 ``Ctrl+A`` ，再按下 ``X`` 来退出 Qemu。

在 K210 平台上运行
+++++++++++++++++++++++++++++++++++++++++++++++++++++++++++

如果是在 K210 平台上运行则略显复杂。

首先，我们需要将 MicroSD 插入 PC 来将文件系统镜像拷贝上去。

.. image:: prepare-sd.gif

.. warning::

   在 ``os/Makefile`` 中我们默认设置 MicroSD 在当前操作系统中可以用设备 ``SDCARD=/dev/sdb`` 访问。你可以使用 ``df -hT`` 命令来确认在你的环境中 MicroSD 是哪个设备，
   并在 ``make sdcard`` 之前对 ``os/Makefile`` 的 ``SDCARD`` 配置做出适当的修改。不然，这有可能导致 **设备 /dev/sdb 上数据丢失**！
   
随后，我们将 MicroSD 插入 K210 开发板，将 K210 开发板连接到 PC ，然后进入 ``os`` 目录 ``make run BOARD=k210`` 
在 K210 开发板上跑 rCore Tutorial 。 

.. image:: k210-final.gif

之后，可以按下 ``Ctrl+]`` 来退出串口终端。

到这里，恭喜你完成了实验环境的配置，可以开始阅读教程的正文部分了！
