# 识别 token 止损、真实 usage 与服务器部署

日期：2026-10-08。范围：AI-01、AI-02、NFR-03、D-075。

## 问题与根因

用户报告服务器随便识别一次约消耗50万token。代码核对确认D-066/D-071线上路径把粗筛后的
200张128×128参考字形分别作为视觉输入，再追加1张待识别照片，共201张图片。请求中的
`max_tokens=400`仅限制输出，不能限制图片产生的输入token；此前真实请求还因图片+文字token
超过模型上限返回400。未读取、打印或保存用户提供的服务器密码。

## 有界修复

- `backend/app/glyph_refs.py`新增生产用`build_reference_sheets`：每张4列×5行、每格保留
  128×128参考字形和ASCII标准ID；200个候选完整生成10张640×800 PNG，不丢候选。
- `backend/app/volcengine_provider.py`发送10张参考对照图和最后1张查询图，共11张；文本继续
  列出每个ID与释义，明确顶部ID不是字形笔画。
- 上游返回`usage`时记录model、reference_count、image_count及prompt/completion/total token；
  不记录图片、API Key、请求头或原始响应。缺usage不伪造。
- 不改top-200粗筛、模型配置、字库、RAG、MySQL、小程序，不训练、不加GPU。

## 本地验证

| 命令 | 结果 |
| --- | --- |
| `.venv\Scripts\python.exe -m pytest backend/tests/test_recognition.py backend/tests/test_xlsx_evaluation.py -q` | 36 passed |
| `.venv\Scripts\python.exe -m pytest backend/tests -q` | 324 passed / 97 skipped；1条既有Starlette弃用警告 |
| `.venv\Scripts\python.exe -m ruff check backend scripts` | 通过 |
| `.venv\Scripts\python.exe -m ruff format --check backend scripts` | 78 files already formatted |
| `git diff --check` | 通过，仅Windows换行提示 |

回归替身验证200个候选全部进入10张参考图、查询图始终最后、总图片数11，并验证usage日志只含
计数。夹具中的24040 token仅用于日志解析测试，不是实测费用。

## 部署

目标：`/home/admin/dongba-trail`；发布备份：
`/home/admin/dongba-releases/20261008-123010-d075-token-fix`。

部署器先校验服务器旧文件指纹、`nginx -t`、唯一8010进程和迁移，再备份`.env`与两个旧文件，
停止旧进程、原子替换、运行200→10拼图探针并重启；失败会恢复旧文件。结果：

- API PID `2035148 -> 2036937`；
- packing probe：`references=200, sheets=10`；
- `/health=200`、`/ready=200`、字符接口200且`total=1403`、管理员接口未授权401；
- MySQL迁移保持`0004_rag_support (head)`；`.env`指纹保持；小程序未动；
- 本机公网严格HTTPS复核`/health`和字符接口通过。

部署文件SHA-256：

| 文件 | SHA-256 |
| --- | --- |
| `backend/app/glyph_refs.py` | `b522c21afd922e4719245021148899cae4848f1ec1a62a094582686ad56eddfc` |
| `backend/app/volcengine_provider.py` | `4335ac62ea3e2f2aeacdade015d4e21c281521ef02deeaf511b43d39d61f26b2` |

## 部署后真实止损探针

为避免继续消耗，只用既有Excel评测的第1条放大截图调用一次真实供应商，关闭RAG且不写业务库。
服务器当前运行配置实际为`doubao-seed-2-0-lite-260428`，与早前实验的turbo模型不同；本次不
擅自更改管理员当前配置。

| 项目 | 结果 |
| --- | --- |
| 参考候选 / 上游图片 | 200 / 11（10张对照图+1张查询图） |
| API usage | prompt **17,797**；completion **49**；total **17,846** |
| 相对用户报告约500,000 | 约减少 **96.4%**，约为原来的1/28 |
| 模型阶段延迟 | 8,114ms |
| 返回 | `NEED_USER_CONFIRM`，1个候选，无接口错误 |
| 正确性 | “天”未命中；正确字也未进入本地top-200 |

17,846是供应商API响应中的usage，不是费用账单；用户所述50万是用户观察值，本轮未取得旧路径
同模型usage，故不伪装为严格A/B账单。单样本仅证明部署路径可调用及token数量级已止损，不能
证明准确率。原50字拼图实验仍只有19/50 top-1，后续批量评测应先由用户确认成本预算。

原始脱敏产物位于Git忽略的`runtime/db1404/d075-server-result.json`和
`runtime/db1404/d075-probe-results.json`；不含密钥。`scripts/code_fingerprint.py`输出为
`sha256:0d8fb176dc16caba981e49546e841e8feb6aa697f59f340f14d94d0c05ad7b65`（306文件）。
`scripts/check_project.py`通过35项需求、证据链接和API检查；当前checkout缺原始DOCX，源哈希比较
按脚本规则跳过，不冒充该项通过。
