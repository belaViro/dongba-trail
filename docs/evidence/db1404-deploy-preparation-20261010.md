# DB1404 服务器部署准备与授权阻塞

日期：2026-10-10。依据：D-086；需求：AI-01 / AI-02 / AI-03 / GOV-01。

## 当前结论

用户要求继续完成部署。本轮只完成本机打包、复核及公网只读探测；
SSH 一次性密钥仍被拒绝，没有登录服务器、上传文件、安装依赖、切换配置或重启服务。
密钥失败不能证明用户提供的密码无效；本轮未使用或记录该密码。

## 已完成工作

- 将 `/.deploy-local/` 加入 `.gitignore`，避免临时部署私钥误入 Git。
  `git check-ignore` 确认私钥、公钥和部署归档均已忽略，
  `git ls-files -- .deploy-local` 为空；没有读取或输出私钥内容。
- 最小后端包：`runtime/deploy/d086-local-model-20261010T060130Z/db1404-local-backend.tar.gz`。
  共 1,440,262 字节、8 个普通文件；包含 5 个后端模块、CPU 依赖清单、模型及 manifest。
  不含 `.env`、凭据、数据库、用户照片、Web 构建或小程序包。
- 归档 SHA-256：`8f5139582edef06410615443624c92dc82d81b45605d83da2f3b7b6fdd8309f1`。
  打包后重新打开归档，逐项核对允许清单、普通文件类型、相对路径及文件摘要；全部通过。
  同目录另存 `manifest.json`、`archive.sha256`，本地生成包不代表服务器已部署。

## 代码与模型指纹

| 归档路径 | SHA-256 |
| --- | --- |
| `backend/app/config.py` | `342cc23d365b8f65f7d01b99c36ec96b95118aa6036f0a6b88cee30880aa7ce5` |
| `backend/app/provider_factory.py` | `7bc94f82ea4ceddb27564f810b078d5e40809ed9a2d3b674624650f5c1ac97cb` |
| `backend/app/system_config.py` | `2183734b5d46a1d915530af3f0b1d8989ec125e40b7e7b6425c43a8cb07f199b` |
| `backend/app/recognition.py` | `e94540c00575ce4a97048ace6263e494cba745421865853be259db02cd16fc47` |
| `backend/app/local_glyph_provider.py` | `ef403b7f2566a52b8e99c2a7e8e3b522572f007fd3f4d2a36d09e59c6de10e2d` |
| `backend/requirements-local-model.txt` | `688769bb69750bd0484ca28b0ba56595e520b86fddf598aacd3d2a28f00253ab` |
| `runtime/db1404-model/inference.pt` | `98e773677ce8df711991a92f41ba55177954cc0d2e36f25ab3a4eda29b5fef89` |

## 本轮验证

- 显式 OpenSSH 客户端，指定一次性身份、`IdentitiesOnly=yes`、`BatchMode=yes`、
  `PasswordAuthentication=no`、`ConnectTimeout=10`，远端仅拟执行 `printf key-auth-ok`。
  返回 `Permission denied (publickey,gssapi-keyex,gssapi-with-mic,password)`；远端命令未执行。
- 用项目虚拟环境 HTTPX 对 `https://www.liorah.top` 做无凭据 GET，不调用识别：
  `/health` 为 JSON 200 且 `status=ok`；`/api/v1/characters?limit=1` 为 200、`total=1403`；
  草稿 `DB1404_0979` 为 404；`/api/v1/admin/system-config` 为 401。
  这仅证明现有公开端点仍响应，不证明模型已切换，也没有把 SPA `/ready` 当 API 就绪证据。
- `.venv\Scripts\python.exe -m ruff check backend scripts`：通过。
- `.venv\Scripts\python.exe -m ruff format --check backend scripts`：89 个文件已格式化。
- `git diff --check`：通过，仅有工作树既有 LF/CRLF 提示。
- `.venv\Scripts\python.exe -m pytest backend/tests -q`：340 通过、97 跳过、1 条既有
  Starlette/AnyIO 弃用警告，93.68 秒；未将跳过的 MySQL/外部依赖检查算作通过。
- `.venv\Scripts\python.exe scripts/check_project.py`：35 项需求、证据链接及 API 检查通过；
  当前工作树缺少原始 DOCX，因此原文摘要比对跳过，不能记为本轮已复核原始文档。

## 恢复步骤与限制

1. 需要服务器管理员通过已有交互式 SSH 窗口输入密码，或通过云控制台安装本机一次性公钥。
   密码不进入工具参数、仓库或证据；授权失败期间不重复尝试密码、不降低服务鉴权。
2. 授权完成后先核对服务器资源、现有文件摘要和有效提供方配置；本地包须与当前源码重新核对。
   数据库运行时配置可能覆盖环境变量，不能只改 `.env` 就声称切换成功。
3. 备份、校验上传、CPU 依赖安装与加载探针通过后，才分阶段切换并验证真实 HTTP 识别与确认绑定。
4. Web 提供方下拉框构建、手动回滚演练和微信真机仍未完成服务器验收；当前包不包含 Web，
   不能称已有网页一键回滚或小程序已发布。AI-02、MySQL 集成和正式发布门槛不因此关闭。
