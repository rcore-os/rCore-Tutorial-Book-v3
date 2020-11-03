项目协作
==================

.. toctree::
   :hidden:
   :maxdepth: 4
   
1. 参考 `这里 <https://www.sphinx-doc.org/en/master/usage/installation.html>`_ 安装 Sphinx。
2. ``pip install jieba`` 安装中文分词。
3. :doc:`/rest-example` 是 ReST 的一些基本语法，也可以参考已完成的文档。
4. 修改之后，在项目根目录下 ``make html`` 即可在 ``build/html/index.html`` 查看本地构建的主页。
5. 确认修改无误之后，在项目根目录下 ``make deploy`` 然后即可 ``git add -A && git commit -m && git push`` 上传到远程仓库。
   如果出现冲突的话，请删除掉 ``docs`` 目录再进行 merge。