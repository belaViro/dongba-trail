# 运行时系统配置本地验收（OPS-03、GEO-01、AUTH-02）

日期：2026-09-26。此证据只覆盖本地代码和一次性 SQLite 测试，不代表公网已部署、真实模型质量或高德线上域名授权。

## 已实现

- Web「AI 与系统 / 系统配置」仅对 admin 显示并可访问；operator、merchant 无权读取或修改。
- 可编辑视觉识别提供方、HTTPS Base URL/完整端点、模型 ID、超时、API Key、地图 Web Key、GCJ-02 无点位中心经纬度和默认缩放。
- Base URL 保存后自动补 `/chat/completions`；拒绝 HTTP、私网/本机地址、用户信息、查询串和片段。
- 模型 API Key 不回显、不写入审计；服务端设置 `DONGBA_SYSTEM_CONFIG_ENCRYPTION_KEY` 时用 Fernet 加密后存储。未设置主密钥时，非敏感配置仍可保存，但在线保存 API Key 明确返回不可用。
- 识别请求、`/ready`、识别服务状态每次读取数据库运行时覆盖；第二个应用实例可读到同一配置，证明不依赖单进程内存。地图公开配置使用 `Cache-Control: no-store`，地图组件进入时读取而非依赖 Vite 构建时 Key。
- 公共地图接口只下发浏览器本来就可见的高德 Web Key、中心和缩放；不下发高德安全密钥、模型 Key、数据库/微信凭据或加密主密钥。

## 验证命令与结果

- `.venv\Scripts\python.exe -m pytest backend/tests -q`：**90 passed, 39 skipped**。
- `.venv\Scripts\python.exe -m pytest backend/tests/test_system_config.py -q`：**3 passed, 3 skipped**；覆盖权限、密钥脱敏、Fernet 存储、缺主密钥、跨应用读取、识别请求热生效、地图配置、缓存头和端点校验。
- `.venv\Scripts\python.exe -m ruff check backend scripts`：通过。
- `.venv\Scripts\python.exe -m ruff format --check backend scripts`：通过。
- `npm run typecheck`：通过。
- `npm run format:check`：通过。
- `npm run build`：通过（需在沙箱外运行，沙箱内 esbuild 子进程返回 EPERM）。
- `npm run test -- tests/map-coordinates.test.ts tests/contracts.test.ts`：**14 passed**。全量 Web 测试仍有既有 `RevisionHistory.vue` 的 SSR scoped-style 测试环境失败，不将其冒称为全量通过。
- `python scripts/export_openapi.py`：导出 97 个路径。
- `python scripts/check_project.py`：通过。

交付指纹（最终本地工作区）：`sha256:ffcb675993f2d9aa70756594cdd5265874c2545d322bee71c5da5fb63148cdfb`（229 files）。

## 运维前置

服务器必须持久设置同一 `DONGBA_SYSTEM_CONFIG_ENCRYPTION_KEY`，否则不能保存模型 API Key；主密钥丢失或变更会使已保存密钥无法解密。部署后管理员要在新版页面重新录入地图 Web Key，限制高德授权域名，并通过公网实际打开地图和发起一次真实模型请求后再做线上验收。本轮未连接服务器、未读取或上传任何凭据。
