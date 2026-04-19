# 药物识别跳转 AI 咨询 — 补齐咨询人参数（v2 · 顶部卡片）

> 本次修复版本：v2 — 用「顶部卡片」展示，覆盖 H5、微信小程序、Flutter App 三端。

## 一、修复背景

之前从「药物识别」跳转到 AI 咨询页时，URL 仅携带 `session_id`，导致咨询页：

1. 无法知道当前是为「哪位家人」识别的药品 → 顶部不显示「咨询对象」
2. 无法知道识别出的药品名称列表 → 顶部不显示「药品摘要」

本次 v2 通过 URL 参数 `member` + `drug_name` 直接把咨询对象与药品摘要带给聊天页，并在聊天页顶部以独立卡片展示，与"健康自检"卡片样式保持一致。

## 二、改动范围

| 端 | 入口 | 关键文件 |
|---|---|---|
| H5（Web） | 识别完成跳转、历史记录跳转、聊天页卡片 | `h5-web/src/app/drug/page.tsx`、`h5-web/src/app/chat/[sessionId]/page.tsx` |
| 微信小程序 | 识别完成跳转、历史记录跳转、聊天页卡片 | `miniprogram/pages/drug/index.{js,wxml}`、`miniprogram/pages/chat/index.{js,wxml,wxss}` |
| Flutter App | 识别完成跳转、历史记录跳转、聊天页卡片 | `flutter_app/lib/screens/health/drug_screen.dart`、`flutter_app/lib/screens/ai/chat_screen.dart`、`flutter_app/lib/providers/health_provider.dart` |

## 三、核心规则（三端一致）

1. **URL 参数**：`member`（咨询对象，如「爸爸·张三」）、`drug_name`（药品列表）。三端均做 URL 编码。
2. **多药拼接**：多个药品名用英文逗号 `,` 拼接，最大长度 **80 字符**，超出截断后追加 `…`。
3. **数据优先级**：URL 参数优先用于初始展示（0 等待）；当 URL 未带某项时，从后端会话详情接口兜底获取。
4. **卡片样式**：💊 图标 + 「用药识别」标题 + 「咨询对象：xxx」副信息 + 药品摘要；浅橙背景 `#fff7e6`、左侧 4px 橙色边框 `#fa8c16`、8px 圆角，**不可点击**。
5. **入口覆盖**：识别完成后跳转 + 历史记录点击跳转，两条路径都按上述规则组装 URL。

## 四、部署与访问入口

本次仅 H5 需要重新构建并部署，部署服务器：`newbb.test.bangbangvip.com`（gateway-nginx → 项目 docker 容器）。

**项目根 URL**：

```
https://newbb.test.bangbangvip.com/autodev/6b099ed3-7175-4a78-91f4-44570c84ed27
```

| 入口 | 链接 | 说明 |
|---|---|---|
| H5 首页 | https://newbb.test.bangbangvip.com/autodev/6b099ed3-7175-4a78-91f4-44570c84ed27/ | 应用入口 |
| 用药识别（本次修改） | https://newbb.test.bangbangvip.com/autodev/6b099ed3-7175-4a78-91f4-44570c84ed27/drug | 上传药盒/历史记录 |
| 聊天会话示例 | https://newbb.test.bangbangvip.com/autodev/6b099ed3-7175-4a78-91f4-44570c84ed27/chat/1 | 顶部卡片展示位 |
| 后端 API 文档 | https://newbb.test.bangbangvip.com/autodev/6b099ed3-7175-4a78-91f4-44570c84ed27/api/docs | Swagger |
| 管理后台 | https://newbb.test.bangbangvip.com/autodev/6b099ed3-7175-4a78-91f4-44570c84ed27/admin/ | 后台 |

链接全量验证结果：10 条核心链接 0 条 5xx。容器状态 ✅ Up。

## 五、用户验证步骤（H5 端）

### 路径 A：识别完成 → 自动跳转

1. 打开 https://newbb.test.bangbangvip.com/autodev/6b099ed3-7175-4a78-91f4-44570c84ed27/drug
2. 选择咨询对象（如「爸爸·张三」），上传 1~3 张药盒图片，点击"开始识别"
3. 识别完成后自动跳转到 `/chat/<session_id>?type=drug_identify&member=...&drug_name=...`
4. **预期**：聊天页顶部立即出现 💊「用药识别」橙色卡片，包含「咨询对象：爸爸·张三」与药品摘要（如「阿莫西林,布洛芬」）。无需等待网络也能看到。

### 路径 B：历史记录 → 点击跳转

1. 在 `/drug` 页面下拉到"历史记录"区，点击任一条记录
2. **预期**：跳转到对应 `chat` 页，顶部卡片立即展示该条历史的咨询对象与药品名（截断到 80 字符）。

### 路径 C：URL 直达兜底

1. 直接访问形如 `…/chat/123?type=drug_identify`（不带 `member` 与 `drug_name`）
2. **预期**：卡片在后端会话详情接口返回后展示完整信息（约 100~500ms）。

## 六、小程序（微信）端验证

打包文件：`dist/miniprogram-drug-fix-v2.zip`（约 313 KB）。

1. 微信开发者工具 → 导入项目 → 选择解压目录
2. 运行至小程序首页 → "药物识别"
3. 重复 H5 路径 A / B 验证，预期顶部卡片样式与 H5 一致。

## 七、Flutter App 端验证

源码已就位，需自行打包：

```bash
cd flutter_app
flutter pub get
flutter build apk --debug   # 安卓
flutter build ios --no-codesign  # 苹果
```

运行后路径同 H5，重点验证：

- 识别完成跳转后，聊天页顶部立即渲染卡片（已修复 `setState` 漏调用导致的"首帧不渲染"问题）。
- 历史记录跳转同样展示卡片。

## 八、回归与适配性结论

- ✅ 普通 AI 咨询（`type=health`）不受影响，不显示用药识别卡片。
- ✅ 健康自检卡片仍正常展示。
- ✅ 当 URL 未带 `member`/`drug_name` 时，仍可由会话详情接口兜底，老链接无破坏。
- ✅ 多药超长场景按 80 字符截断 + `…`，避免折行影响布局。

## 九、变更文件清单

```
h5-web/src/app/drug/page.tsx
h5-web/src/app/chat/[sessionId]/page.tsx
miniprogram/pages/drug/index.js
miniprogram/pages/drug/index.wxml
miniprogram/pages/chat/index.js
miniprogram/pages/chat/index.wxml
miniprogram/pages/chat/index.wxss
flutter_app/lib/screens/health/drug_screen.dart
flutter_app/lib/screens/ai/chat_screen.dart
flutter_app/lib/providers/health_provider.dart
```

