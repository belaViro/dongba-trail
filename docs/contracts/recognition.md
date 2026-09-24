# 识别接口边界（第1轮）

生成的HTTP契约：`openapi.json`。代码是契约源，使用 `python scripts/export_openapi.py` 更新。

## HTTP

- `GET /health`：进程存活，不证明供应商或数据库可用。
- `GET /ready`：检查提供方配置和发布字典；缺任一项返回503。不代替供应商连通性及效果验证。
- `GET /api/v1/characters/{id}`：返回已发布词条，其他情况404。
- `POST /api/v1/recognize`：multipart字段 `image`、`scene=camera|album`。
- 返回与响应头共享的 `request_id`；每次请求由服务端生成。
- 当前每次请求只处理主目标；不承诺多框检测能力，待供应商验证。

## 状态与错误

- `NEED_USER_CONFIRM`：至少一个候选匹配了已发布词条，需要用户确认。
- `UNKNOWN`：没有候选能够匹配已发布词条。
- `CONFIRMED`：当前不输出；校准规则或用户确认流程实现后再开放。
- 400：图像无效；413：超过文件或像素限制；415：不支持的格式；422：字段验证失败。
- 503：依赖未配置/字典不可用/提供方暂不可用；504：提供方超时；502：输出不符合约定。
- 错误体：`request_id`、`code`、`message`，不包含提供方异常文本或密钥。

## 适配器内部协议

`RecognitionProvider.recognize(image, media_type, characters)` 为异步接口，返回 `ProviderResult`。
候选必须包含标准 `character_id`。供应商仅返回名称时，适配器需要按已审核字典做无歧义映射；禁止自动创建词条。
候选数量最多5个；提供方可选返回 `score`（0至1），业务不将其作为准确率。
输出记录 `provider`、`model_version`。未匹配ID被丢弃，同一ID去重，文化内容从内部字典读取。

供应商尚未确定，当前提供方明确不可用。测试通过依赖注入使用固定测试替身，仅验证编排规则。

## 待后续补充

认证、请求限额、原图存储与反馈关联、经纬度/隐私授权、数据库日志、确认接口、多框和经过评估的自动确认规则。
