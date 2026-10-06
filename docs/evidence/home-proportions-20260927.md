# 首页比例与今日字左对齐

日期：2026-09-27。需求：DESIGN-01，涉及 MINI-01。决策：D-047（原首页记录误用D-046，已消歧）。

后续用户反馈“依旧没有居左”：本轮离线通过不能作为实际左对齐验收。
后续容器修正及新验证见[原生按钮布局隔离](home-left-alignment-20260927.md)，以下保留当时记录。

## 有界任务

用户认为上一版首页偏扁，并要求今日字图片与介绍靠左、图片增加白底圆角方框。
本次只调整首页 WXML/WXSS 与离线视觉检查；不修改首页数据逻辑、后端、字典、
接口、其他页面样式或微信发布状态。

## 修改

- 头图区从440rpx增加到480rpx，圆形拍照按钮从270rpx增加到300rpx；相机图标及按钮文字同步放大。背景高度从730rpx调整到820rpx。
- 今日字卡增加上下内边距和标题/正文间距，正文从19rpx/1.5行高改为23rpx/1.65行高，最多3行，不再压成很小的两行。
- 字形框采用176×176rpx白底正方形、20rpx圆角、14rpx内边距和轻阴影；移除图片的乘色混合，保持原图颜色及组件既有的aspectFit，不拉伸、不裁字。
- 今日字按钮明确采用横向flex-start布局、零水平内边距和零水平外边距；图片左边与卡片标题对齐，右侧名称与介绍共用左边线，长词条/介绍仍限制在卡内。
- 快捷入口高度98→114rpx，商户封面156→184rpx，卡片内边距略增；小屏通过滚动展示余下内容，不把所有区块强塞入一屏。
- 视觉检查新增有图分支（中性地图标记仅为图片容器夹具，不是东巴字形），检查正方形、白色背景、圆角、左边线和aspectFit。修正离线渲染器遗漏glyph-image初始failed状态，以及模拟Tab安全区重复计入高度的问题；这两项为预览器修复，不是修改原生组件/Tab。

## 最终验证

```text
node miniprogram/tests/validate-project.js
Validated 18 native pages, JSON/JS syntax, tab routes and WXML event handlers.
Mini-program code SHA-256: 0ade474ae6e74c79d572aac23d2f12a7b34b0c237e19f00214c3b7273749370b

node --test miniprogram/tests/helpers.test.js miniprogram/tests/services.test.js miniprogram/tests/home.test.js
36 passed, 0 failed

node miniprogram/tests/native-compile.js "D:\engineering_software\微信web开发者工具"
WeChat native compiler accepted 21 WXML files and 17 WXSS files.

node miniprogram/tests/visual-preview.cjs
PASS: 49 offline layout cases (320/375/430px)

node miniprogram/tests/visual-preview.cjs --home
PASS: 14 offline homepage cases (320×568, 375×667, 390×844, 430×932)

.venv\Scripts\python.exe scripts/check_project.py
FAILED: OpenAPI drift: run python scripts/export_openapi.py
```

通用与首页专项用例有重叠，不相加视为63个独立用例。源码/样式差异空白检查通过。
项目总检查连续两次报告当前后端与OpenAPI文档漂移；首页任务未修改后端或契约，
因此未覆盖其他工作中的接口文件或自动重导出。不能把本轮项目总检查记录为通过；
需由后端变更负责人确认当前接口后运行导出及项目检查。
截图、`report.json` 和 `home-report.json` 位于 `runtime/miniprogram-visual/`；
重点查看 `home-content-390-viewport.png`、`home-image-present-320-viewport.png`，
以及375px长内容、无图、拒绝定位状态。

## 边界

这些截图是读取当前WXML/WXSS的离线Chromium近似，所有内容为布局夹具；
不代表真机字体、真实字形、文化真实性、相机/定位、实际接口或识别质量验收。
没有重新上传微信体验版；需在微信开发者工具与真机确认不同安全区及实际图片显示。
保留先前未提交和并行部署/RAG改动，不修改原DOCX或凭据。DESIGN-01仍为实现中。
