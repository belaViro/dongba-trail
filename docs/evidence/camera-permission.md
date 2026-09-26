# 相机权限修复证据

日期：2026-09-25

本次修复针对真机进入设置后显示“允许 null 使用”的相机权限流程：

- `miniprogram/app.json` 声明 `scope.camera`，用途为“用于拍摄东巴文字并进行识别”。
- 体验版相机页不再挂载容易卡死的 `<camera>`，改用 `wx.chooseImage({ sourceType: ['camera'] })` 直接拉起系统拍照；不再主动调用 `wx.authorize(scope.camera)`。
- 用户从首页点击“拍照识东巴”进入相机页后，真机会在页面加载时立即打开系统相机；未登录用户也可先完成拍摄，提交识别时再登录。取消系统相机后仍保留重新拍摄和相册入口。
- 相机组件报错时保留“打开设置”入口；开发者工具仍使用相册测试，不挂载原生相机组件。

验证命令：

```text
node --test --test-isolation=none miniprogram/tests/services.test.js miniprogram/tests/helpers.test.js
23 passed

node miniprogram/tests/validate-project.js
Validated 19 native pages, JSON/JS syntax, tab routes and WXML event handlers.
Mini-program code SHA-256: 83d3a78458b3efe2a46cd94ecb600e2807d55111807e7dbb5e8e3dea025f1fc5

node miniprogram/tests/native-compile.js "D:\engineering_software\微信web开发者工具"
WeChat native compiler accepted 21 WXML files and 17 WXSS files.

git diff --check
通过（仅有 Git 的换行符提示）
```

真机验收前提：从 `miniprogram` 目录重新编译并上传体验版。已上传的旧体验版不会包含本次代码；体验版已关闭项目隐私拦截，正式发布前需恢复。应用名称显示由微信账号后台元数据决定，不能由小程序代码设置。
