# D-065 识别质量后端服务器部署证据（2026-10-07）

## 范围

- 用户纠偏：小程序通过微信创作者平台发布，不由服务器部署。本次**仅更新服务器后端**，
  `miniprogram/` 未改动、未上传。
- 代码版本：本地 `main` = `453b15d`（`origin/main` 已同步），工作区干净。
- 部署文件（4 个，均来自 `453b15d`）：
  - `backend/app/config.py`
  - `backend/app/rag.py`
  - `backend/app/volcengine_provider.py`
  - `backend/tests/test_rag.py`
- 不含 `docs/`、`miniprogram/`、`web/`；不改数据库、不跑迁移、不跑业务种子、不读/打印
  `.env` 内容（仅比对哈希）。

## 部署前基线

- 应用目录：`/home/admin/dongba-trail`
- API PID：`2016695`（`scripts/serve.py --port 8010`）
- 迁移：`0004_rag_support (head)`，本轮无数据库变更
- `backend/requirements.txt` SHA-256 与本地一致：`0ccafa16f83376dc31aa6e1850b15aba3cc31cdf4c274c84a6e07bc83052a41f`
- 4 个目标文件在服务器上均为改动前版本（与 `c527543` 基线一致），逐项哈希已记录：
  - `config.py` `3122dd71...` → `d0862a23...`
  - `rag.py` `d27d0893...` → `982a2015...`
  - `volcengine_provider.py` `1ae02944...` → `2c8f4e9c...`
  - `test_rag.py` `6ba3db80...` → `7920822b...`

## 本地验证（部署前）

```text
.venv\Scripts\python.exe -m pytest backend/tests/test_rag.py -q
→ 17 passed, 15 skipped
.venv\Scripts\python.exe -m ruff check backend/app/config.py backend/app/rag.py backend/app/volcengine_provider.py backend/tests/test_rag.py
→ All checks passed!
```

以上为夹具测试，**不代表真实识别准确率**。

## 部署结果

- 发布目录：`/home/admin/dongba-releases/20261007-002431-recognition-backend`
- 发布前逐文件备份到 `<发布目录>/previous-files/`；`.env` 备份 `server.env.backup`（0600，
  仅比对哈希）。
- 上传阶段在服务器临时目录二次校验：4/4 文件哈希与本地 manifest 一致。
- API PID：`2016695` → `2030602`
- 安装后哈希：4/4 与本地 manifest 一致
- `.env` 前后 SHA-256 一致：`56e1a32686a893333310c52204fa69fa67ed92a1828be414fad96bd8a3529ba0`
- 迁移前后一致：`0004_rag_support (head)`；数据库结构未改
- `Settings().quality_min_edge` 实测 `200`
- `apply_hits` 行为探针：provider 候选不再被重复记忆顶掉（`apply_hits_ok: true`）

## 部署后校验

| 检查 | 结果 |
| --- | --- |
| 内部 `8010/health` | 200 |
| 内部 `8010/ready` | 200 |
| 内部 `8010/api/v1/characters?limit=1` | 200 |
| 内部 `8010/api/v1/admin/system-config` | 401（鉴权保持） |
| 本机 `8080/`（Host `www.liorah.top`） | 200 |
| 本机 `8080/health` | 200 |
| 公网 `http://39.96.83.196:8080/` | 200 |
| 公网 `https://www.liorah.top/` | 200 |

## 边界

- 本次只部署后端。小程序改动仍需在微信开发者工具中编译、上传并发布体验版/正式版，
  不在服务器部署范围内。
- 未做真机相机/相册、真实拍摄识别准确率验收；夹具结果不等于真实识别效果。
- #5 字库扩充与 #6 按用户要求未做；识别不到时仍明确拒识而非猜测。
