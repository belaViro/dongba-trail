# 小程序公网联调证据

日期：2026-09-25；目标：`www.liorah.top` 上的 dongba 公网入口。

## 变更

- `miniprogram/config.js` 的 `apiBase` 改为 `https://www.liorah.top/api/v1`。
- Nginx 已加载 dongba 前端和 FastAPI API 路由；后端可信主机包含 `www.liorah.top`。
- 服务器原证书有效期至 2026-09-15，已由 Certbot 申请并切换到 Let's Encrypt 证书，当前证书有效期至 2026-12-24。

## 检查

服务器上执行：

```text
nginx -t
curl --resolve www.liorah.top:443:39.96.83.196 https://www.liorah.top/health
curl --resolve www.liorah.top:443:39.96.83.196 https://www.liorah.top/api/v1/privacy
openssl s_client -connect 39.96.83.196:443 -servername www.liorah.top -verify_return_error
```

结果：Nginx 配置检查通过；`/health` 返回 `{"status":"ok","version":"0.9.0"}`；业务 API 返回 HTTP 200；TLS `Verify return code: 0 (ok)`。

本地执行：

```text
node miniprogram/tests/validate-project.js
node miniprogram/tests/services.test.js
git diff --check
```

结果：小程序项目校验通过，17 项客户端服务测试通过，差异检查无错误。微信体验版需要重新编译并上传该代码版本，旧体验版仍会使用旧的 HTTP/IP 地址。

## 微信凭据临时配置

服务器于 2026-09-25 以隐藏输入方式写入匹配小程序的 AppID/AppSecret 到 `/home/admin/dongba-trail/.env`，凭据未输出、未提交 Git；随后仅重启 `scripts/serve.py --port 8010` 对应后端进程。

```text
curl --noproxy '*' -sS -k https://www.liorah.top/api/v1/privacy
curl --noproxy '*' -sS -k -H 'Content-Type: application/json' \
  -X POST https://www.liorah.top/api/v1/auth/wechat \
  --data-raw '{"code":"test-only-code","privacy_accepted":true}'
```

结果：隐私接口返回 `published: true`；伪造 code 返回 `WECHAT_CODE_INVALID`。这证明服务器已读取微信配置并调用兑换流程，但不替代真实微信 code 的真机验收。

## Ark 视觉识别适配器

2026-09-25 已将火山引擎 Ark OpenAI 兼容适配器同步到服务器，测试 API Key 仅写入服务器 `.env`。本地识别测试 24 项通过；服务器 `/ready` 返回 `provider_configured: true`。改用 `doubao-seed-2-1-lite-260915` 后，使用一张临时测试图片直接调用 Ark 成功返回“房屋”；服务端识别超时配置为60秒并关闭思考模式。临时图片已删除。完整小程序识别仍需登录会话和已发布候选字典联调。

## 优惠券剩余库存部署验证

2026-09-25 已将优惠券 `remaining_count = max(stock - claimed_count, 0)` 同步到服务器并重启后端，同时重新构建 Web 后台。公网验证结果：`GET /api/v1/coupons` 返回 `remaining_count`；`/admin/coupons` 加载的前端资源包含“剩余库存”列。
