# 字典关联区排版证据（2026-09-27）

## 范围

本轮只修正 `miniprogram/pages/character/index.wxml` 与 `index.wxss` 中“在丽江遇见它”和“把丽江风物带回家”两个关联区：移除原生 v2 button 的默认窄宽影响，改为全宽左对齐行；固定缩略图尺寸，文字列自适应并限制长标题/说明，箭头保持在右侧；“全部”使用紧凑外观但保留至少 44px 高点击区。商户仍使用 `item.id`，商品仍使用 `item.merchant_id`，原识别请求参数继续传递。

## 验证结果

| 命令 | 结果 |
| --- | --- |
| `node --test miniprogram/tests/helpers.test.js miniprogram/tests/services.test.js miniprogram/tests/home.test.js miniprogram/tests/map.test.js miniprogram/tests/result.test.js miniprogram/tests/character.test.js` | 77项通过；新增4项覆盖两组关联区结构、商户/商品跳转字段、空状态及识别请求参数保留 |
| `node miniprogram/tests/native-compile.js "D:\engineering_software\微信web开发者工具"` | 官方编译器接受21份WXML、17份WXSS |
| `node miniprogram/tests/visual-preview.cjs --character` | 23项字典页离线布局场景通过；320/375/390/430px，含正常、长文本、缺图、空状态、原生按钮样式干扰和点击命中 |
| `node miniprogram/tests/visual-preview.cjs` | 97项跨页离线布局场景通过，既有首页/地图/结果页回归保持通过 |
| `node miniprogram/tests/validate-project.js` | 18页校验通过；小程序代码汇总SHA-256：`ba6a0bfd2452d54c9e57760e41dd846714e2be3f210e6585ad67c4af09113bbc` |
| `.venv\Scripts\python.exe scripts/check_project.py` | 35项需求、证据链接、原始文档与API漂移检查通过 |

## 本轮代码指纹

| 文件 | SHA-256 |
| --- | --- |
| `miniprogram/pages/character/index.wxml` | `B0EE7C032BF202E57AFD314EF613C6DAD17125336E4F374576256C98773047CE` |
| `miniprogram/pages/character/index.wxss` | `643DB198459B35D68632F361DDADF4882D963E9EFC5D3F002E487BEAC47325A8` |
| `miniprogram/tests/character.test.js` | `054B8A1379CCE292360166F51D987BE73B2E74108B2AA4F286D3044F0D50A7B6` |
| `miniprogram/tests/visual-preview.cjs` | `317D043E3975E77A2387094E43D8A906FCEF23B528670099992DBAE6C51BD6B2` |

截图和报告保存在未提交的 `runtime/miniprogram-visual/`。这些是本地浏览器离线夹具，不是微信开发者工具真机运行、真实接口数据或正式视觉签收；本轮未上传微信、未部署服务器。
