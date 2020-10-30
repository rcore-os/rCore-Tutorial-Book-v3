移除标准库依赖
===========================

.. toctree::
   :hidden:
   :maxdepth: 3

让我们从零开始创建内核项目。一开始，它就和一个普通的 Cargo 项目没有什么不同：

.. code-block:: console

   $ cargo new os --bin

我们加上了 ``--bin`` 选项来告诉 Cargo 我们创建一个可执行项目而不是库项目。此时，项目的文件结构如下：

.. code-block:: console
   
   $ tree os
   os
   ├── Cargo.toml
   └── src
       └── main.rs

   1 directory, 2 files

其中 ``Cargo.toml`` 中保存着项目的配置，包括作者的信息、联系方式以及库依赖等等。显而易见源代码保存在 ``src`` 目录下，目前为止只有 ``main.rs``
一个文件，让我们看一下里面的内容：

.. code-block:: rust
   :linenos:
   :caption: 最简单的 Rust 应用

   fn main() {
       println!("Hello, world!");
   }

利用 Cargo 工具即可一条命令实现构建并运行项目：

.. code-block:: console
   
   $ cargo run
      Compiling os v0.1.0 (/home/shinbokuow/workspace/v3/rCore-Tutorial-v3/os)
       Finished dev [unoptimized + debuginfo] target(s) in 1.15s
        Running `target/debug/os`
   Hello, world!
 

