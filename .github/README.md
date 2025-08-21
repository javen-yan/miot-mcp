# GitHub Actions 自动化工作流

本项目配置了两个 GitHub Actions 工作流来自动化测试和发布流程。

## 🔄 工作流说明

### 1. 测试和构建工作流 (`test.yml`)

**触发条件：**
- 推送到 `main` 或 `develop` 分支
- 向 `main` 分支提交 Pull Request

**功能：**
- 在多个 Python 版本（3.8-3.12）上测试
- 代码质量检查（flake8）
- 测试包构建过程
- 验证包安装和导入

### 2. PyPI 发布工作流 (`publish.yml`)

**触发条件：**
- 发布新的 GitHub Release

**功能：**
- 自动构建包
- 检查包质量
- 发布到 PyPI

## ⚙️ 配置步骤

### 1. 配置 PyPI API Token

1. 登录 [PyPI](https://pypi.org/)
2. 进入 Account Settings → API tokens
3. 创建新的 API token，选择 "Entire account" 或特定项目
4. 复制生成的 token

### 2. 在 GitHub 仓库中添加 Secret

1. 进入 GitHub 仓库页面
2. 点击 Settings → Secrets and variables → Actions
3. 点击 "New repository secret"
4. 名称：`PYPI_API_TOKEN`
5. 值：粘贴刚才复制的 PyPI API token
6. 点击 "Add secret"

### 3. 发布新版本

1. **更新版本号**：
   - 修改 `setup.py` 中的 `version`
   - 修改 `pyproject.toml` 中的 `version`
   - 修改 `mcp_server/server_config.json` 中的 `version`

2. **提交并推送更改**：
   ```bash
   git add .
   git commit -m "Bump version to x.x.x"
   git push origin main
   ```

3. **创建 GitHub Release**：
   - 进入 GitHub 仓库页面
   - 点击 "Releases" → "Create a new release"
   - 标签版本：`v1.0.0`（与代码中的版本号对应）
   - 发布标题：`Release v1.0.0`
   - 描述发布内容和更新日志
   - 点击 "Publish release"

4. **自动发布**：
   - GitHub Actions 会自动触发
   - 构建并发布到 PyPI
   - 可以在 Actions 页面查看进度

## 📋 版本管理最佳实践

### 语义化版本控制

遵循 [Semantic Versioning](https://semver.org/) 规范：

- `MAJOR.MINOR.PATCH` (例如：1.2.3)
- **MAJOR**：不兼容的 API 更改
- **MINOR**：向后兼容的功能添加
- **PATCH**：向后兼容的错误修复

### 发布前检查清单

- [ ] 所有测试通过
- [ ] 版本号已更新（3个文件）
- [ ] 更新日志已准备
- [ ] 文档已更新
- [ ] 代码已合并到 main 分支

## 🔍 监控和故障排除

### 查看工作流状态

1. 进入 GitHub 仓库页面
2. 点击 "Actions" 标签
3. 查看最近的工作流运行状态

### 常见问题

**发布失败：**
- 检查 PyPI API token 是否正确
- 确认包名和版本号唯一
- 查看 Actions 日志了解具体错误

**测试失败：**
- 检查代码语法错误
- 确认依赖项正确安装
- 查看特定 Python 版本的兼容性问题

## 🚀 手动发布备选方案

如果自动发布失败，可以使用本地发布脚本：

```bash
python publish.py
```

或手动执行：

```bash
python -m build
twine upload dist/*
```