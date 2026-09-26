# Web 静态文件重新部署与柱状趋势验收

日期：2026-09-26；对应 `DESIGN-01`、`RELEASE-01`；关联 `GEO-01`。仅更换 Web 静态目录，不修改数据库、后端配置或进程。

## 上传与可回退切换

- 运营地图/侧栏、近期活动卡片布局版：本地 `npm run typecheck`、`npm run format:check`、`npm run build` 和 5/5 离线浏览器检查通过，离线源码指纹 `sha256:44cd00b4995fb06bd7d06674c4f7a55656a4319fb0c48bea3e654391680dfb7f`。首次本地包 `runtime/web-dist-20260926-170122.tar.gz` SHA-256 `0fb9538059c2d6a6f2b68d9a38ca25db6bd0bca26cd2416b071f51a09d50fd14`。服务器校验包和解压后的首页，通过 `nginx -t`，将旧 `dist` 备份到 `/home/admin/dongba-trail/web/dist.backup-20260926-170122` 后切换；新首页 SHA-256 `27b2110daed067101c6649bc830206bc8966d248ad65097517f8033120d2836a`，公网同值。
- 用户追加“运营数据趋势改为最初方案，柱状图”。`web/src/views/DashboardView.vue` 恢复按日分组蓝/绿/红柱状展示（运营端三项、商户端两项），7/30/90 天切换保留；窄屏只在图表内部横向滚动。原有统计接口、点位 API 和“近期活动”布局不变。`npm run typecheck`、`npm run format:check`、`npm run build` 通过；离线 Chrome 浏览器 5/5 通过（含双角色桌面/手机、7/30/90 天柱数、运营空点位），报告和截图：`runtime/web-redesign/2026-09-26T09-13-49-458Z/`；受测源码指纹 `sha256:1d003fa005680196036d593480f3e75d286afc33467ba2f65c82ac8ef727ec9c`，DashboardView 文件指纹 `sha256:e1d5fa01ff24319eb48dfa32e5aab72937cce51fb3663a4cfdc54e0007f6a424`。
- 柱状图版 `runtime/web-dist-20260926-171608.tar.gz` SHA-256 `7924e45d28ed233684f678987535c94389887322659671d6dee63bbb506713a2`；服务器校验包/解压首页和新 JS/CSS、`nginx -t` 后，将上一版 `dist` 备份到 `/home/admin/dongba-trail/web/dist.backup-20260926-171608`，再切换为新 `dist`。本地、服务器、公网首页 SHA-256 均为 `75f634446ecb6f9439bd1ea002624dee58bf63fbd5211c51ca7b2834816b9529`。

## 公网核验与边界

- 严格 HTTPS 校验 `/`、`/login`、`/assets/DashboardView-D3u28jqt.css`、`/assets/DashboardView-C_6FjS2k.js`、`/api/v1/map/pois?limit=1`、`/health` 均 200；点位 API 返回总数 4。公网无业务登录态浏览器打开登录页返回 200，标题正常、无 JS 异常和横向溢出，截图见 `runtime/web-dist-20260926-171608-public-login.png`。
- 地图底图目前仍直接使用 `tile.openstreetmap.org`，**此次部署没有解决中国大陆底图加载失败及卡片布局诉求**。公网验收只证实点位接口可达，并未验证用户当地外部瓦片可用性、登录后的地图渲染或实地点位真实性。改用国内合规地图需确认供应商、使用许可及可用的 Web Key；不得把离线瓦片夹具 5/5 冒充真实底图验收。
