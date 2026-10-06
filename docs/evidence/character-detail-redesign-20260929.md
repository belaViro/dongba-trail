# 东巴字详情页改版与收藏图标修正（2026-09-29）

需求：CONTENT-01、USER-01、REC-01、DESIGN-01；决策：D-064。

## 范围与实际改动

- 按用户图05调整为雪山古城背景、纸感主字形、分类摘要、文化故事、真实音频、相关字形、商户/商品及固定操作栏；复用已有景观资产，未改后端接口、数据库或海报服务。
- 删除详情页“这个字怎么写”卡片及无用展示样式/媒体转换；多写法原始数据和识别结果页功能保留。
- 相关词条缩略图按API媒体地址规范化；缺字形、音频、来源、商户时如实展示缺失状态，不添加虚构拼音、视频、评分、销量或优惠券。
- 保留收藏鉴权与PUT/DELETE、附近商户/商品跳转、识别请求绑定、纠正、寻迹及海报入口。商品仍按merchant_id跳转。
- 用户随后指出收藏图标像方块：原CSS只有矩形外框。现使用72×72透明PNG五角星，未收藏灰褐色空心、已收藏朱红实心，显示44rpx；不是字体缺字，也不再依赖字体符号。两图分别1429/967字节；按钮触控区至少44×48px。
- 图标生成器为本地矢量栅格化脚本，阻断网络，资源可复现；不是AI生成或东巴文化字形。

## 最终版本验证

| 命令 | 结果 |
| --- | --- |
| `node miniprogram/tools/generate-character-icons.cjs` | 两个72×72透明PNG生成成功；空心轮廓已目视复核 |
| `node --test miniprogram/tests/*.test.js` | 162通过，0失败/跳过；日志runtime/character-redesign-tests.log |
| `node miniprogram/tests/native-compile.js "D:\engineering_software\微信web开发者工具"` | 微信官方编译器接受21份WXML和17份WXSS |
| `node miniprogram/tests/visual-preview.cjs --character` | 39个离线布局场景通过，320/375/390/430px；含长词条/摘要、图片存在/缺失、音频播放/缺失、关联空数据、原生按钮样式干扰、安全区与底部触控命中 |
| `node miniprogram/tests/validate-project.js` | 18页结构、JS/JSON语法、注册路由与WXML事件绑定通过 |
| `.venv\Scripts\python.exe scripts/check_project.py` | 35项需求、证据链接、源文档和API检查通过；补充文档后再次执行 |

初次测试启动因沙箱spawn EPERM受阻，获授权后执行本地子进程/无头浏览器通过。没有执行外部生图、网络请求、线上发布或数据库写入。

## 视觉证据与边界

- 布局报告：`runtime/miniprogram-visual/character-report.json`。
- 截图：`character-content-390.png`、`character-detail-long-320.png`、`character-detail-audio-image-390.png`、`character-detail-button-stress-320.png`，均在`runtime/miniprogram-visual/`。
- 离线截图使用明确标注的夹具；图片存在场景用中性地图标记验证图片容器，不冒充真实东巴字形。截图中系统导航为近似外壳，不能证明微信真机或真实音频播放效果。
- 这是前端改版：未改后端行为，未重跑后端/MySQL测试，不沿用旧测试宣称本次集成验收；CONTENT-01与DESIGN-01仍保持“实现中”。需微信开发者工具重新编译/上传后进行真机视觉验收。

## 最终代码指纹

小程序汇总SHA-256（validate-project输出）：`16cade3c51434c1ae52bfa5b84a2314094709edd3236de7372327f18215f5ea2`。

| 文件 | SHA-256 |
| --- | --- |
| `miniprogram/pages/character/index.js` | `869a256dbc5c7ac59e9a429debae4b70302a997927a36e384b9e208829947476` |
| `miniprogram/pages/character/index.json` | `2d9222490203e710065c2a674ab01dc3b306a6524ea9f7c2230dc99b87ee0263` |
| `miniprogram/pages/character/index.wxml` | `0852e87303f430e427adb0486fd76c115dd3df635096b3857a2fd4b4b926010e` |
| `miniprogram/pages/character/index.wxss` | `9ef3a5e5c9f6a6adbcccc21318c0b7e514f64b10ca2a6176d7e728f69cae58fb` |
| `miniprogram/tests/character.test.js` | `fc6f147399d12316e5f81cc1bda67ebb5bbafce7d997851d08f4ea70543ec373` |
| `miniprogram/tests/visual-preview.cjs` | `e28cafcd008ded539d7367ae15df6e7943703ac0569757b667a8977b6095456e` |
| `miniprogram/tools/generate-character-icons.cjs` | `6546aa27ecae4a6b9ade9805a85373bc570d408a5ca816c63706919b39c019fe` |
| `miniprogram/assets/icons/favorite-outline.png` | `d36d114c43a3cebad50c1e9d079d968c2ff1c2a6c0190829b661e62a6fcb5937` |
| `miniprogram/assets/icons/favorite-filled.png` | `cad04b56aec0ca8f508c9835c0c027d7eea940908d8730b2ceedcb1e4f839730` |
