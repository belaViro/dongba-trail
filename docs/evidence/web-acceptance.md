# Web 业务闭环验收

日期：2026-09-23。最终完整浏览器运行结束：2026-09-23 12:20:44（北京时间）。

## 版本和环境

- 验证时项目代码指纹：`sha256:403581abf70f8c3aaa0bf460991de94cfb35787d037b660735a667d5e62db5b5`，182个文件。
- 复核命令：`.\.venv\Scripts\python.exe scripts/code_fingerprint.py`。其他并行模块后续变动可能改变全项目指纹，最终提交以整体验收记录为准。
- Vue 3、TypeScript、Element Plus、Vite；真实 FastAPI 服务与 MySQL 8.0 数据库。
- 浏览器：Playwright Chromium headless shell；桌面1440×960，手机390×844。
- 隔离验收入口：`http://127.0.0.1:5317`，仅代理8011的独立 `dongba_ui` 数据库。
- 用户正常试用入口：`http://127.0.0.1:5318`，代理8010的开发数据库。验收结束后仍为 `setup_required=true`，未注入测试账号或文化内容。
- 两个Vite进程都使用 `--strictPort`，避免误操作占用端口的其他项目。5174是无关应用，未参与本次证据。
- 内置浏览器连接出现基础设施错误后，使用已授权的独立Playwright执行。测试需要的浏览器进程在沙箱外运行。
- 所有文化记录、商户、用户、图片和优惠券均为明确标识的隔离测试数据，无真实文化认定和经济价值；测试凭据仅保存到被Git忽略的 `runtime/e2e/`。

## 执行命令与结果

```powershell
# 工作目录：项目根目录
$env:PLAYWRIGHT_CHROMIUM_EXECUTABLE = Join-Path $env:LOCALAPPDATA 'ms-playwright/chromium_headless_shell-1228/chrome-headless-shell-win64/chrome-headless-shell.exe'
$env:DONGBA_E2E_EXPORTS = '1'
node tests/e2e/acceptance.mjs
node tests/e2e/capture.mjs

# 工作目录：web
npm test
npm run build
npm run format:check
```

- 完整业务脚本：**23项浏览器及真实接口检查通过，浏览器运行错误0**。
- 截图脚本：9张干净的桌面/手机截图，页面身份及菜单关闭/打开状态通过。
- Web回归测试：**12项通过**；包括Vue响应式记录编辑、表单数据隔离、令牌与HTTP错误处理、未知门店坐标不伪造为0,0等。
- TypeScript检查和生产构建通过；Prettier检查通过。
- 首次管理员创建在首轮实际浏览器运行中通过，后续迭代使用该测试管理员重复登录。
- 浏览器最终结果原始记录：[acceptance-result.json](web/acceptance-result.json)。

## 已跑通业务

| 流程 | 实际结果 |
| --- | --- |
| 初始化及登录 | UI创建首位管理员，退出并重新登录；运营与商户进入对应工作区 |
| 字典及图片 | UI新增词条、上传图片、查看私有草稿预览、编辑文化内容、审核、发布；发布前游客不可见，发布后可见 |
| 商户与商品 | UI创建并发布商户，商户提交商品形成草稿；不能修改其他商户商品 |
| 文化标签 | 商户选择已发布词条提出申请，运营实际审核通过 |
| 优惠券核销 | 测试游客通过真实接口领券，商户UI核销成功，再次核销返回已核销；其他商户核销被拒绝 |
| 路线与节点 | 运营UI创建路线和人工节点，配置奖励；生成并下载扫码节点的真实标准二维码 |
| 寻迹奖励 | 测试游客加入路线并提交扫码口令，运营UI完成人工节点；游客获得印记及一张奖励券，完成数进入统计 |
| 海报和分享记录 | 测试游客收藏词条并调用真实海报生成；生成与分享操作事件进入运营统计；小程序码未配置状态保持明确 |
| 运营配置 | 推荐权重在UI保存，真实PATCH返回成功 |
| 运营记录 | 其余运营页面均可打开；按筛选导出CSV成功，服务端出现export审计记录 |
| 停用 | UI确认下架停用，记录状态变为disabled，保留审计及业务关联 |
| 手机工作流 | 仪表盘、核销、表格和编辑器无横向页面溢出；关闭侧栏完全移出视区，打开有遮罩和明确关闭按钮 |

测试中的游客动作使用真实应用接口和隔离账号；不将其称为微信真机验收。商户扫码相机本身需要设备权限与浏览器支持，当前验收验证手工券码核销、任务二维码输出及扫码口令的实际业务判定。

## 本轮修复

1. 已有记录包含Vue响应式数组时，直接structuredClone会导致编辑器打不开；现在先toRaw再复制，取消编辑也不会污染表格数据。
2. 门店未填坐标时保留null，发布前由业务校验要求明确位置；不把未知位置替换为0,0。
3. 手机侧栏关闭时立即不可见且不接收点击，新增关闭按钮；截图及自动检查同时验证位置和遮罩，避免只看页面宽度。
4. 补齐运营任务二维码预览/下载、服务端审计导出与活跃/识别/寻迹/海报/分享操作指标。
5. 对齐核销时间字段、空扫码口令、私有图片鉴权及默认密码保留等接口细节。

## 页面证据

- 用户初始入口：[桌面](web/dongba-user-entry-desktop.png)、[手机](web/dongba-user-entry-mobile.png)。
- 运营概览：[桌面](web/dongba-admin-desktop.png)、[手机](web/dongba-admin-mobile.png)。
- 商户概览：[桌面](web/dongba-merchant-desktop.png)、[手机](web/dongba-merchant-mobile.png)。
- 手机导航：[展开与遮罩](web/dongba-mobile-navigation-open.png)。
- 字典：[桌面](web/dongba-dictionary-desktop.png)、[手机列表](web/dongba-dictionary-mobile.png)、[手机编辑器](web/dongba-editor-mobile.png)。
- 核销：[桌面](web/dongba-redemption-desktop.png)、[手机](web/dongba-redemption-mobile.png)。
- 寻迹：[任务节点](web/dongba-quest-desktop.png)、[任务二维码](web/dongba-quest-qr-desktop.png)。

## 验证范围

覆盖AUTH-02、DATA-01、DATA-02（Web媒体流程）、MERCHANT-01/02、COUPON-02、QUEST-01/02、OPS-01/02/03、ANALYTICS-01及DESIGN-01中的后台页面。FEEDBACK-01的页面可用和导出流程已实现，真实识别纠错数据仍需后续模型接入后验证。

真实模型、已审核文化字库、微信登录/分享、小程序扫码相机与真机导航不属于本次浏览器通过结论；对应交付边界继续在总体验收记录中明确。本次按用户要求优先验证业务贯通，未以这些结果宣称生产负载或安全专项验收完成。
