RISC-V 特权级架构
=====================================

.. toctree::
   :hidden:
   :maxdepth: 5

特权级可以看成 RISC-V 架构 CPU 的工作模式，CPU 会在多个不同的特权级间来回切换。RISC-V 架构中一共定义了 4 种特权级：

.. list-table:: RISC-V 特权级
   :widths: 30 30 60
   :header-rows: 1
   :align: center

   * - 级别
     - 编码
     - 名称
   * - 0
     - 00
     - 机器模式 (M, Machine)
   * - 1
     - 01
     - 监督模式 (S, Supervisor)
   * - 2
     - 10
     - H, Hypervisor
   * - 3
     - 11
     - 用户/应用模式 (U, User/Application)

其中，级别的数值越小，特权级越高，掌控硬件的能力越强。从表中可以看出，M 模式处在最高的特权级。随着特权级的降低

RISC-V 架构规范分为两部分： `RISC-V 无特权级规范 <https://github.com/riscv/riscv-isa-manual/releases/download/Ratified-IMAFDQC/riscv-spec-20191213.pdf>`_ 
和 `RISC-V 特权级规范 <https://github.com/riscv/riscv-isa-manual/releases/download/Ratified-IMFDQC-and-Priv-v1.11/riscv-privileged-20190608.pdf>`_ 。
RISC-V 无特权级规范中给出的指令和寄存器无论在 CPU 处于哪个特权级下都可以使用。
