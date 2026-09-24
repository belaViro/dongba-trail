# 数据补齐接口约定

2026-09-23，对应DATA-01/03/04、FEEDBACK-01、OPS-01/03、PRIVACY-01和原文GAP-01至03。
本文件约定正在实施的接口；实际完成状态以验收和对应证据为准。生成OpenAPI仍从应用导出。

## 字典与修订

字典新增 `source_no: int|null`（非负）、`alias: string[]`、`keywords: string[]`、`commercial_tags: string[]`。
保留现有tags和id；旧数据无字段时按空值兼容。新增数据进入CRUD、搜索与导出。

`GET /api/v1/admin/{resource}/{entity_id}/revisions` 返回 `{items,total}`。
每项为 `{id,entity_id,resource,version,action,actor_id,created_at,snapshot}`；snapshot保存当时完整实体、来源、媒体及审核状态。
仅运营/管理员可读。已有记录迁移为baseline，新建/修改/审核/停用保存修订；不虚构迁移前的历史。
历史版本引用的本地图片仍保留，仅授权人员可查看未发布版本。

## 识别留样

`POST /api/v1/recognize` 增加可选表单字段：

- `sample_consent: boolean = false`，必须游客明确选择，和微信登录授权分开。
- `sample_scene: string = other`，客户端场景选项paper/shop_sign/wall/wood/product/screen/other。
- 原有 `scene=camera|album` 表示上传来源，含义不变。

合法图片在同意后可关联成功或失败的识别请求进入样本池；非法图片不存储。
保存为去除EXIF的PNG，保留可审核图像，不把模型或游客候选自动视为已审核标注。
未配置模型仍返回不可用，不因留样成功伪造识别成功。不同意留样仍可调用识别。

## 样本运营

样本字段：`id,recognition_id?,user_id?,character_id?,image_uri,sample_type,scene,bbox?,quality_score?,label_source,review_status,dataset_split,dataset_version,source_ref,review_note,reviewed_by?,reviewed_at?,consent_version,created_at,updated_at`。

- sample_type：dictionary / augmented / real_photo。
- bbox：可空 `[x,y,width,height]`，对应保存PNG的像素坐标；未检测不填伪造值。
- quality_score：可空0至1，未评测留空。
- label_source：source_material / manual / user_correction。
- review_status：pending / approved / rejected。
- dataset_split：unassigned / train / val / test，仅管理字段，不触发训练。

| 接口 | 行为 |
| --- | --- |
| GET /admin/samples | `{items,total}`；支持q、review_status、character_id、recognition_id、dataset_version、offset、limit |
| POST /admin/samples/upload | multipart file上传合法图片并创建dictionary/pending样本；元数据随后编辑 |
| PATCH /admin/samples/{id} | 维护标签、场景、框、质量、来源、数据集元数据及审核；通过需有效character_id及来源，驳回需原因 |
| GET /admin/samples/{id}/image | 运营鉴权PNG预览 |
| DELETE /admin/samples/{id} | 删除记录及私有图像，保留删除操作审计 |
| POST /admin/samples/export | JSON筛选与limit，默认approved；返回ZIP含manifest.json及images，显式导出未审时如实保留状态 |
| GET /me/samples | 分页查询本人样本 |
| GET /me/samples/{id}/image | 本人鉴权PNG预览 |
| DELETE /me/samples/{id} | 删除本人样本及私有图片 |

与文字反馈通过recognition_id联查，文字审核和图像标注审核保持明确状态。
用户确认只写待审标签，不能覆盖运营已审标签；人工修改已审标注时重新进入审核或明确再次审核。
清空历史同时移除关联样本；游客样本按识别/样本保留期到期删除。运营主动上传的资料样本由运营维护/删除，和游客留样分开。
样本图片不能因被某个已发布内容引用而公开。导出及修订回看延续已有账号权限，不扩大为安全专项。

## 集成函数

业务模块暴露 `store_recognition_sample(database, settings, *, recognition_id, user_id, content, scene, consent_version)`，由识别入口在已验证图片且明确同意后调用。
`delete_samples(session, settings, *, user_id=None, recognition_ids=None, created_before=None)` 联动记录及图片删除，在事务提交后移除文件；清理任务在删识别记录前调用。

验证需要实际MySQL下的字段、修订、样本上传/复核/导出及删除闭环；微信设备能力和真实模型效果另验，测试图片须标注为合成资料。
