# Web 视觉改版与公网部署证据

日期：2026-09-26。对应 `DESIGN-01`，并覆盖 `AUTH-02`、`MERCHANT-02`、`OPS-01/02/03`、`ANALYTICS-01` 的 Web 展示边界。

## 参考图与改版前差异

用户提供的图09（商户后台）与图10（运营后台）共同使用深蓝黑侧栏、丽江雪山/古城文化背景、浅灰蓝页面底色、白色圆角卡片、红色竖线标题标记和紧凑数据看板。图10以蓝色为主色并包含审核、点位、模型和来源区块；图09以茶褐和暖橙为主色并包含门店形象、转化趋势、核销、商品和优惠券区块。

原页面的公共外壳、登录页和首页文化识别度不足，角色主题区分不明显，首页信息密度、图标化指标、移动端排布和参考图差距较大。原接口也不支持参考图中的周期环比、真实 Top-1/Top-5、通知数、游客评价和活动参与人数。

## 修改结果

- `web/src/App.vue`、`web/src/style.css`：统一文化主题外壳、深色侧栏、角色色板、顶部本地菜单搜索、账户区和移动端导航；搜索只进入当前角色已有路由。
- `web/src/views/LoginView.vue`：改为丽江文化视觉登录页。
- `web/src/views/DashboardView.vue`：分别实现运营和商户首页。运营端显示真实指标、按日趋势、待审核状态、已发布坐标分布示意、来源排行、提供方运行数据和已发布活动；商户端显示门店资料、经营指标、领券/核销趋势、快捷入口、转化阶段、来源排行和热门商品。
- `web/public/art/`：从用户参考图的纯背景艺术区裁切 `lijiang-panorama.png`、`lijiang-sidebar.png`、`merchant-tea.png`，不包含参考图中的虚构界面文字或数据。
- 缺少接口依据时显示空状态、破折号或边界说明；不伪造环比、准确率、通知、评价和参与人数。地图区明确是坐标分布示意，不替代正式地图导航。
- 浏览器验收发现并修复运营欢迎横幅和移动地图装饰造成的4至6像素横向溢出；商户趋势移除后端每日聚合不存在的 `merchant_views` 序列，只显示可用的领券和核销。

## 本地验证

- `npm run typecheck`：通过。
- `npm run format:check`：通过。
- `npm run build`：通过，Vite转换1706个模块并生成生产包。
- `node tests/e2e/web-redesign.mjs`：通过4/4；覆盖1672×941和390×844的运营/商户首页，无未知请求、浏览器错误或横向溢出。
- 浏览器证据：`runtime/web-redesign/2026-09-26T07-36-53-453Z/`。测试使用明确标记的夹具，只证明UI行为，不证明真实识别准确率、真实MySQL跨端旅程或生产就绪。
- 浏览器受测代码指纹：`sha256:349f2191c76d829713f7021fd768234ecd1a918c6761de7681491d45fb9585ff`，运行前后源码稳定。
- `npm test`：54项中46项通过、8项失败。失败集中在新增内存组件挂载测试的Vue scoped-style SSR上下文（`Cannot read properties of undefined (reading 'modules')`）；生产类型检查、构建和真实Chromium页面运行均通过，但这8项仍记录为未通过。

## 公网部署

- Nginx 实际静态根目录：`/home/admin/dongba-trail/web/dist`。
- 部署前旧版 `index.html` SHA-256：`5274ebe87817413a8fdfea309647b86767ff85d61d4bef54ef28de53fb185a5f`。
- 上传包 SHA-256：`79e07711112554a61aa062112da060a082e1703944c68c6ffbaaad5b21be0272`。
- 部署后本地、服务器和公网首页对应 `index.html` SHA-256：`ff69f5324a0970e2529a850b14b622e1024b6bde1d62014c19f1888fb9d02f52`。
- 旧版备份：`/home/admin/dongba-trail/web/dist.backup-20260926-154451`。
- `nginx -t`通过，随后完成reload。
- 公网严格HTTPS检查：`/`、`/login`、`/health`、`/api/v1/privacy`、`/art/lijiang-panorama.png`、`/art/lijiang-sidebar.png`、`/art/merchant-tea.png` 均返回200。
- 公网首页引用本次构建的 `index-D04S8LBZ.js`、`index-_8Hh4J6A.css` 等新哈希资源。
- 公网Chromium检查登录页标题、主标题、控制台和页面宽度通过；截图为 `runtime/web-redesign/public-login-20260926.png`。

本次只切换 Web 静态文件，没有修改服务器数据库、媒体库、后端配置或后端进程。部署成功不关闭地图业务、来源归因、真实模型评测、海报和其余设计缺口，也不宣称版本已生产就绪。
