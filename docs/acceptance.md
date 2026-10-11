# 验收跟踪

GitHub同步复核（D-091，2026-10-11）：后端351通过/101跳过，Web170通过、格式/构建通过，
Ruff及35项项目检查通过；小程序173通过/1失败，MINI-01首页相册快捷按钮已被用户工作区改动移除，
与现有测试断言不一致。本次仅保留并上传当前改动，未恢复按钮、未修改测试以消除失败；
不提升MINI-01或其他需求验收状态，未运行新一轮MySQL集成或微信真机验收。
见[同步检查及代码指纹](evidence/github-sync-20261011.md)。

OPS-03 / AI-01 / AI-03 更新（D-088，2026-10-10）：本地模型与Ark备用参数分开展示/保存，
管理服务状态和失败记录使用实际模型版本，统计限同提供方同模型；本地依赖/加载异常明确不可用，
不自动付费兜底。后端351通过/101跳过，系统配置SQLite+独立MySQL专项17通过，Web170通过及构建通过。
当时为本地功能修正，后续已由D-089上线；不是实拍准确率或整体验收，AI-01/OPS-03仍实现中，AI-03既有功能验收状态不变。
见[配置与识别服务修正证据](evidence/admin-recognition-config-20261010.md)。

OPS-03 / AI-01 / AI-03 部署更新（D-089，2026-10-10）：5个后端模块和28个Web资源已同步，
30个未改依赖一致；两遍真实HTTP/MySQL确认实际本地模型身份、权限、识别/显式确认/否定和坏图记录，
HTTPS资源逐文件SHA校验通过，临时账号/会话/识别/反馈/样本行均无残留。模型/环境/运行时配置不变，
无自动Ark兜底或付费调用。备份及回滚入口已留存，未演练停服回滚、未上传微信、未做浏览器/真机整体验收。
见[本轮上线证据](evidence/admin-recognition-config-deploy-20261010.md)。

OPS-03 / DESIGN-01 修正（D-090，2026-10-10）：识别提供方改为未启用/本地DB1404/火山Ark三个
始终可见选项；识别、海报和地图一次只显示一段，状态和只读信息采用紧凑响应式排版。
Web170项、格式和生产构建通过，保存和提供方切换语义不变；28个Web文件已同步服务器并逐项验证HTTPS SHA，
API PID、实际本地模型、环境和运行时配置未变。尚未做带管理员会话的真实浏览器视觉签收。
见[紧凑排版及上线证据](evidence/system-config-compact-layout-20261010.md)。

AI-02新增D-081本地训练实验并由D-086授权后端生产接入；数据审计、训练、离线评测及提供方适配已完成，D-087服务器切换及窄范围真实HTTP/MySQL验证已通过，微信真机仍待验证。旧轮记录见[CPU训练证据](evidence/db1404-cpu-training-20261008.md)。
2026-10-09旧基线训练退化（5轮验证Top-1约0.24%，训练图抽样隐藏层全零/恒定输出）；已安全停止并备份，不能作为有效模型交付。
用户授权D-082修正，v2真实train学习检查已通过，01:19按D-083暂停且当时全量未启动；历史记录保留。
10-09用户明确“继续训练”（D-084），随后授权D-085线程实测：同断点两次实测选择8线程，中位吞吐较2线程提升80.8%；原断点不覆盖，从第1轮5590批迁移续训。10-10完成40轮及最终离线评测：最佳第35轮val Top-1/Top-5为93.32%/98.46%；独立test 44269图为93.24%/98.35%，历史50的49张无歧义图为47/49和49/49。Excel、CSV及推理模型已生成。见[修正恢复证据](evidence/db1404-cpu-v2-recovery-20261009.md)及[线程证据](evidence/db1404-cpu-thread-sweep-20261009.md)。因无可靠writer ID、无新手机实拍盲测且生产仍用外部API，这不构成AI-02整体验收。
上段“生产仍用外部API”是训练完成时的历史状态，已由D-087切换替代。历史50图不是新盲测；D-086本地接入测试不构成手机真机准确率，服务器部署以本轮独立证据为准。
AI-01/02/03部署更新（D-087）：用户确认root后完成最小后端包上传、CPU依赖安装和MySQL运行时提供方切换；真实HTTP识别、原请求确认/拒绝/跨用户绑定、质量错误及发布ID过滤通过，测试临时行已清理。公网健康/字库/鉴权正常；Web/微信版本未上传，单样本不是实拍准确率，AI-01/02整体验收不变。见[服务器部署证据](evidence/db1404-local-server-deployment-20261010.md)；原SSH阻塞为[历史检查点](evidence/db1404-deploy-preparation-20261010.md)。

状态规则：待开发 / 实现中 / 待验证 / 验收通过 / 待外部依赖。
证据必须对应实际代码版本或指纹。单元测试通过不等于外部模型、真机或上线验收通过。

2026-09-23按原始DOCX复核后修正：**业务尚未全部实现**。确定缺口见 [原文核对](source-audit.md)，原33项补回DATA-03/04后共35项。
“实现中”包括已有部分能力但尚有业务缺口；同项仍需真机/素材时另行注明，不再将代码缺失仅标为外部依赖。
按D-015不扩大生产性能/安全专项。已有 [集成证据](evidence/integration-acceptance.md) 仅证明已测流程，本次校核见 [核对证据](evidence/source-audit-checks.md)。

| 需求编号 | 状态 | 证据或剩余工作 |
| --- | --- | --- |
| GOV-01 | 验收通过 | [原文核对](source-audit.md)：35项需求、决策、缺口与关闭条件已落盘，历史指纹和证据保留；文档一致性不等于业务全部通过 |
| INF-01 | 验收通过 | [集成证据](evidence/integration-acceptance.md)：HTTP、请求追踪、79路径OpenAPI与一致性检查通过 |
| AI-01 | 实现中 | [RAG本机证据](evidence/rag-local.md)：独立MySQL审核记忆检索、HTTP识别及故障回退通过；夹具不证明准确率。D-065将RAG纠错记忆改为只追加不前置（分数≥0.45且provider未返回的已发布词条），避免多人累积污染新图片，见[识别质量证据](evidence/recognition-quality-20261006.md)。GAP-10目标占比检测仍未实现，真实检测待供应商。D-071参考字形粗筛已部署：1404条字库按16×16墨迹特征取top-200，见[第四步证据](evidence/db1404-glyph-shortlist-20261007.md)；Excel历史服务器路径top-1 22/50、top-5 26/50且短名单30/50，见[Excel复核证据](evidence/db1404-xlsx-verification-20261008.md)。D-076扫描445,272图并选11,232原型，指定50图长边512口径本地top-200由重建单主图34/50提高到42/50，排除同SHA不变，见[多原型证据](evidence/db1404-multi-prototype-20261008.md)。D-077已生成约23.27MB的路径无关部署包并接入生产加载器，按查询最近原型仍输出200个唯一ID/10张对照图，残缺包整次回退；集成路径保持42/50、仍漏8条，见[运行时接入证据](evidence/db1404-prototype-runtime-integration-20261008.md)。D-078已部署服务器，全资产SHA校验0错且无付费加载探针确认200个唯一ID/10张对照图，健康、迁移、环境及鉴权边界未变，见[服务器部署证据](evidence/db1404-prototype-server-deployment-20261008.md)。以上均不等于模型top-1或真机准确率。 |
| AI-02 | 实现中 | [历史复核](evidence/db1404-xlsx-recheck-20261008.md)保留GLM44%/52%及403/404历史故障；[豆包开通后实验](evidence/db1404-doubao-enabled-20261008.md)确认原200参考图路径token超限，拼图实验50条为首选19/50、前五22/50。[D-075止损部署](evidence/recognition-token-reduction-20261008.md)将线上201张视觉输入降为11张且不减少top-200候选；部署后一次真实API usage为17797 prompt + 49 completion = 17846 total，较用户报告约50万低约96.4%，但不是账单金额，单样本也未命中。[小程序裁剪结果模拟复核](evidence/db1404-miniapp-simulation-20261008.md)以服务器当前实际pro模型完成50条：首选25/50、前五30/50、错误0；因46张原图低于200px而采用长边512归一化，不是原图直传或真机实拍准确率，短名单仅30/50仍待核查。实拍准确率、批量费用与内容审核仍待验收。 |
| AUTH-01 | 待外部依赖 | 已实现真实微信兑换及隐私状态；[客户端HTTP闭环](../miniprogram/VERIFICATION.md)通过，实际微信账号与真机待配置 |
| AUTH-02 | 验收通过 | [业务证据](evidence/business-acceptance.md)：账号、登录退出、权限与商户范围通过MySQL及接口验证；D-053界面文案及错误提示边界已完成专项验证，Web已上线、小程序待上传，见[封装性证据](evidence/user-copy-20260927.md) |
| DATA-01 | 实现中 | [DB1404服务器录入证据](evidence/db1404-server-import.md)：原资料编号、别名、关键词、商业标签、主图/异形、来源及发布状态已支持，公网有80条真实词条；[全量清单第一步](evidence/db1404-catalog-step1-20261007.md)：1404条释义PDF已本地只读解析为清单草稿（编号无缺失、445273张图、164条带标记待确认）；[全量清单第二步](evidence/db1404-catalog-step2-20261007.md)：已离线生成 `data/db1404_full.json`（collection `DB1404_FULL_V3`，1404条12字段、分类无待分类、30组重名/52条超长/979草稿按默认保留，自动选样每字两张），`import_db1404.py` 已支持该 collection。第三步已把 1404 条纯增量入库服务器（报告 created 1324/existing 80/verified 1404、error 0），公网 `total=1403`、抽样 30/30 图可解码 512×512、`DB1404_0979` 正确 404；第四步参考字形粗筛已修复并部署（`MAX_REFERENCES=200` 不再按前缀截断，`load_references(..., query=image)` 按 16×16 墨迹特征排序，自匹配 top-200 40/40），见[第三步证据](evidence/db1404-server-import-full-20261007.md)、[第四步证据](evidence/db1404-glyph-shortlist-20261007.md)。名称与说明仍未经人工或专业审核，**不构成文化内容批准或识别准确率证据**；完整运营导出和后台跨页面验收仍需与其余数据能力一起完成 |
| DATA-02 | 验收通过 | [集成证据](evidence/integration-acceptance.md)：真实MySQL迁移、持久化、备份恢复与媒体访问通过 |
| DATA-03 | 实现中 | D-046纠错附图取消独立样本审核/数据集入口；D-048补显式授权补传、失败阻断和历史缺图说明。保留授权、预览、删除及清理。[附图修复](evidence/feedback-image-20260927.md)、[单次核验](evidence/feedback-single-review.md)；微信发布及真机跨端仍待验收 |
| DATA-04 | 待开发 | GAP-03：只保留当前内容和字段名审计，无可查的历史文化文本/字形/来源版本 |
| MINI-01 | 实现中 | [识别质量证据](evidence/recognition-quality-20261006.md)：19页；D-065以四角框选拍摄/裁剪页替代D-027的 `chooseImage` 直拉相机，原生相机取原图、长边≤1200px只降不升，相册入口复用同一裁剪流程；后端 `quality_min_edge` 96→200，裁剪过小在客户端先提示。[首页资源压缩](evidence/home-assets-map-density-20260927.md)将实际背景压至179457字节并添加200000字节上限测试，原图继续排除打包；后端已部署服务器（见[服务器部署证据](evidence/recognition-quality-server-20261007.md)），小程序走微信平台发布、仍需重新上传体验版验收，夹具不证明真实识别准确率 |
| AI-03 | 验收通过 | [客户端证据](../miniprogram/VERIFICATION.md)：候选、拒识、确认与原请求绑定；[RAG本机证据](evidence/rag-local.md)：辅助候选仍需用户确认，HTTP返回及记录持久化已测，非真实模型效果验收；[图03结果页回归](evidence/result-reference-20260927.md)：默认预览不自动选择/确认、异步候选切换、缺内容、收藏独立性及原请求/附图授权均保留；D-065结果页“参考分数”改为未校准的“候选参考”档位并明示收藏词条不确认识别，见[识别质量证据](evidence/recognition-quality-20261006.md)，夹具测试不代表真实识别准确率 |
| CONTENT-01 | 实现中 | [DB1404服务器录入证据](evidence/db1404-server-import.md)：已发布80条释义及160张同编号手写图；[图03结果页](evidence/result-reference-20260927.md)接入已有已发布字典详情、异形、来源及音频字段，缺失内容明确提示；仍缺结果页关联POI/活动及文化视频能力，音视频等正式文化素材仍待补充；D-053界面文案及错误提示边界已完成专项验证，Web已上线、小程序待上传，见[封装性证据](evidence/user-copy-20260927.md)；D-064详情页已重做并移除写法卡片，多写法数据及结果页保持，真实音频/来源/关联内容仍按接口展示，见[详情页改版证据](evidence/character-detail-redesign-20260929.md)；不因此完成原有视频/POI/活动缺口 |
| USER-01 | 验收通过 | [集成证据](evidence/integration-acceptance.md)：收藏、历史、清空、失败记录重拍及跨页数据同步 |
| FEEDBACK-01 | 实现中 | D-046采纳直接入RAG、驳回不入库；入库失败保持待处理，跨库孤立写入不得检索，重试去重。D-048授权附图先上传后提交、失败不静默丢图。[单次核验](evidence/feedback-single-review.md)、[附图修复](evidence/feedback-image-20260927.md)；微信发布与真实模型效果仍未验收；D-049排版、维护状态与选填说明已部署并完成8080/HTTPS读取校验，见[本次证据](evidence/feedback-layout-20260927.md)；详情全宽工作页和去重操作已发布，见[体验优化证据](evidence/feedback-workspace-20260927.md)；D-053界面文案及错误提示边界已完成专项验证，Web已上线、小程序待上传，见[封装性证据](evidence/user-copy-20260927.md)；D-054统一宽抽屉、信息精简及维护操作按需展示已完成102项Web测试、28项浏览器检查和构建，已部署8080/HTTPS并通过8项公网资源校验，见[抽屉统一证据](evidence/feedback-drawer-20260928.md) |
| MERCHANT-01 | 实现中 | [关联运营数据证据](evidence/operational-demo-data.md)：公网MySQL已有4家商户、POI、8个商品和4个活动的关联演示数据，商户与商品均已有可公网显示的配图；GAP-04仍在，活动缺字/文化主题关联字段，无法完成结果页的相关活动查询；[D-056运营扩充](evidence/operational-expansion-20260928.md)已在本地MySQL验证新增内容、双路线奖励及幂等，公网待认证同步，不改变本项既有缺口/验收边界 |
| GEO-01 | 实现中 | [本地地图与首页验收](evidence/web-amap-dashboard-local.md)及[系统配置本地证据](evidence/runtime-system-config-local.md)：Web采用高德官方JS API、发布POI的GCJ-02坐标及管理员地图配置，旧版5项夹具通过，本机真实底图曾加载。[小程序图06优化](evidence/map-visual-20260927.md)补地图图层/定位/缩放、分类、真实图片地点卡及定位后的直线距离排序；[本轮排版收紧](evidence/home-assets-map-density-20260927.md)删除品牌角标、缩小可见胶囊并保留44px触控高度，地图13项单测、27项离线场景和官方模板/样式编译通过，没有虚构评分或优惠。服务商域名、安全配置、服务器同步、实地坐标、新版Web浏览器及微信真机导航未验，GAP-08小程序路线/地图优惠卡仍待补齐；[D-056运营扩充](evidence/operational-expansion-20260928.md)已在本地MySQL验证新增内容、双路线奖励及幂等，公网待认证同步，不改变本项既有缺口/验收边界 |
| REC-01 | 实现中 | GAP-04/05：直接字商户关系、六权重及无位置降级已有；[图03结果页](evidence/result-reference-20260927.md)复用按当前候选限定的关联商户接口，保留原识别请求跳转，不主动定位或补造距离/优惠/销量；缺主题/商业标签关联、关联POI/活动及营业有效性 |
| COUPON-01 | 验收通过 | [集成证据](evidence/integration-acceptance.md)及[公网关联数据](evidence/operational-demo-data.md)：领券、库存、限额、时间、状态、本人PNG券码及36笔MySQL领取记录；[D-056运营扩充](evidence/operational-expansion-20260928.md)已在本地MySQL验证新增内容、双路线奖励及幂等，公网待认证同步，不改变本项既有缺口/验收边界。[D-079领券状态修复](evidence/miniapp-coupon-claimed-state-20261008.md)使商户详情在成功后及再次进入时显示禁用的“已领取”并阻断重复请求；本地测试/官方编译通过，小程序仍待重新上传和真机验收。 |
| COUPON-02 | 验收通过 | [集成证据](evidence/integration-acceptance.md)及[公网关联数据](evidence/operational-demo-data.md)：24笔由对应商户完成的核销记录可追溯；真实摄像头扫码待设备确认 |
| MERCHANT-02 | 实现中 | [关联运营数据证据](evidence/operational-demo-data.md)：管理端总数及4家商户分域统计已有真实关联行支撑；GAP-07/11仍在，来源排名混合曝光/访问/导航等，核销未继承来源，今日待核销及部分图09细节缺失 |
| QUEST-01 | 验收通过 | [客户端证据](../miniprogram/VERIFICATION.md)：识别、扫码、围栏、核销、人工五种任务在HTTP闭环中通过；[寻迹页呈现回归](evidence/quest-reference-20260928.md)使用真实路线与个人进度，保留既有打卡/奖励流程，未更改业务判定；[D-056运营扩充](evidence/operational-expansion-20260928.md)已在本地MySQL验证新增内容、双路线奖励及幂等，公网待认证同步，不改变本项既有缺口/验收边界 |
| QUEST-02 | 验收通过 | [业务证据](evidence/business-acceptance.md)：完整测试路线、集章、奖励发放及缺货后重试；[演示路线配置](evidence/quest-demo-configuration-20260928.md)已在仓库、本地MySQL及公网数据库配置1条路线、3个节点、自动QR密钥和奖励券关联；公网接口与幂等重跑验证通过；[寻迹页呈现回归](evidence/quest-reference-20260928.md)使用真实路线与个人进度，保留既有打卡/奖励流程，未更改业务判定；[D-056运营扩充](evidence/operational-expansion-20260928.md)已在本地MySQL验证新增内容、双路线奖励及幂等，公网待认证同步，不改变本项既有缺口/验收边界 |
| SHARE-01 | 实现中 | D-062按参考图+审核字形多图输入、AI整图设计，移除缺码/业务说明，不再依赖本机排字；1次真实纸风生成1024×1536并已部署，见[整图证据](evidence/poster-full-design-20260929.md)。D-063修复四种风格被纸风参考压制的问题，选中风格优先且有独立构图/禁用元素，服务端已部署，后端281通过/96跳过、小程序68通过；实际简约样例有明显区分，雪山样例上游不可用未验收，见[风格证据](evidence/poster-style-direction-20260929.md)。[D-061下载修复](evidence/poster-download-repair-20260929.md)的旧原图公网HTTPS下载与哈希仍不变。96项跳过不算MySQL验收；旧图不自动重绘，前端需重新编译/上传；微信取码41030、文化字形逐图审核及真机保存/分享仍另验 |
| OPS-01 | 实现中 | D-052合并审核发布已部署8080/HTTPS；84项Web、5组浏览器、180项后端含MySQL及8项公网资源校验通过，保留发布校验、审核信息、商户限制和历史状态，见[本轮证据](evidence/single-publication-20260927.md)。原GAP-03完整验收仍独立保留，不因本轮界面简化宣称全部完成 |
| OPS-02 | 验收通过 | [业务证据](evidence/business-acceptance.md)：券、活动、路线节点、人工确认和推荐参数可维护；[D-056运营扩充](evidence/operational-expansion-20260928.md)已在本地MySQL验证新增内容、双路线奖励及幂等，公网待认证同步，不改变本项既有缺口/验收边界 |
| OPS-03 | 实现中 | [RAG本机证据](evidence/rag-local.md)及[系统配置证据](evidence/runtime-system-config-local.md)：配置、案例流程和组件回归已测；[部署证据](evidence/server-update-20260927.md)及[RAG服务器修复](evidence/rag-server-config-20260927.md)：独立库已配置，8080/HTTPS已鉴权列表、统计、检索均200，未登录401。真实浏览器登录、公网新增审核闭环、真实模型和微信跨端运营仍待验；D-049排版、维护状态与选填说明已部署并完成8080/HTTPS读取校验，见[本次证据](evidence/feedback-layout-20260927.md)；详情全宽工作页和去重操作已发布，见[体验优化证据](evidence/feedback-workspace-20260927.md)；D-053界面文案及错误提示边界已完成专项验证，Web已上线、小程序待上传，见[封装性证据](evidence/user-copy-20260927.md)；D-054统一宽抽屉、信息精简及维护操作按需展示已完成102项Web测试、28项浏览器检查和构建，已部署8080/HTTPS并通过8项公网资源校验，见[抽屉统一证据](evidence/feedback-drawer-20260928.md)；D-058独立生图配置、密钥保留/清除与模型读取完成148项Web及302项后端回归，2026-09-29公网部署、主密钥生成和未授权复核通过，见[AI海报证据](evidence/ai-poster-20260928.md)与[部署证据](evidence/ai-poster-deploy-20260929.md)，[D-060排障](evidence/poster-generation-repair-20260929.md)确认用户已保存的生图配置可解密并成功实际调用，未变更密钥；微信取码与真实跨端运营仍待验 |
| ANALYTICS-01 | 实现中 | [关联运营数据证据](evidence/operational-demo-data.md)：公网库已用116条演示事件核对曝光、访问、商品详情、导航和分享统计；GAP-06/07仍在，首页/识别开始客户端未完整发送，停留/回流/集章等不足，缺业务比率与正确来源归因；D-053界面文案及错误提示边界已完成专项验证，Web已上线、小程序待上传，见[封装性证据](evidence/user-copy-20260927.md) |
| PRIVACY-01 | 实现中 | 当前原图不留存、授权/历史删除/保留期清理有证据；GAP-01补齐需同步样本用途/保留/删除约定；真实联系信息/供应商政策另待填写 |
| NFR-01 | 待验证 | 按D-015不作为本轮门槛；未进行生产负载与长期可用性验证，不宣称达到原建议指标 |
| NFR-02 | 待验证 | 基础鉴权、上传校验、限流和审计已实现及验证；按D-015不扩大生产安全专项 |
| NFR-03 | 验收通过 | [集成证据](evidence/integration-acceptance.md)：request_id、失败持久化、超时/不可用、后台记录与清理任务通过；真实供应商协议后补 |
| RELEASE-01 | 实现中 | [2026-09-29海报重新部署证据](evidence/ai-poster-deploy-20260929.md)及[2026-09-27部署证据](evidence/server-update-20260927.md)：本次发布已通过备份、哈希、API重启、数据库/环境/Nginx保护、IP和HTTPS入口检查；完整回退演练、主机重启持久化和真机体验版仍待验证 |
| RELEASE-02 | 待外部依赖 | 当前源码、锁文件、运行说明、使用指南及验收记录已齐备；正式接收方格式与签收事项待确定 |
| DESIGN-01 | 实现中 | [图01至图08改版](evidence/miniprogram-visual-redesign.md)、[首页比例/白框](evidence/home-proportions-20260927.md)、[左对齐修正](evidence/home-left-alignment-20260927.md)、[首页触控区](evidence/home-touch-targets-20260927.md)及[地图图06优化](evidence/map-visual-20260927.md)：首页白框/左对齐及148rpx×52px触控区保留。[资源与排版](evidence/home-assets-map-density-20260927.md)将首页背景压至179457字节，地图删除右上品牌角标、分类/导航分别使用36px/34px可见胶囊及44px高触控区。[图03结果页](evidence/result-reference-20260927.md)实现左图右文、异形/候选、文化/商户分区及固定操作栏；[字典关联区排版](evidence/character-association-layout-20260927.md)将两组关联行改为全宽左对齐三列布局并保留44px点击区。最新77项客户端测试、21份WXML/17份WXSS编译、23项字典页/30项结果页/97项跨页离线检查通过，覆盖长内容、缺失/失败状态、按钮样式干扰及44px点击命中。离线截图不是微信真机、真实地图/接口或正式视觉签收；背景图版权、相机/授权/定位真机体验及自定义实时相机、视频、地图路线/优惠卡和海报预览一致性等缺口仍如实保留；[寻迹参考图改版](evidence/quest-reference-20260928.md)新增动态印记/双卡/沿途图片，94项客户端、21份WXML/17份WXSS、91项寻迹及160项跨页离线检查通过；未上传微信，寻迹真机视觉签收仍待验；D-058图08海报编辑/预览完成150项客户端、57项离线布局和官方编译，见[AI海报证据](evidence/ai-poster-20260928.md)，真机与真实文化字形闭环待验；D-064详情页采用雪山纸感分区并将收藏外框改为空心/实心星形图标，162项客户端测试、21份WXML/17份WXSS官方编译及39项离线布局通过，见[详情页改版证据](evidence/character-detail-redesign-20260929.md)；未上传微信、待真机视觉验收 |
