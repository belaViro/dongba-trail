# SHARE-01 / D-063：修复切换风格仍趋同

日期：2026-09-29。范围仅限海报风格生成指令、回归测试和配套记录；不改生成配置、密钥、用户内容或原图。

## 原因与实现

小程序切换事件已经更新 `template` 并清空旧图/旧任务，后端也收到选中的值。根因是D-062公共指令强制暖色纸张、深棕书法标题、古城与雪山拼贴，末尾要求风格只能微调参考图，导致参考图压过选择。

- 改为四套互斥的美术方向，置于提示词最前：纸风为暖色纤维纸/底部拼贴；雪山为冷蓝全幅高山摄影；古城为暖琥珀街巷摄影；简约为至少70%纯白/细线小山/无照片。
- 明确每套方向的配色、材质、版式、主景占比与禁用元素。参考图仍上传，但仅供完成度/内容层级参照，不能覆盖所选风格。保留审核字形、文案白名单、不加业务提示及真实码边界。
- Multipart集成测试覆盖4种风格×4种端点×2种真实码情况，断言只有选中的指令、指令优先级、素材字节顺序和内容边界。
- 小程序新增纸→雪山→古城→简约→纸全链路测试，断言每次清旧图、发送正确template、生成新的幂等令牌；旧图下载不触发重新生成。

## 自动验证（当前交付代码）

| 命令 | 结果 |
| --- | --- |
| `.venv\Scripts\python.exe -m pytest backend/tests -q` | 281通过、96跳过、1条Starlette/AnyIO弃用警告，123.94秒 |
| `.venv\Scripts\python.exe -m pytest backend/tests/test_ai_posters.py -q` | 146通过、31跳过；夹具边界不代表真实视觉准确率 |
| `.venv\Scripts\python.exe -m ruff check backend scripts` | 通过 |
| `.venv\Scripts\python.exe -m ruff format --check backend scripts` | 70文件符合格式 |
| `node --test miniprogram/tests/poster.test.js miniprogram/tests/user-copy.test.js miniprogram/tests/services.test.js` | 68通过，0失败 |

日志：`runtime/poster-style-backend.log`、`runtime/poster-style-focused.log`、`runtime/poster-style-mini.log`。

## 服务端发布

2026-09-29发布目录 `20260929-101516-poster-style`。只更新 `backend/app/image_provider.py`，旧版备份、源/目标哈希检查、确认无待生成任务后重启；内部就绪通过。API新PID为2016695。数据库、密钥和配置均不修改。

- 旧哈希：`3eb702bf8f23f789dad48509a5d78b23615e32a26f32f6c09b815a70de6f3c2f`。
- 新哈希：`145ccbdeca06576b5240076391c233e254bf8c00f221a03adb09c9638d967387`。
- 公网严格HTTPS `/health` 返回JSON `status=ok`；公开 `/ready` 会命中Web SPA，因此不把其HTML 200当作API就绪证据。
- 旧海报再次下载并验证SHA-256 `0503537c500a4e884d1ec0333a25f20be42fd468f1a0a358699bb947b46006b3` 未变。
- 发布记录：`runtime/deploy/poster-style-deployment.json`；健康：`runtime/deploy/poster-style-public-health.json`。

## 真实风格对比

两次有界真实调用使用相同参考图、山/月/花三张素材（共4张图），相同文案“在丽江，收藏时光里的美好。”：

- 简约风成功：45.04秒，1024×1536，705152字节；SHA-256 `1bf61de37e3dd0ee4c0bc168a8aa7655413747268d6734985d19e7e73599f02d`。本地 `runtime/deploy/poster-style-minimal-20260929.png`；已目视检查，大面积白底、墨色标题和三枚字形、页底细线雪山，未沿用纸风的古城摄影/暖黄纸张，文案正确，无业务注释。与D-062实际纸风成图区别清楚。
- 雪山风失败：1.79秒，适配器返回 `IMAGE_PROVIDER_UNAVAILABLE`。没有图片，未继续自动重试，不将单元测试或旧纸风图片冒充本次雪山视觉验收；也不推测上游是否计费。
- 本轮2次上游尝试、1张成功样例，不宣称四种风格全部真人视觉验收。古城/纸风新指令与雪山指令通过请求结构回归，仍可由后续真实生成继续验收。
- 结果 `runtime/deploy/poster-style-generation.json`；服务端私有目录 `20260929-poster-style-review`，未发布测试图、不创建用户任务。前后已有用户任务6/生成事件6均保持；不和先前D-062阶段的2条记录混为同一时点。
- 项目检查 `.venv\Scripts\python.exe scripts/check_project.py` 通过：35条需求、证据链接、原文与API一致性。

## 当前交付指纹（SHA-256）

| 路径 | SHA-256 |
| --- | --- |
| `backend/app/image_provider.py` | `145ccbdeca06576b5240076391c233e254bf8c00f221a03adb09c9638d967387` |
| `backend/app/poster_art.py` | `8f12f9aae8bf21ed29fc00bfae76ecb96e598ec5316d32ef13022c4e92d98c4c` |
| `backend/app/poster_jobs.py` | `edc9c7ca37820271ea9e70224565e17f29687ca51647bccc476202dc850a8707` |
| `backend/app/media.py` | `b0271c10645a6cea22fba3fcce5394983dbd67d18f0aa397454e7dc624870eb5` |
| `backend/assets/poster-reference.jpg` | `4aaff4ebafc99b725a641b916d4392fc3ca9b6ef0e33a01c7fbcfb5f2757942f` |
| `backend/tests/test_ai_posters.py` | `222724540a38b001b418c1e9621f2cc1498177f9d15772f06c49df0f65f9e60b` |
| `backend/tests/test_integration.py` | `250646560968ead93217ab7f17300ff5461781fe5c44ac0be3414db74070637b` |
| `scripts/prepare_poster_reference.py` | `28a924b5bb0919e5e354686dfeea3e868960e79596f5070d463770fbfee0ff6d` |
| `miniprogram/pages/poster/index.js` | `81ce05d7afa63466bd32929fcff56338447e44ed17604a05485de905b0957fd1` |
| `miniprogram/pages/poster/index.wxml` | `633b0f76177bc320ac56628873cdcbfa20f542fd88ccb83fe66dfbf21970db77` |
| `miniprogram/pages/poster/index.wxss` | `1f9c6a5f1962fb2355ccb0310aac3262ca9f7dfb311cefab2bfdab9b394b9b7c` |
| `miniprogram/tests/poster.test.js` | `7715f814d91893be1aee6c120d1b5198529bf2e72b1c29866793b0bfc2e7f29a` |
| `miniprogram/tests/poster-visual.cjs` | `60c41ce537e799c862dd32ee0eeeedc7a54a52cca813a665e6b5efc58480cab6` |
| `miniprogram/tests/user-copy.test.js` | `3079b2270d83de5e0c342406912f1195b47343bf42de83e53f1cb3c319e7928d` |
| `web/src/views/SystemConfigView.vue` | `816e0352a2cd18d6454a524ea479357762880b6f88dde51c55f217f163a3be44` |

## 限制

未启用本地MySQL专项，96项跳过不等于通过；夹具测试不证明模型输出准确率。服务端风格修复不需修改小程序协议；此前去除提示的前端改动仍需重新编译/上传，未代用户提交微信版本。旧图不会因切换标签自动重绘，需要选风格后重新生成。AI逐字/字形准确性、真实码扫描与微信真机体验仍待验。
