# OPS-01 / AUTH-02 / DATA-04：合并审核发布入口（2026-09-27）

## 范围与边界

D-052：八类普通内容统一“审核并发布”，已发布行隐藏该操作；旧reviewed菜单命令不再执行。管理员和运营权限不变，商户无发布入口且后台仍拒绝发布。保留历史reviewed状态/筛选，不批量上线；不改数据库、后端业务规则、API结构、账号启用、纠错审核或其他菜单。现有未提交改动保留。

## 验证记录

- `cd web; npm test -- --reporter=dot`：84项通过（新增15项组件回归）；沙箱首次运行因esbuild子进程EPERM失败，获准沙箱外重跑通过。
- `cd web; npm run build`：类型检查与生产构建通过。
- `node web/tests/publication-browser.cjs`：5组真实Edge无界面浏览器场景通过，使用合成API：管理员草稿直接发布、运营发布旧已审核内容、已发布无审核入口、校验失败保持草稿、商户无发布入口；发布后列表刷新，均无页面脚本异常。截图及结果在 `runtime/single-publication-browser/`，已人工查看管理员菜单截图。
- `$env:DONGBA_RUN_MYSQL_TESTS='1'; .venv\Scripts\python.exe -m pytest backend/tests -q`：180通过、1跳过、1条既有Starlette弃用警告，耗时264.42秒；含隔离MySQL集成。新增14项参数化后端回归覆盖直接发布的审核人/时间、审计和版本快照、缺字形/来源/说明拒绝发布、商户双入口拒绝发布及旧已审核数据不公开。后端应用代码未改动。
- `.venv\Scripts\python.exe -m ruff check backend scripts`、`-m ruff format --check backend scripts`：通过（63个格式文件）。本轮4个Web文件Prettier检查及受影响跟踪文件 `git diff --check` 通过。
- `.venv\Scripts\python.exe scripts/check_project.py`：35项需求、证据链接、原文保护与OpenAPI一致性通过；API结构未改，无需重新导出。
- 组件与业务测试使用合成资料，不证明真实识别准确率。公网真实业务发布尚未执行，不用生产内容做写入测试。

## 服务器发布与公网验证

- 目标：`39.96.83.196` 的 `/home/admin/dongba-trail`，Nginx8080及HTTPS入口，内部API8010。发布前确认监听进程、当前首页/源码SHA256与上轮部署一致，API `/ready` 为ready。
- 发布目录：`/home/admin/dongba-releases/20260927-121927-single-publication`。沿用前端受限发布方式：以前轮完整清单叠加纠错全宽发布清单为基线，仅允许本轮ResourceView生产源码变化；逐文件校验、备份覆盖文件、保留旧hash资源、首页最后原子切换，异常可回退。
- 31个包内文件校验通过，20个文件更新。后台API PID前后均为2004689；不重启后台、不改配置/数据库/媒体；未进行数据库迁移。此前纠错详情改动保留。
- 首页、主JS、ResourceView及FeedbackView脚本分别从公网8080和HTTPS下载，8项SHA256全部与本机受测构建一致。服务器应用就绪检查通过。公网未执行真实内容审核发布写入；真实角色点击闭环由本机浏览器fixture及MySQL接口测试覆盖，不冒称线上账号验收。
- 包、清单及公网校验JSON保留于 `runtime/deploy/single-publication-20260927/`；服务器发布目录保留覆盖前备份、manifest与result.json。小程序及其他本机并行改动未纳入此次前端发布。

## 代码指纹

- Git基线：`858e99d3fdcf8a4159bfb619f76058ba256ba856`，本次交付为保留既有未提交改动的工作区快照，不将HEAD冒充完整代码指纹。
- 发布清单指纹：`021099576f5fb1db29ea1cd2b988b1b9cb34d0efdf3377ba92dc76792ed97e0b`。
- 发布包SHA256：`8783c2ab1e970d082d15c6ea46ae80519a8ac66fb967cea64b62b11cc82da57c`。

| 文件 | SHA256 |
| --- | --- |
| web/src/views/ResourceView.vue | 3cf34bbafde03663e59851ddf1c6a006331003dc76f53fea4dec901c7e6fc823 |
| web/tests/component-harness.ts | d7dedb7c8a0ff1fc81169450544b8cbda59e4c481baebc492c54c900416b494c |
| web/tests/publication-components.test.ts | 7c7856e33aa61eba8edbd12f5032d4485cbf8e8f43a9520b86d9ed1ec073cbad |
| web/tests/publication-browser.cjs | e55a6615a7843eb7aa866868afa857f1af7aa69e96330bae61be2120b20cc23b |
| backend/tests/test_single_publication.py | cba183f11ab9a0ddc8fdcf591ff1a6b6e03546cf9d7f25bc79517b78bd3cbb18 |
| web/dist/index.html | 0d22aeaa68ee3cea284c858c002f09685791f7bd5574b0abf7e32bd707ddf02f |
| web/dist/assets/ResourceView-Vx280Chf.js | 631e0f664afbb72695d010cfa26e81d18cc7e0ac1c90583f8bc6fa49f153bf22 |

本次证据仅验收D-052范围；项目其余缺口、真实识别准确率、微信真机及整体发布门槛仍独立保留。
