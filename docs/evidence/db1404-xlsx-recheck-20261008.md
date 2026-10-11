# Excel 50 字重新核验：原表纠正、服务故障与豆包复测

日期：2026-10-08。范围：AI-01、AI-02、AI-03、DATA-01、D-072/D-073。
本轮任务：以用户现有 Excel 的 50 张 B 列图为输入，读取服务器当前发布字库与运行时提供方，记录真实模型返回；不修改线上业务代码、数据库、环境配置或小程序。

## 已核实的原表与历史结果

- 原文件 `寻迹东巴数据统计.xlsx` SHA-256：`b71067e68524f506367985eb5853d7c196b4529ab5c8f3f8bf5cef8bb1ba7e94`。
- 表中 G 列为 **10 条“否”、40 条“是”**，原表记录正确率为 10/50=20%；此前报告的“47 条错误”是统计笔误。
- 重新从 WPS DISPIMG 提取 B 列，未将 E 列识别结果截图当作输入；与历史清单的编号、释义、G 列及尺寸逐条相同，重新放大得到的 50 张 JPEG 与历史输入逐字节一致。
- 原图最小边 61–224px：**46/50** 在现行质量门返回 `IMAGE_TOO_SMALL`，4/50 通过；此前“全部生产会拒绝”不准确。
- 服务器发布字典为 1403 条；50 个期望释义均可对应至少一个已发布 ID。按同名释义命中计分，**并未由文化专家逐一消除同名异义**。
- 历史服务器 `results-1-50.json` 下载内容与本地逐字节相同：首选 22/50=44%，前五候选 26/50=52%，UNKNOWN 1、错误 0，模型记录均为 `glm-5-3-flash-260828`。
- 历史模型调用时延：均值 7066ms、中位 5975.5ms、P95（nearest rank）7983ms、最大 55531ms。不含提前单独加载参考字形的耗时，不等于 HTTP 全链路时延。

## 11:10–11:11（北京时间）GLM 重跑：模型服务不可用

实际运行时间 UTC `2026-10-08T03:10:54.516673+00:00` 至 `03:11:32.616663+00:00`。
运行时模型仍为 `glm-5-3-flash-260828`，60 秒超时，1403 条发布字、200 张参考图、RAG 关闭。

- 50/50 调用失败，业务错误 `PROVIDER_UNAVAILABLE`；提供方日志仅提取状态和错误代码：**HTTP 403 / AccountOverdueError × 50**。
- **不能将此报告为模型准确率 0%**：没有成功的模型响应，当前识别准确率不可测。该时段属于服务可用性失败。
- 50 个正确释义均在发布字库；其中只有 30/50 出现在实际 200 张参考短名单中，漏召回仍为 20。
- 通过 SSH 严格验证已知主机密钥；密码只经隐藏输入使用；不打印/读取配置秘密，应用自行加载服务器配置用于调用。只新增独立运行目录，没有写业务库或部署应用。
- 启动传输工具等待 shell 输出超时，但远端作业确实完成；通过下载 `complete=true`、50 条结果及起止时间确认，**没有重复启动**。

该阶段冻结的逐条证据：[JSON](db1404-xlsx-recheck-20261008.json)、[CSV](db1404-xlsx-recheck-20261008.csv)。
JSON SHA-256：`44b2ee940c1e532a90b4d4f9e3c28565fbeb3d774520d812aaa9d1bc3f4b9621`。
服务器原始结果 SHA-256：`b583c699827f56d663c0f7306ec5e91e8e7a1c3a96c46c3db65b1dbd2cb032ce`。
历史原始结果 SHA-256：`32d5fc396d326b58013199c73b036e235f964c730aad8ebaf614669ee2078bf9`。
当时评测脚本 SHA-256：`33f31833ab2d0cae7b847c0018d99c23120eb5c52c08a314ef374f969ed8544f`。
该阶段代码指纹为 `1f78d5b871ed4729c9769ff5a12cdfed37e8fecaf8e6b7a3ac79f935ebad9ee4`（305 文件），对应新增 3 项评测记账测试；321 passed / 97 skipped。随后脚本加入首个请求失败停止机制，最终代码与验证见下文。

## 用户更换豆包后的复测

用户最终明确模型为 `doubao-seed-2-1-turbo-260628`，替代中途提到的 GLM5.2。新评测使用独立 `runtime/db1404/xlsx-doubao-20261008/`，不覆盖故障记录或历史结果。
新增运行时模型一致性校验、首次失败停止、连续三次失败停止；探针计入同一50条计划内，不额外调用。

**11:19–11:20（北京时间）结果：配置一致，但首个请求404 / ModelNotOpen，停止剩余49次。**
UTC起止 `2026-10-08T03:19:54.726519+00:00` — `03:20:07.576600+00:00`；计划50、已尝试1、失败1，`complete=false / stopped_reason=first_probe_failed`。此状态是主动停止的不完整评测，不是程序仍在运行。
模型ID与用户指定一致，字库1403、参考图200；当前请求业务返回 `PROVIDER_UNAVAILABLE`。错误通常意味着当前账户/接入点未开通或模型ID与接口不匹配，未据错误代码推定具体计费/权限原因。需在当前供应商控制台核对开通权限及可用ID；本次未修改或自动替换模型。
**豆包准确率不可测，不是0%，也不能沿用历史GLM的44%/52%。**

豆包原始响应摘要、全部31份服务器业务Python代码哈希及停止记录见[冻结JSON](db1404-doubao-probe-20261008.json)。业务代码与本地逐份核对一致。
该JSON SHA-256：`d438d5506e215f4bc74e9574baaa0049d6e2d2cb25e8386a4b6e3c94e9e28916`；远端原始结果 SHA-256：`27bfbc518e16e0df31bc3976035d98aa0964865b99b85560801a811bc1651763`；本次评测脚本 SHA-256：`3494a831c3145a7432c8c3abc00b3363b547154922e54ab87b803bc2c0b5afa3`。

## 最终本地验证

- 后端回归：**322 passed / 97 skipped**，128.51秒；1项Starlette弃用警告。跳过项未验收，本次未执行新增MySQL业务集成测试。
- `ruff check backend scripts`：通过；`ruff format --check backend scripts`：77文件通过。
- `check_project.py`：35项需求、证据链接及API一致性通过；该checkout未找到原始DOCX，原文哈希比较被跳过，不能宣称已验证原文未变。
- 最终代码指纹：`sha256:38a54a95d0defe6e772c5ea47abba74831882bb7f9d4f4686cb138f40c5367d8`，305文件。代码指纹不含Markdown/证据JSON，输入和远端结果另以上述哈希绑定。

## 复现与边界

```powershell
.venv\Scripts\python.exe -X utf8 scripts/evaluate_db1404_xlsx.py prepare 寻迹东巴数据统计.xlsx runtime/db1404/xlsx-doubao-20261008
.venv\Scripts\python.exe -X utf8 -m pytest backend/tests -q
.venv\Scripts\python.exe -X utf8 -m ruff check backend scripts
.venv\Scripts\python.exe -X utf8 -m ruff format --check backend scripts
.venv\Scripts\python.exe -X utf8 scripts/check_project.py
.venv\Scripts\python.exe -X utf8 scripts/code_fingerprint.py
```

`prepare` 拒绝覆盖既有输出目录；再次复现须指定新的目录。在服务器项目根目录使用服务器虚拟环境运行：
`./.venv/bin/python -X utf8 <bundle>/evaluate_db1404_xlsx.py evaluate <bundle> --expected-model doubao-seed-2-1-turbo-260628`。

- Excel 图只在评测副本中等比放大至长边512px，不增加笔画细节；原图质量门另记。调用真实 `recognize()`，但绕过 HTTP 鉴权、质量门、识别历史写入和 RAG；**不是微信真机准确率、不是全字库1403类准确率**。
- 同一小样本单轮结果有抽样及模型波动，不能代表训练泛化或生产 SLA。原表主观错误标记与本轮标准释义匹配口径不完全一致。
- 费用未由现有适配器返回，记为未知，不声称免费或估造成本；未读取账单、未修改密钥、未充值。
- 未调整短名单、参考图或提示词；文化文本批准、实拍评测、微信全链路、账单验证仍未验收。
- 新增脚本测试只验证图片提取与统计/停止规则，不证明真实识别能力；业务 HTTP 契约未变，无须重新生成 OpenAPI。
