# 今日字左对齐：隔离原生按钮布局

日期：2026-09-27。需求：DESIGN-01，涉及 MINI-01。决策：D-047。

## 用户反馈与有界修正

用户明确反馈上一轮仍未居左，因此此前Chromium中的flex/text-align通过不代表实际问题已解决。
本轮检查确认app.json使用style v2，而今日字整行仍是button；离线预览未覆盖原生按钮的默认尺寸及自动外边距差异。
本轮不声称已读取真机计算样式，只消除这个布局依赖：

- `pages/home/index.wxml`：today外层改为全宽view，保留bindtap、aria-role/label及独立原生“查看详情”按钮。
- `pages/home/index.wxss`：保留现有左对齐、176rpx白底圆角方框、等比图片和间距，补充容器选择原因；不进一步改变页面比例。
- `tests/home.test.js`：新增结构回归，防止再次以button承担整行排版。
- `tests/visual-preview.cjs`：每个首页宽度增加按钮默认样式干扰场景，并断言内容行与标题同宽。
- 不修改API、数据、识别、共享组件或其他页面。文档中本首页决策从重复D-046改为D-047，不改RAG决策。

## 模拟负对照与结果

这是显式模拟，不是从微信运行时抽出的样式：向`button.today:not([size="mini"])`施加184px宽及左右auto外边距。
临时替换成旧button结构时，320/375/390/430px视口中的图片左边分别偏离标题46.69/70.50/77.02/94.34px；
恢复当前view后四个视口的图片框与标题左边差值均为0，内容行宽均等于标题宽。
白色圆角正方形、等比图片、介绍左边、长内容边界、空/错/加载等检查继续通过。
目视核对390px按钮干扰截图；截图内容为离线布局夹具，不是已发布文化资料或真实商户。

## 验证命令

```text
node miniprogram/tests/validate-project.js
PASS: 18 native pages, JSON/JS syntax, tab routes and WXML event handlers.
Mini-program code SHA-256: 15ebbd67dff91c5170ca18a203a1a746c827d95e92cc2fe55ffa4f49e7f2e455

node --test miniprogram/tests/helpers.test.js miniprogram/tests/services.test.js miniprogram/tests/home.test.js
PASS: 37 tests, 0 failed.

node miniprogram/tests/native-compile.js "D:\engineering_software\微信web开发者工具"
PASS: native compiler accepted 21 WXML files and 17 WXSS files.

node miniprogram/tests/visual-preview.cjs --home
PASS: 18 offline layout cases (320/375/390/430px).

node miniprogram/tests/visual-preview.cjs
PASS: 52 offline layout cases (320/375/430px).

.venv\Scripts\python.exe scripts/check_project.py
PASS: 35 requirements, evidence links, source and API.
```

首次沙箱内Node测试因spawn EPERM未执行；获得外部执行权限重跑后37项通过。
浏览器/原生编译器亦使用获准执行方式。通用与首页用例重叠，不能合计为70个独立用例。
上一轮OpenAPI漂移是当时结果；本轮重新执行项目检查通过，未由首页任务改动生成契约。
截图与报告保存在`runtime/miniprogram-visual/`，重点文件为
`home-button-default-stress-390-viewport.png`及`home-report.json`。

## 验收边界

只完成源码修正、原生模板编译与离线回归；未上传微信体验版、未连接真机，不能宣布真机视觉已验收。
需用本轮源码重新编译/预览确认实际左对齐，DESIGN-01维持实现中。
