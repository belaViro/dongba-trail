# DB1404 50图小程序裁剪结果模拟复核（2026-10-08）

关联：AI-02、MINI-01、D-080。

## 边界

- 输入为`东巴字图片_按中文含义命名/`中的50张JPG；它们与`寻迹东巴新数据统计(1).xlsx`的50张B列输入逐字节一致，文件名/工作表D列为预期中文含义。
- 小程序相册流程以原图选取、用户框选、JPEG质量0.95上传，长边超过1200时才缩小；后端质量门要求短边至少200px。这批原图46/50低于200px，且默认72%方框下50/50均不足200px，不能作为真实小程序原图直传而不被拒绝。
- 为复核识别算法而模拟“用户已得到可上传裁剪结果”，本次使用既有长边512、JPEG质量95归一化输入，业务语义为`scene=album`。在服务器隔离进程中复用当前线上识别提供方、发布字典、多原型粗筛和10张对照图；关闭RAG，不创建测试账号，不经过公开HTTP认证，不写生产识别历史。
- 因此结果是**小程序裁剪结果模拟**，不是微信真机、实拍照片或原始小图直传准确率。外部供应商真实调用不能由夹具测试替代，但也没有验证小程序网络/登录/结果页跳转。

## 运行控制

- 首次启动要求模型`doubao-seed-2-0-lite-260428`，服务器报告实际配置为`doubao-seed-2-1-pro-260915`，评测在首次调用前因模型指纹不符停止；旧目录结果未覆盖。
- 新建批次`xlsx-current-miniprogram-20261008-pro`并锁定实际模型；首条失败即停、连续三条错误即停。本轮50条无错误，全部完成。
- 原始脱敏结果保存在本地被忽略的`runtime/db1404/xlsx-current-miniprogram-20261008-pro/results.json`。文件记录代码哈希、输入哈希、模型、候选、短名单和时延，不含服务器密码、API密钥、图片base64或供应商原始响应。
- 供应商适配器未返回账单费用；不得用本结果推断实际金额。

## 结果

| 指标 | 结果 |
| --- | ---: |
| 完成 | 50/50 |
| Top-1 | 25/50（50%） |
| Top-5 | 30/50（60%） |
| ERROR | 0 |
| UNKNOWN | 0 |
| 字典覆盖 | 50/50 |
| 模型阶段平均时延 | 8491.9ms |
| 当前服务器粗筛Top-200命中 | 30/50 |
| 原图质量门 | 4通过、46 `IMAGE_TOO_SMALL` |

Top-1错误25字：天、月、雨、地、山、风、亮、深、柴、草、粗、叶、人、立、起、跌、抖、懒、舞、举、得、死、躲、抬、靠。

当前服务器批次的短名单召回30/50，与D-077同50图本地集成复核42/50不一致。外部模型只能从短名单中选择，至少20条不具备选中正确ID的条件；在确认服务器资产版本和输入口径差异前，不能把25条Top-1错误全部归因于模型，也不能宣称多原型已达到此前本地召回。

## Excel产物

- 文件：`东巴字图片_按中文含义命名/东巴字识别结果_小程序模拟_20261008.xlsx`
- SHA-256：`CF36ECA044B2ACE5E2192F4E587A0053921147794B0960F292440396E9BD92ED`
- 大小：8,799,117字节。
- 基于原工作簿副本，仅改写`xl/worksheets/sheet1.xml`，新增O:X列：当前Top-1、当前Top-5、Top-1/Top-5正确性、短名单命中/排名、状态、模型、时延和运行说明。
- ZIP完整性通过，`xl/cellimages.xml`仍存在，工作表范围为`A1:X301`，50行Top-1正确计数为25。通用库未重建工作簿，避免丢失WPS `DISPIMG`图片扩展。

## 验证

```text
.venv\Scripts\python.exe -m pytest backend\tests\test_xlsx_recognition_export.py backend\tests\test_xlsx_evaluation.py -q
8 passed

.venv\Scripts\python.exe -m ruff check scripts\export_xlsx_recognition_results.py backend\tests\test_xlsx_recognition_export.py
All checks passed

.venv\Scripts\python.exe -m ruff format --check scripts\export_xlsx_recognition_results.py backend\tests\test_xlsx_recognition_export.py
2 files already formatted

.venv\Scripts\python.exe -m pytest backend\tests -q
337 passed, 97 skipped, 1 warning

.venv\Scripts\python.exe -m ruff check backend scripts
All checks passed

.venv\Scripts\python.exe -m ruff format --check backend scripts
87 files already formatted

.venv\Scripts\python.exe scripts\check_project.py
Project checks passed: 35 requirements, evidence links, source and API

git diff --check
通过，仅有既有Windows CRLF提示
```

测试覆盖完成状态门槛、序号/中文映射、结果列写入、WPS图片部件保留和不完整结果拒绝。测试使用合成结果，只证明导出逻辑，不作为真实识别准确率证据。
