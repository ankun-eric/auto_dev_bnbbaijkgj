# admin-web 开发规范

本文件用于沉淀管理后台开发过程中需要长期遵守的规范，避免后续接手开发者重复踩坑。

## 1. 侧边栏菜单视觉规范

> 来源：2026-05-01 二级菜单图标统一 Bug 修复（参见 `cursor_prompt_256_20260501234115.txt`）

为了保证管理后台左侧侧边栏菜单整体视觉风格的统一，本项目对菜单图标做出如下强约束：

- 一级菜单**必须**配置图标，呈现为「图标 + 文字」
- 二级菜单**禁止**配置图标，仅以纯文字呈现
- 折叠态弹出浮层中的二级菜单同样**禁止**配置图标
- 管理员头像下拉菜单（个人信息 / 修改密码 / 退出登录）保留各自图标，不在本规范约束范围内

### 实现保证

`src/app/(admin)/layout.tsx` 中提供了 `stripChildrenIcons(items)` 工具函数，会在渲染前递归清洗所有 SubMenu children 的 `icon` 字段。即使后续维护者无意中在 `menuItems` 的子项中配置了 `icon`，也不会显示出来，从源头屏蔽。

但仍**强烈建议**在配置 `menuItems` 时就遵守本规范：

```ts
// ✅ 正确
{
  key: 'product-system',
  icon: <AppstoreOutlined />,   // 一级菜单 icon 必须保留
  label: '商品体系',
  children: [
    { key: '/product-system/categories', label: '商品分类' },  // 二级菜单不带 icon
    { key: '/product-system/products', label: '商品管理' },
  ],
}

// ❌ 错误
{
  key: 'product-system',
  icon: <AppstoreOutlined />,
  label: '商品体系',
  children: [
    { key: '/product-system/categories', icon: <TagsOutlined />, label: '商品分类' }, // 二级菜单不允许 icon
  ],
}
```

### 检查清单

提交涉及侧边栏菜单的改动时，需自查：

- [ ] 一级菜单是否都带 icon？
- [ ] 二级菜单是否全部不带 icon？
- [ ] 折叠态浮层下的二级菜单是否同样不带 icon？
- [ ] 管理员头像下拉菜单的图标未被误删？
