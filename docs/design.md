# 设计要求与实际交付映射

对应原始文档第25章的20项要求。页面使用实际业务数据；原文中的字形、商户名称、
距离、准确率和统计数字均为示例，不作为运行数据填充。
模型调用按D-001/D-013保留可替换接口；数据库按D-014采用MySQL。

2026-09-23重新对照原始DOCX后，确认本映射仅说明已有页面和图源的位置，
不代表20项图示或全部业务已完整覆盖。最新差异以[原文核对](source-audit.md)为准；
样本管理、字典字段和历史、推荐及统计仍有不依赖外部资源的缺口。

## 图01至20

| 图号 | 原始要求 | 实际页面或图源 | 核对说明 |
| --- | --- | --- | --- |
| 图01 | 小程序首页 | [home](../miniprogram/pages/home/index.wxml) | 品牌、识别主入口、今日词条、地图/寻迹/好物、文化商户和四个Tab已实现；真实字典与商户待录入 |
| 图02 | 相机与相册 | [camera](../miniprogram/pages/camera/index.wxml) | 原生相机、补光、相册、预览上传、授权拒绝与质量错误；质量判断在上传后完成，无伪造实时检测提示 |
| 图03 | 结果与行动 | [result](../miniprogram/pages/result/index.wxml)、[character](../miniprogram/pages/character/index.wxml)、[merchant](../miniprogram/pages/merchant/index.wxml) | 结果确认后连接文化、变体、推荐、领券、导航、收藏与纠错；未校准分数不称为准确概率 |
| 图04 | Top-5与拒识 | [result](../miniprogram/pages/result/index.wxml) | 最多5个真实匹配候选，UNKNOWN与“都不是”人工反馈；候选数量与图片能力以提供方实际协议为准 |
| 图05 | 文化详情 | [character](../miniprogram/pages/character/index.wxml) | 审核字形、异形、来源、释义、故事、音频、同类词条及商品商户 |
| 图06 | 文化地图 | [map](../miniprogram/pages/map/index.wxml)、[merchants](../miniprogram/pages/merchants/index.wxml) | 微信真实地图、GCJ-02坐标、文化/商户/任务筛选和导航；当前中性彩色点标不冒充东巴字形 |
| 图07 | 寻迹与集章 | [quests](../miniprogram/pages/quests/index.wxml)、[quest](../miniprogram/pages/quest/index.wxml)、[stamps](../miniprogram/pages/stamps/index.wxml) | 实际节点与进度，识字/扫码/围栏/核销/人工确认，奖励及待发奖励重试 |
| 图08 | 东巴印记海报 | [poster](../miniprogram/pages/poster/index.wxml) | 选择1至3个本人已确认或收藏词条、两模板、后端PNG、保存与好友分享；真实小程序码按配置生成，未生成会明确显示 |
| 图09 | 商户看板 | `/merchant/dashboard`，[DashboardView](../web/src/views/DashboardView.vue) | 已有商户曝光、访问、导航、领券、核销、趋势与来源；缺今日待核销区域，来源计数与“按访问次数”文字口径不一致，图示未完整覆盖 |
| 图10 | 运营总览 | `/admin/dashboard`、`/admin/provider`，[DashboardView](../web/src/views/DashboardView.vue)、[RecordsView](../web/src/views/RecordsView.vue) | 已有部分统计、待审核、模型接口状态及内容/商户/POI/任务/审计入口；缺样本管理、商户地图概览及活动总览，不显示虚构线上准确率 |
| 图11 | 数据生产流水线 | [内容整理与审核](diagrams/11-content-review.mmd) | 现图只覆盖资料、词条、字形、异形审核和发布；样本字段、审核、导出和数据版本仍缺失。自训练不属首期，但用户未取消非训练数据管理；图中范围说明已纠正，完整样本流程图待实现后同步 |
| 图12 | 识别技术链路 | [接口识别边界](diagrams/12-recognition-boundary.mmd) | 图片质量、可替换提供方、词典过滤、候选确认与明确失败；不虚构YOLO/GPU已部署 |
| 图13 | 识别API时序 | [识别时序](diagrams/13-recognition-sequence.mmd) | 上传、request_id、提供方、MySQL记录、确认、文化与推荐请求 |
| 图14 | 商户转化链路 | [业务转化](diagrams/14-business-conversion.mmd) | 使用代码中的事件名称；领券和核销统计由服务端业务结果产生 |
| 图15 | 文化与商业关系 | [文化关系](diagrams/15-cultural-relations.mmd) | 已有部分实体关联与推荐权重，物理存储为MySQL实体及JSON字段；推荐覆盖缺口见原文核对，不能以关系图替代完整业务实现 |
| 图16 | 纠错闭环 | [反馈复核](diagrams/16-feedback-review.mmd) | 已有文字反馈和人工复核；没有识别原图/纠错样本关联、样本池及版本归档，现图未覆盖原文完整数据回流。不自动把用户选择当训练真值 |
| 图17 | 总体架构 | [系统架构](diagrams/17-system-architecture.mmd) | 原生小程序、Vue两后台、FastAPI模块化后端、MySQL、媒体及外部接口 |
| 图18 | 部署拓扑 | [目标部署](diagrams/18-deployment.mmd) | 对应Compose中web/api/db及持久卷；公网域名、证书和真实服务仍为上线配置项 |
| 图19 | 版本发布 | [发布流程](diagrams/19-release-flow.mmd) | 软件检查、业务联调、证据、部署与恢复；未来提供方版本另行实测，没有已实施模型灰度系统 |
| 图20 | 全景里程碑 | [8轮交付](diagrams/20-milestones.mmd) | 与当前8轮计划对应，体现资源依赖和试运营反馈；轮次不表示固定周期或已经全部验收 |

另附[领券核销与寻迹业务流程](diagrams/business-transactions.mmd)，便于顺着实际业务验收。
所有图源为可编辑Mermaid文件，可直接用于支持Mermaid的评审工具；本索引不把图源
等同于已经取得真实数据的成品页面截图。9:16小程序实机截图、16:9后台截图及最终
报告导出格式应随正式交付对象确定，避免将单元测试夹具伪装成经营内容。

## 页面验证

本机已找到 `D:/engineering_software/微信web开发者工具`。
使用其官方WCC/WCSC可执行程序，20个WXML及16个WXSS已通过本地原生编译。
该检查不需要AppID、不上传小程序；不代表已在微信真机完成相机、地图、分享验证。
复现命令、客户端业务链结果及代码指纹保存在
[小程序验证记录](../miniprogram/VERIFICATION.md)。

客户端页面控制器还通过隔离HTTP服务串联：微信登录接口、图片上传、候选确认、
文化与商户推荐、领券、鉴权下载真实券二维码和商户核销、五种任务条件、奖励、真实PNG海报、保存与好友分享
返回值、收藏及历史清理。该测试使用临时SQLite数据库及微信/模型/设备能力替身，
仅验证控制器与API兼容；MySQL行为由后端另行测试，不能合并称为小程序真机或MySQL跨端验收。

## 真机与内容待验收

- 实际AppID/域名及隐私配置后的微信登录、授权拒绝和登录过期处理。
- iOS/Android相机、相册、补光、图片上传、音频、原生地图与GCJ-02导航。
- 已审核真实词条、同字异形、丽江实景媒体及可运营商户路线。
- 已配置模型的真实候选质量、未知图片和失败情况；当前占位接口保持明确不可用。
- 实际店内扫码/核销/围栏/人工节点，完成路线后领取奖励并扫描海报上的真实小程序码。

上述外部项目需在正式使用前按实际资源验证；同时仍须补齐原文核对发现的本地业务缺口，
当前页面与图源不能作为全部业务已完成的证据。
