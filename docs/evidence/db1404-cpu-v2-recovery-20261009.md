# CPU v2 基线退化修正（AI-02 / D-082）

2026-10-09，用户授权修正后重训。范围仅`数据集/东巴字模型训练/`离线实验及记录；不部署、不读取凭据、不调用付费模型。

## 保留旧现场

执行旧`stop-training.ps1`；01:07:58 `stopped_resumable`，epoch=5（第6轮）、batch=6162，PID18372退出。
持有原run锁后用项目Python复制21个源码/测试/配置/README/启动脚本/检查点/状态文件到
`reports/failed-baseline-snapshot-20261009/`，逐项SHA写入`snapshot.json`；原目录和STOP均保留，未删除或移动。
旧代码指纹`added65c30dedfed29f25e6811a55bd529c9088aaecad1f0f49f0c486fc32852`。
新代码与旧模型结构不兼容，禁止用v2续训旧断点；不从失败权重接着训练。

## 修正及预先定义的学习门槛

- 分类头：Linear128→LayerNorm128→LeakyReLU(0.1)→Dropout0.2→Linear1404。卷积主干不变。
- CPU双线程、batch16、lr从0.001降为0.0003、gradient clip norm5；原增强、正则、40轮/早停8轮保留。
- `sanity.py`：只读train图。32类×8图、仍1404输出、1200步，训练图记忆Top-1≥95%且非恒定；再重新初始化跑真实全类别增强流2000步，末200步均值loss比首200步下降>0.1且固定探针至少2种预测、logit不恒定。最终全量再次从固定种子初始化，不复用门槛试验权重。
- `pipeline.py`要求通过记录的源码/配置/划分/PyTorch身份与当前一致，失败或陈旧报告禁止启动。
- 每1000批无梯度、无随机数/BN状态更改地对128张固定train图检查恒定/非有限输出；失败保存`collapse.pt`、状态health_check_failed并退出。不声称检查能发现所有不收敛情况。
- 新运行`checkpoints/cpu_v2`，新最终报告`reports/cpu_v2`；test及历史50未用于修正试验，继续只在选出最终best后评测。

## 验证与待续

- `.venv\Scripts\python.exe -m pytest 数据集/东巴字模型训练/tests -q`：13通过，13.78秒。断点一致性测试已开启v2裁剪和每2批探针，验证不中断/中断续训权重和进度完全一致；新测试覆盖负输入梯度、探针保留RNG/模型状态、恒定输出检测/停训、门槛失败/陈旧拒绝。合成测试不是识别率。
- `.venv\Scripts\python.exe -m ruff check backend scripts 数据集/东巴字模型训练/src 数据集/东巴字模型训练/tests`通过。
- 同范围`ruff format --check`通过，99文件。
- 真实学习检查：`.venv\Scripts\python.exe -X utf8 -u 数据集/东巴字模型训练/src/sanity.py`，日志`logs/cpu-v2-sanity-20261009.log`，退出0、298.93秒。32类256图记忆100%；全类别2000步首/末200步loss=7.276900/6.695468，128图train探针产生43种预测、hidden_zero_fraction=0、输出非恒定。两门槛通过，原始`reports/cpu_v2_sanity.json`。这些仅说明开始能学习，不能冒充验证或实际识别准确率。
- v2 `train.py --benchmark --steps 100`退出0；390788参数、169.669图/秒，估算每轮37.4分钟、40轮24.93小时。与回归测试并行，短测受系统占用影响，不承诺完成时间；`reports/cpu_v2_benchmark.json`。
- `pytest backend/tests -q`退出0：337通过、97跳过、1条既有Starlette警告，137.24秒；无业务改动，跳过不算MySQL验收通过。
- `scripts/check_project.py`和`git diff --check`通过，原DOCX缺席哈希跳过、LF/CRLF提示保留。

## 用户要求暂停（D-083，2026-10-09 01:19）

用户要休息，要求停止并保留记录。已确认sanity、benchmark、后台回归测试均结束（各工具会话退出0），Get-Process无Python进程；旧基线此前安全停止。**v2全量从未启动，无v2 last.pt或正式验证成绩。**
执行现行`stop-training.ps1`在`checkpoints/cpu_v2/STOP`写防误启动标记；不会自动恢复或安排夜间任务。
源码及配置保留，v2源码指纹`bf5a471615989792fa4360232fb81bc66231653e6fa154620826b3feec68d1d1`；split仍为`494fd40a73f6f7fb9d6557f86c38443c28f8de038f640abc467e7cfac9759444`。
逐文件清单`reports/code_manifest_v2.json`，旧现场`reports/failed-baseline-snapshot-20261009/`（21文件SHA已核验），真实学习报告、测速及日志均在训练目录。无Git提交，用户其它修改不动。

仅在用户明确继续后：核对代码/配置/划分/门槛身份；确认v2没有last.pt，移除明确路径`checkpoints/cpu_v2/STOP`并首次运行`start-training.ps1`（不带-Resume）。开始后查实际进程、status、health及周期检查点。严禁把v2代码用于旧cpu_baseline续训，未完成全量不评test/历史50。

## 用户明确继续：首次全量启动（D-084，2026-10-09 10:10）

本次边界任务是恢复已批准的v2离线训练，验证进程持续推进、首个健康探针及周期断点可读；不修改冻结源码/配置/划分，不提前评test/历史50，不触碰生产或原图。

- 先读status/decisions、AI-02需求/验收和识别契约，检查git及训练代码。HEAD仍为`ce2daa430022c49f80dc0488a97a5d6d32636f07`，保留既有未提交修改，无提交。
- 项目Python核对`reports/code_manifest_v2.json`全部文件、`pipeline.verify_learning_gate(config)`身份、v2运行锁和启动前无last.pt/identity；旧失败现场21文件SHA及旧STOP再次核验。记录`reports/resume-preflight-20261009.json`（10:10:27）。源码指纹仍为`bf5a471615989792fa4360232fb81bc66231653e6fa154620826b3feec68d1d1`，划分指纹仍为`494fd40a73f6f7fb9d6557f86c38443c28f8de038f640abc467e7cfac9759444`，PyTorch2.8.0+cpu。
- `.venv\Scripts\python.exe -m pytest 数据集/东巴字模型训练/tests -q`：13通过、15.56秒，退出0；本次未改Python/后端行为，沿用上述同源码Ruff/后端回归证据。夹具不是实际准确率。
- 只移除明确路径`checkpoints/cpu_v2/STOP`，执行`& './数据集/东巴字模型训练/start-training.ps1'`（无-Resume）。10:10:54隐藏后台启动器PID14752、实际Python PID20912，10:11:07进入训练。日志`logs/20261009-101054.stdout.log`及同名stderr.log；旧STOP及`reports/paused-20261009.json`历史保留。
- 10:11:07第1批、10:13:07第1025批（均第1轮，总22123批），进程CPU时间增长。首个1000批health：128张固定train图，finite=true、collapsed=false、15种预测、hidden_zero_fraction=0。仅排除探针上的初期恒定输出，不能据此认定泛化有效。首轮验证、test及历史50均未完成。
- 10:15:20复核：status记录10:15:08第2007批，第二个2000批探针43种预测、finite=true、collapsed=false；实际PID20912仍存活，CPU时间493.83秒，工作集648.7MiB，stderr为0字节。通过项目Python一次性读取本地产生的可信last.pt字节快照再torch.load，确认第880批（14080训练样本）、未完成；模型张量有限，1404标签，模型/优化器/调度器/进度/三种RNG键齐全，代码/配置/划分/PyTorch身份匹配。没有为了验证而中断正在运行的训练；断点续训一致性依据同源码13项测试。
- 上述checkpoint快照4822417字节，SHA256=`05a39840e679ef96e4bcb71b13a122ebcf6aaa48762a089f52debece970eed26`；运行中的last.pt之后会继续更新，此SHA只对应核验时快照。机器可读记录`reports/v2-startup-verification-20261009.json`，包含身份、status、train健康探针及断点进度，不包含测试集评测。
- 本次文档更新后`.venv\Scripts\python.exe scripts/check_project.py`通过（35项需求、证据链接及API）；原DOCX缺席，原文哈希比对跳过。`git diff --check`通过，仅已有LF/CRLF提示。无契约变化，无需重新导出OpenAPI；未新增后端/MySQL验收结论。

后续暂停应通过现有stop-training.ps1并确认stopped_resumable；当前已产生正式v2断点，之后必须核验身份再带-Resume恢复，不能重复首次启动或套用旧基线。机器须保持开机、不休眠才能持续训练；未改系统电源设置。
