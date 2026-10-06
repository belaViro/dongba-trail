# 单次纠错核验（D-046）

日期：2026-09-27。需求：FEEDBACK-01、DATA-03、AI-01/03、OPS-03。

## 交付范围

- 采纳前必须核验一个已发布词条；纯文字反馈允许运营选择原候选之外的正确词条。采纳一次直接索引，驳回必须有原因且不写入RAG。
- 行锁保护反馈决定；索引失败不提交待处理反馈的采纳。跨库业务提交失败留下的孤立案例被检索资格检查排除，重试按识别请求更新原行；不声称跨库原子事务。
- 后台入口合并为纠错审核，附图、原识别、处理意见和RAG状态同页；保留图片删除，取消正常数据集运营入口；已采纳案例可停用及明确重新启用。
- 手工新增RAG接口关闭；旧手工案例和样本数据不删除。旧案例接口不能对反馈来源再次审核/修改。普通字典/活动的审核发布不属于本次精简范围。

## 验证与发布

已完成本机验证并部署到服务器 `39.96.83.196:8080` / `https://www.liorah.top`。本次发布没有修改小程序源码或服务器环境配置。

| 命令 | 结果 |
| --- | --- |
| `.venv\Scripts\python.exe scripts/mysql_local.py` | 本机MySQL 8.0.44恢复运行；使用独立dongba_test / dongba_rag_test验证，不读取或输出凭据 |
| `DONGBA_RUN_MYSQL_TESTS=1 .venv\Scripts\python.exe -m pytest backend/tests -q --tb=line` | 150通过、1项设计性跳过，252.41秒；SQLite单测及真实MySQL集成均运行 |
| `.venv\Scripts\python.exe -m ruff check backend scripts` | 通过 |
| `.venv\Scripts\python.exe -m ruff format --check backend scripts` | 61文件通过 |
| `.venv\Scripts\python.exe scripts/export_openapi.py` | 106路径已再生成，包含反馈GET详情及新反馈核验输入，手工新增案例标记弃用 |
| `.venv\Scripts\python.exe scripts/check_project.py` | 35需求、证据链接、源文档及API一致性通过 |
| `npm run test`（web） | 63通过，包括5项新增纠错页面回归；组件内存宿主测试，不代表真实浏览器视觉验收 |
| `npm run build`（web） | TypeScript及Vite生产构建通过，旧SamplesView/RagCasesView不再作为路由分包 |
| `git diff --check`（本次后端/Web/需求文件） | 通过；仅Git行尾转换提示 |

首次回归发现隔离识别应用没有业务数据库属性，已改为可选参数后全套重跑通过；本机MySQL原先未运行，首次集成尝试终止，启动后以上150项为最终结果。前端首次测试受沙箱子进程限制，批准后运行；按钮测试宿主补充空白归一化后63项通过。最终结果不混用失败运行。

15个本次源码/测试文件的SHA256清单指纹：`7815ddf10bf851794d58ba018232afda20930e9aebfefb11ad91162f9d0275cb`（忽略目录 `runtime/feedback-code-manifest.json` 保存逐文件清单）。构建首页SHA256：`ff2eddf424c5ff8793d597a03706c480b6f96e103d2b3a3845448e798de1e843`。基准提交仍为858e99d，本次交付为保留既有修改的工作区快照，不冒充已提交版本。

新增回归覆盖：一次采纳、幂等、拒绝二次审核绕过、停用/重启、RAG不可用、纯文字反馈选词、业务事务失败隔离与恢复，以及前端成功/失败/驳回和导航收敛。

限制：夹具测试不证明真实模型准确率；微信真机、真实用户采样到识别效果的完整链路尚未验收。历史待审核案例不会无依据批量采纳，原先已采纳但未索引的反馈可在详情主动补同步。

## 服务器发布结果

- 发布目录：`/home/admin/dongba-releases/20260927-102330/`；代码包196个文件，包SHA256为 `7094cb551ff01feee9e6383afccbda75b56c5cf970cfca59b55e070fbabb91ee`，代码指纹为 `452f7cb9cf09280301975a54c22b30f2411db75a7af9ccb4b6d3d7575a643a1f`。
- 发布脚本备份了业务数据库17张表、1463行和354个媒体文件，并独立备份RAG `rag_cases` 0行；服务器 `.env` 哈希保持不变。API新PID为 `2004315`，迁移仍为 `0004_rag_support`。
- 服务器部署器完成196个文件校验、Nginx检查、API重启和内部 `8010/ready` 200；IP:8080与HTTPS首页及 `FeedbackView-KuXH30Xb.js` 均以SHA256核对通过。
- 使用一次性五分钟运维会话检查IP:8080和HTTPS：反馈列表200、详情200（当时已有5条反馈）、详情包含 `sample/recognition/rag_status/rag_case`；未登录反馈接口401；手工RAG新增409 `RAG_FEEDBACK_WORKFLOW_REQUIRED`；RAG统计200。会话已删除，未修改管理员密码或业务数据。
- 本次公网验证没有采纳或驳回真实反馈，没有向生产RAG导入虚构案例；RAG备份仍为0行，生产真实纠错闭环需要运营登录后按实际用户反馈操作。
