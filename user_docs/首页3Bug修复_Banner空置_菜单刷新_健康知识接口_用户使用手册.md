# 首页 3 个 Bug 修复 · 用户使用手册

> 本次修复涉及 App（Flutter）、H5 Web、微信小程序三端首页。本文档介绍修复内容、验证步骤与下载链接。

---

## 一、本次修复的三个问题

### Bug-1：首页 Banner 在后台没有数据时仍然显示
- **修复前**：即使管理员把后台「首页 Banner 管理」清空，前端仍然显示一组默认 Banner（来自代码硬编码）。
- **修复后**：前端完全依赖后端 `/api/home-banners` 接口，没有数据时**整个 Banner 区域不渲染**（无占位、无留白、无渐变背景），接口一旦返回数据又会立刻出现。

### Bug-2：后台调整「首页菜单列数」等配置后，前端不刷新
- **修复前**：首页在初次进入时加载配置后再也不会更新，即使后台配置已改，用户也要杀掉 App / 重装小程序才能看到新列数。
- **修复后**：三端统一加入**下拉刷新 + 切回前台自动刷新（30 秒节流）**，任何时候回到首页都会在满足节流条件时拉取最新配置。

### Bug-3：首页「健康知识」一直是硬编码示例文章
- **修复前**：三端首页显示三条固定的示例文章（"春季养生：如何预防过敏性鼻炎" 等），从不调用后端接口。
- **修复后**：统一调用后端 `GET /api/content/articles?page=1&page_size=3`，取最新 3 篇文章展示；若接口返回空列表，则**整个"健康知识"模块不展示**（标题、"更多>"和卡片全部消失）。

---

## 二、服务器部署信息

| 项目 | 值 |
|------|----|
| 部署域名 | `newbb.test.bangbangvip.com` |
| 项目基础 URL | `https://newbb.test.bangbangvip.com/autodev/6b099ed3-7175-4a78-91f4-44570c84ed27` |
| 部署时间 | 2026-04-21 03:42 |
| 本次提交 | `e06fadd fix(android): 更新 flutter_app android gradle 兼容性配置`（基线 `e556fed fix(home-3bugs): 首页3个Bug修复`） |

最近一次全量链接可达性检查结果：**10 / 10 全部通过 ✅**（首页、登录、tab 首页、admin、5 个核心 API、健康检查）。

---

## 三、各端下载与体验入口

### 3.1 H5 Web（浏览器）

无需下载，直接访问：

| 入口 | URL |
|------|-----|
| H5 首页 | [https://newbb.test.bangbangvip.com/autodev/6b099ed3-7175-4a78-91f4-44570c84ed27/](https://newbb.test.bangbangvip.com/autodev/6b099ed3-7175-4a78-91f4-44570c84ed27/) |
| 登录页 | [https://newbb.test.bangbangvip.com/autodev/6b099ed3-7175-4a78-91f4-44570c84ed27/login](https://newbb.test.bangbangvip.com/autodev/6b099ed3-7175-4a78-91f4-44570c84ed27/login) |
| 我的 | [https://newbb.test.bangbangvip.com/autodev/6b099ed3-7175-4a78-91f4-44570c84ed27/profile](https://newbb.test.bangbangvip.com/autodev/6b099ed3-7175-4a78-91f4-44570c84ed27/profile) |

### 3.2 管理后台 Admin

| 入口 | URL |
|------|-----|
| admin 首页 | [https://newbb.test.bangbangvip.com/autodev/6b099ed3-7175-4a78-91f4-44570c84ed27/admin/](https://newbb.test.bangbangvip.com/autodev/6b099ed3-7175-4a78-91f4-44570c84ed27/admin/) |
| admin 登录 | [https://newbb.test.bangbangvip.com/autodev/6b099ed3-7175-4a78-91f4-44570c84ed27/admin/login](https://newbb.test.bangbangvip.com/autodev/6b099ed3-7175-4a78-91f4-44570c84ed27/admin/login) |

与本次 Bug 相关的后台配置入口：

- 「首页 Banner 管理」→ 增删后刷新前端首页即可看到效果（参考 Bug-1/Bug-2）。
- 「首页菜单管理 / 首页配置（菜单列数）」→ 调整后刷新前端首页即可看到效果（参考 Bug-2）。
- 「内容管理 / 文章」→ 新增/下架文章后，前端"健康知识"模块按创建时间倒序取前 3 篇展示（参考 Bug-3）。

### 3.3 Android APK（Flutter App）

| 类型 | 下载链接 |
|------|----------|
| 最新版（固定链接） | [https://newbb.test.bangbangvip.com/autodev/6b099ed3-7175-4a78-91f4-44570c84ed27/apk/bini_health.apk](https://newbb.test.bangbangvip.com/autodev/6b099ed3-7175-4a78-91f4-44570c84ed27/apk/bini_health.apk) |

> 安装提示：Android 手机直接浏览器打开上方链接下载 APK 后安装。若系统提示"未知来源"，前往 *设置 → 应用管理 → 信任此来源* 开启权限。

### 3.4 微信小程序（zip 源码包）

| 类型 | 下载链接 |
|------|----------|
| 最新版（固定链接） | [https://newbb.test.bangbangvip.com/autodev/6b099ed3-7175-4a78-91f4-44570c84ed27/downloads/miniprogram_latest.zip](https://newbb.test.bangbangvip.com/autodev/6b099ed3-7175-4a78-91f4-44570c84ed27/downloads/miniprogram_latest.zip) |
| 本次唯一包 | [https://newbb.test.bangbangvip.com/autodev/6b099ed3-7175-4a78-91f4-44570c84ed27/downloads/miniprogram_home3bugs_20260421_034031_86c1.zip](https://newbb.test.bangbangvip.com/autodev/6b099ed3-7175-4a78-91f4-44570c84ed27/downloads/miniprogram_home3bugs_20260421_034031_86c1.zip) |

> 使用方法：
> 1. 浏览器下载 zip 解压到任意目录（解压后**根目录**即是 `app.json`/`app.js`/`project.config.json`）；
> 2. 打开**微信开发者工具** → *导入项目* → 选解压后的目录；
> 3. 编译运行即可在模拟器/真机预览首页。

---

## 四、验证步骤

### 场景 1：验证 Bug-1（Banner 空置不渲染）

1. 打开 admin 后台 →「首页 Banner 管理」→ 将所有 Banner **下架 / 删除**。
2. 三端分别操作：
   - **H5**：浏览器刷新首页；
   - **App**：首页下拉刷新 或 回到桌面 30 秒后再进入 App；
   - **小程序**：首页下拉刷新 或 切换 Tab 再切回（满足 30 秒节流条件则刷新）。
3. **预期**：首页搜索框下方**完全没有**轮播 Banner 区域，直接显示"今日打卡 / 菜单"等内容，上下元素无留白/占位。
4. 再回到后台新增一条 Banner 并上架 → 重复第 2 步刷新 → 首页应立刻显示该 Banner。

### 场景 2：验证 Bug-2（菜单列数动态刷新）

1. admin 后台 →「首页配置」→ 把"菜单列数"从 3 改为 4（或相反）→ 保存。
2. **不关闭 App / 不重装小程序**，三端分别操作：
   - **H5**：下拉刷新或切回标签页；
   - **App**：下拉首页（出现转圈指示器）；
   - **小程序**：下拉刷新或从其他 Tab 切回首页（满足 30 秒节流）。
3. **预期**：首页菜单网格立刻按新列数重新排列，无需重启 / 重装。

### 场景 3：验证 Bug-3（健康知识接口化）

1. admin 后台 →「内容管理 / 文章」→ 新建一篇文章 *"饮食健康小贴士"* 发布。
2. 三端刷新首页（下拉 / 切回前台）。
3. **预期**：首页"健康知识"模块显示该文章（按创建时间倒序，只取最新 3 篇）；若后台无任何已发布文章，该模块**整段不展示**（包括"健康知识"标题与"更多 >"入口）。

### 场景 4：节流验证（Bug-2 的性能保护）

App / H5 / 小程序每次切回前台都会触发一次首页刷新，但**30 秒内重复切回不会再次请求**，避免对后端产生频繁压力。开发者可通过 Chrome DevTools Network / 微信开发者工具 Network 观察。

---

## 五、技术要点（供回归/排查参考）

| 端 | 核心文件 | 关键改动 |
|----|----------|----------|
| Flutter App | `flutter_app/lib/screens/home/home_screen.dart`、`flutter_app/lib/services/api_service.dart` | `with WidgetsBindingObserver` + `didChangeAppLifecycleState` + `RefreshIndicator` + `_loadArticles(pageSize:3)`，Banner 空数组时 `if (_banners.isNotEmpty)` 整体隐藏；`getArticles` 支持 `pageSize` |
| H5 Web | `h5-web/src/app/(tabs)/home/page.tsx`、`h5-web/src/lib/useHomeConfig.ts` | `PullToRefresh` + `document.visibilitychange` + `fetchArticles`；`useHomeConfig` 去除 `DEFAULT_BANNERS/MENUS`，暴露 `refetch/clearCache` |
| 小程序 | `miniprogram/pages/home/index.js`、`index.wxml` | 去除 `DEFAULT_BANNERS/MENUS/articles/healthTips`，新增 `loadArticles()`；`onShow` 30s 节流；`onPullDownRefresh` 全量刷新；wxml Banner/健康知识区域 `wx:if="{{items.length>0}}"` |

涉及后端接口（均为既有接口，本次未做变更）：

- `GET /api/home-config` — 首页配置（含菜单列数）
- `GET /api/home-banners` — 首页 Banner 列表（可返回空数组）
- `GET /api/home-menus` — 首页菜单列表（可返回空数组）
- `GET /api/content/articles?page=1&page_size=3` — 健康知识文章列表

---

## 六、回滚方案

如果新版本出现意外问题：

- **服务端**（H5 镜像）：服务器上可执行 `cd /home/ubuntu/6b099ed3-7175-4a78-91f4-44570c84ed27 && git reset --hard 58ebd04 && docker compose -f docker-compose.prod.yml up -d --build --no-deps h5-web`。
- **App**：用户继续使用旧版本 APK 即可（未启用强制升级）。
- **小程序**：放弃本次 zip，使用开发者工具切回上一次提交对应的本地副本即可。

---

## 七、常见问题

**Q1：为什么 App 里下拉刷新看起来没反应？**
- 首页数据量很小，多数情况下刷新在 200~500ms 内返回；若出现 `unhealthy` 等服务器异常，请查看后台或联系运维。

**Q2：切回 App 前台后能看到数据更新吗？**
- 30 秒节流窗口内不会重复请求；建议测试时每次等待至少 30 秒再切回，或直接使用"下拉刷新"强制刷新。

**Q3：小程序每次切 Tab 都在刷接口吗？**
- 不会。`onShow` 时会走 30 秒节流判断，间隔不足时仅做轻量 `loadSelectedCity` 等必要操作；下拉刷新不受节流限制。

---

> 若有任何反馈或问题，请在 admin 后台「反馈管理」模块留言，或直接联系运维。祝使用愉快！
