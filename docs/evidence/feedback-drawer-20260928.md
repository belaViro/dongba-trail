# 纠错审核抽屉统一与信息精简（2026-09-28）

## 范围与结论

- 需求：FEEDBACK-01、OPS-03；附图兼顾DATA-03。决策D-054，按用户确认统一管理端弹窗并减少冗余。
- 仅修改 `web/src/views/FeedbackView.vue`、`web/tests/feedback-components.test.ts`、`web/tests/feedback-image-browser.cjs`，保留其他未提交工作。
- 右侧宽抽屉最大1120px，移动端满宽，一个关闭入口；正文聚焦附图/反馈/原识别/正确词条/选填备注，编号和时间折叠，完成后不展示空说明或内部词条ID。
- 次要维护动作移入更多操作；停用时才要求原因，取消不提交。组合状态仍区分历史审核与当前生效，维护后同时刷新列表和详情。保留采纳直接生效、权限、不可用提示、旧响应防覆盖和图片鉴权机制。
- 本地改造、验证及服务器部署完成，8080/HTTPS资源均已核对一致；未改后端、配置或数据库。

## 本地验证

最终代码于2026-09-27完成验证，2026-09-28复核以下SHA256未改变：

| 命令 | 结果 |
| --- | --- |
| `npm --prefix web run typecheck` | 通过 |
| `cd web; npm test` | 8个文件、102项通过，其中纠错组件17项 |
| `cd web; npm run build` | vue-tsc与Vite构建通过，1713个模块 |
| `node web/tests/feedback-image-browser.cjs` | 28项检查通过；桌面1360/1920及移动390宽度无横向溢出 |
| `.venv\Scripts\python.exe scripts/check_project.py` | 通过：35条需求、证据链接、源文档和API一致性 |

浏览器使用真实Edge渲染和合成API响应，验证鉴权图片展示/缺图/失败重试、抽屉尺寸及唯一关闭、次要信息折叠、筛选/焦点保留、选填备注、停用原因校验、采纳/驳回/停用/启用/重新索引、列表详情状态和无JS错误。不向公网写入测试业务数据，不作为真实识别准确率或微信验收证据。

截图位于 `runtime/feedback-drawer-browser/`：`review-wide.png`、`review-mobile.png`、`maintenance-desktop.png`、`list-desktop.png`、`visible.png`；已目视核对桌面双栏、手机堆叠与底部操作栏。

修复了初轮测试依赖旧页内/维护按钮的断言、测试桩属性命名，并在允许子进程的环境执行esbuild/浏览器检查。后端、API及数据库未修改，本轮不重复计入此前后端测试，不需重新导出OpenAPI。

## 指纹

| 文件 | SHA256 |
| --- | --- |
| `web/src/views/FeedbackView.vue` | `9bb910bc461fbc9c1cfea19cc68d50901274e7f71280f059111e1352f9331ed2` |
| `web/tests/feedback-components.test.ts` | `436b9e22d92d7a76aa89bc79a0be50c97a1d748c90e0e13bc832e3271deb1541` |
| `web/tests/feedback-image-browser.cjs` | `3fd78e38e287d4aa67cedad06758ae06b5ada1973bc3c4fd3161bd49ab986752` |
| `web/dist/index.html` | `a68341a17c2464e140462b9f3c02bb11dc5000c2d7052a4cb9d0ad608ba29fa0` |

发布包 `runtime/deploy/feedback-drawer-20260928/release.tar.gz`，30文件、817022字节。清单指纹 `f26eb78a3ee1b7f50bcc595b95a786da7183d5e6386396f6876fe59f562d2774`；包SHA256 `042d1bc3ef2c5a16cb1e235754a7d8e4e5653ac10e51d9bb7556a57664137f36`。

发布前核对上轮源文件与首页基线；仅原子替换前端资源/上述三文件，入口最后切换、保留旧资源及备份并在失败时恢复。不会重启后端或操作数据库与配置。

## 上线记录

已于2026-09-28 10:31部署到服务器 `/home/admin/dongba-trail`，备份与发布记录：`/home/admin/dongba-releases/20260928-103107-feedback-drawer`。

- 上轮首页及源文件基线通过后才写入；30个包内文件全部SHA256一致，实际更新21文件，入口最后原子切换，旧静态资源与旧文件备份保留。
- 8080继续由nginx提供，后端仍为127.0.0.1:8010、API PID `2004689`；nginx PID `1968337/2004692/2004693`和API PID发布前后均未变，未重启后端、未改数据库或配置，`/ready`检查200。
- 公网HTTP 8080与HTTPS各核对首页、入口JS、纠错JS及CSS，共8项HTTP 200且SHA256与发布清单一致；不是只验证本地文件。
- 线上入口 `index-CXpIZiNo.js`，纠错资源 `FeedbackView-CflQJjOB.js` / `FeedbackView-DQ0ReWvd.css`。校验JSON为 `runtime/deploy/feedback-drawer-20260928/public-check.json`；发布及进程记录分别为 `server-result.json`、`process-check.json`。
- SSH首次免密/交互检查未成功；使用内存密码完成认证，凭据未写文件。第一次执行部署助手因系统Python旧版本缺少Path API中止于项目写入之前；已修正路径包含校验并改用服务器项目虚拟环境后完成发布，没有跳过版本基线或校验。

本轮未用公网账号新增、审核或停用真实纠错，交互行为证据来自本地合成API浏览器检查；不据此宣称真实模型质量、微信端联调或整项目生产验收完成。
