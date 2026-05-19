# _archived_tabs（归档目录）

## 归档原因

本目录是 2026-05 「AI 首页与抽屉入口优化」需求中砍掉的 `(tabs)` 路由组的原始文件。

产品方向已收敛为「AI 优先」，菜单模式首页和底部 Tab Bar 不再使用，
但代码暂时保留以便回查和复用。

> Next.js App Router 自动忽略以下划线开头的目录（`_archived_tabs`），
> 因此本目录不会注册成路由，对线上行为零影响。

## 归档日期

2026-05-19

## 归档前的路由

- `/home`    →  `home/page.tsx`
- `/ai`      →  `ai/page.tsx`
- `/profile` →  `profile/page.tsx`（注：因与 `app/profile/` 同名，原 `(tabs)` 路由组下的 profile 已被归档）
- `(tabs) layout` → `layout.tsx`

## 服务页迁移

原 `(tabs)/services/page.tsx` 已迁移到 `app/services/page.tsx`（路由仍为 `/services`），
迁移过程中：

- 顶部新增「返回 AI 首页」按钮（`router.replace('/ai-home')`）
- 顶部搜索栏由「antd-mobile SearchBar 本地过滤」替换为「全局搜索入口」（点击跳 `/search`）
- 本地搜索相关 state、防抖逻辑、搜索结果态全部删除

## 全局搜索入口组件

为复用从旧 `(tabs)/home` 抠出来的「白底胶囊 + 放大镜图标」搜索入口，已封装为：

`h5-web/src/components/search/GlobalSearchEntry.tsx`

供 `/services` 顶部使用，点击后 `router.push('/search')`。

## 二次清理计划

线上稳定运行 2 个月后（约 2026-07），起独立 PR 整体删除本目录。
