# 对于一些概念等，要有一些比较具体的对应
# 对于如何一步一步实现，需要有阶段性的实验结果

## ch0
### 2os-interface
- 缺少对明确rcore-tutorial 系统调用的概述

### 3os-hw-abstract.html
- 各种抽象能否有些具体的代码对应？

### 4os-features
- 特征能用代码运行来展现吗？

### 5setup-devel-env
- 想把k210相关的挪到附录中

最后有个Q&A比较好


## ch1

三叶虫需要的海洋（硬件）和食物（rustsbi），通过请求sbi call 获得输出能力

- 介绍应用，以及围绕应用的环境

- 解释 sbi 新的参数约定

## ch2
- 引言 对应用程序的进一步讲解
- 特权级在这一章不是必须的

## ch3-ch9
- 引言 对应用程序的进一步讲解

## ch4
- 页面置换算法的实践体现

## ch5 
- 调度算法的实践体现

## ch6
-  从应用角度出发，基于ram来讲解，并逐步扩展，比较方便

## ch7
- 需要循序渐进

## ch8
- 银行家算法的实现
- 死锁检测算法的实现

## ch9 
- 内核允许中断
- 轮询，中断，DMA方式的实际展示
- 各种驱动的比较详细的分析

## convert
make epub //build epub book
calibre // convert epub to docx
