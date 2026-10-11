# DB1404 离线 CPU 训练实施（AI-02 / GOV-01，D-081）

日期：2026-10-08。用户明确授权本地训练、产物放入数据集；不改变线上外部API部署。

## 方案与数据边界

代码与用户操作文档：`数据集/东巴字模型训练/README.md`。
默认CPU双线程、batch16、64×64灰度、轻量空间CNN、AdamW、最多40轮、验证Top-1早停8轮。
所有代码、配置、模型、审计、报告位于数据集内；项目`.venv`只存安装依赖。
读取已有目录映射保留1404数字类别，同名不合类。没有验证过的书写者ID；文件名后缀不能当作者ID。
历史50图已经用于既往算法比较，不能称新盲测，完全不参与训练和验证选模。

审计：445,272图/1404类/0不可读；444,750张L、522张RGB，均64×64。
文件/像素/64×64归一化唯一数均442,596；68组跨类别相同像素，涉及141张，隔离不自动改标签。
首次精确去重353,984/44,272/44,272；36组额外同类16×16缩略图碰撞也同组只留一张，
最终train/val/test=353,954/44,269/44,269，各覆盖1404类。用SQLite独立关联核验像素/缩略图跨划分重复、标签错配、隔离图混入均0；报告`reports/split_integrity.json`。
最终split指纹`494fd40a73f6f7fb9d6557f86c38443c28f8de038f640abc467e7cfac9759444`。
`reports/数据集审计.xlsx`已生成（仅审计，不是模型识别成绩），含真实统计及逐类划分。
历史集无同像素/同缩略图匹配；“粗”同时映射0042/1114，最终报告保持歧义、唯一ID正确率分母49，不与旧50条成绩直接等同。
近似重复审计非穷尽，更广泛同源/书写者泄漏仍可能存在。原图不修改、不整体载入内存。

## 依赖/硬件

通过注册表只读得到CPU `AMD Ryzen 7 6800HS Creator Edition` 和显卡通用名 `AMD Radeon(TM) Graphics`。
没有读取凭据、没有再次申请CIM硬件读取权限。
PyTorch `2.8.0+cpu`、NumPy `2.2.6`、openpyxl `3.1.5`已安装到项目`.venv`。
官方CPU wheel分段下载后合并，619,392,861字节，核对官方SHA256后以`pip install --no-index --no-deps`安装；基础依赖下载使用清华PyPI镜像。导入确认`torch.version.cuda is None`且张量运算成功。
官方索引wheel SHA256：`7631ef49fbd38d382909525b83696dc12a55d68492ade4ace3883c62b9fc140f`。
DirectML PyPI元数据版本`0.2.5.dev240914`要求torch==2.4.1及torchvision==0.19.1；不能直接装入此环境而不降级。
未启用集显，未安装驱动/ROCm/CUDA，未调用付费模型。元数据留在本地训练logs目录。

## 当前验证（阶段性，尚非准确率证据）

- `.venv\Scripts\python.exe 数据集/东巴字模型训练/src/audit.py`：首次全扫描成功342.84秒；原图保持。
- 新训练代码 Ruff check/format check通过（10 Python文件）。
- `ruff check backend scripts`、`ruff format --check backend scripts`：通过，87文件。
- `scripts/check_project.py`：35需求、证据链接及API检查通过；原始DOCX缺席，哈希比较跳过。
- `git diff --check`：通过（仅LF/CRLF提示）。
- 安装小依赖后执行`pytest backend/tests -q`：337通过、97跳过、1条既有Starlette弃用警告，99.15秒。跳过项不算通过；本轮未修改后端行为。
- torch安装完成后重跑`.venv\Scripts\python.exe -m pytest backend/tests -q`：337通过、97跳过、同一条Starlette警告，106.28秒；同时有本地训练占用CPU。没有用这些夹具测试冒充真实模型或MySQL集成验收。
- `pip check`安装torch前后均发现现有SQLAlchemy缺少greenlet；训练依赖未涉及SQLAlchemy且本轮不修业务环境依赖，不能称项目所有依赖完整。
- `.venv\Scripts\python.exe -m pytest 数据集/东巴字模型训练/tests -q`：9通过，7.22秒。覆盖去重/历史留出、标签校验、清单/源图篡改拒绝、进程锁、中途续训与不中断权重和进度完全相同、未完工禁止测试集评测、Excel输出及推理、拒绝覆盖和身份不一致续训。这些是合成夹具，不证明准确率。
- 安装torch后再次执行Ruff check及format check（backend、scripts、训练src/tests）：通过，97文件。
- 更新训练状态文档后重跑`.venv\Scripts\python.exe scripts/check_project.py`及`git diff --check`：通过；仍有原始DOCX缺席跳过及既有LF/CRLF提示。

## 真实CPU测速与启动（2026-10-08 22:52）

命令：`.venv\Scripts\python.exe -X utf8 -u 数据集/东巴字模型训练/src/train.py --benchmark --steps 100`。
从真实train清单读取、增强及校验文件SHA，先热身10步、计时100步（1600图），另50批验证前向只用于测速。
39万参数（390,532），双线程/batch16，计时7.321秒，218.536图/秒；含验证估算每轮1,720.43秒（28.67分钟），40轮19.12小时。
原始报告：`数据集/东巴字模型训练/reports/cpu_benchmark.json`。短测不包含长期热降频/其他程序竞争/全部存盘开销；不是完成时间承诺或识别准确率。正式训练从固定种子重新初始化，不复用测速权重，不查看test结果。

运行：`& ./数据集/东巴字模型训练/start-training.ps1`，隐藏后台启动；虚拟环境launcher PID 23420，实际执行训练PID 18372。
stdout/stderr：`数据集/东巴字模型训练/logs/20261008-225216.stdout.log`及同名前缀`stderr.log`。
22:52:51快照：首轮（status的epoch从0起）、499/22,123批；进程存活且CPU时间增长，常驻内存约552MiB、D盘剩余17.1GiB。
已加载检查`last.pt`初始批次1检查点（4,817,001字节）结构和指纹；每300秒及轮末会继续保存。
22:57:22进一步加载核验首次周期检查点：首轮已保存4,653/22,123批（约21.03%），仍未完成；实际进程PID 18372存活，CPU累计556.78秒、常驻553.1MiB。
该检查点SHA256为`b7e9425ded27ac88b6a95acfd6a36dead6af3f36d8190313fe42c49e8b341dfe`，源代码/数据指纹未变；原始快照和依赖版本记录于`reports/startup_verification.json`。status按30秒写入，快照可略落后于刚保存的checkpoint。
尚无完整轮验证成绩，best_validation_top1为null；没有测试集/历史50的真实识别率，未生成最终模型评测Excel。

## 可复现指纹与后续

Git基线`ce2daa430022c49f80dc0488a97a5d6d32636f07`，工作区存在大量既有未提交修改，本轮没有清理/覆盖。
训练src代码指纹`added65c30dedfed29f25e6811a55bd529c9088aaecad1f0f49f0c486fc32852`。
逐文件src/tests哈希见本地`reports/code_manifest.json`，启动后已重新计算核验全部相符；split指纹同上，身份写入`checkpoints/cpu_baseline/identity.json`和检查点。
训练期间冻结src/config/splits/PyTorch版本，修改会使续训拒绝。暂停用`stop-training.ps1`，确认stopped_resumable后移除明确的STOP文件并`start-training.ps1 -Resume`。
不更改电源设置；电脑睡眠停止计算、重启后不会自动续训。正式训练及最终评测未完成，AI-02仍实施中；线上API/数据库/小程序均未改动。

后续须以当时进程、检查点和报告复核状态，不以本页启动快照冒充持续运行或训练完成。

## 2026-10-09 01:05 查询与退化诊断（AI-02，未修改训练）

用户询问进度；本轮有界任务为读取进程/检查点/验证历史，并在异常时只对训练集做前向诊断，不重训、不提前访问测试集或历史50。
`Get-Process`确认PID18372存活，01:04 CPU累计15152.33秒、常驻378.8MiB；01:04:19和01:05:19的status由第6轮3959批推进至4561批/22123批（epoch字段从0起）。累计运行约2小时13分。
完成5轮，每轮验证44269图；Top-1依次0.24396%、0.23267%、0.24396%、0.24396%、0.24396%；第5轮Top-5为1.15205%。训练loss从7.16235变为7.14362后无实质下降。该成绩仅为验证集，不是测试集或小程序实拍准确率。

使用项目`.venv`运行只读Python诊断：一次读入可信本地last.pt，核对代码指纹，加载现有GlyphCNN为eval模式；固定随机种子20261009从train清单抽256图、1线程无梯度前向，源图仍按原加载器核SHA。
抽样覆盖232类；输入范围0–1且有变化，卷积特征批间平均std约0.276；分类128维隐藏层所有抽样激活为0，激活单元0个，256张预测同一类别，逐类logit在样本间最大变化0。直接证据支持分类隐藏层失活/恒定输出，具体触发因素（初始化、学习率等）尚未通过修复实验确认。
原始JSON：`数据集/东巴字模型训练/reports/progress-diagnostic-20261009.json`，含完整5轮历史、配置、指纹和状态快照。采样检查点为第6轮3833批，SHA256 `f9f3c79516cd27b530293a0d7b23d49869db2c434dd7c6ba0fda6bc7eadd0b72`；训练持续进行，文件随后可能被正常新断点覆盖。
源代码指纹仍为`added65c30dedfed29f25e6811a55bd529c9088aaecad1f0f49f0c486fc32852`，split指纹同上。未修改权重、源代码、配置或运行进程，未生成或声称最终评测成绩。

结论：这次基线没有正常学起来，不能把原19小时估算解释为届时必然有效；建议保留失败现场，暂停旧轮，在新运行用训练集小样本先验证收敛，再正式重训。此建议尚未执行。仅更新状态/验收/证据，未重跑业务测试；`.venv\Scripts\python.exe scripts/check_project.py`通过（35需求，原DOCX缺席哈希跳过），`git diff --check`通过（LF/CRLF提示）。
