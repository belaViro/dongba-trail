# 运行时系统配置（OPS-03、GEO-01、AUTH-02、SHARE-01）

源为 `backend/app/system_config.py`、`backend/app/main.py`，生成的 OpenAPI 在 `openapi.json`。

- `GET /api/v1/admin/system-config`：仅 admin；返回模型类型、完整 HTTPS Chat Completions 地址、模型 ID、超时、`provider_api_key_configured`、`key_editable` 和公开的地图配置。**不返回模型 API Key**。PUT 地址允许 Base URL，例如 `/api/v3`，服务器自动补 `/chat/completions`；也允许完整端点地址。
- `PUT /api/v1/admin/system-config`：仅 admin；完整更新上述非密钥字段，`provider_api_key` 非空替换（要求服务端主密钥）；空串保持原值；`clear_provider_api_key=true` 清除数据库/环境回退；不能同时替换并清除。数据库里仅保存 Fernet 密文；审计仅存字段名和密钥操作类型，不能存密钥或原配置值。
- `GET /api/v1/public/map-config`：公开、高德 JS API Web Key/GCJ-02 默认中心/缩放；浏览器端 Key 本来可见，服务端不应下发高德安全密钥；`Cache-Control: no-store`。
- 环境变量 `DONGBA_SYSTEM_CONFIG_ENCRYPTION_KEY` 必须由运维在服务器私有环境设置为持久 Fernet 主密钥，不能在管理页设置或写入 Git；丢失/变更后已保存的 API Key 无法解密，服务明确返回不可用。更新/备份时须安全保管原主密钥。未设置时允许编辑非敏感字段，禁止在线保存模型 API Key。
- 数据库里没有覆盖时继续使用 `DONGBA_PROVIDER_*` 环境值；地图 Web Key 须由管理员在新版页面重新录入，不再从 `VITE_AMAP_WEB_KEY` 读取。地图已加载旧 SDK 的同一标签页切换 Key 时自动刷新；其他已打开页面在下一次进入地图时读取新值。
- 数据库账号、微信私钥、会话/加密主密钥、高德安全密钥、隐私发布/保留策略及网络部署参数仍属服务器运维/合规范围，不能通过公开的浏览器管理表单热更新。推荐权重继续使用 `/admin/settings`。

## D-088 识别配置与实际服务状态（OPS-03、AI-01、AI-03）

- `provider_name` 接受 `local`/`ark`/`volcengine` 兼容别名，存储和GET统一为
  `db1404-local`/`volcengine-ark`。`unconfigured` 表示未启用，不自动选择备用服务。
- `provider_endpoint`、`provider_model`、`provider_api_key_configured` 是保留的 **Ark 参数**，
  不能用作本地模型的版本/就绪状态。页面仅选择Ark时编辑这些项；切换到本地不清除已有参数或密钥。
  `provider_timeout_seconds` 是两种识别模式共用的请求超时，仍可编辑。
- GET/PUT新增只读 `local_model_version`、`local_model_threads`（服务器部署配置）和
  `recognition_service`（当前保存生效的服务快照）。本地模型文件路径、摘要和线程不能由此PUT更改。
- `recognition_service`及`GET /api/v1/admin/provider`共享生成类型 `RecognitionServiceStatus`：
  `name`/`model` 是实际提供方/实际模型，`kind` 为 `local`/`external`/`unconfigured`，
  `status` 为 `ready`/`configured`/`unavailable`/`unconfigured`，`status_message`为不含异常原文的说明。
  本地 `configured=true`/`status=ready` 须摘要校验且CPU运行时加载成功；加载缓存复用，检查放在线程池，
  不代表实拍准确率或已完成推理。外部 `configured=true`/`status=configured` 只说明配置完整，
  不做连通探测、不请求付费模型。不可用不自动兜底。
- 本地 `endpoint_configured=null`、`cpu_threads`为线程数；外部前者为布尔、后者为null；
  未启用时两者及`timeout_seconds`为null。始终返回 `automatic_fallback=false`、
  `calibrated_confidence=false`，不能据分数自动确认或宣称准确率。
- 本地/未启用不解密备用Ark密钥；`provider_api_key_configured`只代表有保存或环境提供的密钥，
  不代表当前可解密/可用。手动切回Ark仍要求密钥可解密；失败事务回滚，保持原提供方。
- `/admin/provider`允许admin/operator读取，新增 `statistics_scope=current_provider_and_model`、
  `statistics_limit=1000`；`recent_requests`/`recent_errors`只取当前提供方及模型最近最多1000条。
  `p95_latency_ms`按其中无错误请求的nearest-rank P95计算，无成功样本为null；不是每日统计。
  不混入旧模型时延；既有错标失败记录不回写，修正后失败记录使用实际模型身份。
- 后端与新版Web须一起发布；旧部署没有新增状态字段时前端明确提示状态未提供，不能从备用字段推测本地模型。

## D-058 独立海报生图配置（字段明细）

同一管理员GET/PUT新增 `image_provider_name`（`unconfigured` / `openai-compatible`）、`image_provider_endpoint`、`image_provider_model`、`image_provider_timeout_seconds`（10–240，默认180）、`image_provider_size`（1024x1536 / 1024x1024 / 1536x1024 / auto）、`image_provider_quality`（auto / low / medium / high / standard / hd）。这些选项是否被接受取决于实际提供方与模型；不伪造支持能力。

- 域名根地址补 `/v1/images/generations`，已有Base路径补 `/images/generations`，完整地址保持；只允许公网HTTPS。请求/下载不自动携带密钥重定向；返回图片URL的下载不带Bearer，并检查公网地址、大小、实际图片格式与像素。
- `image_provider_api_key` 仅PUT；空串保留，`clear_image_provider_api_key=true` 显式清除数据库及环境回退，替换/清除互斥。GET只返回 `image_provider_api_key_configured`。密文使用现有服务器Fernet主密钥；审计仅记字段及密钥操作，不记值。旧客户端省略新增字段时保持原生图配置，识别与生图密钥互不影响。
- 环境回退为 `DONGBA_IMAGE_PROVIDER_*`，示例文件不含实际凭据。未设置服务器持久加密主密钥时，管理员不能保存密钥，界面明确说明；不能将密钥写进小程序或Web构建文件。
- `POST /admin/system-config/image-models` `{endpoint,api_key?,clear_api_key?}` -> `{items:[{id}]}`，仅admin、不会生图或保存配置。空Key使用同地址的已保存Key；更换地址必须重新输入Key，避免把已保存密钥转发至新站点。20秒超时，响应仅返回模型ID；API错误不回显服务商原文。
- 服务商实际返回的模型ID供管理员选择或手填，不把第三方ID当作对底层模型来源的认证。临时测试凭据不作为正式长期配置。
