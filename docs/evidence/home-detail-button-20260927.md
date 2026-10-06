# 首页“查看详情”短胶囊按钮

日期：2026-09-27。需求：DESIGN-01，涉及 MINI-01。决策：D-047。

## 范围与修改

用户反馈详情按钮过长，与提供的图01不符。本轮只改首页详情按钮及对应回归检查：

- WXML增加`size="mini"`，保留原生button、详情事件与无障碍标签。
- WXSS以`.daily-header .daily-detail[size="mini"]`限定112rpx宽、禁止伸缩、清除原生水平内边距，防止默认常规/mini按钮样式拉长。
- 可见浅色细边胶囊为104×34rpx，右边与卡片内缘对齐；文字18rpx、小右箭头。透明点击区保持44px高。
- 删除小屏详情文字额外放大的规则。未改今日字左对齐、白框、首页比例、接口、数据或共享样式。
- 测试增加mini属性校验、紧凑宽高/右边距/标题不重叠断言，以及模拟原生常规与mini按钮默认样式的干扰检查。

## 验证

```text
node miniprogram/tests/validate-project.js
PASS: 18 native pages, JSON/JS syntax, tab routes and WXML event handlers.
Mini-program code SHA-256: a7688d4c31675f7dc35ba0683d045328dc7be5ee6ead4b8afd5ce43e019d0408

node --test miniprogram/tests/helpers.test.js miniprogram/tests/services.test.js miniprogram/tests/home.test.js
PASS: 38 tests, 0 failed.

node miniprogram/tests/native-compile.js "D:\engineering_software\微信web开发者工具"
PASS: 21 WXML files, 17 WXSS files.

node miniprogram/tests/visual-preview.cjs --home
PASS: 18 offline homepage cases at 320/375/390/430px.
```

首次尺寸检查发现伪元素边框未计入宽度，已显式指定border-box；首次单测旧断言要求属性紧挨，
增加size后失败，已改为允许中间属性且仍检查button及character事件。修正后上述检查全部重跑通过。
测试工作进程、离线浏览器与原生编译器按许可在沙箱外执行。
目视复核`runtime/miniprogram-visual/home-button-default-stress-390-viewport.png`，
测量报告为同目录`home-report.json`。390px视口可见胶囊约54×18px，点击区约58×44px。

## 边界

仅本地源码、原生编译及离线布局验证，不是微信运行时/真机验收；未上传体验版。
本轮未重跑全页面视觉用例，不将上一轮52项结果当作本轮执行结果。
保留其他工作中的后端、Web与部署修改；DESIGN-01维持实现中。
