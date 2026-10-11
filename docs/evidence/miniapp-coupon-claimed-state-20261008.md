# 小程序领券按钮状态修复证据

日期：2026-10-08  
范围：COUPON-01、D-079；仅小程序商户详情，不修改后端规则、数据库或服务器部署。

## 问题与修复

原商户详情在`POST /coupons/{id}/claim`成功后只显示提示，不更新券列表，按钮随即恢复为“领取”；页面重新进入时也没有读取本人领券记录。因此游客会继续点击，最终依赖服务端领取上限报错。

本轮实现：

- 已登录游客加载商户详情时同时读取`GET /me/coupons`，按`coupon_id`恢复已领取状态；未登录游客不请求私人接口。
- 领取成功后立即把对应券标记为已领取；按钮显示“已领取”、置灰并禁用。
- 控制器在发请求前再次检查本地已领取状态，连续点击只产生一次领取请求。
- 服务端返回`CLAIM_LIMIT`时把陈旧页面状态恢复为已领取；库存、每人限额、有效期及核销继续由后端裁决。

## 验证

| 命令 | 结果 |
| --- | --- |
| `node --test --experimental-test-isolation=none miniprogram/tests/merchant.test.js` | 4/4通过：历史领取恢复、成功后即时变更、重复请求阻断、领取上限状态恢复及WXML文案/禁用绑定 |
| 排除`home.test.js`后运行其余`miniprogram/tests/*.test.js` | 157/157通过 |
| `node miniprogram/tests/validate-project.js` | 19个页面静态校验通过；小程序代码SHA-256为`a30fd6fb75743b6642e423a571609e0ebbf72907b9f0b9ddcb08820438d9e35e` |
| `node miniprogram/tests/native-compile.js "D:\engineering_software\微信web开发者工具"` | 微信官方编译器接受22份WXML和18份WXSS |
| `git diff --check -- miniprogram/pages/merchant/index.js miniprogram/pages/merchant/index.wxml miniprogram/pages/merchant/index.wxss miniprogram/tests/merchant.test.js` | 通过；仅有Windows换行提示 |

## 已知限制

- 全量小程序单测中，用户此前删除首页`album-shortcut`后仍有旧断言，故当前全量为1项失败；该失败不涉及商户领券代码。本轮保留该用户修改，没有擅自恢复按钮。
- `run_business_flow.py`当前在读取既有缺失文件`miniprogram/pages/camera/index.js`时停止，尚未走到领券步骤；不能把该HTTP流程记为本轮通过。
- 官方编译只证明模板/样式语法可接受，不等于微信真机或已发布版本验收。本轮未上传体验版/正式版，用户端需重新上传小程序后才会生效。

## 文件指纹

- `miniprogram/pages/merchant/index.js`: `97c74026d0c2e97561fb76c07d56193d667299c6c008d46c21a4d08cb12b45e1`
- `miniprogram/pages/merchant/index.wxml`: `b5182b39d6f0135f1100131a9d43725b27577bc22d795a73bb36e607c8b1f311`
- `miniprogram/pages/merchant/index.wxss`: `54fc44f79cd88ea72c66458f81f05e63edd74409ed70d81fb8fa762878afeb71`
- `miniprogram/tests/merchant.test.js`: `e3d45a2e71254078107aad2d19889c5cb5d0ce4152c7e316025b837eeb6dbbb2`
