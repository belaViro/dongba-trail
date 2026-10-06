# 首页背景压缩与地图排版收紧（2026-09-27）

关联：MINI-01、GEO-01、DESIGN-01、D-050。仅实现用户本轮指定的三项修正；不改后端、接口合同、地图业务逻辑及并行纠错审核工作。

## 修改与边界

- 首页实际引用的 `miniprogram/assets/home/landscape.jpg` 从291725字节减至179457字节（减少38.48%），维持1125×954；JPEG质量72。原始PNG保持不动，已有 `packOptions.ignore` 排除规则保留。
- `generate-home-assets.cjs` 从原图生成时按质量/必要时尺寸逐档尝试，目标不超过190000字节，不能满足则报错；新增 `--landscape-only` 避免重写其他素材。单测校验JPEG格式、实际首页引用、低于200000字节及原图打包排除，防止以后重新生成回到超限体积。
- 地图分类可见胶囊从48px改为36px高，导航从52px改为34px高；它们外层按钮保留44px高透明点击区域。导航宽度190rpx→164rpx、至少76px；详情和排序为44px高，不再继承过大的原生按钮尺寸。
- 图层/定位工具52×58px→44×48px，缩放52×52px→44×44px；同步调整文字、圆角和工具/排序间距。地图上方保留原有说明，不增加新标题。
- 彻底删除地图右上 `map-brand` 节点及其样式。首页品牌、今日字白底圆角框/左对齐、148rpx×52px详情和查看更多点击区保持原样。
- 不添加虚构评分、优惠、销量、点位或图片；真实定位/导航/距离排序行为不改。

## 验证

| 命令 | 结果 |
| --- | --- |
| `node miniprogram/tools/generate-home-assets.cjs --landscape-only` | 输出179457字节、1125×954、质量72；其他素材不重生成 |
| `node miniprogram/tests/validate-project.js` | 18页结构、JSON/JS、路由及事件绑定通过 |
| `node --test miniprogram/tests/helpers.test.js miniprogram/tests/services.test.js miniprogram/tests/home.test.js miniprogram/tests/map.test.js` | 56项通过，含新资源预算断言和品牌文字移除断言；地图业务13项保持通过 |
| `node miniprogram/tests/native-compile.js "D:\engineering_software\微信web开发者工具"` | 官方编译器接受21份WXML、17份WXSS |
| `node miniprogram/tests/visual-preview.cjs --home` | 18个离线场景通过，保留首页白框/对齐/点击区 |
| `node miniprogram/tests/visual-preview.cjs` | 67个跨页离线场景通过 |
| `node miniprogram/tests/visual-preview.cjs --map` | 27个离线场景通过，320/375/390/430px宽，含长内容、缺图、授权失败、空状态、按钮样式干扰 |
| `.venv\Scripts\python.exe scripts/check_project.py` | 35项需求、证据链接、原始文档与API漂移检查通过 |

地图布局测试新增尺寸上限，校验胶囊36px/34px与外层44px点击区分离；工具宽度固定44px，导航宽度有界。逐按钮检查中心与四条边内侧均命中，防止缩小视觉后不可点击。

离线截图及报告位于 `runtime/miniprogram-visual/`（不提交生成目录）：`map-report.json`、`home-report.json`、`report.json`、`map-content-320.png`、`map-content-390.png`、`home-content-390-viewport.png`。人工查看压缩后的背景图和小屏地图/首页截图；背景构图不变，按钮、文字未横向溢出。完整长截图里的固定底栏位置是浏览器全页截屏行为，首屏另存 `*-viewport.png`。

**限制：** 浏览器使用明确标注的原生地图占位和数据夹具；不代表真实微信底图、真实接口数据、真机点击或正式视觉签收。本轮未上传微信、未部署、未修改真实商户记录。真机导航、地图路线/优惠卡等原有缺口仍保留。

## 交付代码指纹

`validate-project.js`汇总SHA256（验证时工作区）：`f0180a504360ab61daa56a0e709f316c5e2a22aacb395bed8414d9ecb8cb64f7`。工作区同时存在其他修改，以下为本轮作用域精确指纹：

| 文件（相对miniprogram/） | SHA256 |
| --- | --- |
| assets/home/landscape.jpg | `8A7E2B007113FB6DE044D2BD0BBCC6F7D6A21E127F2FD0931A7F90B8876A0668` |
| tools/generate-home-assets.cjs | `D3F70D8F9BA6D6BC2DE1E33B14DB50B0117DB6D48F99FB9060DAD0D3B72502C1` |
| pages/map/index.wxml | `79C69CED220350CAC873DE23F089044CEC835EB0368A73090935246E70DE96D5` |
| pages/map/index.wxss | `D2739114E8084D709C5F309FBBD1C88B701100B65A381718AEBB7091E2446BAB` |
| tests/home.test.js | `47CD67A66D611878C54B231C451980F9FE0908634955864D3B2674F9ACC64530` |
| tests/map.test.js | `7F0C2308B3F2AE940032BACD8AA28C3130557CD0B0A60C0F2A6C582690B6C4F8` |
| tests/visual-preview.cjs | `36F77684E1A6F20EF8CD72E1572783F1975BD8196BDE1B9A1A1E01976FE622AA` |
