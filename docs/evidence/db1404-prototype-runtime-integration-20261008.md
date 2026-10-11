# DB1404 多原型部署包与运行时接入（2026-10-08）

## 范围与结论

- 本轮承接D-076，只做可部署图片包、后端运行时接入、同50图集成路径复核；未训练模型、未调用付费API、未连接或部署服务器，也未修改HTTP/OpenAPI响应。
- `scripts/package_glyph_prototypes.py`把本地实验索引中的11,232个选中样本复制为内容寻址图片，并把本地`数据集/DB1404`路径改为包内`assets/...`；11,231个唯一文件共17,225,048字节（有1个跨原型重复内容）。索引含图片SHA-256并在运行时读取前校验。
- 运行时配置`DONGBA_GLYPH_PROTOTYPE_DIRECTORY`默认指向`runtime/glyph-prototype-bundle`。完整包存在时，按每类最近原型排200个唯一已发布字，并实际发送该类查询最近的原型图；仍由既有代码生成10张4×5对照图，加查询图共11张。
- 包缺失、JSON/版本/格式损坏、图片不可读、SHA不符、路径越界或有效类别不足时，整次识别回退到D-071单主图逻辑，不混用残缺包。查询图不写入包、不落盘，告警仅记录错误类型/可用计数，不记录图片、SHA、凭据或上游原始响应。
- 生产`load_references`集成路径复跑用户重点目录`东巴字图片_按中文含义命名/`50图：长边512口径top-200 **42/50**，每例均返回200个唯一ID，仍漏`举、懒、死、舞、跌、躲、雨、靠`。与D-076离线排序结果一致；这是本地短名单召回，不是模型top-1、真机准确率或线上结果。

## 产物

- 部署包：`runtime/glyph-prototype-bundle/`（按项目规则被Git忽略，部署时作为独立运行时资产传输）。
- 索引：6,029,685字节，SHA-256 `3bef223f50d00a8a06738e6350ec35296a3410966b30189096560d3546c7dc43`。
- 11,231个图片资产：17,225,048字节；包索引记录的资产清单SHA-256为`0ed2adfec26bd88e15c9a439e16cba76156cf7b60fbbbf5631c07dbd9beab19d`。
- 含本地评测JSON的当前目录总计23,267,660字节；评测JSON SHA-256为`5d9b56d6eac8527116877ae7b5e9587ed51a7a75c579780c9f8fbc7e2ee155e1`。
- 生成命令：`.venv\Scripts\python.exe scripts/package_glyph_prototypes.py`；输出1,404类、11,232原型、11,231唯一资产。

## 集成评测

`.venv\Scripts\python.exe scripts/evaluate_glyph_prototype_runtime.py`：

- 50/50执行完成；top-200为42/50；每例200个引用且ID全部唯一。
- 平均675.579ms/例，最大957.244ms/例。本机Python与磁盘计时不等于服务器延迟或RSS。
- 评测不调用供应商；`runtime-evaluation.json`只记录文件中文名、期望ID、名次、引用数和耗时，不含图片字节、凭据或查询摘要。

## 自动化验证

- 专项：40项通过后又新增残缺包回退测试，最终专项`backend/tests/test_glyph_prototype_runtime.py`为5项通过。
- 首次全量回归发现“最近原型图片”测试对归一化后的精确像素比较过强；生产归一化统一把64px原型放大至128px，测试改为验证它不是远端竖线原型。最终全量回归 **335通过、97跳过、1条第三方弃用警告**，用时90.29秒；跳过项不算通过。
- Ruff全仓检查通过；85个Python文件格式检查通过。`scripts/check_project.py`通过35项需求、证据链接、来源及API检查；当前检出中无源DOCX，原文哈希比较按脚本设计跳过。`git diff --check`通过，仅输出既有Windows换行转换提示。
- 本证据记录集成里程碑，不代表服务器部署、付费模型效果、手机实拍、MySQL集成或正式发布验收。

## 代码指纹

- `backend/app/config.py`：`e9a1685c473ec91d19da3027d0f93a6340cc6349883f51f10f25e637eb0950c6`
- `backend/app/glyph_refs.py`：`5662b22b31cdbe47649d1b51d84d5e9c6e31af4e3d36d93841350dce4ba791ef`
- `backend/app/glyph_prototypes.py`：`db787c683631ccbe41ff85556997cc5d0e9bea94283c57d50bc1a50e4eac168f`
- `backend/app/recognition.py`：`e94540c00575ce4a97048ace6263e494cba745421865853be259db02cd16fc47`
- `scripts/package_glyph_prototypes.py`：`2f8c5fff7924b6f5e86b26d3c921ae07a6454d9aa06fdf034b3b3a6cfb193998`
- `scripts/evaluate_glyph_prototype_runtime.py`：`dbd2507d0af6ec0a155997934220f29f0f2687b76e29ed7374aa3a3319c7ed59`
- `backend/tests/test_glyph_prototypes.py`：`9f4dea2ae9436e239cfdded2e39b84d6ed4325c49730188ebe91022d5189a3b9`
- `backend/tests/test_glyph_prototype_runtime.py`：`2df7a2e23e2c4dd774761b4569a67105586ff769b4a8031cc7bd5a929ff97ee9`
