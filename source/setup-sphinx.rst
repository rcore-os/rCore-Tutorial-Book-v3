修改和构建本项目
====================================

.. toctree::
   :hidden:
   :maxdepth: 4
   
1. 参考 `这里 <https://www.sphinx-doc.org/en/master/usage/installation.html>`_ 安装 Sphinx。
2. ``pip install sphinx_rtd_theme`` 安装 Read The Docs 主题。
3. ``pip install jieba`` 安装中文分词。
4. ``pip install sphinx-comments`` 安装 Sphinx 讨论区插件。
5. :doc:`/rest-example` 是 ReST 的一些基本语法，也可以参考已完成的文档。
6. 修改之后，在项目根目录下 ``make clean && make html`` 即可在 ``build/html/index.html`` 查看本地构建的主页。请注意在修改章节目录结构之后需要 ``make clean`` 一下，不然可能无法正常更新。
7. 确认修改无误之后，将 ``main`` 主分支上的修改 merge 到 ``deploy`` 分支，在项目根目录下 ``make deploy`` 即可将更新后的文档部署到用于部署的 ``deploy`` 分支上。
   如果与其他人的提交冲突的话，请删除掉 ``docs`` 目录再进行 merge。
