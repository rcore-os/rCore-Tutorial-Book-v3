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
