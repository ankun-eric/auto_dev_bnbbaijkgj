# 三端首页顶部紧凑化 · 用户体验手册

> 本次升级聚焦 **App（Flutter）/ H5 Web / 微信小程序** 三端**首页顶部区域**的视觉与交互重构，目标：去掉冗余 LOGO、压低头部高度、把更多核心功能提到首屏。零后端改动。

---

## 一、本次升级要点

### 1.1 为什么改
- 旧版顶部：大图 LOGO + 标题 + 高 Banner（~144px）占据首屏近一半，核心菜单要下拉才能看到。
- 新版顶部：**品牌绿双行紧凑头** + **小 Banner（~100px）**，首屏直接暴露定位/搜索/扫码/消息/菜单入口。

### 1.2 视觉对比（概念示意）

```
【旧版】                              【新版】
┌───────────────────────┐           ┌───────────────────────┐
│  [LOGO]   扫码  🔔    │           │ 宾尼小康   📍深圳 ▾   │  ← 40px
│                       │           │ 🔍 搜索健康服务…[扫][🔔·3]│ ← 48px
│    🔍 搜索健康服务…   │           ├───────────────────────┤
├───────────────────────┤           │  【 小 Banner ~100px 】│
│                       │           ├───────────────────────┤
│    【 大 Banner ~144px】│           │  菜单区（上移~80px）    │
├───────────────────────┤           │  公告栏 / 健康知识      │
│  菜单区（需滚动可见）  │           └───────────────────────┘
```

### 1.3 改动清单

| 项 | 旧 | 新 |
|----|----|----|
| 顶部 LOGO 图片 | ✅ 显示 | ❌ **移除**，改用"宾尼小康"四字文本 |
| 第一行内容 | LOGO + 标题 + 扫码/消息 | **品牌文字 + 📍地区 ▾**（~40px） |
| 第二行内容 | 搜索单独一行 | **🔍 搜索 + [扫] + [🔔·N]**（~48px） |
| Banner 高度 | ~144px | **~100px** |
| 头部总高（不含状态栏） | ~220px+ | **~188px**（省出 ~30px） |
| App 状态栏 | 默认浅色 | **沉浸式品牌绿**（`AnnotatedRegion` 白色图标） |
| 小程序胶囊按钮冲突 | — | 第一行右侧**留出 200rpx** 避让 |

### 1.4 交互规则（三端一致）
- **"宾尼小康"**：纯文字标题，不可点击。
- **📍地区 ▾**：点击跳转城市选择页（`/city-select`），切换后**仅更新地名显示**，下方内容不刷新。
- **🔍 搜索框**：点击跳转原有搜索页；占位文案由后端 `/api/home-config.search_placeholder` 下发。
- **[扫]**：调起系统扫一扫能力。
- **🔔 消息**：右上角红点显示未读数（>99 显示 `99+`，为 0 时**隐藏红点**）；点击跳转消息中心（`/messages`）；首页进入/Tab 切回时刷新数量。

---

## 二、部署与验证信息

| 项 | 值 |
|----|----|
| 部署域名 | `newbb.test.bangbangvip.com` |
| 项目基础 URL | `https://newbb.test.bangbangvip.com/autodev/6b099ed3-7175-4a78-91f4-44570c84ed27` |
| 部署时间 | 2026-04-21 |
| 核心提交 | `741c409 feat(home-compact): 三端首页顶部紧凑化(去LOGO+双行+小Banner)` |

**全量链接可达性验证：18 / 18 全部通过 ✅**

| 类型 | 路径 | 状态 |
|------|------|------|
| H5 | `/`, `/login`, `/home`, `/city-select`, `/search`, `/scan`, `/messages`, `/profile` | 200 |
| Admin | `/admin/`, `/admin/login` | 200 |
| API | `/api/health`, `/api/home-config`, `/api/home-banners`, `/api/home-menus`, `/api/content/articles`, `/api/notices/active`, `/api/settings/logo` | 200 |
| API（需登录） | `/api/messages/unread-count` | 401（预期，未登录） |

---

## 三、各端体验入口

### 3.1 H5 Web（浏览器打开即可）

| 入口 | URL |
|------|-----|
| 首页 | https://newbb.test.bangbangvip.com/autodev/6b099ed3-7175-4a78-91f4-44570c84ed27/ |
| 登录 | https://newbb.test.bangbangvip.com/autodev/6b099ed3-7175-4a78-91f4-44570c84ed27/login |
| 首页(Tab) | https://newbb.test.bangbangvip.com/autodev/6b099ed3-7175-4a78-91f4-44570c84ed27/home |
| 城市选择 | https://newbb.test.bangbangvip.com/autodev/6b099ed3-7175-4a78-91f4-44570c84ed27/city-select |
| 搜索 | https://newbb.test.bangbangvip.com/autodev/6b099ed3-7175-4a78-91f4-44570c84ed27/search |
| 消息 | https://newbb.test.bangbangvip.com/autodev/6b099ed3-7175-4a78-91f4-44570c84ed27/messages |
| 我的 | https://newbb.test.bangbangvip.com/autodev/6b099ed3-7175-4a78-91f4-44570c84ed27/profile |

### 3.2 管理后台 Admin

- 入口：https://newbb.test.bangbangvip.com/autodev/6b099ed3-7175-4a78-91f4-44570c84ed27/admin/
- Banner 管理：`管理后台 → 首页 Banner`，建议每张 Banner 另存一份**紧凑版小图**到 `image_url_compact` 字段（可选，未配置则复用原 `image_url`）。

### 3.3 微信小程序（开发者工具导入 zip）

| 入口 | URL |
|------|-----|
| 本次构建包（唯一） | https://newbb.test.bangbangvip.com/autodev/6b099ed3-7175-4a78-91f4-44570c84ed27/downloads/miniprogram_home_compact_20260421_164457_ce7d.zip |
| 最新包（永久链接） | https://newbb.test.bangbangvip.com/autodev/6b099ed3-7175-4a78-91f4-44570c84ed27/downloads/miniprogram_latest.zip |

**体验步骤**：
1. 下载 zip 并解压。
2. 打开微信开发者工具 → 导入项目 → 选择解压后的目录。
3. 编译运行，在模拟器或真机上查看首页。
4. 注意小程序首页采用 `navigationStyle: custom`，右上角胶囊按钮不会被遮挡。

### 3.4 Android App（APK）

| 入口 | URL |
|------|-----|
| 本次 APK（唯一） | https://newbb.test.bangbangvip.com/autodev/6b099ed3-7175-4a78-91f4-44570c84ed27/apk/bini_health_home_compact_20260421-170327.apk |
| 最新 APK（永久链接） | https://newbb.test.bangbangvip.com/autodev/6b099ed3-7175-4a78-91f4-44570c84ed27/apk/bini_health.apk |

> APK 由服务器端 Docker + Flutter 构建产出，构建完成后上述链接即可直接下载安装。

### 3.5 iOS App（IPA）

通过 GitHub Actions `iOS Build` workflow 在 macos-runner 上构建，产物发布到仓库 Releases：

- 仓库：https://github.com/ankun-eric/auto_dev_bnbbaijkgj/releases
- 本次版本 tag：`ios-home-compact-20260421-164621`

未签名的 IPA 需使用 AltStore / sideloadly 等工具安装到 iPhone（iOS 开发者签名证书可选）。

---

## 四、验收清单（建议按顺序走一遍）

- [ ] 打开 H5 首页，顶部**看不到任何 LOGO 图片**，只看到"宾尼小康"文字。
- [ ] 顶部明显比旧版**矮一截**，进入即可看到菜单区/公告栏。
- [ ] 点击 📍 地区，进入城市选择页，选中新城市后返回 → 顶部地名变化、下方 Banner/菜单等**不刷新闪烁**。
- [ ] 点击 🔔，进入消息中心；若有未读，红点显示正确（>99 显示 `99+`）。
- [ ] 点击扫码按钮，系统相机正常调起。
- [ ] 小程序真机预览：右上角胶囊按钮与第一行内容**不重叠**。
- [ ] Flutter App：状态栏与头部同色（沉浸式品牌绿），状态栏图标为白色。
- [ ] Banner 高度明显变矮（~100px），圆角、两侧留白自然。
- [ ] 后台新上传一张 Banner（带 `image_url_compact`），三端都能正确显示小图；未配置 compact 时回退显示原图。

---

## 五、已知限制 / 注意事项

1. **Banner 图片建议**：为获得最佳紧凑效果，建议后台运营方上传 1125×300（或等比 16:5 ~ 16:4.5）压缩过的小图到 `image_url_compact`。
2. **地区切换不刷新**：按 PRD 约定，仅更换显示文案，不重新拉 `/api/home-banners` 等接口（避免首屏闪烁）。如有需要下拉刷新即可重新加载。
3. **老用户小程序体验版**：如看到旧版头部，请在开发者工具"清缓存 → 编译"，或真机杀后台重进。

---

文档生成时间：2026-04-21  
相关 PRD：《三端首页顶部紧凑化改造》
