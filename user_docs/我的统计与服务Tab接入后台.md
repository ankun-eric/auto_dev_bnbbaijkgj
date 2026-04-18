# 「我的」统计 & 「服务」Tab 接入后台 — 用户体验手册

> 上线日期：2026-04-19
> 版本提交：`032b776 fix(backend): /api/products/categories 500 — 异步关系 lazy load`
> 部署服务器：`https://newbb.test.bangbangvip.com/autodev/6b099ed3-7175-4a78-91f4-44570c84ed27`

---

## 一、功能概述

本次发版围绕"个人中心数据真实化"和"服务页全平台后台化"两大主题，覆盖 H5、微信小程序、Flutter App、管理后台四端：

1. **「我的」页统计真实化**：积分 / 优惠券 / 收藏 三个数字现在全部来自后端实时聚合，不再硬编码 0。
2. **「服务」Tab 全部接入后台数据**：H5、小程序、Flutter App 的服务页不再使用本地静态数据，全部通过商品后台统一管理。
3. **管理后台分类拖拽排序**：商品分类列表支持鼠标拖拽行调整同级顺序，所见即所得。
4. **H5 路由统一**：废弃旧的 `/service/[id]` 商品详情路由，统一收口到 `/product/[id]`。

---

## 二、访问入口

| 端 | 入口 | 说明 |
|---|---|---|
| H5 | `https://newbb.test.bangbangvip.com/autodev/6b099ed3-7175-4a78-91f4-44570c84ed27/` | 底部 Tab → 我的 / 服务 |
| 管理后台 | `https://newbb.test.bangbangvip.com/autodev/6b099ed3-7175-4a78-91f4-44570c84ed27/admin/` → 商品体系 → 商品分类 | 拖拽行调整顺序 |
| 微信小程序 | 源码包 `user_docs/miniprogram_20260419012842.zip`（导入开发者工具体验） | 底部 Tab → 我的 / 服务 |
| 安卓 APK | GitHub Actions 构建中 → 完成后位于 `https://github.com/ankun-eric/auto_dev_bnbbaijkgj/releases/tag/android-v20260419012905` | 直接下载安装 |

---

## 三、功能详解

### 3.1 「我的」页统计

**修改前**：积分显示用户字段，优惠券和收藏写死为 0。

**修改后**：进入「我的」页后立刻请求 `GET /api/users/me/stats`，三端同步刷新展示：
- **积分**：当前用户余额
- **优惠券**：未使用且**未过期**的券数量
- **收藏**：所有类型（商品 / 文章 / 视频）的收藏总数

**自动刷新时机**：
- H5：进入页面 + 浏览器 Tab 切回前台
- 小程序：`onShow`（每次切到「我的」Tab 都刷新）
- Flutter App：`initState` + 应用从后台恢复 + 从子页面（积分页 / 我的优惠券 / 我的收藏）返回

**联动**：H5 的 `/my-coupons` 列表在「未使用」标签下也启用了 `exclude_expired=true` 过滤，与「我的」页统计口径完全一致——再也不会出现"统计 0 张但点进去看到一堆已过期券"的混淆。

---

### 3.2 「服务」Tab 接入后台

#### 3.2.1 H5 服务页 `/services`

- 顶部 Tab 改为动态渲染，来源 `GET /api/products/categories` 的顶级分类。
- 切换 Tab 后请求 `GET /api/products?category_id={id}&page=...` 拉取该分类下商品。
- 列表支持搜索框关键词过滤（前端实时过滤当前已加载列表）+ 上拉加载更多（`InfiniteScroll`）。
- 商品卡优先使用 `cover_image`，无封面时显示分类 emoji 图标作占位。
- 点击商品 → 跳转 `/product/[id]`（已废弃 `/service/[id]`）。

#### 3.2.2 小程序服务页

- 顶部分类 Tab 由 `wx:for="{{tabs}}"` 动态渲染，来源同上。
- 支持下拉刷新分类 + 上拉加载更多商品。
- 点击商品 → `wx.navigateTo` 到 `/pages/product-detail/index?id=`。
- 空数据 / 加载中 / 没有更多 三种状态完整呈现。

#### 3.2.3 Flutter App 服务页

- 用 `TabController` 渲染分类 Tab；切换 Tab 自动加载对应商品。
- 每个 Tab 内的商品列表独立维护页码与 hasMore，支持 `RefreshIndicator` 下拉刷新。
- 滚动到底部触发 `_loadProducts(...)` 加载更多。
- 顶部右侧悬浮 FAB「找专家」入口保留。

---

### 3.3 管理后台分类拖拽排序

进入「商品体系 → 商品分类」：

1. 表格首列出现拖拽手柄图标（≡）。
2. **按住任意行向上 / 向下拖动**，拖到目标位置释放鼠标，列表立即刷新并提示「排序已更新」。
3. **仅支持同级拖拽**：跨级移动会弹提示「请使用编辑修改上级分类」。
4. 排序结果写入 `sort_order` 字段，立即生效，前端三端切换 Tab 时即可看到新顺序。

底层调用：`POST /api/admin/products/categories/reorder`，请求体：
```json
{ "parent_id": null, "ordered_ids": [3, 1, 2] }
```

---

## 四、新增 / 变更接口一览

| 方法 | 路径 | 说明 |
|---|---|---|
| GET | `/api/users/me/stats` | 聚合：`{points, coupon_count, favorite_count}` |
| GET | `/api/coupons/mine?exclude_expired=true` | 已有接口新增过滤参数 |
| GET | `/api/products/categories` | 返回 `{items: 顶级树, flat: 全部扁平列表}` |
| POST | `/api/admin/products/categories/reorder` | 同级拖拽排序 |

测试覆盖：`backend/tests/test_my_stats_and_reorder.py` 4 个用例。

---

## 五、部署验证记录

- 后端 / h5 / admin 三个容器已通过 `docker compose up -d --build` 重建并 Up
- 关键链接全部 200 / 401（未登录正常）：

| URL | 状态 |
|---|---|
| `/` | 200 |
| `/admin/` | 200 |
| `/api/health` | 200 |
| `/api/products/categories` | 200 |
| `/api/products?page=1&page_size=5` | 200 |
| `/api/users/me/stats`（未登录） | 401 |
| `/api/coupons/mine?exclude_expired=true`（未登录） | 401 |
| `/api/admin/products/categories/reorder`（未登录 GET） | 405 |

---

## 六、回归测试要点（建议人工跑一遍）

1. 「我的」页：
   - 进入页面，三个数字均能在 1 秒内显示。
   - 切到其他 Tab 再切回，数字会重新拉取（不显示骨架闪烁则更佳）。
2. 「服务」页：
   - 顶部分类 Tab 数量与管理后台一致。
   - 切换 Tab 后商品列表能正常滚动加载。
   - 点击商品成功跳到详情页（H5 → `/product/{id}`）。
3. 管理后台分类：
   - 拖拽两行调换顺序后，前端三端切到「服务」页都能看到新顺序。
4. 优惠券：
   - 后台造一张已过期的未使用券，「我的」页计数不应包含它；进 `/my-coupons` 选「未使用」也不应看到它。

---

## 七、已知 / 历史 Bug 修复

本次发版同时修复了一个潜在的 500 错误：

> `/api/products/categories` 在 async 上下文中通过 `model_validate(orm_obj)` 触发 `children` 关系的 lazy load，报 `MissingGreenlet`。
> **修复方式**：手动构造 dict 并预填空 children 数组，避免触发 SQLAlchemy 同步 lazy 加载。

如有任何反馈请联系研发。
