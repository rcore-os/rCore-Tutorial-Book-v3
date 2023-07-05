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
   chapter8/index
   chapter9/index

.. toctree::
   :maxdepth: 2
   :caption: Part2 - Do it better!
   :hidden:

.. toctree::
   :maxdepth: 2
   :caption: 附录
   :hidden:

   final-lab
   appendix-a/index
   appendix-b/index
   appendix-c/index
   appendix-d/index
   appendix-e/index
   appendix-f/index
   terminology

.. toctree::
   :maxdepth: 2
   :caption: 开发注记
   :hidden:

   setup-sphinx
   rest-example
   log

欢迎来到 rCore-Tutorial-Book 第三版！

欢迎参加 `2022年开源操作系统训练营! <https://learningos.github.io/rust-based-os-comp2022/>`_

.. note::

   :doc:`/log` 



项目简介
---------------------

这本教程旨在一步一步展示如何 **从零开始** 用 **Rust** 语言写一个基于 **RISC-V** 架构的 **类 Unix 内核** 。值得注意的是，本项目不仅支持模拟器环境（如 Qemu/terminus 等），还支持在真实硬件平台 Kendryte K210 上运行（目前主要在 rCore-Tutorial-v3 仓库的 `k210 <https://github.com/rcore-os/rCore-Tutorial-v3/tree/k210/>`_ 分支上维护）。

导读
---------------------

请大家先阅读 :ref:`第零章 <link-chapter0>` ，对于项目的开发背景和操作系统的概念有一个整体把控。
 
在正式进行实验之前，请先按照第零章章末的 :doc:`/chapter0/5setup-devel-env` 中的说明完成环境配置，再从第一章开始阅读正文。

.. chyyuu 如果已经对 RISC-V 架构、Rust 语言和内核的知识有较多了解，第零章章末的 :doc:`/chapter0/6hardware` 提供了我们采用的真实硬件平台 Kendryte K210 的一些信息。

项目协作
----------------------

- :doc:`/setup-sphinx` 介绍了如何基于 Sphinx 框架配置文档开发环境，之后可以本地构建并渲染 html 或其他格式的文档；
- :doc:`/rest-example` 给出了目前编写文档才用的 ReStructuredText 标记语言的一些基础语法及用例；
- `项目的源代码仓库 <https://github.com/rcore-os/rCore-Tutorial-v3>`_ && `文档仓库 <https://github.com/rcore-os/rCore-Tutorial-Book-v3>`_
- 时间仓促，本项目还有很多不完善之处，欢迎大家积极在每一个章节的评论区留言，或者提交 Issues 或 Pull Requests，让我们一起努力让这本书变得更好！
- 欢迎大家加入项目交流 QQ 群，群号：735045051

本项目与其他系列项目的联系
----------------------------------------------

随着 rcore-os 开源社区的不断发展，目前已经有诸多基于 Rust 语言的操作系统项目，这里介绍一下这些项目之间的区别和联系，让同学们对它们能有一个整体了解并避免混淆。

rcore-os 开源社区大致上可以分为两类项目：即探索使用 Rust 语言构建 OS 的主干项目，以及面向初学者的从零开始写 OS 项目。它们都面向教学用途，但前一类项目参与的开发者更多、更为复杂、功能也更为完善，也会用到更多新的技术；而后一类项目则作为教程项目，尽可能保持简单易懂，目的为向初学者演示如何从头开始写一个 OS 。

主干项目按照时间顺序有这些：最早的是用 Rust 语言实现 linux syscall 的 `rCore <https://github.com/rcore-os/rCore>`_ ，这也是 rcore-os 开源社区的第一个项目。接着，紧跟 Rust 异步编程的浪潮，诞生了使用 Rust 语言重写 Google Fuchsia 操作系统的 Zircon 内核的 `zCore <https://github.com/rcore-os/zCore>`_ 项目，其中利用了大量 Rust 异步原语实现了超时取消等机制。最新的主干项目则是探索 OS 模块化架构的 `arceos <https://github.com/rcore-os/arceos>`_ 。

教程项目则分布在 rcore-os 和 `LearningOS <https://github.com/LearningOS>`_ 两个开源社区中。最早的第一版教程是 `rcore_step_by_step <https://github.com/LearningOS/rcore_step_by_step>`_ ，第二版教程是 `rCore_tutorial <https://github.com/rcore-os/rCore_tutorial>`_ ，第三版教程是 `rCore-Tutorial <https://github.com/rcore-os/rCore-Tutorial>`_ ，最新的教程（暂定 v3.6 版本）就是本项目 `rCore-Tutorial-v3 <https://github.com/rcore-os/rCore-Tutorial-v3>`_ 仍在持续更新中。

教程项目均以 rCore 为前缀，是因为它们都是主干项目 `rCore <https://github.com/rcore-os/rCore>`_ 的简化版。 "rCore" 这个词在不同的语境中指代的具体项目也不一样：如果在讨论教程项目的语境，比如以 xv6 和 ucore 以及 ChCore 等项目类比的时候，那么往往指的是最新的教程项目；相反如果讨论的是大规模项目的话，应该指代 `rCore <https://github.com/rcore-os/rCore>`_ 或者其他主干项目。由于教程项目是由 `rCore <https://github.com/rcore-os/rCore>`_ 简化来的，所以“大rCore”指的是 `rCore <https://github.com/rcore-os/rCore>`_ 主干项目，相对的 “小rCore/rCore教程”则指的是最新版的教程项目。

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
- 2021-03-06：第七章完成。到这里为止第一版初稿就已经完成了。
- 2021-10-20：第八章代码于前段时间完成。开始更新前面章节文档及完成第八章文档。
- 2021-11-20：更新1~9章，添加第八章（同步互斥），原第八章（外设）改为第九章。
- 2022-01-02：第一章文档更新完成。
- 2022-01-05：第二章文档更新完成。
- 2022-01-06：第三章文档更新完成。
- 2022-01-07：第四章文档更新完成。
- 2022-01-09：第五章文档更新完成。
