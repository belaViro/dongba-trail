# 国内地图与运营/商户首页本地验收（GEO-01、DESIGN-01）

日期：2026-09-26；受测源码指纹：sha256:2acf3ed30e68f575fa7fceece087e7d4ab9ad84847e62d549b5413c91d5a8c5b（浏览器脚本对 web/src、web/public、Web package.json、脚本及 OpenAPI 计算，前后相等；不包含忽略的临时 Key 或 dist）。

## 代码及效果

- 运营概览从 OpenStreetMap/Leaflet 改用高德官方 JS API 2.0；前端 Web Key 存于 Git 忽略的 web/.env.local，参与本地构建，**并非服务器端保密存储**。未收到单独的安全密钥，因此不将安全密钥放入前端。已删除不再引用的 Leaflet 依赖。失败时显示不可用，不使用未授权瓦片。
- 继续从后端 /map/pois 拉取已发布 POI（分页）并以 GCJ-02 坐标叠加，不转到 WGS-84；弹窗文字使用安全的 textContent，演示点位单独标记。
- 地图容器由固定 290px 改为 flex 自适应卡片余高（桌面不低于 340px、手机不低于 290px），底边贴合卡片；运营数据柱状趋势默认近 7 天且仍可切换 30/90，商户端仍默认 30 天；移除商户背景上重复叠放的文案。

## 验证

-
pm run typecheck、
pm run format:check、
pm run build 均通过；
px vitest run tests/map-coordinates.test.ts 2/2 通过。
-
ode tests/e2e/web-redesign.mjs 用本机 Chrome 验证运营桌面/手机、运营无点位、商户桌面/手机，**5/5 通过**；验证地图容器底边与卡片底边相差不超过 2px、默认周期、点位标记、商户重复文案已移除。截图及报告：untime/web-redesign/2026-09-26T09-45-05-802Z/。该检查拦截业务 API 及地图 SDK，以假点位/假底图运行，**不能证明真实地图可用**。另在同一本地页面通过 `runtime/web-redesign/live-map-smoke.mjs` 只拦截业务 API，让地图 SDK 和底图直连高德：浏览器显示丽江真实道路/地名、高德标识和 1 个合成点位，`mapError=null`，地图内图片 2/2 加载；截图 `runtime/web-redesign/live-map-smoke.png`。这证明本机网络加载成功，不代表服务器公网或用户当地网络已通过，也不代表合成点位是真实数据库数据。
- 全量
pm run test 为 48/56 通过、8 项失败，失败均位于已有的 	ests/data-foundation-components.test.ts，挂载缺少 Vue scoped-style SSR 上下文（Cannot read properties of undefined (reading 'modules')）。不把全量测试视为通过。
- SSH 免密连接 39.96.83.196 失败（拒绝 publickey），本轮**未上传服务器**；公网仍是上一版。未经公网登录态与用户当地网络验证，绝不称真实地图已可用。

## 待办

高德官方文档的 JS API 加载说明包含安全密钥/代理配置；当前临时 Web Key 在本机可加载 SDK 和底图，但仍须确认服务商域名授权及线上安全配置，若使用安全密钥应通过安全代理而非写进浏览器。取得安全配置及可用的服务器登录方式后，按现有 web-static-redeploy.md 的备份/校验流程发布，不能直接覆盖在线目录。