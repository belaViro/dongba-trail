# 参考字形对照识别修复（2026-10-07）

需求：AI-01、AI-02、MINI-01；决策：D-066。用户反馈：“识别效果还是不行啊，我用小程序拍照去识别‘东巴字典’里面有的字，识别不对”。

## 根因：模型从未看到过字典里的字形

修复前 `VolcengineArkProvider` 只把 `- DB1404_0001: 天` 这种“编号: 中文释义”文字目录
发给视觉模型。东巴字形与中文释义之间没有可推断的形态关系，模型无法把照片里的笔画
映射到某个 `DB1404_*` 编号，只能靠释义猜，因此必然错。

## 真实模型对照实验（非夹具）

服务器 `/tmp/dongba-vprobe-0a24c3a156`，从 80 条已发布词条随机抽样，直接调用
`doubao-seed-2-1-lite-260915`。注意：这两个探针里，查询图与它对应的参考图是**同一条目的
同一张已审核 PNG**（自匹配），因此衡量的是“模型能不能用参考字形做对照”的上限，
**不是**跨样本或实拍准确率：

| 方案 | 结果 |
| --- | --- |
| 现状：只给文字目录 | top1 **0/8** |
| 6 选 1：同时给参考字形图片 | top1 **8/8** |
| 全部 80 个参考字形一次性给出 | top1 **6/6**、top3 **6/6**，延迟 6.5–40.2s |

原始结果：`vprobe-result.json`、`vprobe2-result.json`（运行时目录，不入库）。

为补上跨样本证据，另写了真实代码路径探针 `probe3_production_path.py`：调用生产
`load_references` + `VolcengineArkProvider.recognize`，查询图取该字**另一张** variants
样本并做旋转/梯形/JPEG 劣化。该探针已在服务器隔离副本成功导入并跑通到“加载 80 张参考图、
构造请求”这一步，但所有调用返回 `403 AccountOverdueError`（见下）。

## 代码改动

- 新增 `backend/app/glyph_refs.py`：把已审核词条的 PNG 归一化为 128×128 灰度
  白底居中图（`REFERENCE_SIDE=128`、`MAX_REFERENCES=200`），带按
  `(character_id, mtime_ns, size)` 的内存缓存；单张坏图跳过，不影响识别。
- `backend/app/recognition.py`：调用 provider 前用线程池加载参考图；加载失败只记
  告警并回退文字目录，不让识别整体失败。
- `backend/app/providers.py`：适配器协议与未配置实现增加 `references` 可选参数。
- `backend/app/volcengine_provider.py`：整文件重写消息构造，改为
  “逐条「编号+释义+参考字形图片」→ 待识别照片”的多图消息；没有参考图时回退原
  文字目录提示词；`max_tokens` 300→400；上游 4xx/5xx 只记录状态码与上游错误码
  （如 `AccountOverdueError`），不打印消息与凭据。

## 验证命令

| 命令 | 结果 |
| --- | --- |
| `.venv\Scripts\python.exe -m pytest backend/tests -q` | 284 通过 / 97 跳过 |
| `.venv\Scripts\python.exe -m ruff check backend scripts` | All checks passed |
| `.venv\Scripts\python.exe -m ruff format --check backend scripts` | 71 files already formatted |
| `.venv\Scripts\python.exe scripts/check_project.py` | 35 项需求、证据链接、源文档与 API 检查通过 |

新增用例：参考图归一化尺寸/模式与缓存命中、缺失/损坏/非本站 URL 跳过、`limit=0`
返回空；夹具 provider 与管理员配置用例的 `recognize` 替身补齐 `references` 形参。

## 服务器部署（2026-10-07）

后端 4 个文件已部署到 `/home/admin/dongba-trail`，发布目录
`/home/admin/dongba-releases/20261007-155049-recognition-reference-backend`，API PID
`2030602 → 2032841`；`/health`、`/ready`、`/characters` 返回 200，admin 路由返回 401；
加载 80 条参考字形（634936 字节）。`.env`、数据库结构与迁移、`miniprogram/` 均未改动。

## 用户真机人工验收（2026-10-07）

欠费解除后用户把运行时模型由 `doubao-seed-2-1-lite-260915` 换为
`glm-5-3-flash-260828`（文本与图片调用均返回 200）。用户随后**在小程序实拍“东巴字典”
里的字，人工确认识别成功**（用户原话：“非常成功，我人工试了一下，你不用跑了”）。
该结论来自用户人工实拍，属于真实识别验收，不是夹具或探针结果。

## 未验证边界

- 自动化准确率评测（标准图/实拍评测集、top1/top3、时延与成本）仍未做；本次只有用户
  人工抽验，不代表全量或长期准确率。
- 火山方舟账号曾欠费（`403 AccountOverdueError`）阻断早期真实复测；该路径下的历史
  探针结果不作为准确率证据。
- 未做微信真机拍照/相册/裁剪的自动化验收；小程序走微信平台发布，不在服务器部署。
- 每张参考图约 7.9KB（80 张 635KB），请求体随词库扩大而增长；词库显著扩容后需重新
  评估库大小、token 上限与延迟（当前 `provider_timeout_seconds=60`）。
