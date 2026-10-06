# RAG本机闭环验证

2026-09-26执行。范围限定独立MySQL纠错案例库、运营审核/检索/图片预览、识别辅助候选、结果持久化与不可用降级；不涉及向量服务、训练、公网部署或模型准确率。最终回归代码指纹：`sha256:f15802dcc07134ed60977ad849f3671f76deb4e48d74217db3414ff2895b6e45`（243文件）。

## 已验证

- 独立MySQL业务库迁移到 `0004_rag_support`，专用RAG库和表初始化完成。
- 纠错反馈保存与RAG待审核案例为两个独立事务；反馈成功而RAG失败时业务结果仍保留，响应为明确不可用。
- 管理端支持案例录入、编辑、审核、停用、检索、重建和鉴权图片预览；未审核或停用案例不参与检索。
- 识别供应商候选可由已审核案例排序或补充，公开响应只返回安全摘要字段，保存结果记录持久化；用户确认仍必选。
- RAG库不可用时管理接口返回明确不可用；识别检索失败退回供应商候选，不伪造候选。
- 本机未配置识别供应商且无已发布字典时，`/ready`明确显示不可用，不把夹具数据当作真实识别效果。

## 执行命令与结果

| 检查 | 命令/记录 | 结果 |
| --- | --- | --- |
| MySQL集成回归 | `runtime/rag-final-backend-mysql-tests.log` | 144 passed, 1 skipped |
| 最终MySQL全量回归 | `runtime/final-regression-backend-mysql.log`、`runtime/final-regression-backend-mysql-skip-reasons.log` | 144 passed, 1 skipped；唯一skip为SQLite副本的`Backup is a MySQL-only operation`，MySQL副本已执行 |
| 静态检查 | `runtime/rag-final-ruff.log`、`runtime/rag-final-ruff-format.log` | 全部通过 |
| 最终静态检查 | `runtime/final-regression-ruff.log`、`runtime/final-regression-ruff-format.log` | 全部通过 |
| OpenAPI导出 | `runtime/final-regression-openapi.log`、`runtime/final-regression-openapi-second.log` | 连续两次导出106个路径，7个RAG管理路径齐全 |
| Web回归 | `runtime/final-regression-web-tests.log` | 5个文件、58项通过 |
| Web构建 | `runtime/final-regression-web-build.log` | 构建通过 |
| 小程序回归 | `runtime/final-regression-mini-tests.log`、`runtime/final-regression-mini-validate.log` | 23项通过；18个原生页面静态校验通过 |
| 启动检查 | `runtime/final-clean-backend.*.log`、`runtime/final-clean-web.*.log` | 8010/5173均监听；日志无启动异常 |

## 最终启动与HTTP检查

- 清除旧测试进程后从干净状态启动 `scripts/serve.py --port 8010` 和 Vite 5173；两个端口分别由本轮新进程监听，日志显示FastAPI startup complete和Vite ready。
- `/health`返回200；`/api/v1/characters`与`/api/v1/map/pois`返回200（开发库为空）；`/api/v1/public/map-config`返回200；`/openapi.json`返回106个路径；Web `/login`和`/admin/rag-cases`返回应用入口200。
- `/ready`返回预期的503 `PROVIDER_NOT_CONFIGURED`、`DICTIONARY_NOT_READY`，与开发库未配置供应商、未发布字典一致；不把该状态当作RAG或业务服务不可用。
- 未登录访问`/api/v1/admin/rag/cases`返回401 `AUTH_REQUIRED`。本机开发库`setup_required=true`，本轮不创建测试管理员，因此未执行登录态管理页浏览器验收；该边界不影响接口、服务和已鉴权管理链路的自动化证据。

管理端流程和HTTP字段约定见 [RAG契约](../contracts/rag.md)。测试覆盖识别、检索、保存与确认链路，但不证明真实模型准确率。
