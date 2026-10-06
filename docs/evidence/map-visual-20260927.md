# 小程序地图页优化（2026-09-27）

关联：GEO-01、DESIGN-01、D-049。对照用户提供的图06（`runtime/docx-audit/image6.png`）。

## 本轮范围

- 保留微信原生导航栏、地图与底部 Tab；收紧顶部雪山背景/说明区，避免重复标题挤占地图，增加红色分类胶囊、地图品牌角标和圆角地点面板。
- 原生地图使用 `cover-view` 工具覆盖层：标准/卫星图切换、定位、缩放；同步手势缩放，选中卡片/标记时居中并突出对应标记。
- 地点卡片使用真实商户图片（缺图/失败明确占位）、左对齐名称与地址、类型/任务标签、商户详情和红色“去这里”。导航与详情点击区高52px，分类/排序至少48px，地图工具52px宽。
- 显式请求定位后，通过现有GCJ-02坐标计算直线估算距离并支持距离排序；未授权不显示距离，后续授权失败清除旧距离和距离排序。默认排序保留接口顺序，不称为推荐评分。
- POI优先，合并关联商户的图片/地址/标签并去重；无效POI不阻止有效商户坐标回退。任务服务失败显示提示，其他文化点和商户仍可浏览。
- 没有照搬参考图的茶主题、评分、销量、优惠金额、虚构点位或插画街道。未修改后台、接口合同及首页实现。

## 验证结果

| 命令 | 结果 |
| --- | --- |
| `node miniprogram/tests/validate-project.js` | 18页静态结构、路由及事件绑定通过 |
| `node --test miniprogram/tests/helpers.test.js miniprogram/tests/services.test.js miniprogram/tests/home.test.js miniprogram/tests/map.test.js` | 55项通过，其中本轮地图13项 |
| `node miniprogram/tests/native-compile.js "D:\engineering_software\微信web开发者工具"` | 微信官方编译器接受21份WXML、17份WXSS |
| `node miniprogram/tests/visual-preview.cjs --map` | 27个离线场景通过，320/375/390/430px宽；含长内容、缺图、拒绝定位、空分类、加载/错误、模拟原生按钮样式干扰及中心/边缘命中检查 |
| `node miniprogram/tests/visual-preview.cjs --home` | 18个首页离线回归场景通过，原有左对齐/图片白框/按钮点击区未破坏 |
| `node miniprogram/tests/visual-preview.cjs` | 67个跨页面离线场景通过，无横向溢出和小于44px高的按钮 |
| `.venv\Scripts\python.exe scripts/check_project.py` | 35项需求、证据链接、原文和API检查通过 |
| `git -c core.safecrlf=false diff --check -- <本轮修改文件>` | 通过；仅Git换行格式提示 |

地图单测覆盖发布点位去重/真实媒体合并、四类筛选、标记稳定ID、卡片/标记相机联动、定位与距离排序、拒绝/撤销授权降级、按卡片ID导航与详情、缩放/图层、图片失败、任务及地点服务故障、无效坐标回退。

本机截图与报告在 `runtime/miniprogram-visual/`（运行时文件，不作为小程序内容提交）：`map-report.json`、`home-report.json`、`report.json`；已人工查看 `map-content-390.png`。所有照片/距离测试数据明确为夹具，原生地图区域明确标注占位；离线报告不代表真实底图、真实商户推荐或识别准确率。

## 交付代码指纹

`validate-project.js` 输出的小程序代码SHA-256：
`211b47fe6522e5322c2258ba0409c77eb8abd4f0bfc60d69183755d4e3a60f9b`

交接检查发现全目录指纹相对首轮发生变化，本轮以下6个文件指纹均未改变；已在当前工作区重新执行55项单测、官方编译、67项跨页/18项首页/27项地图离线检查，全部通过，复跑前后全目录指纹一致。此处记录最终复跑版本，不把首轮指纹与后续工作区混用。

| 文件 | SHA-256 |
| --- | --- |
| `miniprogram/pages/map/index.js` | `53205A2A3398C87DED3416BD11969D7B461E57AACBD22FA39D0A16F04F8478E4` |
| `miniprogram/pages/map/index.wxml` | `A357783B457727F637DF370DBEAEDA9F513DAEB0B95B04406480EAC68935B9AF` |
| `miniprogram/pages/map/index.wxss` | `D910C34F617FC5FE97DC1132CD9F4BFDE36FB43322635440AFF00082C000ADE1` |
| `miniprogram/pages/map/index.json` | `518B2E899DB99455085E1EF1AC8A0AC16A091D636F1F0348D372FC614C62E02D` |
| `miniprogram/tests/map.test.js` | `39D30A5E54121C453E4D9BEB93708055E119F48677AF68C6A2B8DB238D6CE7AA` |
| `miniprogram/tests/visual-preview.cjs` | `A9CF248342DD286B463A35F490D4459C4E36AFF0986557F9DC063F746DE5EA55` |

## 未验证与边界

- 尚未上传微信体验版，未进行微信运行时/真机验收。原生地图控件叠层、卫星图层、手势与缩放同步、GCJ-02实地点位、授权弹窗和导航仍需真机验证。
- 图06插画底图与示例茶主题未冒充真实地图；路线连线、地图内有效优惠卡及主题关联推荐仍是既有缺口，不将GEO-01或DESIGN-01改为已验收。
- 页面背景沿用现有资源，其版权状态不因本次局部调整而改变。不存在新生成文化释义或真实识别准确率结论。
