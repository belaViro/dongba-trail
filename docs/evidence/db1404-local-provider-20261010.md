# DB1404 本地模型后端接入证据（D-086）

日期：2026-10-10。范围：AI-01 / AI-02 / AI-03 的本地代码接入与验证；**尚未部署服务器或上传微信版本**。

## 交付内容

- `backend/app/local_glyph_provider.py`：惰性加载CPU模型、固定SHA-256校验、训练同口径64×64预处理、已发布ID过滤、最多Top-5。
- `backend/app/provider_factory.py`及`system_config.py`：支持`db1404-local`，Ark继续作为人工选择的回滚项，不自动双调用。
- `backend/requirements-local-model.txt`：单独列出CPU Torch依赖；模型文件继续放在Git外。
- 小程序HTTP契约不变，沿用现有裁剪、质量校验、候选确认和“都不是”流程。

受信任模型：`数据集/东巴字模型训练/reports/cpu_v2_threads8/inference.pt`，SHA-256为
`98e773677ce8df711991a92f41ba55177954cc0d2e36f25ab3a4eda29b5fef89`，版本
`db1404-cpu-v2-20261010`。

## 验证

1. `.venv\Scripts\python.exe -m pytest backend/tests/test_local_glyph_provider.py -q`
   - 3 passed。
   - 覆盖提供方工厂、缺失/错误摘要不可就绪、模型加载及只返回发布ID。
2. `.venv\Scripts\python.exe -m pytest backend/tests -q`
   - 340 passed，97 skipped，1 warning，92.56秒。
3. `.venv\Scripts\python.exe -m ruff check ...`及`ruff format --check ...`
   - 均通过。
4. `npm run build`（`web/`）
   - Vue类型检查与Vite生产构建通过。
5. `npm test -- --run tests/poster-config.test.ts`（`web/`）
   - 两次均在Vitest配置加载阶段因Windows受限环境`spawn EPERM`未启动；不是测试失败，也不能记为通过。
6. 用运行时适配器读取用户手机照片的既有紧裁剪探针`manual-phone-probe/glyph_tight.jpg`，在发布集合（排除草稿979）中结果：
   - Top-1 `DB1404_0018`（电），未校准分数0.946376；
   - 后续候选为0188、0919、0333、0509。

## 限制与上线门槛

- 单张既有实拍探针只证明裁剪流程和模型路径一致，不构成手机实拍准确率。
- 模型没有可靠未知字/非东巴字拒识，分数不是正确概率，不能设自动确认阈值。
- 必须在服务器Git外复制模型并复核SHA、安装CPU依赖、分阶段切换提供方，验证`/ready`、真实识别、质量错误、ID过滤及确认绑定；失败时人工切回Ark。
- 微信平台未上传，因此不能称“小程序已发布”。
