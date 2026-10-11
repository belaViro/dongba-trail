# DB1404 参考字形粗筛修复与服务器部署证据（第四步）

日期：2026-10-07
范围：AI-01、DATA-01、D-071；后端 `backend/app/glyph_refs.py`、`backend/app/recognition.py`；
服务器 `39.96.83.196` 的 `/home/admin/dongba-trail` 与 `https://www.liorah.top/`。

## 背景问题

第三步把 `DB1404_FULL_V3` 全量 1404 条导入服务器后，`load_references` 仍按字典顺序
只取前 `MAX_REFERENCES = 200` 张参考字形。其余 1204 条字永远无法作为参考图参与识别，
导入后识别质量可能反而下降。本次修复不改模型、不训练、不加 GPU。

## 代码变更（本地）

- `backend/app/glyph_refs.py`
  - 新增 `FEATURE_SIDE = 16` 与 `_feature_cache`；
  - 新增 `_candidate_pairs` / `_feature` / `_cached_feature` / `_rank_candidates`；
  - `_feature`：灰度 → autocontrast → 阈值 128 取墨迹 bbox → 等比缩放到 16×16 白底画布；
  - `_rank_candidates`：对查询图与每条已发布字形的 16×16 特征做 L1 距离排序，读不到特征的
    条目一律保留在末尾，绝不因坏图丢弃字；
  - `load_references(characters, media_directory, limit=MAX_REFERENCES, query=None)`：
    仅当给定 `query` 且候选数超过 `limit` 时按特征排序，无 `query` 时保持原有前缀顺序。
- `backend/app/recognition.py`
  - 调用改为 `load_references(characters, settings.media_directory, query=image)`。

## 本地验证

| 检查 | 命令 | 结果 |
| --- | --- | --- |
| 后端测试 | `.venv\Scripts\python.exe -X utf8 -m pytest backend/tests -q` | 318 passed / 97 skipped |
| 静态检查 | `ruff check backend scripts` | 通过 |
| 格式检查 | `ruff format --check backend scripts` | 75 files already formatted |
| 项目检查 | `scripts/check_project.py` | Project checks passed: 35 requirements, evidence links, source and API |
| 自匹配 top-200 | `runtime\db1404\bench_topn.py` | 40 / 40（1404 条 published_like 全集，随机基线约 14%） |

新增回归：

- `test_reference_loader_shortlists_by_local_feature_instead_of_prefix`：无 `query` 回退前缀序；
  有 `query` 时目标字进入 top-2、不相似字被排除；
- `test_reference_loader_query_keeps_every_character_reachable`：随 limit 从 1 增至全集，
  每个字都能在某次 shortlist 中被取到，证明没有字符被永久截断。

## 性能

在 2808 张 512×512 PNG（1404 条 × 2 张）上实测：

- 冷启首次全量特征构建约 12.45s；
- 热态（特征缓存命中）约 0.317s；
- 本机完整 `bench_topn.py`（含 40 次查询与缓存冷启）总耗时约 20.6s。

## 服务器部署

部署脚本 `runtime/db1404/d071_deploy.py`（仅服务器端，位于被 Git 忽略的 `runtime/`）：

1. `nginx -t`；
2. 校验 staged 文件 SHA-256；
3. 备份 `.env`（0o600）与两个旧文件到
   `/home/admin/dongba-releases/20261007-232633-d071-glyph-shortlist/previous-files/`；
4. 停旧 API 进程、原子替换两个文件、校验安装后哈希；
5. 运行 `_feature` 探针；
6. 启动新进程并做健康检查；失败自动回滚并重启。

部署结果 `/home/admin/dongba-releases/d071-glyph-shortlist-result.json`：

```json
{
  "state": "complete",
  "checks": {
    "8010/health": 200,
    "8010/ready": 200,
    "8010/api/v1/characters": 200,
    "8010/api/v1/admin/system-config": 401
  },
  "api_pid_before": 2032841,
  "migration_before": "0004_rag_support (head)",
  "shortlist_probe": {"feature_bytes": 256, "side": 16},
  "published_total": 1403,
  "api_pid_after": 2035148,
  "files_changed": 2,
  "files_verified": 2,
  "environment_preserved": true,
  "database_schema_unchanged": true,
  "miniprogram_untouched": true
}
```

文件哈希（本地与服务器一致）：

| 文件 | SHA-256 |
| --- | --- |
| `backend/app/glyph_refs.py` | `7629645c28aa22c4c15e933509dedb8ec60b4b76d63a1a2610aa082fb45be220` |
| `backend/app/recognition.py` | `8a9f694eaa983fe3822d1040176fd56314f3ea81e7dea516d5b1e1bfd070a0e5` |

## 公网复验

从服务器侧严格 HTTPS 访问 `https://www.liorah.top`：

- `GET /api/v1/characters?limit=100` 返回 `total = 1403`、当页 100 条；
- 末页抽样 15 条 × 2 图，30/30 可解码为 512×512 PNG；
- `GET /api/v1/characters/DB1404_0979` 返回 404（draft 正确隐藏）。

## 未验证边界与风险

- 本步只修复“参考字形被前 200 条截断”，**不构成真实识别准确率证据**；准确率仍需真机
  实拍评测集与用户人工确认。
- 16×16 特征只做粗筛，保证目标字大概率进入 top-200，不保证排序第一；最终判定仍由外部
  视觉模型完成。
- 自动选样只保证同编号两张图“差异较大”，不代表书写质量最佳，也未与既有 80 条人工挑图
  做一致性对比。
- `name/intro/visual/usage` 仍为程序模板文本、未经东巴文化专业人员审核。
- 小程序按用户说明走微信平台发布，本步未改、未部署小程序。

## 复现要点

```powershell
.venv\Scripts\python.exe -X utf8 -m pytest backend/tests -q
.venv\Scripts\python.exe -X utf8 runtime\db1404\bench_topn.py
.venv\Scripts\python.exe -X utf8 runtime\db1404\run_d071.py
```
