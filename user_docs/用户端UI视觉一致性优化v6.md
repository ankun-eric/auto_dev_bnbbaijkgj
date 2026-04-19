# 用户端 UI 视觉一致性优化 · v6 使用手册

> 版本：v6（最终闭环版）
> 发布日期：2026-04-20
> 适用平台：H5、微信小程序、Flutter App（用户端）

---

## 1. 功能介绍

本次更新对宾尼小康用户端进行了一次系统性的视觉与体验优化，目标是**让所有页面看起来像"同一个产品"**，并且**让中老年用户在任何页面都能轻松调大字号**。

主要变化：

1. **统一的绿色顶栏**：除首页外，所有子页面（包括健康计划、订单、优惠券、设置、邀请好友等 22+ 个页面）的顶部导航栏统一改为主品牌绿（`#52c41a`），白色加粗居中标题，移除多余 LOGO。
2. **三档字号系统升级**：从两档"关怀模式"升级为「**标准 / 大字号 👨‍🦳 / 超大字号 👴**」三档，全局基准字号从 14px 提升到 16px。
3. **「我的」页字号快捷入口**：在「我的」页头像下方新增一条浅绿色横条 ——「**字号偏小？点这里调大 →**」，一键弹出字号设置面板。
4. **健康计划三个子页布局重做**：用药提醒、健康打卡、自定义计划，删除冗余 banner，关键信息直接呈现。
5. **打卡统计页升级**：月视图从柱状图升级为"平滑曲线 + 渐变填充 + 最高/最低点标注"，更直观。
6. **首页搜索栏视觉升级**：浅绿底色 `#E8F7EE` + 主绿放大镜 + 新文案「**想找什么服务/商品？**」。
7. **AI 头像统一化**：所有 AI 头像统一为"绿青渐变圆 + 白色 AI"。
8. **订单/优惠券 Tab 选中态**：绿色加粗文字 + 绿色 2px 下划线，更清晰可辨。
9. **后端 Bug 修复**：「打卡统计 → 各计划完成率」之前空数据 Bug 已修复，现在能正确聚合用药提醒、健康打卡、自定义计划三类数据。

---

## 2. 操作步骤（用户视角）

### 2.1 一键调大字号

> 适合所有觉得"字太小看不清"的用户，特别推荐给爸妈用。

1. 打开 H5 用户端首页：[https://newbb.test.bangbangvip.com/autodev/6b099ed3-7175-4a78-91f4-44570c84ed27/](https://newbb.test.bangbangvip.com/autodev/6b099ed3-7175-4a78-91f4-44570c84ed27/)
2. 点击底部导航栏「**我的**」进入个人中心：[https://newbb.test.bangbangvip.com/autodev/6b099ed3-7175-4a78-91f4-44570c84ed27/profile](https://newbb.test.bangbangvip.com/autodev/6b099ed3-7175-4a78-91f4-44570c84ed27/profile)
3. 在头像区下方，找到浅绿色的 **「字号偏小？点这里调大 →」** 横条，点击。
4. 弹出"字体大小设置"，可选三档：
    - **标准**（16px）—— 默认值，年轻人适用
    - **大字号 👨‍🦳**（19px）—— 老花眼推荐
    - **超大字号 👴**（22px）—— 视力较差或长辈推荐
5. 点击想要的档位，**全 App 字号立即生效**，并保存到本地，下次打开自动应用。

> 也可以从「我的 → 设置 → 字体大小」进入相同的设置面板。

### 2.2 查看健康计划与打卡统计

1. 我的 → 健康计划：[https://newbb.test.bangbangvip.com/autodev/6b099ed3-7175-4a78-91f4-44570c84ed27/health-plan](https://newbb.test.bangbangvip.com/autodev/6b099ed3-7175-4a78-91f4-44570c84ed27/health-plan)
2. 三个子模块新版布局：
    - **用药提醒**：[https://newbb.test.bangbangvip.com/autodev/6b099ed3-7175-4a78-91f4-44570c84ed27/health-plan/medications](https://newbb.test.bangbangvip.com/autodev/6b099ed3-7175-4a78-91f4-44570c84ed27/health-plan/medications) —— 直接显示所有用药提醒列表
    - **健康打卡**：[https://newbb.test.bangbangvip.com/autodev/6b099ed3-7175-4a78-91f4-44570c84ed27/health-plan/checkin](https://newbb.test.bangbangvip.com/autodev/6b099ed3-7175-4a78-91f4-44570c84ed27/health-plan/checkin) —— 顶部直接展示「打卡积分进度卡片」
    - **自定义计划**：[https://newbb.test.bangbangvip.com/autodev/6b099ed3-7175-4a78-91f4-44570c84ed27/health-plan/custom](https://newbb.test.bangbangvip.com/autodev/6b099ed3-7175-4a78-91f4-44570c84ed27/health-plan/custom) —— 直接进入分类选择
3. 打卡统计：[https://newbb.test.bangbangvip.com/autodev/6b099ed3-7175-4a78-91f4-44570c84ed27/health-plan/statistics](https://newbb.test.bangbangvip.com/autodev/6b099ed3-7175-4a78-91f4-44570c84ed27/health-plan/statistics)
    - **周视图**：保留柱状图（适合短期回顾）
    - **月视图**：平滑曲线 + 浅绿渐变填充，自动标注最高（▲ 绿色）和最低（▼ 橙色）打卡日
    - **各计划完成率**：现在能正确显示「用药提醒、健康打卡、自定义计划」的完成率排行

### 2.3 体验全新的统一顶栏

进入以下任意页面，可直观感受全新的绿色顶栏：

| 页面 | 链接 |
|---|---|
| 我的订单 | [/unified-orders](https://newbb.test.bangbangvip.com/autodev/6b099ed3-7175-4a78-91f4-44570c84ed27/unified-orders) |
| 我的优惠券 | [/my-coupons](https://newbb.test.bangbangvip.com/autodev/6b099ed3-7175-4a78-91f4-44570c84ed27/my-coupons) |
| 优惠券中心 | [/coupon-center](https://newbb.test.bangbangvip.com/autodev/6b099ed3-7175-4a78-91f4-44570c84ed27/coupon-center) |
| 邀请好友 | [/invite](https://newbb.test.bangbangvip.com/autodev/6b099ed3-7175-4a78-91f4-44570c84ed27/invite) |
| 积分中心 | [/points](https://newbb.test.bangbangvip.com/autodev/6b099ed3-7175-4a78-91f4-44570c84ed27/points) |
| 积分商城 | [/points/mall](https://newbb.test.bangbangvip.com/autodev/6b099ed3-7175-4a78-91f4-44570c84ed27/points/mall) |
| 我的收藏 | [/my-favorites](https://newbb.test.bangbangvip.com/autodev/6b099ed3-7175-4a78-91f4-44570c84ed27/my-favorites) |
| 收货地址 | [/my-addresses](https://newbb.test.bangbangvip.com/autodev/6b099ed3-7175-4a78-91f4-44570c84ed27/my-addresses) |
| 健康档案 | [/health-profile](https://newbb.test.bangbangvip.com/autodev/6b099ed3-7175-4a78-91f4-44570c84ed27/health-profile) |
| 体检报告 | [/checkup](https://newbb.test.bangbangvip.com/autodev/6b099ed3-7175-4a78-91f4-44570c84ed27/checkup) |
| 拍照识药 | [/drug](https://newbb.test.bangbangvip.com/autodev/6b099ed3-7175-4a78-91f4-44570c84ed27/drug) |
| 健康自查 | [/symptom](https://newbb.test.bangbangvip.com/autodev/6b099ed3-7175-4a78-91f4-44570c84ed27/symptom) |
| 中医养生 | [/tcm](https://newbb.test.bangbangvip.com/autodev/6b099ed3-7175-4a78-91f4-44570c84ed27/tcm) |
| 家人绑定 | [/family-bindlist](https://newbb.test.bangbangvip.com/autodev/6b099ed3-7175-4a78-91f4-44570c84ed27/family-bindlist) |
| 在线客服 | [/customer-service](https://newbb.test.bangbangvip.com/autodev/6b099ed3-7175-4a78-91f4-44570c84ed27/customer-service) |
| 系统通知 | [/notifications](https://newbb.test.bangbangvip.com/autodev/6b099ed3-7175-4a78-91f4-44570c84ed27/notifications) |
| 设置 | [/settings](https://newbb.test.bangbangvip.com/autodev/6b099ed3-7175-4a78-91f4-44570c84ed27/settings) |

### 2.4 体验全新搜索栏

打开首页，搜索栏现在是**淡绿色背景 + 主绿放大镜 + 「想找什么服务/商品？」**：

[https://newbb.test.bangbangvip.com/autodev/6b099ed3-7175-4a78-91f4-44570c84ed27/](https://newbb.test.bangbangvip.com/autodev/6b099ed3-7175-4a78-91f4-44570c84ed27/)

### 2.5 体验全新 AI 头像

进入 AI 健康咨询页：[https://newbb.test.bangbangvip.com/autodev/6b099ed3-7175-4a78-91f4-44570c84ed27/ai](https://newbb.test.bangbangvip.com/autodev/6b099ed3-7175-4a78-91f4-44570c84ed27/ai)

顶部 AI 头像现在是**绿青渐变的圆形 + 白色加粗 "AI" 字样**，简洁、醒目、统一。

---

## 3. 三端覆盖

| 改造项 | H5 (Next.js) | 微信小程序 | Flutter App |
|---|---|---|---|
| 统一绿色顶栏 | ✅ 22+ 子页面 | ✅ 全局 `app.json` 设置 | ✅ `appBarTheme` 全局生效 |
| 三档字号系统 | ✅ Tailwind + useFontSize + 设置弹窗 | ✅ 我的页"字号偏小"横条→设置入口 | ✅ FontProvider 三档 + FontSizeSheet |
| 我的页字号横条 | ✅ | ✅ | ✅ |
| 健康计划三子页重做 | ✅ | （现有布局） | （现有布局） |
| 打卡统计折线图（月） | ✅（SVG 平滑曲线） | （后续可同步） | （后续可同步） |
| 首页搜索栏新视觉 | ✅ | ✅ | （后续可同步） |
| AI 头像绿青渐变 | ✅ | ✅ | （已为绿色主题） |
| 订单/优惠券 Tab 选中态 | ✅ | （现有 tab 已绿色） | （现有 tab 已绿色） |

> 三端按 PRD 关键同步点全部覆盖；H5 端为本期重点改造（最大变更面）。

---

## 4. 注意事项

1. **字号设置只对当前设备/账号生效**：选择的字号档位会保存在本地（H5 是 localStorage、Flutter 是 SharedPreferences、小程序跳到 H5 设置共享配置），换设备会重新走默认值（默认是「标准 16px」）。
2. **健康计划"各计划完成率"为空？** 现在只要您有任意一个用药提醒/健康打卡/自定义计划，就会出现条目。如果仍为空，请确认已创建至少一个计划并开始打卡。
3. **小程序绿色顶栏是系统原生效果**，无法做渐变；如需"绿青渐变"效果，请使用 H5 或 Flutter 端。
4. **Flutter App 的 AppBar 主题**已设置为绿底白字加粗居中，所有用 `Scaffold(appBar: AppBar(...))` 的页面自动继承，无需逐页修改。
5. **退出登录或清缓存** 不会清空字号偏好（这是为了不打扰长辈用户）。如需重置，请在「我的 → 设置 → 字体大小」中重新选择"标准"。

---

## 5. 反馈与问题

如发现页面顶栏样式不统一、字号设置不生效、健康计划完成率仍异常等问题，请通过：

- H5 在线客服：[https://newbb.test.bangbangvip.com/autodev/6b099ed3-7175-4a78-91f4-44570c84ed27/customer-service](https://newbb.test.bangbangvip.com/autodev/6b099ed3-7175-4a78-91f4-44570c84ed27/customer-service)

提交反馈，并附上**页面链接**和**截图**。

---

> 本次更新已部署至测试环境，正式环境将在回归通过后同步上线。

!#@ 用户端UI视觉一致性优化v6.md @#!
