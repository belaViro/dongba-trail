# Web 静态文件重新部署与柱状趋势验收

日期：2026-09-26；对应 `DESIGN-01`、`RELEASE-01`；关联 `GEO-01`。仅更换 Web 静态目录，不修改数据库、后端配置或进程。

## 上传与可回退切换

- 运营地图/侧栏、近期活动卡片布局版：本地 `npm run typecheck`、`npm run format:check`、`npm run build` 和 5/5 离线浏览器检查通过，离线源码指纹 `sha256:44cd00b4995fb06bd7d06674c4f7a55656a4319fb0c48bea3e654391680dfb7f`。首次本地包 `runtime/web-dist-20260926-170122.tar.gz` SHA-256 `0fb9538059c2d6a6f2b68d9a38ca25db6bd0bca26cd2416b071f51a09d50fd14`。服务器校验包和解压后的首页，通过 `nginx -t`，将旧 `dist` 备份到 `/home/admin/dongba-trail/web/dist.backup-20260926-170122` 后切换；新首页 SHA-256 `27b2110daed067101c6649bc830206bc8966d248ad65097517f8033120d2836a`，公网同值。
- 用户追加“运营数据趋势改为最初方案，柱状图”。`web/src/views/DashboardView.vue` 恢复按日分组蓝/绿/红柱状展示（运营端三项、商户端两项），7/30/90 天切换保留；窄屏只在图表内部横向滚动。原有统计接口、点位 API 和“近期活动”布局不变。`npm run typecheck`、`npm run format:check`、`npm run build` 通过；离线 Chrome 浏览器 5/5 通过（含双角色桌面/手机、7/30/90 天柱数、运营空点位），报告和截图：`runtime/web-redesign/2026-09-26T09-13-49-458Z/`；受测源码指纹 `sha256:1d003fa005680196036d593480f3e75d286afc33467ba2f65c82ac8ef727ec9c`，DashboardView 文件指纹 `sha256:e1d5fa01ff24319eb48dfa32e5aab72937cce51fb3663a4cfdc54e0007f6a424`。
- 柱状图版 `runtime/web-dist-20260926-171608.tar.gz` SHA-256 `7924e45d28ed233684f678987535c94389887322659671d6dee63bbb506713a2`；服务器校验包/解压首页和新 JS/CSS、`nginx -t` 后，将上一版 `dist` 备份到 `/home/admin/dongba-trail/web/dist.backup-20260926-171608`，再切换为新 `dist`。本地、服务器、公网首页 SHA-256 均为 `75f634446ecb6f9439bd1ea002624dee58bf63fbd5211c51ca7b2834816b9529`。

## 公网核验与边界

- 严格 HTTPS 校验 `/`、`/login`、`/assets/DashboardView-D3u28jqt.css`、`/assets/DashboardView-C_6FjS2k.js`、`/api/v1/map/pois?limit=1`、`/health` 均 200；点位 API 返回总数 4。公网无业务登录态浏览器打开登录页返回 200，标题正常、无 JS 异常和横向溢出，截图见 `runtime/web-dist-20260926-171608-public-login.png`。
- 地图底图目前仍直接使用 `tile.openstreetmap.org`，**此次部署没有解决中国大陆底图加载失败及卡片布局诉求**。公网验收只证实点位接口可达，并未验证用户当地外部瓦片可用性、登录后的地图渲染或实地点位真实性。改用国内合规地图需确认供应商、使用许可及可用的 Web Key；不得把离线瓦片夹具 5/5 冒充真实底图验收。


## 2026-09-26 重新部署（当前版本）

用户再次提供服务器登录方式后，按“先校验、再备份、后切换”的流程重新上传当前提交 `858e99d`：

- 源码包 `runtime/deploy/dongba-trail-858e99d.tar.gz` SHA-256：`b4d7f16585d15872af515d0e4a2b034c6d073bcd307aab5a0b5acf9d3a885903`。
- Web 包 `runtime/deploy/web-dist-858e99d.tar.gz` SHA-256：`d3f62ec230a78b0e64fa381c463d2b928492f444febcf9b5063bf7aa230f0817`。
- 服务器旧项目完整备份（排除虚拟环境、Git、媒体、MySQL 和 DB1404 运行时大目录）：`/home/admin/dongba-trail.backup-20260926-204739.tar.gz`，SHA-256：`ded62b8db12c7bbd31afd3f8481dba438bbf2744fd0fc88465c98373833c0f23`。
- 旧 Web 静态目录备份：`/home/admin/dongba-trail/web/dist.backup-20260926-204739`。服务器 `.env`、`data/`、`runtime/` 和数据库未被压缩包覆盖。
- `alembic upgrade head` 后当前迁移为 `0003_data_foundation (head)`；API 使用项目虚拟环境重启为 `scripts/serve.py --port 8010`，公网 `/health` 返回 `{"status":"ok","version":"0.9.0"}`，`/ready` 返回 `status=ready`、80 个已发布字典词条。
- `nginx -t` 通过并 reload。公网首页 SHA-256 与服务器静态首页一致，均为 `3150814fc188c0411eaad43ac4ac3fba62ae69c2d67f240404aa61d375dffef1`；`/api/v1/public/map-config`、`/api/v1/map/pois?limit=2`、CSS 和丽江图片资源均通过严格 HTTPS 检查。
- 公网地图配置当前返回高德 Web Key、中心 `100.235, 26.875` 和缩放 `12`；Web Key 属于浏览器公开配置，后续应在高德控制台限制授权域名。地图 SDK/底图的真实管理员登录态验收仍需目标浏览器执行，POI 接口本身返回4个已发布点位。
- 服务器 `Settings().system_config_encryption_key` 检查结果为未配置。故系统配置页的非敏感项可修改，但保存模型 API Key 会按设计拒绝，需运维先设置持久的 `DONGBA_SYSTEM_CONFIG_ENCRYPTION_KEY`；本次没有读取或记录任何密钥值。

本次部署同时包含后端运行时系统配置代码和数据库迁移，不只是静态页面切换；若要回退，先恢复上述 Web `dist` 目录，再按备份内容恢复源码并重新启动 API，数据库回退须单独评估，不执行自动降级。
