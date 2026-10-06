# 小程序图01至图08视觉改版证据

日期：2026-09-27（首页图01对齐增量）  
需求：`DESIGN-01`，同时涉及 `MINI-01`、`AI-03`、`CONTENT-01`、`GEO-01`、`QUEST-01`、`QUEST-02`、`SHARE-01`。  
范围：`miniprogram/` 原生微信小程序；未修改后端接口契约。

## 输入与方法

本轮逐张查看了用户提供的 `runtime/docx-audit/image1.png` 至 `image8.png`。这些图片是AI生成的视觉参考，不被当作已实现功能、真实数据或新增接口承诺。

改版前阅读并采用了以下在线设计资料中的通用原则：

- `design-wechat-miniapp-skill`：https://github.com/xypasolini-droid/design-wechat-miniapp-skill
- `UI/UX Pro Max` 移动端设计说明：https://github.com/nextlevelbuilder/ui-ux-pro-max-skill/blob/main/src/ui-ux-pro-max/templates/base/skill-content.md

实际采用的原则：首屏只突出一个主操作；交互控件至少约44px；选中态不能只依赖颜色；底部按钮考虑安全区；加载、空、错误和能力不可用状态必须明确；参考图只指导视觉，不得为贴图而虚构业务能力。

## 八张参考图与实际实现差异

| 参考图 | 参考图表达 | 本轮实际落地 | 未硬凑的差异 |
| --- | --- | --- | --- |
| 图01 首页 | 全屏丽江雪山、圆形拍照主按钮、今日字、快捷入口、横向商户 | 首页增加雪山横幅、品牌标题、蓝色圆形拍照CTA、纸笺今日字、三项快捷入口和横向商户卡；商户只显示接口已有字段 | 现有横幅素材较窄，作为装饰头图而非伪造全屏实景；不补造评分、销量、优惠和距离 |
| 图02 相机 | 自定义全屏相机、取景框、闪光灯、相册、实时模糊/亮度/目标大小检测 | 保留D-033的微信系统相机直达，首页明确“系统相机拍摄，识别后由你确认” | 未恢复独立相机页；没有实时画质、取景框、闪光灯控制和目标检测能力，不制作假控件 |
| 图03 识别Top-1 | 单个主结果、参考分数、文化入口 | 改为照片对照区、最多5个候选的双列卡片、明显选中态和确认入口 | 供应商分数只标“参考分数”，不称准确率；文化说明不由模型生成 |
| 图04 候选确认 | 多候选、都不匹配、人工复核 | 保留候选确认、都不是、补充说明和人工复核提交状态；选择态使用红框、勾选和文字 | 人工复核不宣称自动训练模型，也不会直接把不确定结果当答案 |
| 图05 字详情 | 大字形、文化故事、音视频、相关内容和周边 | 增加雪山纸笺头图、多写法、文化故事、真实音频可用/不可用状态、相关字、地点和商品卡 | 后端没有文化视频字段与播放流程，因此不显示假的视频播放器 |
| 图06 文化地图 | 地图分类、点位、路线、地点优惠卡 | 优化原生`<map>`、分类筛选、选中地点卡、列表选中态、定位和导航入口 | 尚无路线折线与地图内优惠卡接口，不伪造路线、优惠或距离 |
| 图07 寻迹旅程 | 固定“12个东巴字”、固定路线、分阶段奖励 | 改为动态路线卡、真实进度、动态节点和任务条件，保留“我的印记”入口 | 路线、节点和奖励来自后端配置，不写死12字、固定奖励或虚构完成条件 |
| 图08 海报 | 选字、模板、丽江背景、自定义内容、最终分享海报 | 明确分为选1至3字、选纸笺/远山模板、查看示意/实际生成结果三步；支持现有PNG、保存和分享 | 丽江场景合成、自定义文案、预览与最终完全一致及小程序码仍未全部接入；页面直接说明限制 |

## 代码修改

- 全局视觉系统：`miniprogram/app.wxss`
- 首页：`pages/home/index.wxml`、`pages/home/index.wxss`
- 识别结果：`pages/result/index.wxml`、`index.wxss`、`index.js`
- 字详情：`pages/character/index.wxml`、`index.wxss`
- 地图：`pages/map/index.wxml`、`index.wxss`
- 路线与节点：`pages/quests/`、`pages/quest/`
- 海报：`pages/poster/index.wxml`、`index.wxss`
- 共用状态：`components/feature-note/`、`view-state/`、`glyph-image/`
- 装饰素材：`miniprogram/assets/lijiang-panorama.png`
- 回归工具：`miniprogram/tests/visual-preview.cjs`
- 重拍测试随首页Tab路由修正：`miniprogram/tests/services.test.js`

### 首页图01对齐增量（2026-09-27）

- `pages/home/` 采用全宽背景、品牌标题与红色印章、雪山下竖排题字、蓝色发光拍照入口、纸笺今日字卡、三项横向快捷入口和横向商户卡；原生 TabBar 改用 `assets/tabs/` 图标。
- `assets/home/landscape.jpg` 由用户提供的 `assets/lijiang-home-background.png` 压缩生成；源 PNG 保留在工作区但由 `project.config.json` 排除封包。`assets/home/` 和 `assets/tabs/` 的图标、纸纹、墨山为本地程序化 UI 素材，不是东巴字形或文化内容。
- 首页逻辑继续从已发布 API 读取字形、分类、摘要、商户图和标签；定位授权存在时才复用，拒绝或坐标无效时显示明确状态且不显示虚构距离。商户排序只在真实坐标可用时进行。

窄屏检查发现并修复了首页横向商户容器约12px的页面溢出、负边距头图的布局风险，以及海报生成按钮在320px下低于44px的问题。首页、字详情和海报头图改为容器内圆角布局，避免依靠全屏负边距。

## 验证结果

```text
node miniprogram/tests/validate-project.js
Validated 18 native pages, JSON/JS syntax, tab routes and WXML event handlers.
Mini-program code SHA-256: da34a5bb67df370d98233ea0212dc513dc3873ae6045a61ead8755aefe95cef6

node --test miniprogram/tests/helpers.test.js miniprogram/tests/services.test.js miniprogram/tests/home.test.js
36 passed, 0 failed

node miniprogram/tests/native-compile.js "D:\engineering_software\微信web开发者工具"
WeChat native compiler accepted 21 WXML files and 17 WXSS files.

node miniprogram/tests/visual-preview.cjs
PASS: 46 offline layout cases at 320/375/390/430px

.venv\Scripts\python.exe scripts/check_project.py
Project checks passed: 35 requirements, evidence links, source and API
```

离线预览截图和报告位于 `runtime/miniprogram-visual/`，覆盖首页、候选、详情、地图、路线、节点和海报的内容态；首页额外覆盖320/375/390/430px及拒绝定位、缺图、长内容状态，重点截图为 `home-content-375-viewport.png`。

## 证据边界与剩余缺口

- Chromium预览是由真实WXML/WXSS转换的离线布局夹具，只检查布局、横向溢出和触控高度；它不是微信运行时、真机视觉签收、真实API、真实地图或真实识别验收。
- 官方编译结果只证明模板与样式可编译，不是签名上传、体验版或真机验证。
- 夹具中的字、文化段落、商户、路线和商品均明确为布局示例，不是发布内容，也不能证明文化准确性或推荐质量。
- 仍需真机验证系统相机、登录、授权、定位、导航、音频、海报保存/分享和不同微信字体渲染。
- `MINI-01` 的实时拍摄质量提示、`CONTENT-01` 的文化视频、`GEO-01` 的路线与有效优惠卡、`SHARE-01` 的丽江背景配置/预览一致性/小程序码仍未完成，不能因本轮视觉改版改判为验收通过。
- 不以供应商参考分数冒充识别正确率，不以夹具测试冒充真实模型质量或生产就绪。
