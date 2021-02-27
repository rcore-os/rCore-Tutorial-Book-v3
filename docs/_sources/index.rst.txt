.. rCore-Tutorial-Book-v3 documentation master file, created by
   sphinx-quickstart on Thu Oct 29 22:25:54 2020.
   You can adapt this file completely to your liking, but it should at least
   contain the root `toctree` directive.

rCore-Tutorial-Book 第三版
==================================================

.. toctree::
   :maxdepth: 2
   :caption: Part1 - Just do it!
   :hidden:
   
   chapter0/index
   chapter1/index
   chapter2/index
   chapter3/index
   chapter4/index
   chapter5/index
   chapter6/index
   chapter7/index

.. toctree::
   :maxdepth: 2
   :caption: Part2 - Do it better!
   :hidden:
   
   chapter8/index

.. toctree::
   :maxdepth: 2
   :caption: 附录
   :hidden:

   appendix-a/index
   appendix-b/index
   appendix-c/index
   appendix-d/index
   terminology

.. toctree::
   :maxdepth: 2
   :caption: 开发注记
   :hidden:

   setup-sphinx
   rest-example
   log

欢迎来到 rCore-Tutorial-Book 第三版！

.. note::

   :doc:`/log` 

   项目/文档于 2021-02-27 最后一次更新，情况如下：

   完善了 ``easy-fs`` ：

   - 订正了 ``easy-fs`` 块缓存层的实现，移除了 ``dirty`` 子模块。
   - 支持二级间接块索引，使得支持的单个文件最大容量从 :math:`94\text{KiB}` 变为超过 :math:`8\text{MiB}` 。调整了单个 ``DiskInode`` 大小为 128 字节。
   - 在新建一个索引节点的时候不再直接分配一二级间接索引块，而是完全按需分配。
   - 将 ``easy-fs`` 的测试和应用程序打包的函数分离到另一个名为 ``easy-fs-fuse`` 的 crate 中。

   从 ch7 开始：

   - 出于后续的一些需求， ``sys_exec`` 需要支持命令行参数，为此用户终端 ``user_shell`` 中需要相应增加一些解析功能，内核中 ``sys_exec`` 的实现也需要进行修改。新增了应用 ``cmdline_args`` 来打印传入的命令行参数。
   - 新增了应用 cat 工具可以读取一个文件的全部内容。
   - 在用户终端中支持通过 ``<`` 和 ``>`` 进行简单的输入/输出重定向，为此在内核中新增了一个 ``sys_dup`` 系统调用。 

   另外，在所有章节分支新增了 docker 支持来尽可能降低环境配置的时间成本，详见 :ref:`使用 Docker 环境 <link-docker-env>` 。


项目简介
---------------------

这本教程旨在一步一步展示如何 **从零开始** 用 **Rust** 语言写一个基于 **RISC-V** 架构的 **类 Unix 内核** 。值得注意的是，本项目不仅支持模拟器环境（如 Qemu/terminus 等），还支持在真实硬件平台 Kendryte K210 上运行。


导读
---------------------

请大家先阅读 :ref:`第零章 <link-chapter0>` ，对于项目的开发背景和操作系统的概念有一个整体把控。
 
在正式进行实验之前，请先按照第零章章末的 :doc:`/chapter0/5setup-devel-env` 中的说明完成环境配置，再从第一章开始阅读正文。

如果已经对 RISC-V 架构、Rust 语言和内核的知识有较多了解，第零章章末的 :doc:`/chapter0/6hardware` 提供了我们采用的真实硬件平台 Kendryte K210 的一些信息。

项目协作
----------------------

- :doc:`/setup-sphinx` 介绍了如何基于 Sphinx 框架配置文档开发环境，之后可以本地构建并渲染 html 或其他格式的文档；
- :doc:`/rest-example` 给出了目前编写文档才用的 ReStructuredText 标记语言的一些基础语法及用例；
- `项目的源代码仓库 <https://github.com/rcore-os/rCore-Tutorial-v3>`_ && `文档仓库 <https://github.com/rcore-os/rCore-Tutorial-Book-v3>`_
- 时间仓促，本项目还有很多不完善之处，欢迎大家积极在每一个章节的评论区留言，或者提交 Issues 或 Pull Requests，让我们
  一起努力让这本书变得更好！

项目进度
-----------------------

- 2020-11-03：环境搭建完成，开始着手编写文档。
- 2020-11-13：第一章完成。
- 2020-11-27：第二章完成。
- 2020-12-20：前七章代码完成。
- 2021-01-10：第三章完成。
- 2021-01-18：加入第零章。
- 2021-01-30：第四章完成。
- 2021-02-16：第五章完成。
- 2021-02-20：第六章完成。