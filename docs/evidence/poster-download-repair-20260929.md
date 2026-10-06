# SHARE-01 海报下载地址修复（D-061，2026-09-29）

## 有界任务与原因

用户已有真实AI海报，但小程序提示“海报已生成，图片下载失败。重试只会下载原图”。本轮只恢复原PNG下载，不再次调用生图、不变更运营配置、密钥、字形、任务数据或用户记录。

线上只读核对发现唯一已完成任务保存了`http://127.0.0.1:8010/api/v1/media/...png`；服务器内部与公网HTTPS的同一资源均返回200。`scripts/serve.py`覆盖`public_base_url`为回环地址，旧`generate_poster`用该值拼接URL，客户端又原样使用绝对URL，导致手机访问自己的回环地址。

## 实现与增量发布

- 新生成结果返回站点相对媒体路径；旧任务通过`job_view`在返回时转换严格匹配的回环媒体地址，不重写数据库。仅HTTP(S)、已知回环主机、32位小写十六进制PNG文件名且无用户信息/查询/片段匹配；第三方、无关路径、签名链接不改。
- 小程序`api.mediaUrl`在下载原图之前兼容旧缓存URL，复用`config.apiBase`域名；原任务重试控制器不变，不增加POST/GET或AI调用。
- 单文件备份并替换服务器`backend/app/poster_jobs.py`，检查原/新SHA-256及无进行中海报后正常重启API，ready通过（80个发布字）。未部署小程序新包、未修改Nginx/数据库/环境/运营配置。
- 备份：`/home/admin/dongba-releases/20260929-045342-poster-font/poster_jobs.py.before`。复用已有回滚发布工具，目录后缀沿用其名称。
- 原服务端哈希：`a5107d9aa3ae67fa364773f33ee9e4b1f168a20e0af4846a340b830ad50ac52c`；新哈希见下表，与线上一致。

## 实际原图验证（没有调用AI）

- 唯一原任务创建于2026-09-29 04:37:41 UTC（北京时间12:37:41），已完成。部署前后任务数均1、`poster_generate`事件数均1，持久化旧URL保持原样；读取视图已转换为相对URL。
- 服务端内部HTTP及公网HTTPS下载均200、`image/png`，两者逐字节等于原文件。
- 从Windows本机使用严格HTTPS `curl.exe --fail --silent --show-error --proto '=https' --max-time 30 <existing-public-media-url> --output runtime/deploy/poster-original-recovered-20260929.png`取回同一原图。首次受沙箱代理阻断，获准后重试原下载成功，未调用AI。
- Pillow加载成功：PNG、900×1400、1,241,894字节。
- 原文件、修复后线上文件、本机下载文件SHA-256均为`0503537c500a4e884d1ec0333a25f20be42fd468f1a0a358699bb947b46006b3`。
- 脱敏诊断/发布记录保存在`runtime/deploy/poster-download-before-20260929.json`、`poster-download-after-20260929.json`、`poster-download-apply-20260929.json`；没有输出密钥或访问令牌。

## 验证命令与结果

全部Python使用项目`.venv\Scripts\python.exe`。本地工作区包含此前未提交修改；以下测试对应交付时文件指纹，不以旧聊天结果代替执行。

| 命令 | 结果 |
| --- | --- |
| `python -m pytest backend/tests/test_ai_posters.py -q` | 106通过、30跳过；隔离SQLite/模拟提供方，不是实际生图或MySQL回归 |
| `python -m pytest backend/tests -q` | 241通过、95跳过，64.43秒；未启用本地MySQL专项，1项已有Starlette/AnyIO弃用警告 |
| `node --test miniprogram/tests/poster.test.js miniprogram/tests/services.test.js` | 61通过；首次沙箱EPERM后获准重跑；含原图缓存下载重试、无新增请求及URL边界 |
| `python -m ruff check backend scripts` | 通过 |
| `python -m ruff format --check backend scripts` | 68文件通过；新增测试已格式化 |
| `node miniprogram/tests/validate-project.js` | 18页、JSON/JS语法、路由及WXML事件通过 |
| `python scripts/export_openapi.py` | 重新导出110路径；接口字段未增加 |
| `python scripts/check_project.py` | 35项需求、证据链接、源文档及API漂移通过 |

生产MySQL仅作现有任务/事件只读核对，不执行测试表重建、种子或迁移，不冒充MySQL集成回归。自动化使用合成图片并断言只生成一次；真实资源验证只GET既有图片。微信downloadFile白名单、正式包发布、真机保存/分享、微信41030仍需相应环境另验。旧运行实例若缓存旧URL，需更新小程序代码；重新编译可能清空页面内存任务，不应因此重新付费生成，既有PNG已单独取回。

## 代码指纹

基线HEAD：`858e99d`（脏工作区；按文件指纹确定本轮交付）。小程序结构检查聚合指纹：`327c2d2ed6108e80426a87a630b192ff22edd8ec2305af68950dab8571d3833d`。

| 文件 | SHA-256 |
| --- | --- |
| `backend/app/poster_jobs.py` | `f06ccba06cc0a9b0dbceb260b80ebb2dca3ca78cbfb9334abe143d97bc5c8bdd` |
| `miniprogram/utils/api.js` | `e44a3bdcaaf9b39f5afc2381c8d49fe2f7b34d9031b7a0b9761e978a24003efd` |
| `backend/tests/test_ai_posters.py` | `62459e5111cca2f908e6da6c9effbbb885c867b2b406729d0e78d1f61ae1ac8b` |
| `miniprogram/tests/poster.test.js` | `8f4e55efc9902ccc00ccf158c4ba2f8d6ceace736f348747273e1ebe91dddedc` |
| `miniprogram/tests/services.test.js` | `7fd223daaa26100b21e86686b72d69f7bdb5d693b139495bb2b74fd70e2a22cd` |
