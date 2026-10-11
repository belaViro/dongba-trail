# GitHub同步检查（2026-10-11 / D-091）

## 范围

- 用户要求：上传到GitHub。目标为既有`origin`的`belaViro/dongba-trail`、`main`分支。
- 起始HEAD：`ce2daa4`；`git fetch origin main`成功后，`git rev-list --left-right --count HEAD...origin/main`为`0 0`。
- 提交现有后端/Web/小程序改动、DB1404字库清单、训练源码/配置及证据；不恢复用户删除的首页相册快捷按钮。
- 新增忽略`东巴字图片_按中文含义命名/`，该目录含51张JPEG及约19.7MB的派生Excel，均保留在本地。
- 既有忽略继续排除`.env`、数据集原图/划分/检查点、模型权重、运行目录、部署备份、依赖及构建产物；仅`.env.example`随源码版本化。
- 不部署服务器、不发布微信、不执行训练或付费识别，不把GitHub同步当正式发布。

## 本轮验证

| 命令/检查 | 结果 |
| --- | --- |
| `.venv\Scripts\python.exe -m pytest backend/tests -q` | 351 passed、101 skipped、1条既有Starlette弃用警告，104.65秒；跳过项不算通过 |
| `.venv\Scripts\python.exe -m ruff check backend scripts` | All checks passed |
| `.venv\Scripts\python.exe -m ruff format --check backend scripts` | 90 files already formatted |
| `.venv\Scripts\python.exe scripts/check_project.py` | 35项需求、证据链接及API检查通过；原DOCX不在本检出中，源摘要比较跳过 |
| `npm --prefix web test` | 10个测试文件、170项通过 |
| `npm --prefix web run build` | vue-tsc及Vite生产构建通过 |
| `npm --prefix web run format:check` | 通过 |
| `node --test miniprogram/tests/*.test.js` | 174项中173通过、1失败，退出码1 |
| 凭据模式/大文件预检 | 候选文件未发现私钥、GitHub/API/AWS令牌模式或大于50MiB文件；唯一带密码URL模式命中为`.env.example`第3行，经不回显值检查确认是占位符且与起始HEAD相同 |

Node/Vitest首次受沙箱子进程限制报`spawn EPERM`，获批在沙箱外重跑后得到上述真实测试结果。
小程序失败用例：`detail, quick navigation, merchant navigation and camera retain working routes`，
`miniprogram/tests/home.test.js`仍断言首页有`album-shortcut`按钮，而工作区`pages/home/index.wxml`已删除它。
本轮不擅自恢复用户改动，也不放宽测试；MINI-01该项仍待后续明确处理。完整本地日志位于忽略目录
`runtime/github-sync-20261011-miniapp.log`。此次没有运行MySQL集成、训练源码专项或微信真机测试，
未验证实拍准确率、跨端全旅程或正式发布门槛。

本轮未改应用接口，无须重新生成既有OpenAPI；项目检查确认当前应用与契约无漂移。
本次凭据检查为有限模式扫描，不宣称完成全面安全审计；未读取本地真实环境凭据文件。

## 代码指纹

源码集合取`git ls-files --cached --others --exclude-standard -z`去重并按路径排序，
包含`backend/`、`scripts/`、`web/`、`miniprogram/`、`data/`、`数据集/`内可提交文件，
以及`.env.example`、`.gitignore`、`pyproject.toml`。每项编码为UTF-8
`路径 + NUL + 文件原始字节SHA256 + LF`，再对串联结果计算SHA256。
排除文档以避免证据自引用；本轮未修改上述应用源码。

- 文件数：343。
- SHA-256：`79f89e2e43ae459db3ad0115f70ccfe6cf2a9421e8794c0156821716dc979731`。
- 指纹基于本地原始字节；Git按既有换行配置归一化时对象摘要可能不同。
- 本文随同步提交保存；最终提交ID与远端推送结果在操作回执核对，不预先宣称已推送。
