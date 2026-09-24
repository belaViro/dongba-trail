# 运行与运维

本轮按D-015交付业务可运行版本。本地环境采用MySQL；Docker方案已提供配置，但未在本轮启动容器部署。性能、容量和正式环境稳定性验证不作为本轮结束条件。

## 本地服务

按照 [README](../README.md) 安装项目虚拟环境和Web依赖。将MySQL 8.0+的bin目录加入当前终端PATH，然后执行：

```powershell
.venv\Scripts\python.exe scripts/mysql_local.py
.venv\Scripts\python.exe -m alembic -c backend/alembic.ini upgrade head
.venv\Scripts\python.exe scripts/serve.py --port 8010
```

`mysql_local.py` 在 `runtime/mysql` 维护独立实例，默认监听127.0.0.1:3307；开发库为 `dongba`，自动测试库为 `dongba_test`，界面验收库为 `dongba_ui`。已有实例会核对数据目录后复用，连接配置写入 `.env`，不输出凭据。如果需要其他端口，首次初始化使用 `--port`；已有状态文件会保留原端口。

工作台在另一终端运行：

```powershell
Set-Location web
npm ci
npm run dev -- --host 127.0.0.1 --port 5318 --strictPort
```

默认代理后端8010。选择其他后端端口时，在启动Web前设置 `DONGBA_PROXY_TARGET`，例如 `http://127.0.0.1:8012`，并同步修改小程序 `apiBase`。`serve.py --database ui --port 8012` 专门使用隔离的界面验收库，不作为普通业务入口。

## 初始化与迁移

首次本地打开工作台可以创建管理员；也可使用离线初始化：

```powershell
.venv\Scripts\python.exe scripts/bootstrap_admin.py --username admin --display-name Administrator
```

脚本交互输入至少12位密码，只允许创建首位管理员，已有管理员时保持原账户。自动化场景可通过进程环境变量 `DONGBA_BOOTSTRAP_PASSWORD` 输入密码；不要把实际密码写入命令示例或提交到仓库。

数据库修改通过Alembic管理：

```powershell
.venv\Scripts\python.exe -m alembic -c backend/alembic.ini current
.venv\Scripts\python.exe -m alembic -c backend/alembic.ini upgrade head
.venv\Scripts\python.exe -m alembic -c backend/alembic.ini check
```

当前迁移包含初始业务结构和现有MySQL表的存储/排序规则更新。正式环境设置 `DONGBA_AUTO_CREATE_SCHEMA=false`，使用迁移建立表结构。不要将 `downgrade base` 当作日常回滚，它会移除业务表；版本回退应结合兼容的应用版本和备份恢复进行。

## 备份与恢复

备份脚本读取 `.env` 中配置的MySQL和媒体目录，生成包含业务表、迁移版本、媒体文件与校验信息的ZIP，不覆盖同名文件：

```powershell
.venv\Scripts\python.exe scripts/backup.py backup runtime/backups/dongba-20260923.zip
```

本地已用真实MySQL演练备份、空库恢复和逐行/媒体一致性；对应自动测试为 `backend/tests/test_operations.py`。这是本地恢复证据，不表示Docker或正式服务器已经部署。

恢复使用专门准备的空数据库和空媒体目录：

1. 将运行环境的 `DONGBA_DATABASE_URL` 和 `DONGBA_MEDIA_DIRECTORY` 指向恢复目标。
2. 将目标数据库迁移到备份记录的同一revision，保留迁移建立的初始setup记录即可。
3. 执行恢复，再启动服务核对账号、字典、门店、券记录和图片。

```powershell
.venv\Scripts\python.exe scripts/backup.py restore runtime/backups/dongba-20260923.zip
```

目标已有业务记录、媒体目录非空、迁移版本不同或校验失败时，脚本会拒绝恢复。备份不包含 `.env` 和服务器证书；目标环境配置由部署人员单独维护。备份时先暂停内容上传，便于数据库与媒体保持同一业务时点。

## 保留期清理

`DONGBA_RETENTION_DAYS` 默认30天。后端运行期间每小时执行一次清理：过期识别元数据及关联反馈、过期访问事件、失效会话、旧登录尝试，以及超过保留期且未被内容引用的生成媒体。

可先预览数量，再手动执行：

```powershell
.venv\Scripts\python.exe scripts/maintenance.py
.venv\Scripts\python.exe scripts/maintenance.py --apply
```

游客也可在小程序中主动清空本人识别历史；该操作删除对应识别记录和反馈。当前识别原图只在请求中处理，不落盘保存。

## 外部能力配置

| 能力 | 配置或工作 |
| --- | --- |
| 模型识别 | 在 `backend/app/provider_factory.py` 实现服务商适配，再配置提供方名称、地址、密钥、模型与超时；目前保留占位 |
| 微信登录 | 后端AppID/AppSecret；与小程序AppID对应 |
| 隐私信息 | 核对 `/api/v1/privacy` 内容，填写联系信息与版本，再设置发布状态 |
| 地图和真机 | 真实GCJ-02点位、微信平台权限与合法域名配置；手机使用可访问的HTTPS服务 |
| 分享码 | 微信账号与小程序路径配置；缺失时海报返回明确状态，不绘制假的小程序码 |
| 文化与商户内容 | 通过工作台录入有来源的真实字形、文化内容、门店、POI和路线，审核后发布 |

`/health` 用于服务存活检查。`/ready` 反映识别依赖是否就绪；模型占位或空字典导致503时，先核对对应配置和内容，不能据此认定所有后台业务异常。

## Docker方案

`deploy/compose.yml` 定义MySQL 8.4、API和Web/Nginx；API启动脚本会执行迁移，数据库和媒体使用持久卷。按 `deploy/.env.example` 准备部署环境，证书放在 `deploy/certs/tls.crt` 与 `tls.key`。

```powershell
docker compose --env-file deploy/.env -f deploy/compose.yml config --quiet
```

当前仅完成Compose配置校验，没有启动Docker引擎上的实际部署。后续环境准备完成后再执行构建启动、首次管理员初始化和业务回归；本轮不宣称已验证公网服务、容器备份或正式可用性。

## 自动验证

常规命令见README。需要重跑真实MySQL测试时，仅使用本地初始化脚本配置的隔离测试库：

```powershell
$env:DONGBA_RUN_MYSQL_TESTS='1'
.venv\Scripts\python.exe -m pytest backend/tests -q
```

测试会重建 `dongba_test` 的测试表，不要将其用于业务数据。界面验收使用独立 `dongba_ui`。每次提交以 `docs/evidence/` 中的结果和代码指纹为依据。
