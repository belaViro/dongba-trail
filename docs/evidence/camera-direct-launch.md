# 拍照识别直达相机证据

日期：2026-09-25

本次调整针对用户反馈的“点击拍照识东巴仍进入识别页面”：

- 删除 `pages/camera/index` 独立识别页，并从 `app.json` 移除注册。
- 新增 `utils/recognition.js`，点击入口后立即调用 `wx.chooseImage({ sourceType: ['camera'] })`。
- 首页“拍照识东巴”、历史失败重拍和任务识别都复用该工具；任务识别保留 quest/node 上下文。
- 拍照成功后直接上传识别并进入结果页，不再渲染中间相机页；取消拍照时停留在原页面。
- 保留 `app.json` 的 `scope.camera` 用途声明；图片超过 8 MB 有明确提示，取消不误报错误。

验证命令：

```text
node --test --test-isolation=none miniprogram/tests/services.test.js miniprogram/tests/helpers.test.js
23 passed

node miniprogram/tests/validate-project.js
Validated 18 native pages, JSON/JS syntax, tab routes and WXML event handlers.
Mini-program code SHA-256: a0926ff591ec3b49277a36700c4b1409a152ea54be2bb4102fa913fb4250a3b5
```

限制：本机 `node miniprogram/tests/native-compile.js "D:\engineering_software\微信web开发者工具"` 因 wcc.exe 报 `EPERM`，未完成本轮原生编译复跑。项目校验和 23 项客户端服务测试已通过。真机仍需重新上传体验版后验收；不能把替身测试冒称为真实相机验收。