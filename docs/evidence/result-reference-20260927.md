# 图03识别结果页本地改版

日期：2026-09-27。范围：AI-03、CONTENT-01、REC-01、DESIGN-01，延续D-048附图授权，决策D-051。按用户提供的 `runtime/docx-audit/image3.png` 优化原生小程序结果页，不修改后端、API契约、业务数据库或其他页面实现。

## 实现

- 复用小于200KB的 `assets/home/landscape.jpg`，采用淡雪山背景、纸白圆角卡、朱红重点及原生标题栏。原照片在左，候选名字、参考分数、分类、音频和收藏在右。原照片加载失败后明确标为“字典字形·非原照片”，不把字典图片当作用户原图。
- 同字异形与最多五个去重候选并排，320px小屏纵向排列，横向可滑动；文化正文/来源及音频只取已发布字典内容。没有异形或音频时提示缺失，不造三个写法或虚构视频。
- 当前候选下的已发布关联商户横向卡片，图片失败单卡降级；详情/更多保持原 `recognition_id`。不触发定位，不补造距离、评分、销量或优惠。未实现的POI/活动/文化视频仍未验收。
- 第一候选只预览，`selected`仍为空；用户点选候选后才可确认。收藏不调用识别确认，参考分数不称作置信度或准确率。底部保留反馈、重拍、显式确认，而不是未经确认便展示参考图里的领券/导航动作。
- 保留“都不是”人工复核、选填说明、默认关闭的附图同意及先上传后提交规则；无图、上传失败、拒识、词条读取失败均显式处理。候选切换/退出后旧异步结果不得覆盖当前内容，停止并释放旧音频；收藏读取失败先重试状态，不盲目切换。
- 按钮显式 `size="mini"`规避原生宽按钮默认值；最小44px点击高度，底栏48px，适配安全区。标题定为两行标语，读音按钮紧随字名。首页和地图本轮不修改。

## 验证命令与结果

| 命令 | 结果 |
| --- | --- |
| `node miniprogram/tests/validate-project.js` | 18页JSON/JS、路由及WXML事件绑定通过 |
| `node --test miniprogram/tests/helpers.test.js miniprogram/tests/services.test.js miniprogram/tests/home.test.js miniprogram/tests/map.test.js miniprogram/tests/result.test.js` | 73项通过；结果页新增17项，覆盖预览不确认、去重/零分、媒体与缺内容、异步切换/卸载、收藏鉴权/退出登录、音频生命周期、跳转及纠错；既有附图授权/上传失败阻断测试保持通过 |
| `node miniprogram/tests/native-compile.js "D:\engineering_software\微信web开发者工具"` | 官方编译器接受21份WXML、17份WXSS |
| `node miniprogram/tests/visual-preview.cjs --result` | 30个离线场景通过；320/375/390/430px，含待选择/已选、纠错、长文本、媒体缺失、拒识、过期、加载/失败/收藏错误及原生按钮样式干扰 |
| `node miniprogram/tests/visual-preview.cjs` | 85个跨页离线场景通过；首页、地图及原有页面无横向溢出/过小按钮回归 |
| `.venv\Scripts\python.exe scripts/check_project.py` | 35项需求、证据链接、原始文档与API漂移检查通过 |
| `git diff --check -- miniprogram/pages/result miniprogram/tests/result.test.js miniprogram/tests/visual-preview.cjs docs/status.md docs/decisions.md docs/acceptance.md docs/evidence/result-reference-20260927.md` | 通过；仅Git预告LF→CRLF规范化，无空白错误 |

布局测试检查左图右文、标题不溢出、全页不横向滚动、按钮至少44px，主要动作中心及四条边内侧实际命中且不被底栏覆盖；正常、窄屏、长内容均检查。离线首屏、底部及全页截图与报告在不提交的 `runtime/miniprogram-visual/`：`result-report.json`、`report.json`、`result-content-390-viewport.png`、`result-content-320-viewport.png`、`result-content-390-bottom.png`等。人工查看390/320首屏和底部布局，并复查最终390首屏标题换行及读音位置。全页长截图中的固定底栏位置是浏览器截屏行为，另存首屏和底部截图避免误判。

初轮单元测试中，零分夹具同时给同一候选100%导致断言失败；已确认已有去重规则保留较高分数，修正夹具为一致零分，没有改动既有去重逻辑。最终73项全部通过。

**限制：** 本轮是本地代码/编译/离线布局验证，浏览器内容及原生导航是明确的夹具，不是微信运行时、真机点击或真实接口集成验收，不提供识别准确率证据。未上传微信、未部署服务器、未提交真实反馈或改商户记录；真实文化媒体、微信安全区/音频/附图端到端体验及正式视觉签收仍待验。不存在后端行为/契约改动，未以本轮UI测试替代MySQL或真实识别测试。

## 交付代码指纹

`validate-project.js`汇总SHA256：`591d62756898c5af3e7fb32efc5ce5052fb4d7a02b9a56130842ac90c2d70a88`。工作区含其他并行修改，仅下列客户端文件属于本轮执行范围，文档记录不属于可执行代码哈希。

| 文件（相对miniprogram/） | SHA256 |
| --- | --- |
| pages/result/index.js | `1E7E074B8A60AB3A2653C55DB789D0C73CA7C33640260B0C4E0C0E248BEF16E4` |
| pages/result/index.json | `445AC6AD11D1975EC5B14B5CE11C128EE31A77984E904CE2EC038E5CC56CD07D` |
| pages/result/index.wxml | `FAF80215F597CE4AFF9B84AFAF3A46C7FFF98F11AD1D7D4DADCA5866FCA52A04` |
| pages/result/index.wxss | `8B3CC8ECBEBBCDD8DC3E7180E8424A81A9F4EEA82953ACB047F1C9DF083EBAF6` |
| tests/result.test.js | `52F66DF1FD1020777682F13EB07C3F5B26D24EC99C9FE2CC4622AAB36220F321` |
| tests/visual-preview.cjs | `EB259F095DEE3307A9EF06AA43F90BD17B0ACA926E9A95F9BFABCF77FC626EE7` |
