# 首页详情与更多：扩大可见尺寸及真实点击区

日期：2026-09-27。需求：DESIGN-01、MINI-01。决策：D-047。

用户指出前一版短胶囊仍太小、不好点击，查看更多也是。本轮以用户反馈取代前轮尺寸：
- 两个原生按钮统一148rpx宽、52px高，mini模式配合局部高优先级样式，防止默认宽度/内边距覆盖。
- 详情可见胶囊136×42rpx，文字21rpx；更多文字23rpx，左右各12rpx内边距。右上角对齐和左侧今日字布局保留。
- 点击区使用透明矩形，只有详情的可见胶囊使用圆角，避免圆角裁去按钮边角点击范围。
- 未改后端/API、文化内容、跳转处理函数、共享样式或其他页面。改动为首页WXML/WXSS、首页结构测试和离线视觉脚本。

## 验证命令及最终结果

```text
node miniprogram/tests/validate-project.js
PASS: 18 pages, JSON/JS syntax, routes and event handlers.
Mini-program code SHA-256: c9c7fb19bd90cb637c816c21eb5c757d18157e624744aaf2f6bd63a7341d4737

node --test miniprogram/tests/helpers.test.js miniprogram/tests/services.test.js miniprogram/tests/home.test.js
PASS: 42 tests, 0 failed.

node miniprogram/tests/native-compile.js "D:\engineering_software\微信web开发者工具"
PASS: 21 WXML files, 17 WXSS files.

node miniprogram/tests/visual-preview.cjs --home
PASS: 18 offline homepage cases, 320/375/390/430px.
```

新增实际DOM命中检测：滚动到按钮可见位置后，检测四个边角向内3px及中心；所有点须命中该原生按钮对应的HTML元素，文字不溢出，宽高不得缩水。最终报告已按并行源码更新后重跑。
初次检测在430px发现详情下方两个边角命中父容器/纸纹；排除滚动影响后仍复现。去掉透明按钮本身的圆角后全部通过，胶囊伪元素圆角保留。
这属于离线浏览器问题复现及修复，不声称已读到微信真机计算样式。
最终每个按钮在390px视口为约77×52px点击区；最小320px视口为约63×52px。查看详情的可见胶囊在390px约71×22px。
截图及测量/命中报告保存在`runtime/miniprogram-visual/`，目视核对`home-button-default-stress-390-viewport.png`。

浏览器、测试进程和原生编译器按许可执行。本轮未重跑全页面视觉用例；未上传微信体验版、未进行真机触控验收。
项目总检查本轮受并行后端OpenAPI改动影响，报告`OpenAPI drift`，未把该失败归因于首页，也未重导出其他负责人的契约。
截图内容仍为布局夹具，不是实际业务数据或识别效果。DESIGN-01维持实现中。
