# 验收跟踪

状态规则：待开发 / 实现中 / 待验证 / 验收通过 / 待外部依赖。
证据必须对应实际代码版本或指纹。单元测试通过不等于外部模型、真机或上线验收通过。

2026-09-23按原始DOCX复核后修正：**业务尚未全部实现**。确定缺口见 [原文核对](source-audit.md)，原33项补回DATA-03/04后共35项。
“实现中”包括已有部分能力但尚有业务缺口；同项仍需真机/素材时另行注明，不再将代码缺失仅标为外部依赖。
按D-015不扩大生产性能/安全专项。已有 [集成证据](evidence/integration-acceptance.md) 仅证明已测流程，本次校核见 [核对证据](evidence/source-audit-checks.md)。

| 需求编号 | 状态 | 证据或剩余工作 |
| --- | --- | --- |
| GOV-01 | 验收通过 | [原文核对](source-audit.md)：35项需求、决策、缺口与关闭条件已落盘，历史指纹和证据保留；文档一致性不等于业务全部通过 |
| INF-01 | 验收通过 | [集成证据](evidence/integration-acceptance.md)：HTTP、请求追踪、79路径OpenAPI与一致性检查通过 |
| AI-01 | 实现中 | GAP-10：上传后基础质量校验、可替换占位与字典映射已验证；目标过小目前仅检查整图尺寸，目标占比未实现，真实检测待供应商 |
| AI-02 | 待外部依赖 | 模型协议、凭据、审核字典和真实评测图片由用户后补，不以夹具成绩代替模型效果 |
| AUTH-01 | 待外部依赖 | 已实现真实微信兑换及隐私状态；[客户端HTTP闭环](../miniprogram/VERIFICATION.md)通过，实际微信账号与真机待配置 |
| AUTH-02 | 验收通过 | [业务证据](evidence/business-acceptance.md)：账号、登录退出、权限与商户范围通过MySQL及接口验证 |
| DATA-01 | 实现中 | [DB1404服务器录入证据](evidence/db1404-server-import.md)：原资料编号、别名、关键词、商业标签、主图/异形、来源及发布状态已支持，公网有80条真实词条；完整运营导出和后台跨页面验收仍需与其余数据能力一起完成 |
| DATA-02 | 验收通过 | [集成证据](evidence/integration-acceptance.md)：真实MySQL迁移、持久化、备份恢复与媒体访问通过 |
| DATA-03 | 待开发 | GAP-01：无图片样本关联、预览复核、元数据管理及样本导出；取消自训练未取消该业务 |
| DATA-04 | 待开发 | GAP-03：只保留当前内容和字段名审计，无可查的历史文化文本/字形/来源版本 |
| MINI-01 | 实现中 | [直达相机证据](evidence/camera-direct-launch.md)：18页；独立识别页已删除，首页/历史/任务点击后直接调用 `chooseImage` 拉起相机；缺即时质量提示，真机仍需重新上传体验版验收 |
| AI-03 | 验收通过 | [客户端证据](../miniprogram/VERIFICATION.md)：候选、拒识、确认与原请求绑定，真实HTTP页面流程通过 |
| CONTENT-01 | 实现中 | [DB1404服务器录入证据](evidence/db1404-server-import.md)：已发布80条释义及160张同编号手写图；仍缺结果页关联POI/活动及文化视频能力，音视频等正式文化素材仍待补充 |
| USER-01 | 验收通过 | [集成证据](evidence/integration-acceptance.md)：收藏、历史、清空、失败记录重拍及跨页数据同步 |
| FEEDBACK-01 | 实现中 | GAP-01：文字候选确认/纠错/复核/导出已验证，但没有对应图片样本，无法完成原文图像复核闭环 |
| MERCHANT-01 | 实现中 | [关联运营数据证据](evidence/operational-demo-data.md)：公网MySQL已有4家商户、POI、8个商品和4个活动的关联演示数据，商户与商品均已有可公网显示的配图；GAP-04仍在，活动缺字/文化主题关联字段，无法完成结果页的相关活动查询 |
| GEO-01 | 实现中 | [本地地图与首页验收](evidence/web-amap-dashboard-local.md)及[系统配置本地证据](evidence/runtime-system-config-local.md)：Web 本地已采用高德官方 JS API，后端已发布 POI 的 GCJ-02 坐标及地图铺满卡片；地图 Web Key/默认中心/缩放改由管理员运行时配置。旧版夹具 5/5 通过，本机真实底图曾加载；服务商域名、安全配置、服务器同步、实地坐标和新版浏览器实测未验，GAP-08 小程序路线另待验 |
| REC-01 | 实现中 | GAP-04/05：直接字商户关系、六权重及无位置降级已有；缺主题/商业标签关联、关联POI/活动及营业有效性 |
| COUPON-01 | 验收通过 | [集成证据](evidence/integration-acceptance.md)及[公网关联数据](evidence/operational-demo-data.md)：领券、库存、限额、时间、状态、本人PNG券码及36笔MySQL领取记录 |
| COUPON-02 | 验收通过 | [集成证据](evidence/integration-acceptance.md)及[公网关联数据](evidence/operational-demo-data.md)：24笔由对应商户完成的核销记录可追溯；真实摄像头扫码待设备确认 |
| MERCHANT-02 | 实现中 | [关联运营数据证据](evidence/operational-demo-data.md)：管理端总数及4家商户分域统计已有真实关联行支撑；GAP-07/11仍在，来源排名混合曝光/访问/导航等，核销未继承来源，今日待核销及部分图09细节缺失 |
| QUEST-01 | 验收通过 | [客户端证据](../miniprogram/VERIFICATION.md)：识别、扫码、围栏、核销、人工五种任务在HTTP闭环中通过 |
| QUEST-02 | 验收通过 | [业务证据](evidence/business-acceptance.md)：完整测试路线、集章、奖励发放及缺货后重试；真实示范路线需运营配置 |
| SHARE-01 | 实现中 | GAP-09：选字/PNG/保存入口已有；缺丽江背景配置与合成，预览文案和选字顺序与成品不一致；真码/真机另待验 |
| OPS-01 | 实现中 | GAP-03：内容发布/标签/文字反馈审核与操作审计已有；审核内容历史版本不可查 |
| OPS-02 | 验收通过 | [业务证据](evidence/business-acceptance.md)：券、活动、路线节点、人工确认和推荐参数可维护 |
| OPS-03 | 实现中 | [系统配置本地证据](evidence/runtime-system-config-local.md)：管理员可在线配置提供方、HTTPS 地址、模型、超时、加密 API Key，后续识别及状态读取数据库；权限、脱敏、跨进程与夹具调用已测；未配置仍明确不可用。真实模型/公网部署与图像样本运营仍待验 |
| ANALYTICS-01 | 实现中 | [关联运营数据证据](evidence/operational-demo-data.md)：公网库已用116条演示事件核对曝光、访问、商品详情、导航和分享统计；GAP-06/07仍在，首页/识别开始客户端未完整发送，停留/回流/集章等不足，缺业务比率与正确来源归因 |
| PRIVACY-01 | 实现中 | 当前原图不留存、授权/历史删除/保留期清理有证据；GAP-01补齐需同步样本用途/保留/删除约定；真实联系信息/供应商政策另待填写 |
| NFR-01 | 待验证 | 按D-015不作为本轮门槛；未进行生产负载与长期可用性验证，不宣称达到原建议指标 |
| NFR-02 | 待验证 | 基础鉴权、上传校验、限流和审计已实现及验证；按D-015不扩大生产安全专项 |
| NFR-03 | 验收通过 | [集成证据](evidence/integration-acceptance.md)：request_id、失败持久化、超时/不可用、后台记录与清理任务通过；真实供应商协议后补 |
| RELEASE-01 | 实现中 | [运维说明](operations.md)及[公网联调证据](evidence/public-miniapp-deployment.md)：dongba 公网 Nginx、API、HTTPS 证书和小程序地址已联通；完整生产回退、重启持久化和真机体验版仍待验证 |
| RELEASE-02 | 待外部依赖 | 当前源码、锁文件、运行说明、使用指南及验收记录已齐备；正式接收方格式与签收事项待确定 |
| DESIGN-01 | 实现中 | [本地地图与首页验收](evidence/web-amap-dashboard-local.md)：本地完成运营趋势默认 7 天、商户背景重复字删除、国内 SDK 地图卡片填满；5/5 离线浏览器检查。公网仍为上一版，本机真实地图已显示，但线上/用户环境及其余原型页面未验收 |
