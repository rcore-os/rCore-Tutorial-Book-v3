# rCore-Tutorial-Book-v3

Documentation of rCore-Tutorial version 3 in Chinese.

## News

- 2022.07.01 Welcome to JOIN [**Open-Source-OS-Training-Camp-2022 !**](https://learningos.github.io/rust-based-os-comp2022/)

## [Deployed Page](https://rcore-os.cn/rCore-Tutorial-Book-v3/)

## Deploy your own docs

### 1. (可选) 配置并激活 Python 虚拟环境

使用 venv（Python 3 内置）：

```sh
python3 -m venv venv
source venv/bin/activate  # Linux/Mac
# 或
venv\Scripts\activate  # Windows
```

或使用 conda：

```sh
conda create -n rcore-book python=3.10
conda activate rcore-book
```

### 2. 安装 Sphinx

```sh
pip install -U sphinx
```

更多安装方式可参考 [Sphinx 官方文档](https://www.sphinx-doc.org/en/master/usage/installation.html)。

### 3. 安装依赖

```sh
pip install -r requirements.txt
```

如果使用国内镜像源（如 Tuna）：

```sh
pip install -r requirements.txt -i https://pypi.tuna.tsinghua.edu.cn/simple
```

### 4. 构建文档

```sh
make html
```

构建完成后，生成的文档位于 `build/html` 目录。

更多构建相关的详细信息可参考 [环境配置与构建](https://rcore-os.cn/rCore-Tutorial-Book-v3/setup-sphinx.html)。

---

**完整的流程示例：**

```sh
# Fork 并克隆仓库
git clone --recursive https://github.com/YOUR_USERNAME/rCore-Tutorial-Book-v3.git
cd rCore-Tutorial-Book-v3

# (可选) 创建并激活虚拟环境
python3 -m venv venv
source venv/bin/activate

# 安装 Sphinx
pip install -U sphinx

# 安装依赖
pip install -r requirements.txt

# 构建文档
make html

# 查看生成的文档
# build/html/index.html
```
