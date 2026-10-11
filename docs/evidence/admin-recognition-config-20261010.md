# 后台系统配置与识别服务修正（2026-10-10）

关联：OPS-03 / AI-01 / AI-03 / AUTH-02，D-088。
用户最新要求“修正一下后台的系统配置和识别服务”。本轮只修本地代码、验证与Web构建；
没有SSH连接、服务器覆盖、运行时配置切换或微信上传。线上仍以D-087部署记录为准。
开始前状态见[归档](status-before-admin-recognition-config-20261010.md)。

## 有界任务与结果

1. 系统配置显示“当前已保存并生效”的真实服务快照；提供方选择未保存时另提示，
   本地版本/CPU线程只读。Ark端点/模型/密钥仅选择Ark时显示，切换不删除已有备用参数/密钥；
   离开Ark取消未提交密钥替换/清除操作。共享识别超时在本地及Ark都可编辑。
   海报独立配置、读取模型接口及地图保持原语义。
2. 新增共享状态响应及生成OpenAPI类型，管理状态的model和失败记录不再误用备用Ark模型。
   本地ready须SHA和CPU运行时加载通过，成功加载复用缓存；状态不包含异常原文、路径或凭据。
   缺文件、坏摘要、模型无法加载、torch缺失/动态库异常均明确不可用；/ready及识别就绪检查放在线程池。
   外部configured只表示配置完整，查询管理状态没有连通测试或付费调用。
3. 本地运行不再尝试解密无关的备用Ark密钥；密钥状态只表示有保存值，不承诺可解密。
   切回Ark仍验证解密，失败事务回滚，不把本地服务切坏。别名统一为规范提供方名。
4. 识别服务页面用中文明确展示实际模型、状态、线程/超时、无自动付费兜底及分数未校准。
   请求/错误/P95仅当前提供方+当前模型的最近1000条；P95用无错误请求nearest-rank计算，无样本显示暂无数据。
   旧接口缺少统计范围时不展示混合历史统计，不把旧响应的Ark模型当本地模型。
5. 不重写历史错标记录，不调整模型权重、已发布字库、寻迹确认/优惠券规则、不自动调用Ark。

## 验证（最终代码）

全部Python命令使用项目 `.venv\Scripts\python.exe`；Web命令在 `web/` 执行。

| 命令/项目 | 结果 |
| --- | --- |
| `python -m pytest backend/tests -q` | 351 passed / 101 skipped / 1 warning，91.76秒。默认运行中的MySQL分支未启用；fixture不证明准确率 |
| 独立MySQL环境下 `python -m pytest backend/tests/test_system_config.py -q` | 17 passed / 1 warning，28.19秒，含SQLite和MySQL参数分支，无跳过 |
| `python -m ruff check backend scripts` | 通过 |
| `python -m ruff format --check backend scripts` | 90 files already formatted |
| `python scripts/export_openapi.py` | 从隔离配置导出110条路径；增加实际服务状态及系统配置响应类型 |
| `npm test` | 10个测试文件、170项通过；新增识别配置/状态22项，原海报46项仍通过 |
| `npm run format:check` | 所有匹配文件通过 |
| `npm run build` | vue-tsc及Vite生产构建通过，1714 modules，5.80秒 |
| `python scripts/check_project.py` | 35项需求、证据链接和API检查通过；原始DOCX缺失，源摘要比较明确跳过 |
| `git diff --check` | 通过；仅工作树既有LF/CRLF提示，无空白错误 |

专项覆盖：权限401/403、别名规范化、保存后即时可见、本地→Ark参数/密钥保留、隐藏密钥操作取消、
未保存选择/保存失败、旧响应安全降级、本地实际版本、有效摘要但不可加载、依赖缺失/损坏、缓存及文件被改坏、
本地失败无Ark调用、无关坏密钥不阻塞本地、切回失败事务回滚、同提供方/模型统计排除旧记录和失败P95。

独立MySQL为本机8.0.44、仅127.0.0.1:13318，数据目录 `runtime/mysql-d088-20261010/data`，
全新无业务数据且仅创建`dongba_test`。测试URL经进程环境显式注入，不读取项目.env或现有库凭据；
测试fixture仅在显式URL不存在时沿用旧.env回退。测试可drop_all的范围仅此新建测试库，未碰现有MySQL/生产库。
测试结束通过mysqladmin正常关闭临时进程；临时数据不入Git。

早期统计测试误把actor字典当user_id导致单项失败，已修正为id并完成最终全量重跑。
Windows MySQL绝对中文datadir启动失败后改为专用cwd相对data成功，未对既有数据库操作。
Web初次沙箱执行遇到spawn EPERM；经授权沙箱外重跑，全套测试/格式/构建均通过。
后端唯一warning为既有Starlette/anyio BlockingPortal弃用提示。

## 指纹

基线Git HEAD：`ce2daa430022c49f80dc0488a97a5d6d32636f07`。工作树包含大量用户既有未提交修改，
未回滚或提交；交付以以下工作树SHA-256为准，不能只凭HEAD恢复。

| 文件 | SHA-256 |
| --- | --- |
| backend/app/main.py | 5723c01c3f8d62f7736070ccff9a700f483618ce5901f67f5f9736b8ceee0a1b |
| backend/app/provider_status.py | 8ae9b74cec2ea6de16a6dd4392c4608427639763d23ed7832dfb360043d94967 |
| backend/app/local_glyph_provider.py | 3835d1e5db5ce206de4a2cc40c3422562c30945fd7000ab9a034453683dccbe3 |
| backend/app/provider_factory.py（既有本地接入依赖） | 7bc94f82ea4ceddb27564f810b078d5e40809ed9a2d3b674624650f5c1ac97cb |
| backend/app/recognition.py | 2f5d9db5cb534bb97e1305827676c252b2c9b57317539bb9e17a6ea55c31b42f |
| backend/app/system_config.py | ed87e9e828a5980afcd2a834e64b7077a9c5e11fe1aad0c3791044ff15e1cced |
| backend/tests/test_system_config.py | d77db190728e133fbba81a9b49aa7f4fc62bd348cfd52b98cd6715a7e5a55df4 |
| backend/tests/test_local_glyph_provider.py | 5298f0aaaf4aff26c773a53674cbb691d88233ca9fe02ed8198afb2c0eccce60 |
| backend/tests/test_business_api.py | 2a8b4b381fc8220bdca082dbebcaf81f23f958ed015137abb9435fcd1f6606aa |
| web/src/recognition-status.ts | c0b58a678ed0e38564a68a5255951be5442104f0e94d9cf1832ff1477a44b81c |
| web/src/views/SystemConfigView.vue | 40c13263e277b54b5cab9689814a4e54b6a6f9bab2b1fff5cdaf5b4cf50bda05 |
| web/src/views/RecordsView.vue | 22b7eec4ac92adeaf2e9407a2f2a5a7cf547b9e6ce965d6d457e4433fcc182e1 |
| web/tests/recognition-status-components.test.ts | 27a4e2e92c606dea8b0329f8bb6944e31813015eca969eb001976dffecdf87b0 |
| web/tests/poster-config.test.ts | 53ed367ab912edad48fb09c8e6b3c3092d1a5a596692e589b47f9c41a504970c |
| docs/contracts/openapi.json | 889e114770e029be6382f54fa886f29d6729b797eaeaa8840d3d673b1b65fd95 |
| web/dist/index.html（本地构建，未上传） | e93321d3b18c05f54f9dce622d0ad31227b0a7d13e2bc4eb6474b129e390874d |

## 边界与交接

- 本次状态/配置/无自动兜底测试都是夹具功能验证，CPU模型夹具为随机权重，绝非真实模型准确率。
- 已做真实MySQL存储/事务验证，但不是公网HTTP、浏览器真机或跨端整体验收；本轮未调用外部模型。
- 正式模型已在线是D-087历史事实，本轮新增后端与Web修复尚未上线，发布时须同时备份/更新二者并核验指纹。
- 公网 `/ready` 在D-087记录中仍是SPA，后续上线应检查本机API的真正JSON，不以HTML作就绪证据。
- OPS-03/AI-01/AI-03整体仍实现中；未满足 `docs/release.md` 全部正式发布门槛。
