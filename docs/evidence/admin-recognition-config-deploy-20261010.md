# D-089 系统配置与识别服务上线证据

日期：2026-10-10。关联 OPS-03 / AI-01 / AI-03、D-088 / D-089。
用户要求“同步到服务器”；本次完成的是已验证修正的窄范围发布，不是整个0.9.0正式发布验收。
结束复核服务器UTC为2026-10-10T07:39:35Z（北京时间15:39:35）。

## 范围、身份与保护

- 目标 `39.96.83.196`，根目录 `/home/admin/dongba-trail`。
- 发布5个Python模块：`main.py`、新`provider_status.py`、`local_glyph_provider.py`、
  `recognition.py`、`system_config.py`，均在 `backend/app/`；另发布 `web/dist/` 的28个文件。
- 上传前核对[D-088修正证据](admin-recognition-config-20261010.md)中全部16个代码/测试/构建指纹，全部一致。
  未修改任何业务源码；复用对应后端351通过/101跳过、隔离MySQL专项17通过、Web170通过及生产构建证据，
  本轮不将这些历史命令说成重新执行。
- 服务器其余29个后端Python依赖及 `scripts/serve.py` 共30个文件按LF规范化SHA校验，全部与本地相同。
- 保留本地模型 `db1404-cpu-v2-20261010` / CPU双线程，未安装新依赖、未迁移数据库、未改Nginx。
  模型、环境文件及MySQL整个运行时配置在发布前后和两次验证中摘要不变；Ark备用密钥/参数、海报和地图保留。
  不输出凭据，不把环境文件、密钥、数据库内容、模型或微信上传资料放进发布包。

## 包与指纹

Git HEAD：`ce2daa430022c49f80dc0488a97a5d6d32636f07`，存在用户未提交修改，未回滚或提交。
本地操作目录 `runtime/deploy/d089-admin-sync-20261010/`（Git外）；服务器独立发布目录：

`/home/admin/dongba-releases/20261010-d089-admin-config`

| 项目 | SHA-256 |
| --- | --- |
| payload.tar.gz（820186字节，33个普通文件） | fbdae5f738ddfac837e7884144ad8e6f9e6128d815239cdd4803714849399cac |
| manifest.json（文件及依赖完整清单） | dd15dc8dff67d694c01e095760b47fe1769aa275b521995b5d0ce71386d869ab |
| deploy.py（一次性发布/验证/回滚脚本） | 8114b84270158018bf6af0b84cfaa587832fae12872710dbfe6c570e59d216d6 |
| backend/app/main.py | 5723c01c3f8d62f7736070ccff9a700f483618ce5901f67f5f9736b8ceee0a1b |
| backend/app/provider_status.py | 8ae9b74cec2ea6de16a6dd4392c4608427639763d23ed7832dfb360043d94967 |
| backend/app/local_glyph_provider.py | 3835d1e5db5ce206de4a2cc40c3422562c30945fd7000ab9a034453683dccbe3 |
| backend/app/recognition.py | 2f5d9db5cb534bb97e1305827676c252b2c9b57317539bb9e17a6ea55c31b42f |
| backend/app/system_config.py | ed87e9e828a5980afcd2a834e64b7077a9c5e11fe1aad0c3791044ff15e1cced |
| web/dist/index.html | e93321d3b18c05f54f9dce622d0ad31227b0a7d13e2bc4eb6474b129e390874d |
| 原有模型inference.pt（未上传/修改） | 98e773677ce8df711991a92f41ba55177954cc0d2e36f25ab3a4eda29b5fef89 |

## 实际命令与结果

本地Python均为 `.venv\Scripts\python.exe`，服务器为项目 `.venv/bin/python`。

| 命令/步骤 | 结果 |
| --- | --- |
| `python -m ruff check runtime/deploy/d089-admin-sync-20261010/deploy.py` | 通过；初始长行已修正，最终脚本指纹如上 |
| `python -m ruff format --check runtime/deploy/d089-admin-sync-20261010/deploy.py` | 1文件已格式化 |
| `python -m py_compile runtime/deploy/d089-admin-sync-20261010/deploy.py` | 通过 |
| 打包与SCP上传，服务器 `sha256sum` | 三个上传文件与本地指纹一致；SSH启用严格主机密钥校验，交互鉴权 |
| `python <release>/deploy.py prepare` | 33个暂存文件、30个依赖校验通过；15个将覆盖的旧文件已备份，完整旧Web另备份178个文件 |
| 隔离目录导入新后端并加载真实CPU模型 | `isolated_import_and_model_load_passed`；此阶段不连接生产业务库，只用无业务SQLite内存配置检查导入 |
| `nohup python <release>/deploy.py install` | 精确SIGTERM旧API PID2041358，原子替换目标文件、index最后；PID2041885就绪；内置verify通过 |
| `python <release>/deploy.py verify` 再独立运行一次 | 第二遍真实HTTP/MySQL及公网资源验证同样通过 |
| `nginx -t` | 配置语法及测试成功，未修改/重载配置 |
| `curl -fsS http://127.0.0.1:8010/ready` | ready；provider_configured=true；published_characters=1403；reasons=[] |
| 从Windows本机经HTTPX访问HTTPS与IP:8080 | 两个入口index SHA一致、health=ok/version=0.9.0、两个admin接口匿名均401 |

发布脚本输出 `deployment.json` 为 deployed / pid=2041885 / provider=db1404-local。
两轮安全验证报告保留为服务器 `verification-first.json`、`verification.json`；
发布摘要在 `install.log`；本机外公网结果在本地操作目录 `external-verification.json`。

两轮verify均验证：

1. 本机API及HTTPS的管理员配置返回实际 `db1404-local` / `db1404-cpu-v2-20261010`、ready、2线程；
   endpoint_configured=null、automatic_fallback=false、calibrated_confidence=false。
   Ark备用参数仍在，API Key仅返回配置布尔值、不返回原文；未PUT任何配置、未调用外部模型。
2. admin可读取系统配置与服务状态；operator可读取服务状态、配置403；tourist服务状态403；匿名两个接口401。
   统计口径为current_provider_and_model，limit=1000，错误数不超过请求数。
3. 使用D-087既有 `glyph_tight.jpg` 做真实模型HTTP探针，Top-5两轮均为
   DB1404_0018 / 0188 / 0919 / 0333 / 0509；状态NEED_USER_CONFIRM，记录初始未确认。
   显式选择首选及随后“都不是”接口均200；坏图400/INVALID_IMAGE，失败记录的provider/model正确。
4. HTTPS逐一下载全部28个新Web资源，每个SHA均与manifest相同；IP:8080首页同指纹。
5. 每轮仅创建短期专用admin/operator/tourist及内存随机会话，不读取真实用户凭据；finally按精确ID清理
   反馈、识别、会话和用户。最终另查本次d089前缀：users/sessions/recognitions/feedback/samples全部0。

## 备份与回滚

- 本次发布目录权限0700，`state.json`和报告0600；state只存受保护配置的摘要及旧目标文件摘要，不存配置值。
- `backup/`保存本次涉及的15个旧文件，`backup-web-dist/`保存完整旧站178文件。
  新增文件有清单；上线保留旧哈希资源，避免已打开浏览器的懒加载失效。
- 安装失败路径已设置自动调用本次rollback；本次成功，未触发也未专门演练停服回滚。
- 如需回滚，先复核仍为本次发布且配置/模型未被后续改变，使用：

```sh
cd /home/admin/dongba-trail
.venv/bin/python /home/admin/dongba-releases/20261010-d089-admin-config/deploy.py rollback
```

回滚会核对文件只能是本次old/new指纹、保护配置/模型摘要、核对API PID/cwd/命令，停止本次API，
恢复旧文件、删除本次新增文件并重启。存在后续改动时拒绝盲目覆盖；不要用D-087回滚脚本回滚D-089。
无业务配置变更，因此本次不做全库恢复；临时测试写入已定向清理，不覆盖其他用户数据。

## 限制与最终检查

- 真实CPU加载有既有torch缺NumPy警告，但导入及两轮实际推理通过；未为消除警告扩大依赖变更。
- 复用单张“电”是功能烟测，不是新盲测、手机实拍准确率、未知字拒识或AI-02整体验收。
- 公网 `/ready` 仍为SPA，真就绪证据来自服务器8010的JSON；未更改Nginx路由。
- 未执行公网浏览器登录/交互或微信真机跨端旅程；微信版本未上传；完整停服回滚未演练。
- 本地业务测试依然是D-088对应指纹的证据，不把fixture或SQLite当成真实模型准确率/生产MySQL验证。
- 文档收尾 `python scripts/check_project.py` 通过35项需求/证据链接/API检查，原DOCX缺失而明确跳过源摘要比较；
  `git diff --check`通过，仅有既有LF/CRLF提示。另重跑 `python -m ruff check backend scripts` 及
  `python -m ruff format --check backend scripts` 均通过，90文件已格式化。
  不因本轮部署把整个版本标记为production-ready。
