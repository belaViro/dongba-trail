# DB1404 离线轻量模型（AI-02 / D-081）

这是独立实验，不修改线上识别服务，不调用付费大模型。
原始 `../DB1404` 保持不动；训练代码、模型、划分、日志和报告都在本目录。

当前为 **CPU v2（D-082）**。旧`cpu_baseline`在5轮后出现分类头失活、验证Top-1约0.24%，
已安全停止；原检查点保持，源码/配置/检查点备份在`reports/failed-baseline-snapshot-20261009/`。
不要用v2代码续训旧模型。v2从头训练，仍使用原去重划分，未借用test或历史50挑方案。

## 方案

- 本机已读到 AMD Ryzen 7 6800HS Creator Edition，显卡通用名 AMD Radeon(TM) Graphics。
  先用 CPU 双线程、batch 16；AMD 集显不能用 CUDA，DirectML 尚未验证，不能声称已启用。
- 64×64 灰度输入，三段卷积+池化，保留4×4空间布局，隐藏层128维、Dropout 0.2。
  v2分类头改为Linear→LayerNorm→LeakyReLU(0.1)，避免旧隐藏层全零后没有梯度。
  全1404类分类；不合并同名释义，保留原数字类ID，中文标签复用项目已提取目录映射。
- AdamW、初始学习率0.0003、weight decay 0.0001、label smoothing 0.05、余弦退火、梯度范数上限5，
  最多40轮，验证Top-1连续8轮不提升则早停。流式读图，加载清单但不将图片整体放入内存。
- 温和旋转±7°、平移±3像素、缩放0.92–1.08、亮度与小概率轻微模糊。
  不做翻转、大旋转或笔画删除。推理/验证使用同一灰度+保持比例白底补边预处理。
- 全量审计原文件SHA、解码像素SHA、归一化64×64像素SHA；按重复组只留一个代表，
  跨类同图隔离。全库排除历史50图的相同归一化像素/相同16×16缩略图。
  还将相同16×16缩略图同组只留一张，避免已发现的36组近重复跨集合。
  划分按类约80/10/10，增强只作用训练集；测试集不参与选模。
- PDF是编号/释义目录，尚无可信书写者ID元数据；**不假定 `+数字` 是作者编号**。
  这是去重后的分层测试，不是书写者独立测试；其它相似但不同缩略图的写法仍可能跨集合。
- 50张中文命名图片是已反复比较过的**历史比较集**，不是新盲测。只在最终模型选定后评测，
  中文名称无法唯一映射的样本明确列出，不静默猜标签；当前“粗”对应0042/1114两类，
  不纳入唯一ID正确率分母，报告单独列明49条可唯一映射及1条歧义，应额外收集新手机实拍集。

## 依赖与命令

以下从项目根目录运行，使用项目虚拟环境（Python 3.11），不使用全局Python。
CPU安装包较大，安装不等于训练已启动。
本机已装好依赖和完成审计，不需要重复下载或覆盖划分；下面包含首次安装流程。

```powershell
.venv\Scripts\python.exe -m pip install "https://download.pytorch.org/whl/cpu/torch-2.8.0%2Bcpu-cp311-cp311-win_amd64.whl" "numpy==2.2.6" "openpyxl==3.1.5"
.venv\Scripts\python.exe 数据集/东巴字模型训练/src/audit.py
.venv\Scripts\python.exe -m pytest 数据集/东巴字模型训练/tests -q
.venv\Scripts\python.exe 数据集/东巴字模型训练/src/sanity.py
.venv\Scripts\python.exe 数据集/东巴字模型训练/src/train.py --benchmark --steps 100
& ./数据集/东巴字模型训练/start-training.ps1
```

审计中断可用同一命令继续；若已生成`manifest.json`则拒绝覆盖，应使用新`--output`目录。
审计SQLite只是本地图片索引，不是业务数据库。完成后`audit_report.json`记录真实数量。

v2全量流水线要求`reports/cpu_v2_sanity.json`学习检查通过且代码/配置/划分/PyTorch指纹相同：
1. 只从train取32类×8图，保留全1404输出，训练1200步；训练样本记忆Top-1须≥95%，输出不恒定。
2. 重新初始化、温和增强、全类别train流训练2000步；后200步平均loss较前200步至少下降0.1，探针输出有区分。
两项均是训练诊断，不是泛化准确率；全量训练再次从固定种子重新初始化，不复用试验权重。
报告存在时sanity拒绝覆盖；需重做时明确指定新报告路径并核验，不能把旧通过记录冒充新源码结果。

### 查看、暂停和继续

```powershell
Get-Content 数据集/东巴字模型训练/checkpoints/cpu_v2/status.json
Get-Content 数据集/东巴字模型训练/checkpoints/cpu_v2/health.json
Get-Content 数据集/东巴字模型训练/checkpoints/cpu_v2/history.json
& ./数据集/东巴字模型训练/stop-training.ps1
# 等status变为stopped_resumable；若正在验证，先等本轮验证结束。
Remove-Item -LiteralPath ./数据集/东巴字模型训练/checkpoints/cpu_v2/STOP
& ./数据集/东巴字模型训练/start-training.ps1 -Resume
```

启动脚本隐藏运行窗口，日志位于`logs/时间.stdout.log`及`stderr.log`。
每5分钟和每轮保存`last.pt`，验证成绩改善保存`best.pt`；暂停在batch边界保存。
检查点含优化器/调度器/RNG/轮次/批次进度/完整配置和数据、代码指纹。
重复启动有进程锁；已有训练必须`-Resume`。代码、配置、划分或PyTorch版本改变则拒绝续训。
意外断电最多重算上次保存之后的工作；重新开机后手动续训，不设置系统自启。
电脑睡眠会暂停计算，接通电源和保持唤醒由用户自行选择；脚本不修改系统电源配置。
`status.json`是最近写入的快照，不单独证明进程仍活着；异常查看`logs/failure-PID.json`及stderr。
每1000批对128张固定train图无梯度检查输出。若恒定或非有限，保存`collapse.pt`、状态变为
`health_check_failed`并退出，不再白跑；该检查不保证发现所有不收敛问题。`health.json`里的命中率
仅为训练集探针，不是验证准确率；正式验证成绩在`history.json`，一轮结束后才有。

### D-085 八线程迁移

2026-10-09在第1轮5590批安全暂停后，用同一断点和相同批次正反各测一次2/4/6/8线程。
8线程中位338.39图/秒，2线程187.18图/秒，提升80.8%，健康探针均正常，因此创建
`cpu_v2_threads8`继续；原`cpu_v2`断点保持停止且未覆盖。当前运行须查看新目录：

```powershell
Get-Content 数据集/东巴字模型训练/checkpoints/cpu_v2_threads8/status.json
Get-Content 数据集/东巴字模型训练/checkpoints/cpu_v2_threads8/history.json
& ./数据集/东巴字模型训练/stop-training-threads8.ps1
# 确认stopped_resumable后，移除新目录STOP并恢复：
Remove-Item -LiteralPath ./数据集/东巴字模型训练/checkpoints/cpu_v2_threads8/STOP
& ./数据集/东巴字模型训练/start-training-threads8.ps1
```

线程迁移只改变CPU执行线程，模型、batch、优化器、调度器、RNG和训练进度均保留。测速权重丢弃；
机器记录在`reports/thread-sweep-20261009/`及新run的`migration.json`。不要再用旧的停止脚本控制
当前八线程运行，也不要删除原run；最终报告输出到`reports/cpu_v2_threads8/`。

### 完成后

流水线训练完成会自动用`best.pt`评测独立test和历史50图，写入`reports/cpu_v2/`：

- `summary.json`：Top-1/Top-5、宏平均、前向耗时、文件大小、指纹和局限。
- `test_predictions.csv`、`per_class.csv`、`confusions.csv`、`historical_comparison.csv`。
- `东巴字模型评测.xlsx`：含历史原图、逐字结果、逐类指标及混淆统计。
- `inference.pt`：仅推理权重、标签和配置；尚未部署线上。

报告阶段失败可单独重新运行，不需要重训：

```powershell
.venv\Scripts\python.exe 数据集/东巴字模型训练/src/evaluate.py
.venv\Scripts\python.exe 数据集/东巴字模型训练/src/predict.py 东巴字图片_按中文含义命名/天.jpg
```

只加载自己生成的可信checkpoint；训练检查点使用pickle，不能加载陌生模型文件。
softmax是未校准参考分，不代表正确概率；该分类器还没有可靠的未知字拒识。
短测速不代表长期速度，夹具测试不代表识别准确率；能否超过外部模型须等真实评测。
所有原图、SQLite、拆分清单、模型、日志和报告默认不进Git，仅代码和配置纳入版本管理。
