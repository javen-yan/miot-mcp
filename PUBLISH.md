# 发布到 PyPI 指南

本项目已经配置好了所有必要的文件，可以直接打包并发布到 PyPI。

## 📋 准备工作

### 1. 安装构建工具

```bash
pip install build twine
```

### 2. 注册 PyPI 账户

- 访问 [PyPI](https://pypi.org/) 注册账户
- 访问 [TestPyPI](https://test.pypi.org/) 注册测试账户（推荐先在测试环境发布）

### 3. 配置 API Token（推荐）

在 PyPI 账户设置中创建 API Token，然后配置：

```bash
# 创建 .pypirc 文件
cat > ~/.pypirc << EOF
[distutils]
index-servers =
    pypi
    testpypi

[pypi]
username = __token__
password = pypi-your-api-token-here

[testpypi]
repository = https://test.pypi.org/legacy/
username = __token__
password = pypi-your-test-api-token-here
EOF
```

## 🚀 发布流程

### 方法一：使用自动化脚本（推荐）

```bash
python publish.py
```

这个脚本会自动：
1. 清理之前的构建文件
2. 安装构建依赖
3. 构建包
4. 检查包的完整性
5. 询问是否上传到 PyPI

### 方法二：手动步骤

#### 1. 清理之前的构建

```bash
rm -rf build/ dist/ *.egg-info/
```

#### 2. 构建包

```bash
python -m build
```

#### 3. 检查包

```bash
twine check dist/*
```

#### 4. 先发布到测试环境（推荐）

```bash
twine upload --repository testpypi dist/*
```

#### 5. 测试安装

```bash
pip install --index-url https://test.pypi.org/simple/ miot-mcp
```

#### 6. 发布到正式 PyPI

```bash
twine upload dist/*
```

## 📦 包信息

- **包名**: `miot-mcp`
- **版本**: `1.0.1`
- **描述**: Mijia smart device MCP server
- **作者**: Javen Yan
- **许可证**: MIT

## 🔧 项目结构

项目包含以下关键文件：

- `setup.py` - 传统的安装配置文件
- `pyproject.toml` - 现代 Python 项目配置文件
- `MANIFEST.in` - 指定要包含的非 Python 文件
- `requirements.txt` - 项目依赖
- `README.md` - 项目说明文档

## 📋 发布检查清单

发布前请确认：

- [ ] 版本号已更新（在 `setup.py` 和 `pyproject.toml` 中）
- [ ] README.md 内容完整且准确
- [ ] 依赖列表正确
- [ ] 许可证文件存在
- [ ] 代码已测试
- [ ] 所有必要文件都在 MANIFEST.in 中列出

## 🎯 安装和使用

发布后，用户可以通过以下方式安装：

```bash
pip install miot-mcp
```

然后可以通过命令行启动：

```bash
miot-mcp
```

或在 Python 代码中使用：

```python
from mcp_server.mcp_server import main
main()
```

## 🔄 更新版本

当需要发布新版本时：

1. 更新 `setup.py` 中的版本号
2. 更新 `pyproject.toml` 中的版本号
3. 更新 `mcp_server/server_config.json` 中的版本号
4. 重新构建和发布

## 🐛 常见问题

### 包名冲突
如果包名已存在，需要选择不同的名称。

### 上传失败
- 检查网络连接
- 确认 API Token 正确
- 确认包名和版本号唯一

### 依赖问题
- 确保所有依赖都在 PyPI 上可用
- 检查版本兼容性

## 📚 参考资源

- [Python 打包用户指南](https://packaging.python.org/)
- [PyPI 官方文档](https://pypi.org/help/)
- [Twine 文档](https://twine.readthedocs.io/)