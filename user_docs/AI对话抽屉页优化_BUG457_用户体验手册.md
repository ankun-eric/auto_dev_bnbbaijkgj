# AI 对话抽屉页优化 · 用户体验手册（BUG-457）

> 版本：v1.0  
> 发布时间：2026-05-11  
> 适用端：H5 端（手机浏览器、微信内置浏览器）

---

## 访问链接

以下是当前项目的体验链接，点击即可打开：

> ⚠️ 所有链接均使用宿主机 Nginx 代理端口（80/443），请勿使用 Docker 容器内部端口。

| 服务 | 链接 | 说明 |
|------|------|------|
| H5 首页 | [https://newbb.test.bangbangvip.com/autodev/6b099ed3-7175-4a78-91f4-44570c84ed27/](https://newbb.test.bangbangvip.com/autodev/6b099ed3-7175-4a78-91f4-44570c84ed27/) | 项目主页面入口 |
| AI 对话首页（本次修复主页面） | [https://newbb.test.bangbangvip.com/autodev/6b099ed3-7175-4a78-91f4-44570c84ed27/ai-home](https://newbb.test.bangbangvip.com/autodev/6b099ed3-7175-4a78-91f4-44570c84ed27/ai-home) | 进入 AI 对话页，点击右上角 ☰ 即可拉出修复后的抽屉 |
| 个人资料编辑（点击 ID 胶囊跳转目标） | [https://newbb.test.bangbangvip.com/autodev/6b099ed3-7175-4a78-91f4-44570c84ed27/profile/edit](https://newbb.test.bangbangvip.com/autodev/6b099ed3-7175-4a78-91f4-44570c84ed27/profile/edit) | 修改昵称、头像等个人信息 |
| 我的优惠券 | [https://newbb.test.bangbangvip.com/autodev/6b099ed3-7175-4a78-91f4-44570c84ed27/my-coupons](https://newbb.test.bangbangvip.com/autodev/6b099ed3-7175-4a78-91f4-44570c84ed27/my-coupons) | 抽屉资产 4 格的「优惠券」目标页 |
| 统一订单 | [https://newbb.test.bangbangvip.com/autodev/6b099ed3-7175-4a78-91f4-44570c84ed27/unified-orders](https://newbb.test.bangbangvip.com/autodev/6b099ed3-7175-4a78-91f4-44570c84ed27/unified-orders) | 抽屉资产 4 格的「订单」目标页 |
| 我的收藏 | [https://newbb.test.bangbangvip.com/autodev/6b099ed3-7175-4a78-91f4-44570c84ed27/my-favorites](https://newbb.test.bangbangvip.com/autodev/6b099ed3-7175-4a78-91f4-44570c84ed27/my-favorites) | 抽屉资产 4 格的「收藏」目标页 |
| 积分中心 | [https://newbb.test.bangbangvip.com/autodev/6b099ed3-7175-4a78-91f4-44570c84ed27/points-center](https://newbb.test.bangbangvip.com/autodev/6b099ed3-7175-4a78-91f4-44570c84ed27/points-center) | 抽屉资产 4 格的「积分」目标页 |

---

## 功能简介

本次更新针对 **「AI 对话模式 → 右上角 ☰ 抽屉」** 页面进行 4 项优化，提升信息准确性与交互一致性：

1. **去除 ID 胶囊后的多余复制图标**，点击 ID 胶囊改为直接跳转到「个人资料编辑」页面
2. **删除顶部中间多余的「会员二维码」入口**，顶栏只保留「🔔 消息」「⚙ 设置」两个真正常用的入口
3. **修复资产 4 格（积分 / 优惠券 / 订单 / 收藏）数字始终为 0 的问题**，现已与「菜单模式 → 我的」页面读取相同接口，数据一致
4. **修复「历史对话」加载失败 / 列表空白的问题**，并把异常态收窄为只在真正断网时显示「加载失败，点击重试」

---

## 使用说明

### 1. 进入 AI 对话页并打开抽屉

1. 在浏览器中访问 [AI 对话首页](https://newbb.test.bangbangvip.com/autodev/6b099ed3-7175-4a78-91f4-44570c84ed27/ai-home)（首次访问需先登录）
2. 登录成功后将进入 AI 对话首页
3. 点击右上角的 **☰** 图标，左侧抽屉将从左侧滑出

### 2. 抽屉顶部交互（修复点 1 + 2）

打开抽屉后，请重点查看以下变化：

| 区域 | 修复前 | 修复后 |
|------|--------|--------|
| 顶部右上图标区 | 🔔 消息 / ⊞ 会员二维码 / ⚙ 设置（**三个**） | 🔔 消息 / ⚙ 设置（**两个**） |
| ID 胶囊 | `ID: xxxxx 📋` 点击后弹「ID 已复制」Toast | `ID: xxxxx`（**无图标**），点击直接跳转个人资料编辑页 |

**操作步骤**：

1. 抬眼看顶部右上区域 → 应**只有 🔔 和 ⚙ 两个圆形图标**，中间不再有「⊞」
2. 看 ID 胶囊（昵称下方那条灰色椭圆条） → 应**只显示「ID: 你的编号」**，右侧不再有 📋
3. 点一下 ID 胶囊 → 直接跳转到 [个人资料编辑](https://newbb.test.bangbangvip.com/autodev/6b099ed3-7175-4a78-91f4-44570c84ed27/profile/edit) 页面，不再弹出"已复制"提示
4. 在编辑页中，如需复制 ID，可像复制普通文字一样长按 / 选中 ID 后复制即可

### 3. 抽屉中部资产 4 格（修复点 3）

抽屉中部从左到右四个图标分别是：**积分 / 优惠券 / 订单 / 收藏**。

**新规则**：
- 数字 = **0** 时不显示红色角标
- 数字 **1～98** 原样显示
- 数字 **≥ 99** 显示「99+」
- **订单角标** = 待付款 + 待收货 + 待使用 三者之和

**自查方法**：
1. 打开抽屉，记下中部 4 个数字
2. 退出抽屉，从底部菜单切换到「菜单模式 → 我的」页面
3. 对比"我的"页面中的相同 4 项数据 → **应完全一致**
4. 点击抽屉中任意一格图标 → 应跳转到对应的列表页（如优惠券 → 我的优惠券）

### 4. 抽屉底部历史对话（修复点 4）

历史对话区分组规则保持不变：

```
置顶 → 最近 7 天 → 最近 30 天 → 更早
```

每条会话展示：
- **标题**（一行省略）
- **摘要**（≤30 字，超出加省略号）
- **咨询人圆点 + 角色文字**（本人/配偶/爸爸/妈妈/孩子/老人 6 色固定配色）
- **相对时间**（如「3 分钟前」「昨天」「3 天前」）
- **置顶标签**（如已置顶）

**异常态处理**：
- 接口正常但暂无对话 → 显示「💬 还没有对话记录，开始你的第一次咨询吧」+ 返回首页按钮
- 真正网络异常时 → 显示「加载失败」+「点击重试」按钮，点击后重新加载

**操作入口三态共存**：
- 单条点 ⋯ 按钮 → 弹出「置顶 / 删除」菜单
- 单条向左滑动 → 暴露右侧「置顶 / 删除」两色块按钮
- 点击右上角「管理」 → 进入批量管理态，可勾选多条后底部「删除」

---

## 注意事项

1. **必须登录后才能看到真实数据**：未登录状态下，资产 4 格仍可能显示 0、历史对话为空，这是正常的鉴权行为，不属于 Bug
2. **数据一致性**：抽屉中的资产 4 格与「菜单模式 → 我的」页面共用相同后端接口（`/api/points/summary`、`/api/coupons/summary`、`/api/orders/unified/counts`、`/api/users/me/stats`），如发现两处数字不一致，请刷新页面后再次对比
3. **会员二维码功能并未删除**：仅是抽屉里的入口被移除，会员二维码功能本身仍可通过「我的」页面或其他入口访问
4. **复制 ID 功能彻底取消**：用户如需复制 ID，请进入「个人资料编辑」页后自行选中复制；这是设计上的精简，不会再恢复
5. **此次仅 H5 端优化**：未涉及小程序、安卓、iOS、桌面端等其他客户端，无需重新下载安装包

---

## 修复前后对比

| 编号 | 区域 | 修复前 | 修复后 |
|------|------|--------|--------|
| Bug 1 | ID 胶囊 | 后跟 📋 图标，整条点击触发"已复制"Toast | 无 📋 图标，整条点击跳 `/profile/edit` |
| Bug 2 | 顶栏图标 | 🔔 + ⊞ + ⚙ 共 3 个 | 🔔 + ⚙ 共 2 个，中间「⊞ 会员二维码」已删除 |
| Bug 3 | 资产 4 格 | 全部为 0（接口路径与字段错误） | 数字与「菜单模式 → 我的」一致，0 不显示角标，≥99 显示「99+」 |
| Bug 4 | 历史对话 | 加载失败 / 空白 / `.catch` 拦截过宽 | 列表正常加载，分组完整，仅在真正网络错误时显示「加载失败，点击重试」 |

---

## 自测验证清单

| # | 验证项 | 预期 |
|---|--------|------|
| 1 | 顶部仅剩 🔔 + ⚙ 两个圆形图标 | ✅ |
| 2 | 「⊞ 会员二维码」已消失 | ✅ |
| 3 | ID 胶囊无 📋 图标 | ✅ |
| 4 | 点击 ID 胶囊跳转到个人资料编辑页 | ✅ |
| 5 | 点击 ID 胶囊不再弹出「ID 已复制」Toast | ✅ |
| 6 | 资产 4 格数字与「我的」页面一致 | ✅ |
| 7 | 订单角标 = 待付款 + 待收货 + 待使用 三者之和 | ✅ |
| 8 | 数量为 0 时角标不显示 | ✅ |
| 9 | 数量 ≥ 99 时角标显示「99+」 | ✅ |
| 10 | 历史对话能正常加载，不再"加载失败" | ✅ |
| 11 | 历史对话置顶组在最上方 | ✅ |
| 12 | 历史对话 6 色咨询人圆点稳定不变色 | ✅ |
| 13 | 每条历史对话有摘要预览（≤30 字） | ✅ |
| 14 | 历史对话相对时间显示正确 | ✅ |
| 15 | 网络错误时显示「加载失败，点击重试」而非空白 | ✅ |
| 16 | ⋯ 按钮、左滑、管理态交互三态全部正常 | ✅ |

---

## 访问链接

以下是当前项目的体验链接，点击即可打开：

> ⚠️ 所有链接均使用宿主机 Nginx 代理端口（80/443），请勿使用 Docker 容器内部端口。

| 服务 | 链接 | 说明 |
|------|------|------|
| H5 首页 | [https://newbb.test.bangbangvip.com/autodev/6b099ed3-7175-4a78-91f4-44570c84ed27/](https://newbb.test.bangbangvip.com/autodev/6b099ed3-7175-4a78-91f4-44570c84ed27/) | 项目主页面入口 |
| AI 对话首页（本次修复主页面） | [https://newbb.test.bangbangvip.com/autodev/6b099ed3-7175-4a78-91f4-44570c84ed27/ai-home](https://newbb.test.bangbangvip.com/autodev/6b099ed3-7175-4a78-91f4-44570c84ed27/ai-home) | 进入 AI 对话页，点击右上角 ☰ 即可拉出修复后的抽屉 |
| 个人资料编辑（点击 ID 胶囊跳转目标） | [https://newbb.test.bangbangvip.com/autodev/6b099ed3-7175-4a78-91f4-44570c84ed27/profile/edit](https://newbb.test.bangbangvip.com/autodev/6b099ed3-7175-4a78-91f4-44570c84ed27/profile/edit) | 修改昵称、头像等个人信息 |
| 我的优惠券 | [https://newbb.test.bangbangvip.com/autodev/6b099ed3-7175-4a78-91f4-44570c84ed27/my-coupons](https://newbb.test.bangbangvip.com/autodev/6b099ed3-7175-4a78-91f4-44570c84ed27/my-coupons) | 抽屉资产 4 格的「优惠券」目标页 |
| 统一订单 | [https://newbb.test.bangbangvip.com/autodev/6b099ed3-7175-4a78-91f4-44570c84ed27/unified-orders](https://newbb.test.bangbangvip.com/autodev/6b099ed3-7175-4a78-91f4-44570c84ed27/unified-orders) | 抽屉资产 4 格的「订单」目标页 |
| 我的收藏 | [https://newbb.test.bangbangvip.com/autodev/6b099ed3-7175-4a78-91f4-44570c84ed27/my-favorites](https://newbb.test.bangbangvip.com/autodev/6b099ed3-7175-4a78-91f4-44570c84ed27/my-favorites) | 抽屉资产 4 格的「收藏」目标页 |
| 积分中心 | [https://newbb.test.bangbangvip.com/autodev/6b099ed3-7175-4a78-91f4-44570c84ed27/points-center](https://newbb.test.bangbangvip.com/autodev/6b099ed3-7175-4a78-91f4-44570c84ed27/points-center) | 抽屉资产 4 格的「积分」目标页 |
