# 原文核对验证记录

日期：2026-09-23。对应 [原文核对报告](../source-audit.md) 和D-016；本次不修改业务代码或业务数据库，不执行正式部署。

## 原文复读

执行：

```powershell
.\.venv\Scripts\python.exe scripts/extract_requirements.py 'D:\MyCode\aaaa5k项目\东巴寻迹-丽江-研发需求与技术设计说明书-V1.0(4).docx'
```

结果：1010个有文本段落、45张表格、20个实际PNG媒体文件。覆盖第1至25章及附录；通过4张缩略图汇总另行查看全部20张原文配图。
提取脚本原先把ZIP内 `word/media/` 目录项计入图片，本次改为忽略目录，图片数由21纠正为20。
文本提取工具本身不做图片视觉验收，因此 `source-manifest.json` 中关于文本提取限制的提示仍有效。

源文件SHA-256保持：`120955debd76095f4fac72fca511b9579db16fcea9282c1e3cc567051796102f`。
原DOCX未编辑。提取文本、清单和报告属于派生产物。

## 只读实现核对

除了阅读实际模型、路由、前端与测试，还通过运行时Python对象检查字段和表注册信息，无需连接数据库：

| 检查对象 | 观察结果 |
| --- | --- |
| `CharacterInput.model_fields`及验证器 | 缺 `source_no`、`alias`、`keywords`、`commercial_tags`；逐项均被 `extra_forbidden` 拒绝 |
| `RESOURCE_SCHEMAS` | 只有activities、characters、merchants、pois、products、coupons、quests、quest-nodes，无samples |
| `EXPORTS` | 只有audit、characters、feedback、recognitions、tag-claims，无样本导出 |
| `RecognitionRecord`与`Feedback`列 | 没有原图URI、样本ID或图像关联 |
| `Entity`列及更新逻辑 | 保留当前data和最后审核时间，更新覆盖当前JSON；审计没有历史内容快照 |
| `ProviderResult.model_fields` | 仅candidates及model_version，无bbox或分目标结果 |

临时检查脚本、观测JSON和配图在忽略目录 `runtime/docx-audit/`；报告中的结论同时引用实际源码和原文，不依赖该临时目录保留才能理解。

## 本次执行的检查

| 命令 | 结果与边界 |
| --- | --- |
| `node --test --experimental-test-isolation=none miniprogram/tests/helpers.test.js miniprogram/tests/services.test.js` | 审计分支重跑22项全部通过；不覆盖本次发现的全部原文缺口 |
| `.venv\Scripts\python.exe -m ruff check backend scripts` | 全部通过 |
| `.venv\Scripts\python.exe -m ruff format --check backend scripts` | 40个文件符合格式 |
| `.venv\Scripts\python.exe scripts/check_project.py` | 35项需求编号/证据链接/源文件哈希/OpenAPI一致性通过；不是全部业务验收 |
| `.venv\Scripts\python.exe scripts/code_fingerprint.py` | 182文件，当前指纹见下 |

没有重跑后端MySQL全量测试、Web浏览器测试、真机或正式部署。业务实现未改变，无须将历史全套验证重复描述成此次执行。

## 代码与证据版本

历史集成证据对应：

`sha256:403581abf70f8c3aaa0bf460991de94cfb35787d037b660735a667d5e62db5b5`，182文件。

本次工作区指纹：

`sha256:3302264af80b01c535cffbcdb99d0a18dd7740a603b6898b1307f7e4d8e3256f`，182文件。

本轮纳入代码指纹的变更为 `scripts/extract_requirements.py` 的媒体目录计数修正；文档/图示修正不改变应用运行行为。
指纹工具排除Markdown与运行目录，不包括原文报告本身；DOCX另以源文件哈希追溯。
未改写历史证据的指纹，也不声称新指纹已重跑全部历史业务测试。

## 状态修正

- 原33项基线补回DATA-03图片样本运营和DATA-04文化数据版本，共35项。
- 原文核对记录11组确定业务差异，分别列原文短引、章节/行号、实际代码、影响及关闭条件。
- 更新需求、验收、状态、决策、实施安排、README、设计/发布说明及集成证据范围；图11同步撤回样本数据被排除的说明。
- 保留模型配置占位、MySQL、自训练退出首期及业务优先的用户决定；不将原文建议、示例数量或未取得的真实资源伪装成已经验收。
- 核对结束时这些产品缺口尚未修复，继续开发应从报告中的关闭条件恢复。
