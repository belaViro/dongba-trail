# 东巴寻迹 · 丽江

以东巴文字为入口的文旅应用：识别与候选确认、文化内容、商户推荐、优惠券核销、寻迹集章和分享海报。

已有 FastAPI 业务后端、MySQL 持久化、Vue 运营与商户工作台，以及原生微信小程序。重新核对原始文档后，确认 **业务尚未全部覆盖**：样本管理、字典字段与历史、推荐和统计等仍需补齐，详见[原文核对](docs/source-audit.md)。当前继续按用户确定的“全部业务流程跑通”标准推进；模型接口保留配置和适配器占位，由用户后续补充。真机与正式上线事项单独记录，不以新增性能、安全或稳定性专项延长本轮。

## 项目入口

- [业务使用指南](docs/user-guide.md) · [运行与运维](docs/operations.md) · [系统结构](docs/architecture.md)
- [需求基线](docs/requirements.md) · [验收记录](docs/acceptance.md) · [交付边界](docs/release.md)
- [当前状态](docs/status.md) · [决策记录](docs/decisions.md) · [迭代计划](docs/roadmap.md)
- [原文核对与缺口](docs/source-audit.md) · [历史集成验证与指纹](docs/evidence/integration-acceptance.md) · [浏览器验证与截图](docs/evidence/web-acceptance.md) · [小程序说明](miniprogram/README.md)

恢复开发前阅读 [AGENTS.md](AGENTS.md)、当前状态与决策记录，再检查代码和对应验收证据。

## 本地启动

环境：Python 3.11+、MySQL 8.0+、Node.js 22.12+ 和 npm；小程序使用微信开发者工具。以下命令在仓库根目录执行。已有 `.venv` 时跳过创建步骤。

```powershell
python -m venv .venv
.venv\Scripts\python.exe -m pip install -r backend/requirements-dev.lock.txt
$env:Path = 'C:\Program Files\MySQL\MySQL Server 8.0\bin;' + $env:Path
.venv\Scripts\python.exe scripts/mysql_local.py
.venv\Scripts\python.exe -m alembic -c backend/alembic.ini upgrade head
.venv\Scripts\python.exe scripts/serve.py --port 8010
```

MySQL 安装位置不同时调整 PATH。初始化脚本在项目 `runtime/mysql` 创建独立实例，默认端口3307，并将开发、自动测试和界面验收库连接写入被忽略的 `.env`，不输出密码。已有外部 MySQL 时直接配置 `DONGBA_DATABASE_URL` 并执行迁移，不运行本地初始化脚本。保留已有 `.env`；不要用模板覆盖已生成的连接配置。

另开一个终端启动工作台：

```powershell
Set-Location web
npm ci
npm run dev -- --host 127.0.0.1 --port 5318 --strictPort
```

- 工作台：[http://127.0.0.1:5318](http://127.0.0.1:5318)，首次本地访问可创建管理员。
- API文档：[http://127.0.0.1:8010/docs](http://127.0.0.1:8010/docs)。
- 运营和商户共享 `web/`，按登录角色进入 `/admin/` 或 `/merchant/`，无需分别构建两个工程。
- 端口已占用时选择其他空闲端口；改变后端端口时同步配置工作台的 `DONGBA_PROXY_TARGET` 和小程序 `apiBase`。

`/health` 检查服务存活。模型未配置或字典为空时 `/ready` 返回503属于识别未就绪，后台业务仍可使用。

## 小程序

微信开发者工具导入 `miniprogram/`，替换 `project.config.json` 的 AppID，并设置 `config.js` 中的 `apiBase`，默认 `http://127.0.0.1:8010/api/v1`。小程序不需要 npm 构建。

真实微信登录需要后端 AppID/AppSecret、已发布隐私信息和联系信息；真机使用可访问的测试 HTTPS 域名，不能使用电脑的127.0.0.1。完整步骤见 [小程序说明](miniprogram/README.md)。

已有小程序HTTP控制器测试使用临时SQLite及微信/模型/设备能力替身。MySQL由后端独立测试，
两类结果不能合并称为小程序真机或MySQL跨端验收，也不能证明原始文档全部业务已实现。

## 数据与模型

通过工作台维护和发布字典、字形、商户、优惠券及任务路线。应用不会预置虚构的已审核文化资料或门店；空列表表示尚未录入内容。普通业务字典来自 MySQL，修改旧的 `data/characters.json` 不会替代后台管理。

模型接入点为 [provider_factory.py](backend/app/provider_factory.py)。后续需要实现选定服务商的适配协议，再填写提供方配置；仅填写环境变量不会自动启用识别。未配置时明确显示不可用，测试结果不能当作真实东巴文字识别效果。

## 验证与维护

```powershell
.venv\Scripts\python.exe -m pytest backend/tests -q
.venv\Scripts\python.exe -m ruff check backend scripts
.venv\Scripts\python.exe -m ruff format --check backend scripts
.venv\Scripts\python.exe scripts/export_openapi.py
.venv\Scripts\python.exe scripts/check_project.py
node miniprogram/tests/validate-project.js
```

在 `web/` 执行 `npm test`、`npm run typecheck` 和 `npm run build`。启用真实 MySQL 自动测试的方法、离线管理员创建、备份恢复与保留期清理见 [运维说明](docs/operations.md)。

Docker Compose、API/Web 镜像和Nginx配置位于 `deploy/`。Compose配置检查已通过；当前未启动Docker部署，不将其标记为已经上线。`.env`、运行目录和凭据不进入Git。
