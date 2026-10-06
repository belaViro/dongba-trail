# 寻迹演示路线配置证据（2026-09-28）

## 配置结果

- 新增已发布路线 `OPS_QUEST_OLD_TOWN_01`：古城东巴文化寻迹（演示）。
- 节点1 `OPS_QUEST_NODE_PAPER_QR`：纸坊扫码集章，系统自动生成不少于16字符的QR密钥；公开接口不返回密钥。
- 节点2 `OPS_QUEST_NODE_TEA_GEOFENCE`：茶院到店打卡，关联 `OPS_MERCHANT_TEA` / `OPS_POI_02`，半径150米。
- 节点3 `OPS_QUEST_NODE_PAPER_RECOGNITION`：识别 `DB1404_1241`，关联纸坊商户与点位。
- 完成路线奖励 `OPS_COUPON_PAPER_20`；路线、商户和地址继续明确标注为演示数据。

## 验证

- `ruff format` 与 `ruff check scripts/seed_operational_demo.py`：通过。
- 独立MySQL 8.0.44（127.0.0.1:3307）实写：创建1条路线、3个节点；脚本内校验 `quests=1`、`quest_nodes=3`。
- `pytest backend/tests/test_business_api.py -q -k 'quest or node or stamp or reward'`：4通过、4项MySQL参数化用例因该次未开启环境开关而跳过；此前专项MySQL回归仍保留在业务验收证据中。
- 本地公开接口：路线列表200且总数1；详情200、节点顺序为QR/围栏/识别、奖励券关联正确；所有公开节点均不含 `qr_token`。
- 数据库受控检查：QR密钥已自动生成且长度合规，未输出密钥内容。

## 公网部署

- 部署前已备份服务器数据与媒体：`runtime/backups/quest-before-20260928-103743.zip`，备份包含17张表、2052行数据和352个媒体文件。
- 配置与脚本通过SHA-256核对后同步到 `/home/admin/dongba-trail`，服务器端 `ruff check` 与格式检查通过。
- 在公网MySQL数据库执行幂等脚本后创建1条路线和3个节点；再次执行时 `created={}`，未重复创建数据。
- 公网 `https://www.liorah.top/api/v1/quests` 与路线详情接口均返回200；详情节点顺序为QR、围栏、识别，奖励券为 `OPS_COUPON_PAPER_20`。
- 公网详情不返回 `qr_token`；数据库受控检查确认密钥存在且长度合规，未读取或记录密钥内容。
- 服务器 `/health`、`/ready` 均返回200。本次只更新幂等运营数据，不需要重启API进程。

## 交付指纹

- `data/operational_demo.json`：`sha256:933ff95f64e6e6b6cf18ee31817c6ad9c7da05a0fc7387c22a03340dea8590be`。
- `scripts/seed_operational_demo.py`：`sha256:92cd17aafced435ef953a415eb81dfbd8b69eab0584a7b7b2c10bf959375b0ad`。

## 限制

- 演示商户及地址不代表真实合作关系；真实上线前需运营替换为核验后的商户、POI坐标、路线时段和奖励库存。
