# 旅行海报生成故障修复 — 2026-09-29

关联：D-060、SHARE-01、OPS-03。用户反馈已在服务器配置生图但小程序提示海报暂时不可用。

## 定位与修复

- 服务器生图配置可解密并通过校验；提供方、模型、尺寸、质量、超时和密钥均未改动。此前失败并非“未保存API Key”。诊断只返回白名单字段、错误码和布尔值，不输出凭据。
- 第一个阻断点是`POSTER_FONT_UNAVAILABLE`，尚未创建海报任务或调用付费AI。服务器是Alibaba Cloud Linux，已有Droid Sans Fallback中文字体，但旧代码仅查Windows/Noto的三个路径。`backend/app/media.py`补充实际安装路径并跳过不可加载的候选字体；保留原优先级，无字体时仍明确不可用。
- 字体修复后，真实链路又在微信分享码阶段失败。微信token获取成功，取码接口HTTP 200但返回业务错误41030；没有打印原始响应、token、appid或secret。该次验证在AI调用前停止，生图调用次数为0。
- `backend/app/poster_jobs.py`仅将已知`WECHAT_SHARE_UNAVAILABLE`作为可选分享码不可用处理。真实AI背景、字形/文案合成照常，结果返回`share_code_available=false`，现有小程序已有“本张未含小程序码”提示。不修改微信环境或路径校验，不伪造二维码；无关异常、未配置生图或提供方失败仍显式失败。

## 服务器交付

- 仅更新`backend/app/media.py`和`backend/app/poster_jobs.py`；未改生图/识别/微信密钥、数据库、用户数据、Nginx、Web或小程序源文件。已有服务器文件必须匹配已审查SHA-256，否则发布拒绝执行。
- 字体修复备份：`/home/admin/dongba-releases/20260929-041047-poster-font/media.py.before`。
- 分享码处理备份：`/home/admin/dongba-releases/20260929-042723-poster-font/poster_jobs.py.before`。
- 两次均检查无排队/生成中的海报任务后最小替换、正常停止并重启API，失败可还原原文件。最终PID为2015962，内部`/ready`为ready、80个已发布字条；Pillow已加载Droid Sans Fallback并确认不同中文字形不同。
- 分享码补丁首次发布因临时脚本参数索引错误在文件替换前终止，服务器源文件哈希未变；修正脚本后成功。不将失败尝试记为成功部署。

## 验证记录

| 命令/步骤 | 结果与边界 |
| --- | --- |
| `.venv\Scripts\python.exe -X utf8 -m pytest backend/tests -q --tb=short` | 最终代码231通过、92跳过，91.58秒；未启用本地MySQL专项，不能称为全量MySQL回归。现有Starlette/AnyIO弃用警告1条。 |
| `node --test miniprogram/tests/poster.test.js` | 38通过，含无分享码提示、预览/保存/分享、重试与幂等场景；首次沙箱EPERM，授权重跑通过。不是微信真机验收。 |
| `.venv\Scripts\python.exe -m ruff check backend scripts` | 通过。 |
| `.venv\Scripts\python.exe -m ruff format --check backend scripts` | 68份文件通过。 |
| `.venv\Scripts\python.exe -X utf8 scripts/export_openapi.py` | 从应用重新导出110条路径；公开接口结构未变。 |
| 真实生成验证 | 使用服务器现有配置，AI调用一次成功；背景1024×1536，合成PNG为900×1400、1288035字节，总计43.26秒。真实微信码不可用，未绘制假码。样张仅保存于受限发布目录，未创建公开媒体或用户记录；下载后目视确认中文标题、三个已发布字形和文案可见。 |
| 公网与版本 | 严格TLS的`https://www.liorah.top/health`返回200/ok；两份服务器代码SHA-256与本地交付代码一致。 |
| `.venv\Scripts\python.exe -X utf8 scripts/check_project.py`与本次文件`git diff --check` | 更新状态、需求、验收及证据后通过35条需求、证据链接、源文件及API检查；无空白错误，仅Git自动换行提示。 |

字体专项覆盖四种路径与三种字号、优先级、不可加载文件、全部不可用共16种情况。新增分享码兼容用例验证真实PNG且无假码、真实码保留、无关错误不吞、AI失败仍不生成占位海报。MySQL服务器只读用于配置和已发布字形查询；不写用户生成事件、任务、收藏或媒体记录。

## 运行记录与代码指纹

脱敏材料位于忽略目录`runtime/deploy/`：`poster-diagnose-20260929.json`、`poster-font-publish-20260929.json`、`poster-wechat-diagnose-20260929.json`、`poster-share-publish-20260929.json`、`poster-repair-backend-tests-20260929.log`、`poster-repair-client-tests-20260929.log`。SSH密码仅通过隐藏交互输入，不保存到文件。

- `backend/app/media.py`：`67131cf573c08fcf332209e44924422de50c4a60fd701fdf8476deaa2b628427`。
- `backend/app/poster_jobs.py`：`a5107d9aa3ae67fa364773f33ee9e4b1f168a20e0af4846a340b830ad50ac52c`。
- `backend/tests/test_poster_fonts.py`：`36f7de7c6c82c0f2c3ca93a767702db991380628647e1ca42f1ebd73bb1cc334`。
- `backend/tests/test_ai_posters.py`：`caeb8a6bbc7eec9c01b7066b161a662794e8a1cddbcc6970c8f1ff0161fce9d8`。
- 验证PNG SHA-256：`1066fd97648fc22ed8b7f7865aaf8daefce117bf317a902d5ec96e7c557278b0e`；服务器样张位于第二个发布目录的`verification.png`（0600），不公开用户任务或伪造用户生成事件。
- 最终真实生成与公网结果分别为`runtime/deploy/poster-repair-generation-20260929.json`及`poster-repair-public-20260929.json`。

## 未关闭的边界

微信返回的取码错误未在微信平台侧修复；真实可扫描码、正式文化字形内容审核、微信真机保存/分享与小程序上传仍分别验收。无分享码提示是明确状态，不是声称微信能力已可用。不得称为整产品生产就绪。
