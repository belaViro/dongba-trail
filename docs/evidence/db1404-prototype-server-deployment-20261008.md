# DB1404 多原型运行时服务器部署（2026-10-08）

## 范围与结论

- 将D-077的4个后端文件和独立运行时原型包部署到`/home/admin/dongba-trail`；未修改`.env`、MySQL数据、媒体、小程序、Nginx或供应商模型配置。
- 最小归档`d077-glyph-prototype-runtime-20261008.tar.gz`为16,692,413字节，SHA-256 `05ebdfb87cd56194412072f3dfc58a1c5cfb64bee455c7093fde034afba18d91`。归档只含4个后端文件、`index.json`和11,231个原型图片资产，不含凭据、`.env`、数据库、用户查询图片或本地评测JSON。
- 发布备份目录为`/home/admin/dongba-releases/20261008-203716-d077-prototypes`；旧代码、原型包缺失标记和服务器内`.env`备份均保留。API PID由`2036937`变为`2038367`，回滚未触发。
- 部署后服务器内无供应商调用的运行时探针得到1,403个已发布词条、11,231个唯一资产、0个坏SHA、200个唯一引用和10张对照图。该探针证明部署包加载及短名单编排，不证明模型top-1、实拍准确率或费用。

## 部署前检查与保护

- 目标目录和虚拟环境存在，根卷约40GB、剩余约18GB；8010仅一个监听进程。
- `nginx -t`通过；本机`/health`和`/ready`均为200，`/ready`报告1,403个已发布词条。
- 数据库迁移为`0004_rag_support (head)`；部署前服务器尚无`glyph_prototypes.py`和原型包。
- `.env`只记录指纹，不读取或输出内容；部署前后SHA-256均为`56e1a32686a893333310c52204fa69fa67ed92a1828be414fad96bd8a3529ba0`。
- 上传后服务器归档大小和SHA与本机一致，归档路径检查无绝对路径或`..`越界；共11,493个条目，其中11,231个图片文件。解压到发布暂存目录并先做编译、导入和索引结构检查，再停止旧API。

## 部署与指纹

停止唯一8010进程后，将代码先写入同目录临时文件再改名，将完整原型目录从暂存位置改名到运行目录；随后编译、导入、索引检查并启动新API。失败路径预先保留旧文件和原型包缺失标记，可恢复旧代码并重启。

| 文件 | 服务器部署后SHA-256 |
| --- | --- |
| `backend/app/config.py` | `e9a1685c473ec91d19da3027d0f93a6340cc6349883f51f10f25e637eb0950c6` |
| `backend/app/glyph_refs.py` | `5662b22b31cdbe47649d1b51d84d5e9c6e31af4e3d36d93841350dce4ba791ef` |
| `backend/app/glyph_prototypes.py` | `db787c683631ccbe41ff85556997cc5d0e9bea94283c57d50bc1a50e4eac168f` |
| `backend/app/recognition.py` | `e94540c00575ce4a97048ace6263e494cba745421865853be259db02cd16fc47` |
| `runtime/glyph-prototype-bundle/index.json` | `3bef223f50d00a8a06738e6350ec35296a3410966b30189096560d3546c7dc43` |

索引声明1,404类、11,232个原型和11,231个唯一资产。服务器逐一重算11,231个资产SHA-256，错误数为0。

## 部署后验证

- 本机8010：`/health=200`、`/ready=200`、`/api/v1/characters?limit=100`为200且`total=1403`、草稿`DB1404_0979=404`、未授权`/api/v1/admin/system-config=401`。
- 公网`https://www.liorah.top`和`http://39.96.83.196:8080`的`/health`返回API JSON 200，字典`total=1403`、草稿404和管理端401状态一致。两处公网`/ready`虽为200，但`Content-Type: text/html`且响应为既有管理端SPA，因此不把它记为API就绪通过；API就绪证据来自服务器本机8010的JSON响应。本轮未修改Nginx路由。
- `nginx -t`部署后仍通过；迁移仍为`0004_rag_support (head)`；`.env`指纹未变。
- 运行时探针直接调用本地`_load_prototype_references`和`build_reference_sheets`，未进入外部识别provider：200个引用、200个唯一ID、10张4×5对照图。
- 本轮没有付费API调用，因此没有新增模型效果、token或账单证据；D-076重点50图的42/50仍只是本地top-200召回结果。0.9.0仍未满足正式发布门槛。

## 本机验证基线

部署代码在发布前已完成：后端335通过、97跳过、Ruff检查和格式检查通过，`scripts/check_project.py`通过35项项目检查，详见[运行时接入证据](db1404-prototype-runtime-integration-20261008.md)。本记录只补充服务器部署与无付费运行时验证，不把夹具或单次字形探针报告为真实识别准确率。
