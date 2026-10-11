# DB1404 全量字库服务器入库证据（第三步）

日期：2026-10-07
范围：DATA-01、AI-03、D-068/D-069 第三步；服务器 `39.96.83.196` 的 `dongba` MySQL 与 `https://www.liorah.top/`。

## 本次动作

用户授权“继续”后，把第二步产出的 `data/db1404_full.json`（collection `DB1404_FULL_V3`，1404 条）
与 2808 张规范化字形图批量写入服务器数据库。导入为**纯增量**，不覆盖既有 80 条
`DB1404_*` 词条，不修改小程序（小程序按用户说明走微信平台发布）。

## 前置备份

导入前用项目 `scripts/backup.py` 做逻辑备份：

```text
{"tables": 17, "rows": 2857, "media_files": 368}
归档：/home/admin/dongba-releases/db1404-full-backup/pre-import-20261007.zip（37,316,683 字节）
```

## 上传与校验

| 文件 | 本地 SHA-256 | 服务器 SHA-256 |
| --- | --- | --- |
| `scripts/import_db1404.py` | `02b0165e…97ca` | 一致 |
| `data/db1404_full.json` | `8f27f7eb…1493` | 一致 |
| `runtime/db1404-full-import.zip` | `912523da…f81a` | 一致 |

包内 `manifest.json` + `images/` 2808 张 512×512 PNG 解压到
`runtime/db1404/import-bundle-full`（105M）。导入前已备份旧脚本为
`scripts/import_db1404.py.bak-20261007`。

## 后台导入结果

命令（服务器后台 `nohup`，约 42 分钟）：

```text
.venv/bin/python scripts/import_db1404.py --manifest data/db1404_full.json \
  --bundle-dir runtime/db1404/import-bundle-full \
  --report runtime/db1404-full-import-report.json \
  --import-live --confirm-database dongba --base http://127.0.0.1:8010
```

报告 `runtime/db1404-full-import-report.json`：

```json
{"created": 1324, "existing": 80, "verified": 1404, "error_type": null}
```

- 新建 1324 条，跳过既有 80 条（幂等，不覆盖）；
- 逐条校验 1404/1404 全部 `valid`，每条 2 张媒体资源、revision 存在；
- 导入后数据库 `characters` 计数 1404（published 1403 + draft 1，编号 979 按设计保持 draft）；
- 服务器媒体目录 `runtime/media` 5664 个文件、156M。

## 公网验证

严格 HTTPS 访问 `https://www.liorah.top`：

- `GET /api/v1/characters?limit=100` 返回 `total = 1403`（仅已发布；draft 不公开）；
- 末页抽样 15 条 × 2 图，30/30 返回并可解码为 512×512 PNG，无坏图；
- `GET /api/v1/characters/DB1404_0979` 返回 404（draft 正确隐藏）。

## 未验证边界与风险（必须知晓）

- 全部 `name/intro/visual/usage` 仍是**程序模板文本、未经东巴文化专业人员审核**，
  导入即公网可见；不构成文化内容批准或识别准确率证据。
- **本次导入不保证识别变好，反而可能变差**：`backend/app/glyph_refs.py` 的
  `MAX_REFERENCES = 200` 在 1404 条字典下只把前 200 张参考字形发给模型，其余
  1204 条字无法作为参考图参与识别；同时提示词会附带更长的候选目录。
  第四步（本地图像特征粗筛 top-N 后再交模型）是本次导入的配套修复，**尚未实施**。
- 自动选样只保证同编号内两张样本“差异较大”，不代表书写质量最佳，也未与既有 80 条
  人工挑图做一致性对比。
- 本次为数据录入与媒体可达性证据，**不作为 DB1404 识别准确率证明**。

## 复现要点

```powershell
.venv\Scripts\python.exe -X utf8 scripts\import_db1404.py --manifest data\db1404_full.json `
  --bundle-dir runtime\db1404\import-bundle-full --bundle-zip runtime\db1404-full-import.zip `
  --report runtime\db1404-full-import-report.json --prepare
```
