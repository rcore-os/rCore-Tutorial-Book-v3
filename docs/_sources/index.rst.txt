.. rCore-Tutorial-Book-v3 documentation master file, created by
   sphinx-quickstart on Thu Oct 29 22:25:54 2020.
   You can adapt this file completely to your liking, but it should at least
   contain the root `toctree` directive.

rCore-Tutorial-Book 第三版
==================================================

.. toctree::
   :maxdepth: 2
   :caption: 章节列表
   :hidden:
   
   quickstart
   chapter0/index

欢迎来到 rCore-Tutorial-Book 第三版！

reStructuredText 基本语法
----------------------------------------------

.. note::
   下面是一个注记。

   `这里 <https://www.sphinx-doc.org/en/master/usage/restructuredtext/basics.html#hyperlinks>`_ 给出了在 Sphinx 中
   外部链接的引入方法。注意，链接的名字和用一对尖括号包裹起来的链接地址之间必须有一个空格。链接最后的下划线和片段的后续内容之间也需要
   有一个空格。

   接下来是一个文档内部引用的例子。比如，戳 :doc:`quickstart` 可以进入快速上手环节。

.. warning::

   下面是一个警告。

   .. code-block:: rust
      :linenos:
      :caption: 一段示例 Rust 代码

      // 我们甚至可以插入一段 Rust 代码！
      fn add(a: i32, b: i32) -> i32 { a + b }

   下面继续我们的警告。

.. error::

   下面是一个错误。


这里是一行数学公式 :math:`\sin(\alpha+\beta)=\sin\alpha\cos\beta+\cos\alpha\sin\beta`。

基本的文本样式：这是 *斜体* ，这是 **加粗** ，接下来的则是行间公式 ``a0`` 。它们的前后都需要有一个空格隔开其他内容，这个让人挺不爽的...

`这是 <https://docs.readthedocs.io/en/stable/guides/cross-referencing-with-sphinx.html#the-doc-role>`_ 一个全面展示
章节分布的例子，来自于 ReadTheDocs 的官方文档。事实上，现在我们也采用 ReadTheDocs 主题了，它非常美观大方。
