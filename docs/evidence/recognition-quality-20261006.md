# 拍照识别质量修复与四角框选（2026-10-06）

需求：MINI-01、AI-01、AI-03；决策：D-065。用户反馈 #1-#4，明确本轮不做 #5
字库扩充与 #6。

## 范围与实际改动

- #1 拍照参数：小程序新增 `pages/capture/index`，用原生 `<camera resolution="high">`
  和 `takePhoto({quality:'high'})` 取原图，相册用 `chooseImage({sizeType:['original']})`；
  本地按长边 ≤1200px 等比缩放，**只降不升**（`utils/image.js` 的 `targetSize`）。
  后端 `quality_min_edge` 96→200，低于阈值返回 `IMAGE_TOO_SMALL` 而非对模糊图强给候选。
- #2 结果漂移：`backend/app/rag.py` 的 `apply_hits` 改为只追加不前置。provider 有候选时
  保持其顺序，RAG 仅在分数 ≥`MIN_APPLY_SCORE`(0.45) 且提供 provider 未返回的已发布词条时
  追加；弱命中不引入；仅真正贡献新候选才 `applied=True`。避免全体用户累积纠错污染新图片。
- #3 参考分数：结果页“参考分数”改为“候选参考”档位（较高/中等/较低），`helpers.score`
  非数值返回空串、clamp [0,1]，页面明示分数未经准确率校准、收藏词条不确认识别。
- #4 四角框选与相册：相机页叠加四角取景框，拍后进入裁剪视图可拖动整体与四角
  （`MIN_FRAME=80`，clamp 到图片边界）；确认时换算回原图坐标后裁剪再上传。首页新增
  相册入口，`utils/recognition.js` 统一跳 capture 页。
- 边界：`MIN_SOURCE_SIDE=200` 与后端阈值同步，裁剪过小在客户端先提示，不再上传后才失败；
  从相册入口重拍会重置 `source` 为 `camera`，避免场景误标。

## 验证命令

| 命令 | 结果 |
| --- | --- |
| `.venv\Scripts\python.exe -m pytest backend/tests -q` | 282 通过 / 97 跳过 |
| `.venv\Scripts\python.exe -m ruff check backend scripts` | All checks passed |
| `.venv\Scripts\python.exe -m ruff format --check backend scripts` | 70 files already formatted |
| `node --test --experimental-test-isolation=none miniprogram/tests/*.test.js` | 170 通过 / 0 失败 |
| `node miniprogram/tests/validate-project.js` | 19 页、路由与事件绑定通过 |
| `.venv\Scripts\python.exe scripts/check_project.py` | 35 项需求、证据链接、源文档与 API 检查通过 |

小程序新增用例：`utils/image.js` 的 fit/targetSize/info/crop 4 项；capture 页
相册原图裁剪、相机全分辨率确定性取景、四角拖动边界钳制各 1 项；RAG 记忆不越权前置 1 项。

## 指纹

小程序汇总 SHA-256（validate-project 输出）：
`5950e0dae544b8fe617a9b7e50d22fbe7ea0a2e25a35a1277b94ed2dc832f92c`

| 文件 | SHA-256 |
| --- | --- |
| `backend/app/rag.py` | `982a2015235f719aef311d96c038b3246c3113806129e2d63bccf1b60f34e1de` |
| `backend/app/config.py` | `d0862a23fb7f5765aff862853098f6c3653f4e1f7ac8a6fd67318e3f035b7114` |
| `backend/app/volcengine_provider.py` | `2c8f4e9c3b67cb43f7f6de599714a4de2f571d85dd1df35eb1ad8222607e356a` |
| `miniprogram/pages/capture/index.js` | `927fcbd2c7a23b7a8f819b23df6e704a02408e4948e18d4d5e3791801c606bc5` |
| `miniprogram/pages/capture/index.wxml` | `65886f91dbf5fbffe446ad16b4feead5337cceb0b5f0f1bdda3b7fcc55ac2091` |
| `miniprogram/pages/capture/index.wxss` | `f367e36c1b329d532e17b794c3d1ea7db6be46d969d55c7111b59cd64396286f` |
| `miniprogram/utils/image.js` | `130bdd84057096223eb579ad80cca4b67f7641c3aaaf6acc24f1f328a5f2491a` |
| `miniprogram/utils/recognition.js` | `2101fccf5845851504e424cbd4a32c0d9136844e36262af3aa92d827363a8c33` |
| `miniprogram/utils/helpers.js` | `7e7143654415ef95fef2931f263331e987782914734dca0bd6c47acd219d2338` |

## 未验证边界

- 夹具与离线测试**不代表真实识别准确率**；未跑真实模型评测。
- 未做微信真机相机/相册/裁剪验收，需微信开发者工具重新编译并上传体验版。
- 本地 MySQL 未运行（127.0.0.1:3307 拒连），真实识别链路与数据库写入未复验。
- #5 字库量少导致的“未找到可靠结果”按 AI-03 保持明确拒识，不在本轮扩充词库。
