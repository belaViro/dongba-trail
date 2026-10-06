# 运营演示内容扩充 — 2026-09-28

关联决策：D-056。需求：QUEST-01/02、MERCHANT-01、GEO-01、COUPON-01、OPS-02。

## 交付范围与环境

用户要求再增加两条路线，并增加活动、店铺和文化点位。本次新增的是明确披露的虚构演示内容，不是核准的真实门店、展览、活动预约、可消费优惠或实地导航资料。不添加或改写字典释义；文化关联只引用已有已发布DB1404条目。

**仓库及本地MySQL已完成；公网数据库尚未同步。** 公网只读检查仍返回原有1条路线。root/admin现有SSH密钥均认证失败，没有进行服务器文件替换、数据库写入或进程重启。不得将本地验证称为公网已上线。

| 内容 | 本次新增 | 演示数据合计 |
|---|---:|---:|
| 路线 | 2 | 3 |
| 路线节点 | 8 | 11 |
| 店铺 | 4 | 8 |
| 门店POI | 4 | 8 |
| 独立文化POI | 6 | 6 |
| 活动 | 8 | 12 |
| 商品 | 8 | 16 |
| 优惠券 | 4 | 12 |

## 两条新路线

- `OPS_QUEST_HANDCRAFT_02` 古城纸艺与手作之旅（演示）：书屋扫码 → 纸字展签识别 → 手作纹样点位150米围栏 → 陶绘工坊扫码；完成奖励`OPS_COUPON_POTTERY_15`。
- `OPS_QUEST_SHUHE_03` 束河织色与纸语慢行（演示）：织色小院扫码 → 雪山主题展点150米围栏 → 纸品留念点识字 → 明信片屋扫码；完成奖励`OPS_COUPON_POSTCARD_8`。
- 原`OPS_QUEST_OLD_TOWN_01`及三个节点保留，未改变已参与路线的有效期、条件、奖励或QR密钥。新QR密钥由应用生成，不写入配置/证据，公开接口不返回。
- 新商户：古城象形书屋、巷里陶绘工坊、束河织色小院、雪山纸语明信片屋，名称均带“演示”；新文化点位无商户归属，可独立出现在文化地图分类。
- 新时效内容沿用种子窗口：执行时间前30天至后180天；已存在内容不会被重跑续期。新增库存、价格及名额仅为演示值。无核准联系电话/照片时不填造数据，图片沿用客户端缺图降级。

## 实现与数据保护

- `data/operational_demo.json`升级`OPS_DEMO_20260928_V2`，保留原ID及原有顺序，新增独立`cultural_pois`。
- `scripts/seed_operational_demo.py`取消节点固定绑定单一路线，改为每节点显式`quest_id`；计划及验证数量从目录动态读取，不再硬编码1路线/3节点。
- 新增`--content-only`，使用已有内容服务完成引用验证、审核发布、修订/审计及券库存初始化；跳过演示账号、识别记录、行为事件、领券和核销生成。本次没有创建新商户登录账号，也不回显任何凭据。
- 先备份再增量创建，仅不存在的ID会写入；重跑`created={}`。没有覆盖既有商户图片、手工内容或原路线参与记录。
- 新测试验证目录唯一性、引用/顺序、演示标识、奖励有效期、已报名原路线不变、无模拟行为新增、重跑不新增修订，以及两条新路线分别完成/重复打卡只领取各自一张奖励。

## 验证与产物

所有Python命令均使用项目`.venv\Scripts\python.exe`。目录：`runtime/operational-expansion-20260928/`（忽略目录，不提交备份和运行报告）。

- 本地MySQL **8.0.44 / 127.0.0.1:3307 / dongba**。写入前`backup.py backup .../local-before.zip`成功：17张表、511行、20个媒体文件；备份含业务与认证数据，不公开归档内容。
- 设置`DONGBA_RUN_MYSQL_TESTS=1`后运行`-m pytest backend/tests/test_operational_demo.py -q`：**3通过**（目录、SQLite隔离单测、专用`dongba_test`的MySQL闭环）。识别记录为测试夹具，不证明真实识别准确率；测试坐标不证明实地打卡准确率。
- `scripts/seed_operational_demo.py --content-only --apply --confirm-database dongba --report .../local-apply.json`创建数量与上表一致；`local-rerun.json`中`created={}`。
- 两次实写报告中用户、今日活跃用户、识别、领券、核销的`dashboard_delta`均为0。
- 以真实本地数据库通过TestClient调用公开HTTP接口：路线3、店铺8、点位14、活动12、商品16、券12；各接口200；路线节点数3/4/4，奖励关联正确，节点均不暴露`qr_token`。见`local-public-api.json`。这不是微信真机导航或视觉验收。
- 设置`DONGBA_RUN_MYSQL_TESTS=1`后执行`-m pytest backend/tests -q`：**183通过、1跳过**，耗时287.39秒；唯一跳过为SQLite参数下的MySQL专用备份测试，并非MySQL集成未执行。既有Starlette/AnyIO弃用警告1条不影响结果；原始日志`backend-mysql-tests.log`。包含新增专项测试、两条路线独立奖励闭环和既有业务回归，结果对应本节记录的代码指纹。
- `-m ruff check backend scripts`、`-m ruff format --check backend scripts`：通过（64份Python文件）。`scripts/check_project.py`：35条需求及证据/源文件/接口漂移检查通过。`git diff --check`通过，只有Git的LF/CRLF提示，没有空白错误。
- 公网`GET /api/v1/quests`只读返回`total=1`、`OPS_QUEST_OLD_TOWN_01`；见`public-before.json`，因此新数据暂未出现在连接公网的小程序中。

## 待授权发布

已准备本机交互式发布助手：

```powershell
.venv\Scripts\python.exe runtime\operational-expansion-20260928\publish.py
```

必须在本机终端执行并按提示输入SSH密码，不通过聊天、参数或环境变量传递密码。助手验证known_hosts和文件哈希、拒绝覆盖未知服务器版本，先备份数据库/媒体和两个原始源文件，再仅同步数据JSON与种子脚本，以`content_only=True`增量写入并验证重跑。源文件检查失败会恢复原文件且不写库；不会重启API或上传小程序。助手只完成语法及静态检查，**因缺少有效服务器认证，本轮未实际执行服务器发布**。发布完成后还须复核HTTPS接口、运行报告并更新本证据/状态，不能仅凭脚本存在认定上线。

## 代码指纹

- 整仓代码指纹：`sha256:e5619e6643e263a98fd1ca8a9d6b2cb7d2a3023d2ddceedd2b758e10efcc8c3c`，282文件；范围含原有未提交工作，未改动与本任务无关的业务代码。
- `data/operational_demo.json`：`adf947560c1cadddaf4a21864110ed316122778a0836145da741234269ec82a4`。
- `scripts/seed_operational_demo.py`：`bfce96636dbdb29a9503dc4061672b793a5c71014e7bb0cf11654a1b52834f5c`。
- `backend/tests/test_operational_demo.py`：`c7262a91376dd6267e10daa57963a1631bec11917eeab0e93feace340f8b050a`。

## 未关闭的边界

- MERCHANT-01的活动按字/文化主题关联字段、GEO-01的真机导航/实地坐标与路线优惠卡缺口，均不因增加演示数据而视为关闭。
- 新照片未提供；不复制无关商户照片冒充新店铺。所有新地点、活动、库存、价格及名额应在真实运营前经过核验。
- 公网发布及微信实机展示尚未验证，原D-055小程序界面本身仍需单独上传微信。
