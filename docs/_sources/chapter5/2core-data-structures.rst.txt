进程机制核心数据结构
===================================

本节导读
-----------------------------------

为了更好实现进程抽象，同时也使得整体架构更加灵活能够满足后续的一些需求，我们需要重新设计一些数据结构包含的内容及接口。本节将按照如下顺序来进行介绍：

- 基于应用名的应用链接/加载器
- 进程标识符 ``PidHandle`` 以及内核栈 ``KernelStack``
- 任务控制块 ``TaskControlBlock``
- 任务管理器 ``TaskManager``
- 处理器监视器 ``Processor``

基于应用名的应用链接/加载器
------------------------------------------------------------------------

在实现 ``exec`` 系统调用的时候，我们需要根据应用的名字而不仅仅是一个编号来获取应用的 ELF 格式数据。因此原有的链接和加载接口需要做出如下变更：

在链接器 ``os/build.rs`` 中，我们需要按顺序保存链接进来的每个应用的名字：
  
.. code-block::
    :linenos:
    :emphasize-lines: 8-13

        // os/build.rs

        for i in 0..apps.len() {
            writeln!(f, r#"    .quad app_{}_start"#, i)?;
        }
        writeln!(f, r#"    .quad app_{}_end"#, apps.len() - 1)?;

        writeln!(f, r#"
        .global _app_names
    _app_names:"#)?;
        for app in apps.iter() {
            writeln!(f, r#"    .string "{}""#, app)?;
        }

        for (idx, app) in apps.iter().enumerate() {
            ...
        }

第 8~13 行，我们按照顺序将各个应用的名字通过 ``.string`` 伪指令放到数据段中，注意链接器会自动在每个字符串的结尾加入分隔符 ``\0`` ，它们的位置则由全局符号 ``_app_names`` 指出。

而在加载器 ``loader.rs`` 中，我们用一个全局可见的 *只读* 向量 ``APP_NAMES`` 来按照顺序将所有应用的名字保存在内存中：

.. code-block:: Rust

    // os/src/loader.rs

    lazy_static! {
        static ref APP_NAMES: Vec<&'static str> = {
            let num_app = get_num_app();
            extern "C" { fn _app_names(); }
            let mut start = _app_names as usize as *const u8;
            let mut v = Vec::new();
            unsafe {
                for _ in 0..num_app {
                    let mut end = start;
                    while end.read_volatile() != '\0' as u8 {
                        end = end.add(1);
                    }
                    let slice = core::slice::from_raw_parts(start, end as usize - start as usize);
                    let str = core::str::from_utf8(slice).unwrap();
                    v.push(str);
                    start = end.add(1);
                }
            }
            v
        };
    }

使用 ``get_app_data_by_name`` 可以按照应用的名字来查找获得应用的 ELF 数据，而 ``list_apps`` 在内核初始化时被调用，它可以打印出所有可用的应用的名字。

.. code-block:: rust

    // os/src/loader.rs

    pub fn get_app_data_by_name(name: &str) -> Option<&'static [u8]> {
        let num_app = get_num_app();
        (0..num_app)
            .find(|&i| APP_NAMES[i] == name)
            .map(|i| get_app_data(i))
    }

    pub fn list_apps() {
        println!("/**** APPS ****");
        for app in APP_NAMES.iter() {
            println!("{}", app);
        }
        println!("**************/")
    }


进程标识符和内核栈
------------------------------------------------------------------------

任务控制块
------------------------------------------------------------------------

任务管理器
------------------------------------------------------------------------

处理器监视器
------------------------------------------------------------------------