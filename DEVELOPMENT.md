# 制作指南

本仓库包含成品和制作代码。只下载作品无需运行以下步骤。重新构建会覆盖对应 PNG、PSD 及检查报告，修改前请自行备份。

## 瀚海星云徽标

需要 Windows PowerShell、Node.js/npm 和 Python 3.12；程序需在 PATH 中可用。项目已附参考图、字体和字体许可证。

在 `瀚海星云徽标` 目录中运行：

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File scripts/setup.ps1
python scripts/prepare.py
npm run build
npm run verify
python scripts/verify_independent.py
```

安装脚本将 Node 依赖放到 `node_modules`，Python 依赖放到 `.python-deps`；安装缓存和临时文件留在项目内部。Python 下载源使用清华 PyPI 镜像。`work` 由准备与构建步骤生成，成品输出到 `output`。

PSD 文字编辑所需字体位于 `assets/fonts`。可自行安装字体，或运行 `scripts/install-font.ps1` 为当前 Windows 用户安装，再使用 `scripts/verify-font.ps1` 检查。

图层和检查范围详见 [制作说明](瀚海星云徽标/制作说明.md)。未进行 Photoshop 桌面编辑验收。

## 科小牛科研助手

需要 Python 3.12。在 `科小牛科研助手` 目录中运行：

```powershell
python -m pip install --target .work/pythonlibs -r 制作工具/requirements.txt
python 制作工具/build_artwork.py
python 制作工具/verify_artwork.py
```

依赖及临时检查 PSD 放在 `.work`，不提交到仓库。生成素材已保存于 `制作素材`；上述命令执行拆分、组装与检查，不会重新调用图像生成服务。AI 工具使用情况及完整美术提示词分别保存在项目说明和素材目录中。

## 发布范围

保留当前 PNG、PSD、素材、自有代码、说明和依赖版本清单；不发布依赖副本、安装日志、缓存与旧成品。新增素材前应确认来源和公开传播权限；不要把包含本机路径、账号信息或密钥的环境文件加入仓库。权利说明见仓库首页。
