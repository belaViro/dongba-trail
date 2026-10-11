# DB1404 本地模型服务器部署（2026-10-10）

依据：D-086 / D-087；需求：AI-01、AI-02、AI-03、GOV-01。

## 结论与范围

用户补充确认 SSH 用户名为 `root` 后，成功登录 `39.96.83.196`，将已验证的最小后端包
部署到 `/home/admin/dongba-trail`。14:30 左右完成切换，实际提供方为 `db1404-local`，
模型版本 `db1404-cpu-v2-20261010`，API PID 从 2038367 变为 2041358。
没有上传 Web 构建或微信小程序版本，不代表 0.9.0 正式发布或 AI-02 整体验收。

- 服务器 2 核、内存 1870MiB，推理使用 2 线程；官方 CPU 索引安装 `torch==2.8.0+cpu`，
  `torch.version.cuda=None`，未安装 GPU 基础设施。
- 只更新归档中的 5 个后端模块、CPU 依赖清单和 Git 外模型；未修改 Nginx、媒体或字库。
- MySQL 仅持久修改 `settings.runtime_system_config` 的 `provider_name`，从
  `volcengine-ark` 改为 `db1404-local`。JSON_SET 保持 Ark 端点、模型及密钥等其他字段原样。
  `.env` 未改，环境默认仍为 Ark，但数据库覆盖已验证实际生效。
- 密码仅用于 SSH/SCP 交互认证，未写文件或 Git；没有读取或输出 `.env` 内容。
  发布目录权限 0700，服务器内配置备份权限 0600，不下载凭据。

## 上传与指纹

发布/备份目录：`/home/admin/dongba-releases/20261010-d086-local-model`。

归档 `db1404-local-backend.tar.gz`：1,440,262 字节，SHA-256
`8f5139582edef06410615443624c92dc82d81b45605d83da2f3b7b6fdd8309f1`。
本地当前代码、包内代码及服务器落盘文件逐项匹配；8 个普通条目（7 个载荷+manifest），
无绝对路径、越界、符号链接、配置或数据库。逐文件摘要见[准备证据](db1404-deploy-preparation-20261010.md)。

- 模型 SHA-256：`98e773677ce8df711991a92f41ba55177954cc0d2e36f25ab3a4eda29b5fef89`。
- `.env` 部署前后 SHA-256：`56e1a32686a893333310c52204fa69fa67ed92a1828be414fad96bd8a3529ba0`。
- 一次性部署脚本 `server_deploy.py` SHA-256：
  `ee4fa979a6b85cb92dc5668ef82d67827b0946be4a757959bbc26f8168a8f50c`。
  本地副本在忽略目录 `runtime/deploy/d086-local-model-20261010T060130Z/`，服务器发布目录同名。
- 另核对服务器未改动的 main/dictionary/providers/schemas 和 business/api/auth/database/models
  共 8 个相关模块，其 SHA-256 与本地回归代码一致。

## 执行顺序与验证

1. SSH 只读检查：旧 API `/health`、`/ready` 正常，1403 条发布字；迁移
   `0004_rag_support (head)`；磁盘可用约 18GB；单一 8010 监听进程。
2. SCP 上传，服务继续运行；安装前保存依赖列表及环境文件服务器内备份。
   `pip install 'torch==2.8.0+cpu' --index-url https://download.pytorch.org/whl/cpu` 成功，
   `pip check` 为 `No broken requirements found`。期间 SSH 连接重置，重连核对安装和旧 API
   正常后才继续，没有因断线重复切换。Torch 提示缺可选 NumPy，但本适配器不使用 NumPy，
   实际加载/前向/HTTP 均通过，未为消除警告扩大依赖范围。
3. `.venv/bin/python <发布目录>/server_deploy.py prepare`：校验包、备份旧文件，
   从暂存目录加载受信模型并读取真实 MySQL 发布集合；1403 条、Top-5 正常，
   只传入一个允许 ID 时只返回该 ID。生产代码及提供方尚未修改。
4. `nohup .venv/bin/python <发布目录>/server_deploy.py cutover`：优雅停止指定旧 PID，
   同目录临时文件替换、事务更新提供方，沿用 `scripts/serve.py --port 8010` 启动；
   就绪后执行独立子进程真实 HTTP 验证，任何切换/验证异常会恢复备份与旧提供方。
   本次成功，未触发回滚。无 systemd 服务迁移，不宣称新增开机自启能力。
5. 真实 HTTP+MySQL 冒烟执行两遍，非 fixture：
   - 上传既有 305×230 裁剪探针，首选 `DB1404_0018`（电），后续 0188/0919/0333/0509；
     未校准分数 0.9463765621，返回 `NEED_USER_CONFIRM`，不自动确认。
   - 实际 provider/model 字段正确；响应头与响应体 request_id 一致；MySQL 记录绑定请求用户。
   - 非请求用户确认 404，非原候选 422，合法确认 200 并核对数据库；
     “都不是”提交 200，确认字段清空。
   - 32×32 图片为 400 `IMAGE_TOO_SMALL`，无效图片为 400 `INVALID_IMAGE`；
     草稿 979 为 404，未鉴权管理配置为 401。
   - 使用两个专用临时游客身份和内存中 15 分钟会话；不读取真实用户登录信息。
     每遍结束限定这些临时 ID 删除反馈、识别、会话和用户并复核，未污染运营账号或历史。
     未开启样本保留，没有创建寻迹/优惠券数据。
   - 首次含模型加载的服务端 recognition latency 为 1292ms，热运行复测 8ms；
     这是两次单样本内部计时，不是端到端 SLA 或统计性能指标。
6. 服务器侧通过公网域名 `https://www.liorah.top` 和 IP 8080 检查：
   health JSON 200、字库 JSON 200/total=1403、草稿404、管理端401。
   公网 `/ready` 仍为既有 SPA HTML，不能当 API 就绪证据；本机 8010 `/ready` 才是 JSON ready。
   Windows 受限工具中的无提升公网探针出现 ConnectError，不记为该客户端验证成功。
7. 迁移 head 未变，`nginx -t`通过，环境/模型摘要匹配；API RSS 约292MiB，
   服务器 available 约765MiB（单次快照）。

## 回滚与限制

旧文件在 `<发布目录>/backup/`，旧提供方及各文件摘要在 `state.json`；逐一复核备份摘要通过。
事务内将 provider 改回 Ark、读回确认后 ROLLBACK，通过且未提交旧提供方、未调用付费 Ark。
这只是配置事务干跑，不是完整停服/文件恢复演练。

紧急完整回滚命令（服务器根目录，先确认没有后续新发布）：

```sh
cd /home/admin/dongba-trail
.venv/bin/python /home/admin/dongba-releases/20261010-d086-local-model/server_deploy.py rollback
```

Ark 配置保留，不自动双调用。Web 下拉框本轮未上传，不能声称网页回滚入口已更新。
单张既有照片不能代表实拍准确率；无可靠未知字拒识、手机真机与跨客户端整体验收仍未完成。

## 本机检查

- 当前源文件/归档摘要复核：通过。
- `.venv\Scripts\python.exe -m pytest backend/tests -q`：340 passed，97 skipped，
  1 条既有 AnyIO 弃用警告，91.34秒；跳过不算 MySQL 验收。
- `python -m ruff check backend scripts`：通过。
- `python -m ruff format --check backend scripts`：89 files already formatted。
- `python scripts/check_project.py`：35 项需求、证据链接及 API 检查通过；
  工作树无原始 DOCX，原文摘要比较跳过。
- 14:35更新状态/决策/验收/发布边界后再次运行项目检查通过；`git diff --check`通过，
  仅有既有LF/CRLF提示。用户已有修改保留，本轮没有提交Git。
- 一次性 runtime 脚本语法编译与真实执行通过；额外 Ruff 检查提示31项导入/长行/zip strict
  风格项，不属于 backend/scripts 全库 Ruff 通过范围；为保留实际执行指纹未事后改写脚本。
- 本次没有改后端源码或 HTTP 契约，无需再生成 OpenAPI；不把本机夹具回归算作识别率。
