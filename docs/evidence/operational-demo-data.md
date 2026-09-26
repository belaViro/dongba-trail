# 公网正式库关联运营数据证据

日期：2026-09-25
范围：AUTH-02、MERCHANT-01/02、COUPON-01/02、ANALYTICS-01；服务器 `39.96.83.196` 的 MySQL `dongba` 库。

## 目标与统计口径

用户反馈此前录入实体后，管理员“运营概览”的“用户总数”没有变化。代码核对确认 `/api/v1/admin/stats` 每次请求都会调用 `statistics(session)`，其中 `users` 是 `users` 表总行数，不是商户、词条或其他 `entities` 行数。因此只创建门店、商品或优惠券不会增加用户总数。

本轮新增 `data/operational_demo.json` 与 `scripts/seed_operational_demo.py`。脚本默认只读预演，正式执行必须同时提供 `--apply --confirm-database dongba`；通过现有内容、账号、领券和核销业务函数写入，保持库存、审计、修订、事件和商户归属一致。全部人名、门店、电话和地址均为虚构运营演示资料，不冒充已经核验的真实商户或顾客。

## 关联数据

- 4家已发布商户及4个商户账号：东巴纸坊·古城文化体验店、纳西茶香小院、玉水银饰手作馆、雪山礼物与哈达工坊；
- 24个游客账号，和商户账号一起真实写入 `users` 表；
- 4个商户POI、8个商品、4个活动、8张有效优惠券；
- 门店、POI和商品关联已发布的 DB1404 词条；
- 36次用户领券，其中24次由对应商户账号到店核销，另12张保持可使用；
- 16条明确标记为 `operational-demo` 的模拟识别记录，只用于联动看板，不作为模型识别准确率证据；
- 116条首页、曝光、商户详情、商品详情、导航和分享事件，另有领券与核销服务端事件。

## 服务器执行结果

只读预演的基线：用户4、识别5、领券0、核销0。执行：

```text
.venv/bin/python scripts/seed_operational_demo.py --apply --confirm-database dongba
```

事务提交并由脚本逐项校验后：

| 指标 | 执行前 | 执行后 | 增量 |
| --- | ---: | ---: | ---: |
| 用户总数 | 4 | 32 | 28 |
| 今日活跃用户 | 1 | 10 | 9 |
| 识别记录 | 5 | 21 | 16 |
| 优惠券领取 | 0 | 36 | 36 |
| 到店核销 | 0 | 24 | 24 |

角色总数为管理员1、商户5、游客26；其中包含库中原有账号。4家新增商户分别产生8/9/10/9次领取，每家6次核销，能够在商户范围统计中独立查询。

第二次执行同一命令的 `created` 为空，用户仍为32、领取仍为36、核销仍为24，全部统计增量为0，证明脚本幂等。优惠券 `claimed_count` 逐券与实际领取记录计数一致。

运行服务无需重启；通过 `127.0.0.1:8010/api/v1` 的当前服务读取到4家新增商户和8张新增优惠券。管理员概览接口与本次验证调用同一个无缓存统计函数；浏览器 MCP 本轮因工具缺少 `sandboxPolicy` 元数据未能建立页面会话，因此未把浏览器截图列为证据。

服务器报告保存在忽略目录：

- `runtime/operational-demo-report.json`；
- `runtime/operational-demo-rerun.json`；
- 新建商户账号的随机密码仅保存在权限收紧的 `runtime/operational-demo-merchant-credentials.json`，未输出到日志或提交Git。

## 本地验证

```text
SQLite隔离业务验证：首次创建28用户、36领取、24核销、16识别、116业务事件；第二次创建0

.venv\Scripts\python.exe -m pytest backend\tests -q
85 passed, 36 skipped, 1 warning

.venv\Scripts\python.exe -m ruff check backend scripts
All checks passed!

.venv\Scripts\python.exe -m ruff format --check backend scripts
51 files already formatted

.venv\Scripts\python.exe scripts\check_project.py
Project checks passed: 35 requirements, evidence links, source and API

.venv\Scripts\python.exe scripts\code_fingerprint.py
sha256:fbbf3c3f0b44740f3564c342bc70a473053c41c3253c5d70859eeca116b3189e
files:213
```

SQLite仅用于快速验证脚本业务路径；本轮最终数据写入和统计核对均在服务器 MySQL `dongba` 库完成。

## 配图补充

日期：2026-09-25。4家商户和8个商品原先 `image_url` 为空，小程序列表会跳过缩略图。新增 `data/operational_demo_images.json` 与 `scripts/enrich_operational_demo_images.py`：从 Unsplash 下载与门店、纸品、茶席、银饰、雪山和礼盒主题匹配的图片，裁成 1200×800，经 `save_asset` 与 `save_entity` 写入，保留发布状态、审计和修订。图片按 Unsplash License 使用，只作虚构演示配图，不表示这些是已核验商户或商品的实拍。

优惠券、活动和 POI 的数据模型没有独立图片字段，因此不另造图片地址。

服务器执行：

```text
.venv/bin/python scripts/enrich_operational_demo_images.py --apply --confirm-database dongba
.venv/bin/python scripts/enrich_operational_demo_images.py --apply --confirm-database dongba --replace OPS_PRODUCT_TEA_PACK
.venv/bin/python scripts/enrich_operational_demo_images.py
```

首次写入12张；烤茶体验包与茶馆首图重复，已单独替换为茶叶图。随后只读预演为附加0、跳过12。公网 `https://www.liorah.top/api/v1/merchants` 与 `/products` 返回全部12个图片地址；严格 TLS 下载后均可解码为 1200×800 RGB，烤茶包与茶馆图片内容不同。

本轮脚本检查：

```text
.venv\Scripts\python.exe -m pytest backend\tests\test_operational_demo_images.py -q
2 passed

.venv\Scripts\python.exe -m ruff check scripts\enrich_operational_demo_images.py backend\tests\test_operational_demo_images.py
All checks passed!
.venv\Scripts\python.exe scripts\check_project.py
Project checks passed: 35 requirements, evidence links, source and API

.venv\Scripts\python.exe scripts\code_fingerprint.py
sha256:b538ffa05841519776a90d5754bd1ff446d75e28b7201e55ad48fb100e3e0354
files:216
```
