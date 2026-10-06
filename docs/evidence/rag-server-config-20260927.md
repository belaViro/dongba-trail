# 2026-09-27 公网 RAG 独立库配置修复

对应 OPS-03、AI-03、FEEDBACK-01、RELEASE-01、D-044。用户报告请求编号 `aa28c728-d93c-45c5-bbd4-9a0f993ffc4c` 的 RAG 数据库不可用错误。本轮只修复服务器配置与建库，不修改应用业务代码，不导入夹具案例。

## 原因与修复

- 只输出配置存在性和非敏感状态的 SSH 检查确认：`DONGBA_RAG_DATABASE_URL` 未设置、`dongba_rag` 库不存在；业务库 `dongba` 在原 MySQL 8.0.46 / 127.0.0.1:3307 正常运行。未将用户请求编号对应的日志作为额外已验证证据。
- 北京时间 2026-09-27 09:49，在同一 MySQL 实例建立独立 `dongba_rag` schema，并按已部署模型创建 `rag_cases` 表。新专用账号只授权该库，不复用业务账号或授予全局权限；随机连接密码仅在服务器内存和受限配置中使用，没有显示、写入仓库或传到本机。
- 修改前备份服务器环境，目录 `/home/admin/dongba-releases/rag-20260927-094903/`，备份 `server.env.backup` 权限 0600；只补充 RAG 连接键，逐项验证其余环境设置保持不变。
- 重启内部 8010 API，PID 从 2003961 变为 2004157，保留 Nginx 8080 与 HTTPS 入口。没有修改原业务数据、媒体、账号密码或前端构建。
- 完成结果保存于备份目录 `result.json` 和 `/tmp/dongba-rag-repair-result.json`。回退逻辑可恢复原环境并启动旧配置，不自动删除新独立库；本轮未触发回退。

## 验证结果

| 检查 | 结果 |
| --- | --- |
| MySQL 独立库和 ORM 表查询 | 成功；初始案例数 0 |
| 8080 与严格 HTTPS：已鉴权 `GET /api/v1/admin/rag/cases?limit=1` | 两个入口均 HTTP 200 |
| 8080 与严格 HTTPS：已鉴权 `GET /api/v1/admin/rag/stats` | 两个入口均 HTTP 200 |
| 8080 与严格 HTTPS：已鉴权 `POST /api/v1/admin/rag/search` | 两个入口均 HTTP 200；只查询空库，没有创建案例 |
| HTTPS 未鉴权案例列表 | HTTP 401，鉴权要求未放开 |
| 内部 8010 `/ready` | HTTP 200，`status=ready`、`provider_configured=true`、已发布词条 80、原因列表为空 |
| 运维验证会话 | 使用现有活跃管理员关联的随机五分钟临时会话进行服务器侧 HTTP 检查，验证后删除；不改管理员密码，不输出令牌，不代表真实浏览器登录验收 |
| `.venv\Scripts\python.exe -m py_compile runtime/deploy/repair_rag_20260927.py` | 通过 |

## 指纹与边界

- 应用沿用前次 339 文件部署快照，部署清单指纹 `f191d3f9a23c9fb91bafa6dbc524afc29cfd54ae751b0328f25ba1c589a53699`，详见 [部署证据](server-update-20260927.md)。本轮不修改或重新部署应用源码，不宣称重新运行全部后端/Web 单测。
- 专项运维脚本 `runtime/deploy/repair_rag_20260927.py` 的 SHA-256 为 `ec03082a87a2c4dea28ec491663262601c921268792b3bd437b9151443676119`；脚本所在 runtime 被 Git 忽略，包含操作逻辑但不含实际凭据。
- 本轮确认原数据库不可用状态已修复；零案例是正确初始状态，不伪造纠错知识。仍需运营录入有来源的案例并审核；公网新增/编辑/审核写入闭环、真实识别准确率、微信跨端和完整回退未在本轮验收，不因此关闭整个 OPS-03 或正式发布门槛。
