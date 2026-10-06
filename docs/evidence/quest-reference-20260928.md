# 寻迹页参考图改版（2026-09-28）

## 范围与依据

- 需求：QUEST-01、QUEST-02、DESIGN-01；决策：D-055。
- 用户要求参考 `runtime/docx-audit/image7.png` 美化原生小程序寻迹页。
- 有界任务：重做 `miniprogram/pages/quests/` 的呈现与只读数据组合，保留既有 `pages/quest/` 报名、条件校验、打卡和领奖流程。不修改后端、运营数据、接口契约或其他业务页面。
- 视觉使用现有本地雪山古城背景、纸纹、水墨、品牌和图标资产；新增红色题签、环形印记进度、下一目标/奖励双卡、沿途卡片及主操作。1–4节点收紧环形留白，9–12节点调整间距，超过12节点转为网格。

## 真实数据与状态

- 路线来自 `/quests` 和 `/quests/{id}`，个人进度来自 `/me/quests`；分子仅统计本路线已完成节点，完成状态仍以服务端为准。保留已报名但不再公开的路线记录。
- 环形节点数量动态生成，不补造十二字、不固定4/12，不伪造距离或锁定顺序。任务类别图标不是东巴字形；仅在已发布字典详情提供图片时使用真实字形。
- 商户缩略图与奖励名称通过现有公开详情接口读取；相关图片失败时回退类别图标，奖励不可用时明确提示，不影响路线展示。重复关联去重、分批读取；切换路线/离开页面时忽略旧响应。
- 全部/我的路线、印记册、文化地图和任务详情入口保留；游客访问公共路线不强制登录，个人入口继续登录校验。

## 文件与验证

主要文件：`miniprogram/pages/quests/index.{js,json,wxml,wxss}`、`utils/quest-view.js`、`tests/quests.test.js`、`tests/quest-fixtures.{js,cjs}`、`tests/visual-preview.cjs`。

| 命令 | 结果 |
| --- | --- |
| `node --test miniprogram/tests/*.test.js` | 94项通过，0失败；其中寻迹13项，覆盖节点排序/计数、边界状态、公开/个人接口、媒体回退、请求竞态、登录与导航 |
| `node miniprogram/tests/native-compile.js 'D:/engineering_software/微信web开发者工具'` | 微信官方编译器接受21份WXML、17份WXSS |
| `node miniprogram/tests/validate-project.js` | 18页、JSON/JS语法、原生Tab路由及WXML事件检查通过；指纹见下 |
| `node miniprogram/tests/visual-preview.cjs --quests` | 91组离线布局通过；320×568、375×667、390×844、430×932；包括0–12及15节点、长文案、缺图、完成/关闭/加载/错误/奖励缺失和原生按钮样式干扰 |
| `node miniprogram/tests/visual-preview.cjs` | 160组跨页离线布局通过 |
| `.venv\Scripts\python.exe scripts/check_project.py` | 35条需求、证据链接、原文完整性与API契约检查通过 |

布局断言包含：无横向溢出、印记点击区至少44×44px且不重叠、双卡容纳、资源加载、标题避开模拟胶囊、主操作/地图/印记册等点击命中。修复了窄屏12节点点击区重叠，以及WXML逻辑运算符不应作HTML实体转义的问题。浏览器测试滚动到按钮中心再校验，原生Tab栏在离线HTML中仅作固定层模拟，不属于应用自行绘制的组件。

人工查看了普通路线与320px十二节点截图；预览样例及图片均明确为离线布局夹具，不接入页面生产数据。

产物（本地运行生成）：
- `runtime/quest-redesign/unit-tests.txt`、`native-compile.txt`。
- `runtime/miniprogram-visual/quests-report.json`、`report.json`。
- `runtime/miniprogram-visual/quests-content-390-viewport.png`、`quests-content-390.png`、`quests-twelve-stamps-320.png`、`quests-long-content-375.png`。

最终小程序代码与资源SHA-256（由validate-project生成）：
`7ee6f1819fab34a5f9d964045ae205d513b1a1c2e1026faab70a7185ba7b8ace`

## 边界

仅本地改版，未上传微信体验版，未部署后端或改写运营数据库。浏览器截图为断网HTML/CSS近似，不是微信模拟器/真机视觉验收；原生胶囊、安全区、图片裁切、网络加载及各入口完整真机体验仍需开发者工具和设备检查。相关任务业务验收不因本次视觉修改撤销，但DESIGN-01保持未完成，不以夹具证明真实识别准确率或发布就绪。

## 最终检查

- 项目检查通过：35条需求、证据链接、原文完整性与API契约一致；本轮未修改后端行为或生成契约，因此未将历史后端测试冒充为本轮新验证。
- 最终JSON导航文字颜色设为白色后，重新执行94项测试、官方编译与18页校验，均通过，代码指纹与上文一致。
- `git diff --check -- miniprogram/pages/quests docs/status.md docs/decisions.md docs/acceptance.md` 通过。Git提示后续可能转为CRLF，这是仓库行尾策略提示，不是代码错误；未为消除提示重写其他文件。
- 验证与参考图均为本地材料，未提交Git、未上传微信或改动服务器配置，保留工作区已有的其他修改。
