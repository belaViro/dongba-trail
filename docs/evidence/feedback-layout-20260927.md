# 纠错审核排版、实时维护状态与选填说明（2026-09-27）

范围：FEEDBACK-01 / DATA-03 / OPS-03，决策D-049。本次不修改小程序首页等并行改动，不宣称真实识别准确率或发布就绪。

## 实现

- 桌面1080px双栏详情：左侧附图/识别/反馈，右侧核验或审核记录/RAG维护；底部固定采纳、驳回按钮，手机堆叠。列表突出用户反馈，识别UUID降为辅助信息。
- 审核结果和当前RAG状态独立；列表按当前页一次查询独立案例库，返回rag_status、rag_case_id、rag_updated_at。缺库显式unavailable。
- 停用、重新启用和重建索引先应用服务端响应，再同时读取列表/详情。保留已确认结果，旧请求不能覆盖；读取失败分别提示。刷新按钮同时更新已打开详情。
- 核验说明和驳回原因前后端均选填；省略/空串/空白可驳回，不生成默认原因。采纳仍校验正确词条；停用原因和其他业务审核约束不变。

## 验证

- `$env:DONGBA_RUN_MYSQL_TESTS='1'; .venv\Scripts\python.exe -m pytest backend/tests -q`：166 passed / 1 skipped，297.84秒。包含业务MySQL与独立RAG MySQL集成；SQLite仅隔离单测。覆盖省略/空/空白拒绝说明、采纳→停用→重建索引、列表详情一致、RAG缺库、鉴权，保留原审核结果。
- `.venv\Scripts\python.exe -m ruff check backend scripts`：通过；`ruff format --check backend scripts`：62文件通过。
- `.venv\Scripts\python.exe scripts/export_openapi.py`：107路径生成；`scripts/check_project.py`：35项需求、证据及契约一致性通过。
- `cd web; npm run test`：6文件67测试通过（反馈组件9项）；`npm run build`：vue-tsc和Vite构建通过。组件覆盖操作后双端刷新、失败保留确认状态、无说明驳回和保留填写说明。
- `node web/tests/feedback-image-browser.cjs`：11项真实Edge浏览器检查通过，API/图片为合成夹具，不是实拍识别证据。原图blob正常、无图及403重试、桌面双栏、手机堆叠/边界、采纳/停用/启用/重复重建、列表状态与更新时间、空说明驳回均通过。首次手机测量落在抽屉入场动画中，修正为等待动画结束后重测通过。
- 截图位于runtime/feedback-image-browser/：visible.png、maintenance-desktop.png、list-desktop.png、review-mobile.png；已人工查看桌面与手机布局。
- 本次5个源码/测试文件指纹：4b16314b7c49b2d167ad4ff43b36b3a5c0d6b7b4c8adfe739dc1a0caedef1c80。清单保存在runtime/feedback-layout-code-manifest.json。

## 发布

- 已发布到39.96.83.196的`/home/admin/dongba-trail`，Nginx继续监听8080，API监听8010；发布目录`/home/admin/dongba-releases/20260927-111341`，新API PID为2004689。迁移保持0004_rag_support，107条OpenAPI路径。
- 204个包文件逐一校验通过；与前一发布相比，业务源码只改变backend/app/business/api.py、backend/tests/test_rag.py、web/src/views/FeedbackView.vue。另含本次前端测试、构建和文档。未部署小程序并行改动，未改动服务器环境配置。
- 发布前备份17业务表、1744行和356个媒体文件，并另备份1条现有RAG案例。旧代码和数据库/媒体备份均保留；没有对生产反馈执行测试性采纳、驳回、停用或重建。
- 8080及HTTPS鉴权列表均200，各逐条核对7条反馈详情，审核结果、rag_status、rag_case_id、rag_updated_at一致；当时1条indexed、6条not_indexed。匿名列表401。临时5分钟运维会话已在finally删除并再次确认不存在。
- 内部8010真实`/ready`返回200 JSON；公开首页、健康、词条、地图接口正常。IP:8080和HTTPS首页及新版FeedbackView脚本均与本地构建SHA256相同。
- 本机HTTPS初次因Windows沙箱Schannel凭据错误失败，授权在沙箱外重试后通过；未关闭证书验证。一次等待中的SSH会话因暂停而关闭，后续新会话校验成功，未重复发布。
- 包SHA256：`4deaf06ca208e0d21220bdbd57d968eb7253de1242e7d6e411a096b8ebb67b58`；204文件清单指纹：`63dc9e746a8c29f4c023934165ac3583905d5ea0f2f9fb18aba37775c8008f9e`。
- 首页SHA256：`654440d9f06c63c4c61ced6010c4873dacc0435b2b0007a33b88425f5de49bd7`；FeedbackView-CpzBZ_lZ.js：`8341b7c76d13313b886e3a01c7db8bfb340b9543f674f73691df1ca19e351aab`。
- 服务器证据：发布目录内`result.json`和`feedback-layout-checks.json`；本机发布包及清单：runtime/deploy/feedback-layout-20260927/。本节和本地状态是在上线校验后补记，不计入此前封存的发布包哈希。
- 完整操作闭环由专用MySQL集成及真实浏览器合成数据回归证明；生产环境只做鉴权读取/资产校验，不把这些证据宣称为真实识别准确率、微信真机或全部业务验收。
