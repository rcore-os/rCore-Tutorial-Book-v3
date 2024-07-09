修改和构建本项目
====================================

.. toctree::
   :hidden:
   :maxdepth: 4
   
1. 参考 `这里 <https://www.sphinx-doc.org/en/master/usage/installation.html>`_ 安装 Sphinx。
2. 切换到仓库目录下， ``pip install -r requirements.txt`` 安装各种 python 库依赖。
3. :doc:`/rest-example` 是 ReST 的一些基本语法，也可以参考已完成的文档。
4. 修改之后，在项目根目录下 ``make clean && make html`` 即可在 ``build/html/index.html`` 查看本地构建的主页。请注意在修改章节目录结构或者更新各种配置文件/python 脚本之后需要 ``make clean`` 一下，不然可能无法正常更新。
5. 如想对项目做贡献的话，直接提交 pull request 即可。

.. note:: 
   
   **实时显示修改rst文件后的html文档的方法**

   1. ``pip install autoload`` 安装 Sphinx 自动加载插件。
   2. 在项目根目录下 ``sphinx-autobuild source  build/html`` 即可在浏览器中访问 `http://127.0.0.1:8000/` 查看本地构建的主页。

.. note::

   **如何生成教程pdf电子版**

   注意：经过尝试在 wsl 环境下无法生成 pdf ，请使用原生的 Ubuntu Desktop 或者虚拟机。

   1. 首先 ``sudo apt update`` ，然后通过 ``sudo apt install`` 安装如下软件包： latexmk texlive-latex-recommended texlive-latex-extra texlive-xetex fonts-freefont-otf texlive-fonts-recommended texlive-lang-chinese tex-gyre.
   2. 从 Node.js 官方网站下载最新版的 Node.js ，配置好环境变量并通过 ``npm --version`` 确认配置正确。然后通过 ``npm install -g @mermaid-js/mermaid-cli`` 安装 mermaid 命令行工具。
   3. 确认 Python 环境配置正确，也即 ``make html`` 可以正常生成 html 。
   4. 打上必要的补丁：在根目录下执行 ``git apply --reject scripts/latexpdf.patch`` 。
   5. 构建：在根目录下执行 ``make latexpdf`` ，过程中会有很多 latex 的警告，但可以忽略。
   6. 构建结束后，电子版 pdf 可以在 ``build/latex/rcore-tutorial-book-v3.pdf`` 找到。

.. note::

   **如何生成epub格式**

   1. 配置好 Sphinx Python 环境。
   2. ``make epub`` 构建 epub 格式输出，产物可以在 ``build/epub/rCore-Tutorial-Book-v3.epub`` 中找到。