# AI旅行海报重新部署（2026-09-29）

关联：SHARE-01、OPS-03、DESIGN-01、RELEASE-01；D-058。

## 授权与范围

- 用户提供服务器登录信息并要求“重新传一下”；将已验证的AI海报后端、管理员系统配置页面和对应客户端源码上传至 `39.96.83.196` 的现有项目，不重建环境。
- 准备工作始于9月28日晚；实际服务器部署时间为 **2026-09-29 00:19（北京时间）**。运行资料沿用 `runtime/deploy/ai-poster-20260928/` 目录名，不把它当作实际发布日期。
- SSH密码仅经隐藏输入进入内存，校验已知主机密钥；不保存到项目、环境文件、脚本、发布包或Git，不打印凭据。未读取并显示原环境文件中的凭据。
- 部署前比较全部后端应用/Web源码，服务器仅缺8个预期功能文件；其他依赖源码逐项哈希相同，Python依赖内容相同。保留前序未提交改动，不将无关内容混入发布包。
- 不运行运营数据种子，不同步D-056的新增路线/店铺；不变更Nginx配置、不升级依赖、不执行数据库迁移，不调用付费生图接口。

## 发布、备份与校验

- 应用目录：`/home/admin/dongba-trail`；发布/回退目录：`/home/admin/dongba-releases/20260929-001906-ai-poster`。
- 停止旧API后备份：`database-media.zip`，17张表、2307行、354个媒体文件；`previous-files/` 保存被覆盖文件，`server.env.backup` 保存原环境文件，均在服务器受限发布目录内，不下载到本地。
- 发布包SHA-256：`67b4bacd729c136a1bdbc7c9f99d560de4aa3d599386e037052e6f59a1cdbbe2`。
- 49个交付文件逐项哈希通过，39个文件新增/变更；先同步带哈希静态资源，最后替换HTML入口，保留旧资源。
- 公网HTML SHA-256：`cfc1b8c7a54059028368e8c6f5d77a18d618c29a2df7569a370a637f5ab3fcba`；HTTP/HTTPS入口均与本地构建一致。
- 交付清单指纹：`802f270d49fb3c124b3b4fd9f25ddb486d409abd0f00dbb1dc30498dc8d2db32`；算法为对按路径排序的 `files` 哈希映射进行紧凑JSON序列化再计算SHA-256，清单见运行目录的 `manifest.json`。
- 原API PID 2004689，更新后PID 2014750；内部 `/health`、`/ready` 均200，后者为 `ready`、80个已发布字典词条、无原因项。OpenAPI共110条路径，已含异步海报任务及管理员生图模型读取接口。
- 数据库版本前后均为 `0004_rag_support (head)`；原环境内容逐字节保留，Nginx配置未改变，原识别有效密钥保持一致。

## 系统配置

- 检测到服务器未提供 `DONGBA_SYSTEM_CONFIG_ENCRYPTION_KEY`、数据库也没有依赖旧主密钥的加密配置后，仅在服务器生成持久Fernet主密钥并追加到 `.env`，文件权限0600；密钥不返回客户端或本地日志。
- 只读配置检查：`key_editable=true`，原识别密钥已配置；独立生图字段完整，默认1024×1536、180秒、质量auto。
- 生图仍为 `unconfigured`、`image_provider_api_key_configured=false`。用户先前的临时测试密钥**没有**保存到服务器，正式使用需管理员在“AI与系统 / 系统配置”填写正式端点、模型和API Key。此未配置状态按设计明确不可用，不伪装成可生图。

## 验证命令与结果

| 命令/步骤 | 结果 |
| --- | --- |
| `.venv\Scripts\python.exe -X utf8 runtime/deploy/poster_prepare.py` | 18个功能代码/测试文件与此前已测试指纹一致；依赖及预期服务器差异核对通过，49文件打包，密钥格式扫描通过 |
| `npm --prefix web run build` | 通过，9.27秒；首轮受限环境EPERM，授权重试成功；入口 `index-CXctzswy.js` |
| 服务器 `.venv/bin/python <临时发布目录>/apply.py <发布包> <SHA-256>` | `state=complete`；备份、哈希、环境保护、进程重启、内部就绪及新OpenAPI路由检查通过 |
| 服务器 `.venv/bin/python <临时发布目录>/config-verify.py` | 管理员生图字段、主密钥可用状态、原识别配置及就绪状态通过；仅输出非敏感字段/布尔值，无付费请求 |
| `.venv\Scripts\python.exe -X utf8 runtime/deploy/poster_public_verify.py` | 通过；HTTP `39.96.83.196:8080` 与严格TLS `https://www.liorah.top` 各校验首页及6个入口/生图配置资源，共14项静态哈希、10项接口状态；`/health` 和字符接口200，管理员配置/生图模型/海报任务未授权均401 |
| `.venv\Scripts\python.exe scripts/check_project.py` | 部署前及交付文档更新后均通过：35条需求、证据链接、原文和API一致性 |
| `git diff --check -- docs/status.md docs/decisions.md docs/acceptance.md docs/evidence/ai-poster-20260928.md docs/evidence/ai-poster-deploy-20260929.md` | 通过；仅Git自动换行提示，无空白错误 |

上次完整测试对应代码未变：302项后端（包含MySQL，1项跳过）、148项Web、150项小程序及原生编译等见[实现证据](ai-poster-20260928.md)。本次不是重新执行该全量测试，不以源码复制冒称真机验收。

## 交付边界

- 服务器文件已更新不等于微信体验版已上传；微信开发者工具重新上传、真机保存/分享、真实审核字形合成及完整付费生成旅程仍待验证。
- 不持久化临时生图凭据；正式凭据尚未配置，不宣称生图业务已经可直接使用。
- 不恢复用户已取消的其他补充任务；D-056运营数据公开同步不属于本次发布范围。
- 已生成回退所需文件，但本次成功发布未执行故障回退演练，也未验证主机重启持久化；RELEASE-01及相关需求继续为实现中，不宣称生产就绪。
- 脱敏运行记录：`server-result.json`、`config-verification.json`、`public-verification.json`、`manifest.json`、`build.log`，位于忽略的运行目录。服务器受限目录中的原环境备份及业务数据库备份不纳入Git。
