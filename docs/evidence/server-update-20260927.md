# 2026-09-27 8080 项目更新证据

对应 RELEASE-01、DATA-02、OPS-03；用户明确要求更新 39.96.83.196 的 8080 dongba 项目。实际切换于服务器北京时间 2026-09-27 09:36 执行，结果 complete。不是仅上传暂存包。

## 发布范围与指纹

- 应用路径 `/home/admin/dongba-trail`；Nginx 8080 提供 `web/dist`，代理 API 到 `127.0.0.1:8010`，保持原有 HTTP/HTTPS 配置。
- 发布本机未提交工作区的封包快照，不将其冒称为仅 Git 提交 `858e99d`。339 个源码/文档/测试/静态文件在服务器逐一校验 SHA-256，通过后才确认完成。
- 包：`runtime/deploy/release-20260927/release.tar.gz`；SHA-256 `ad9ec2b77d78462d7da4c163f5d0a93d831528475f1f2e85d41a67d7ee90e2d0`。
- 部署清单指纹：`f191d3f9a23c9fb91bafa6dbc524afc29cfd54ae751b0328f25ba1c589a53699`。算法为将相对路径到原始文件 SHA-256 的映射按键排序、紧凑 JSON 序列化后再次计算 SHA-256；完整清单为本机 `runtime/deploy/release-20260927/manifest.json` 和服务器发布目录 `release-manifest.json`。
- 首页 SHA-256：`bcc79fdb68dffa0340a77374d8a6df8eceb946c9f1fa6105cc92f99cfeb3d220`；本机构建、服务器静态文件、公网 IP:8080 和严格 HTTPS 域名入口一致。
- 保留服务器 `.env`（部署前后哈希一致）、业务数据库、媒体、运行时文件和已有 Web 哈希资源；没有上传本机环境凭据、私有小程序配置或数据集，也没有用本机 data 覆盖服务器数据。

## 备份与切换

- 回退资料：`/home/admin/dongba-releases/20260927-093615/`，目录仅服务器 root 可读。
- `previous-files/` 保存本次将覆盖的旧文件，`server.env.backup` 为受限备份；`database-media.zip` 为旧业务模型生成的 MySQL 一致性备份及媒体，17 表、1329 行、354 个媒体文件。未读取或输出凭据。
- 停止已确认路径的旧 API PID 2002481 后备份数据库与媒体，再复制文件，执行 `alembic upgrade head`，迁移从 `0003_data_foundation` 到 `0004_rag_support (head)`。
- 新 API PID 2003961，仍使用项目 `.venv/bin/python scripts/serve.py --port 8010`。`nginx -t` 和 reload 成功。
- 部署结果和命令日志：发布目录 `result.json`、`commands.log`；后台执行日志 `/tmp/dongba-release-20260927.log`。
- 首次尝试因依赖文件原始字节差异在修改线上前终止；改为仅规范换行后比较文本，实际依赖内容一致，第二次成功。并未忽略依赖内容变化。
- 回退方案是停止新 API、按清单恢复 previous-files 和旧静态入口、再启动旧 API；新增文件依据清单处理，不自动执行数据库 downgrade。脚本含失败回退，但本轮成功发布没有触发或演练完整回退，不能据此关闭 RELEASE-01 全部门槛。

## 本轮验证

| 命令/检查 | 结果 |
| --- | --- |
| `.venv\Scripts\python.exe -m pytest backend/tests -q` | 99 passed, 46 skipped；本轮未启用专用 MySQL 测试，不能冒称 145 项均执行。日志 `runtime/deploy/release-pytest.log` |
| `.venv\Scripts\python.exe -m ruff check backend scripts` | 通过 |
| `.venv\Scripts\python.exe -m ruff format --check backend scripts` | 61 文件通过 |
| `.venv\Scripts\python.exe scripts/check_project.py` | 35 项需求、证据、原文件、API 一致性通过 |
| `npm run build`、`npm test`、`npm run format:check`（web） | 构建、58 项测试、格式检查通过；首次沙箱阻止 esbuild 子进程，授权重跑通过 |
| 服务器 8080：`/`、`/login`、`/health`、字典、POI、地图配置 | 均 200 |
| SSH 内部直连 `http://127.0.0.1:8010/ready` | HTTP 200；`status=ready`、`provider_configured=true`、`published_characters=80`、`reasons=[]` |
| 服务器 OpenAPI | 106 路径，其中 9 个 RAG 管理路径 |
| 未登录 RAG 管理接口 | 401，未绕过鉴权 |
| 本机 curl 访问 `http://39.96.83.196:8080/` 和 `https://www.liorah.top/` | 均成功，首页哈希一致；HTTPS 未关闭证书校验 |
| 公网 `/health`、新 RAG JavaScript 文件 | 均成功，RAG 静态资源与构建内容哈希一致 |
| 公网 8080 `/ready` 路由 | 返回 SPA HTML，不是后端就绪 JSON；不能用它的 HTTP 200 证明就绪。以内部 8010 的真实检查为准，本轮未改动此既有 Nginx 路由 |

## 边界

- 本次发布 RAG 代码和业务库字段，不新建或猜测独立 RAG 数据库配置；服务器仅检查配置是否存在，结果 `RAG_DATABASE_CONFIGURED=False`，未读取或输出凭据。案例库未配置时仍按契约明确不可用，不阻断普通识别。未进行真实模型准确率、登录态 RAG 运营或微信真机验收。
- 小程序源码随封包上传不等于微信体验版/正式版发布；需要另行在微信开发者工具上传。
- 封包之后检测到本机 `miniprogram/app.json` 和 `pages/home/index.js`、`index.wxml`、`index.wxss` 有并行变更；保留这些本机改动，没有把封包后未验证变更混入服务器发布。后端与 Web 受测文件仍匹配部署清单。
- 既有业务、正式发布和长期稳定性缺口不因本次部署而被标记完成。
