# RAG纠错案例库（D-042 / D-046 / D-049 / D-054）

范围：AI-01、AI-03、FEEDBACK-01、OPS-03。这是已审核纠错记忆的词面检索与候选辅助，不是向量数据库、训练或模型生成文化内容。生成的HTTP契约以 `openapi.json` 为准。

## 数据与状态

- 业务库保存词条、样本、反馈、识别记录；独立MySQL库 `rag_cases` 保存原始文本、纠正文本、词条ID、关键词、来源、样本引用、审核状态及检索计数。不得配置成同一个业务库。
- 用户反馈默认 `pending`。`PATCH /admin/feedback/{id}` 的 `approved` 操作直接生成 `indexed` 案例，不再二次审核或发布；`rejected` 不写RAG。两种操作的 `review_note` 均选填，省略、空串或纯空白均保存为空串；不编造默认原因。可由运营传入已发布的 `character_id` 核验纯文字纠错或纠正原候选，采纳仍要求有效词条。
- 反馈完成后决定不可反向修改；同一采纳请求可以重试补同步，按识别请求去重且不静默撤销停用。`GET /admin/feedback/{id}` 返回原识别、附图、案例和RAG状态；列表保留原分页/筛选，新增 `rag_status`、`rag_case_id`、`rag_updated_at`，只对当前页批量查询RAG。缺库或读取失败标明 `unavailable`，没有案例标明 `not_indexed`。详情同时提供这三个字段。
- 审核结果与当前生效状态语义独立：列表分列、详情以紧凑组合状态显示；停用后反馈仍是 `approved`，RAG是 `deprecated`；重新启用/重建索引后显示服务器返回的状态及更新时间。Web先应用操作响应，再同时刷新列表和详情；刷新失败保留已确认状态并提示失败，不被操作前发起的旧请求覆盖。刷新按钮同时刷新已打开详情。D-049仅取消反馈核验/驳回说明必填，停用原因及其他业务审核约束不变。
- 只有 `approved`/`indexed` 参与检索；来源为反馈的案例还必须在业务库具有已采纳且词条一致的反馈。`draft`/`pending`/`rejected`/`deprecated` 均不参与。旧手工案例保留维护接口，但不能借旧接口编辑/再次审核反馈来源的案例。
- 创建、编辑和批准时检查关联词条已发布；识别时再次过滤未发布/失效词条。检索分数不是准确率；最多输出5个候选，不自动确认。
- 中文按单字匹配、英文按词匹配，结合查询覆盖和完整子串计分。同步重建 `search_document`，不启动后台索引任务，不引入额外服务。

## 纠错审核界面（D-054）

- 详情统一使用右侧宽抽屉，桌面最大1120px、移动端满宽；一个关闭入口，列表保持挂载，关闭后保留筛选和操作焦点。
- 主体保留附图、用户反馈、原识别、正确词条和选填备注；已完成详情不展示空说明，编号/时间等次要信息默认折叠，不以内部词条ID代替名称。
- 审核及维护请求期间阻止重复操作和关闭；响应后沿用列表、详情同步刷新及旧响应保护。停用/重新启用/更新识别参考/删除附图在更多操作中按权限与状态显示，停用原因只在执行时必填，取消不发请求。
- 无附图、图片访问失败和识别参考不可用继续明确区分，不伪造状态或静默隐藏故障。仅界面变更，HTTP契约和后端规则不变。

## 接口

所有 `/api/v1/admin/rag/` 接口要求运营权限：

- `GET cases`：q/status/character_id/scene/offset/limit筛选；`GET stats`：状态计数。
- `POST cases`：已弃用，有效手工新增请求返回409 `RAG_FEEDBACK_WORKFLOW_REQUIRED`，新案例只从反馈核验进入。
- `PATCH cases/{id}`、`POST cases/{id}/review`：仅兼容旧手工案例维护；对反馈来源返回409，不允许绕过统一核验。
- `POST cases/{id}/deprecate`：reason必填；`POST cases/{id}/reindex` 和 `POST rebuild` 同步完成。单条反馈案例重新索引必须核对已采纳反馈和已发布词条，明确操作可以重新启用已停用案例；批量重建不提升未审核/停用案例权限。
- `POST search`：text、limit（1–50）；返回有匹配词和分数的审核案例。
- `GET cases/{id}/image`：从业务库解析sample_id，再读受控媒体文件；鉴权获取，已删除样本返回404，不到RAG库查业务样本。

识别供应商可返回 `observed_text`、`keywords`、`scene`；系统据此查记忆并排序/补充字典候选。公开识别响应增加 `observed_text`、`rag_applied`、`rag_hits`；hits仅含 `id/character_id/score/matched_terms`，不泄露其他游客文本、图片和审核信息。业务记录保留观测文本与公开命中信息。

## 配置与失败

- `DONGBA_RAG_DATABASE_URL` 留空可关闭RAG；启用时用独立 `mysql+pymysql` 库。SQLite仅用于隔离单测。
- 管理接口缺库/缺表返回503 `RAG_DATABASE_UNAVAILABLE`；图片无效返回404 `RAG_IMAGE_UNAVAILABLE`。配置缺失或初始化失败不会伪造案例数据。
- 识别检索失败保留供应商候选；供应商本身未配置/失败仍按原识别错误处理，RAG不能替代供应商。
- 两库无分布式事务：锁定反馈，先提交RAG索引，再提交业务采纳。RAG写失败返回503，待处理反馈保持原状；业务提交失败可能留下RAG孤立行，但检索必须核对业务采纳状态，因此不会影响识别，重试可修复且不重复创建。不能将此描述为跨库原子事务。已采纳的历史反馈补同步失败不撤销原决定；详情明确显示不可用/待同步，没有自动重试队列。

## 本机运行

项目根目录执行（使用项目虚拟环境）：

```powershell
.venv\Scripts\python.exe scripts/mysql_local.py
.venv\Scripts\python.exe -m alembic -c backend/alembic.ini upgrade head
.venv\Scripts\python.exe scripts/init_rag_database.py
.venv\Scripts\python.exe scripts/serve.py --port 8010
```

另开终端：

```powershell
cd web
npm run dev
```

Web默认地址 `http://127.0.0.1:5173`；运营登录后访问 `/admin/feedback`。原 `/admin/samples` 和 `/admin/rag-cases` 重定向到纠错审核，独立样本/案例录入界面不再打包到生产入口。先发布有来源的词条，再核验用户纠错并采纳入RAG；详情可查看/删除附图及停用/重新索引。真实拍照识别另需供应商配置及微信端联调，不得用测试凭据/虚构内容冒充正式数据。

`mysql_local.py` 为本机开发环境创建 `dongba_rag` 和专用 `dongba_rag_test` 并更新忽略的配置，勿用于代替服务器部署。已有部署应备份后执行业务迁移与独立RAG初始化，重启API。2026-09-27公网独立RAG库已完成初始化和连接验证，详见[服务器配置修复](../evidence/rag-server-config-20260927.md)；案例内容及审核仍由运营维护。
