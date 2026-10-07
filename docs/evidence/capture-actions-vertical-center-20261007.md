# “框选东巴字”页底部按钮文字垂直居中修复（2026-10-07）

需求：MINI-01；决策：D-067。用户反馈：

> “框选东巴字”页面的，下面三个按钮中的文字并没有垂直居中对齐。

## 根因

`miniprogram/pages/capture/index.wxml` 第 31–33 行的三个动作按钮都带
`size="mini"`。微信原生 `button[size="mini"]` 会把按钮设为 `inline-block`
（选择器优先级 0,1,1），压过 `miniprogram/app.wxss` 里全局
`button { display:flex; align-items:center }`（0,0,1）；同页原有的
`.crop-actions button { line-height: 1 }` 又把行高压到 1，文字因此贴在按钮顶部。
同页 `.icon-button` / `.album-entry` / `.shutter` 都已显式写 flex 居中，
只有这三个动作按钮漏了；`pages/map/index.wxss`、`pages/result/index.wxss`
此前已用 `[size="mini"]` 选择器修过同类问题，capture 页漏改。

## 改动

`miniprogram/pages/capture/index.wxss`：把原 `.crop-actions button { ... }`
换为带页面作用域的 `[size="mini"]` 选择器（优先级 0,2,1），强制 flex 居中：

```css
.capture-page .crop-actions button[size="mini"] {
  display: flex; align-items: center; justify-content: center;
  flex: 1; min-height: 88rpx; margin: 0; font-size: 28rpx; line-height: 1;
}
```

只改样式，不改 WXML 结构、按钮文案、禁用态与事件绑定。

## 验证

| 命令 | 结果 |
| --- | --- |
| `node --test --test-isolation=none miniprogram/tests/services.test.js` | 25 通过 / 0 失败 |
| `node miniprogram/tests/validate-project.js` | 19 页、JSON/JS 语法、tab 路由与 WXML 事件处理校验通过；小程序代码指纹 `81cb8e6ba844ef3a09d46bc8c5e543c43bb0488246921ab28cb7fcbf2fbce1a1` |

以上为离线静态校验与既有测试，**未做像素级视觉确认**。

## 未验证边界

- 微信官方编译器（`native-compile.js`）需传入本机开发者工具目录，本轮未运行。
- 离线布局夹具（`visual-preview.cjs`）未覆盖 capture 页，因此本次没有该页的
  离线截图比对；按钮文字位置需在微信开发者工具或真机复核一次才算视觉签收。
