# 健康档案页面优化 - 家庭成员Tab统一与标题修复

> 版本：v1（2026-06-03）
> 适用端：H5（影响所有使用「成员 Tab」的页面）

## 访问链接

以下是当前项目的体验链接，点击即可打开：

> ⚠️ 所有链接均使用域名 80/443 端口（无端口号），由 Nginx 反向代理到容器内部端口。

| 服务 | 链接 | 说明 |
|------|------|------|
| H5 主入口 | [https://newbb.test.bangbangvip.com/autodev/6b099ed3-7175-4a78-91f4-44570c84ed27/](https://newbb.test.bangbangvip.com/autodev/6b099ed3-7175-4a78-91f4-44570c84ed27/) | 项目 H5 主页面入口 |
| 健康档案 - 家庭成员列表 | [https://newbb.test.bangbangvip.com/autodev/6b099ed3-7175-4a78-91f4-44570c84ed27/health-profile/archive-list](https://newbb.test.bangbangvip.com/autodev/6b099ed3-7175-4a78-91f4-44570c84ed27/health-profile/archive-list) | 本次修复点 1：顶部标题 + 返回箭头 |
| 新增用药计划 | [https://newbb.test.bangbangvip.com/autodev/6b099ed3-7175-4a78-91f4-44570c84ed27/ai-home/medication-plans/new](https://newbb.test.bangbangvip.com/autodev/6b099ed3-7175-4a78-91f4-44570c84ed27/ai-home/medication-plans/new) | 本次修复点 2：标题居中 + 主题蓝 |
| 居家安全（成员 Tab） | [https://newbb.test.bangbangvip.com/autodev/6b099ed3-7175-4a78-91f4-44570c84ed27/home-safety](https://newbb.test.bangbangvip.com/autodev/6b099ed3-7175-4a78-91f4-44570c84ed27/home-safety) | 本次修复点 3：成员显示完整 |
| AI 主页 | [https://newbb.test.bangbangvip.com/autodev/6b099ed3-7175-4a78-91f4-44570c84ed27/ai-home](https://newbb.test.bangbangvip.com/autodev/6b099ed3-7175-4a78-91f4-44570c84ed27/ai-home) | 顶部成员 Tab 同样受益 |

## 功能简介

本次健康档案页面优化包含 3 个修复点，统一前后端「家庭成员」相关入口的视觉与数据口径：

1. **修复点 1 — 家庭成员列表页标题与返回箭头**：进入「健康档案 → 家庭成员列表」页后，顶部固定显示「家庭成员」标题，左侧带返回箭头「<」，与其它二级页样式一致。
2. **修复点 2 — 新增用药计划标题样式**：「新增用药计划」页标题改为居中对齐 + 主题蓝色（#1677FF），与 App 其它二级页面标题统一。
3. **修复点 3 — 顶部 Tab 成员显示不全（核心 Bug 修复）**：修复入口卡显示「已管理 5 人」但顶部 Tab 只能切换 3 个成员的口径不一致 BUG，让所有「未删除」的成员（含已退出 / 邀请中等中间态）都显示在 Tab 中，并对已解绑成员加上灰色「已解绑」标记。

## 使用说明

### 修复点 1：家庭成员列表页

1. 在 H5 中打开「健康档案」页面
2. 点击进入「家庭成员」二级页
3. **现在**：顶部固定显示天蓝色导航栏 + 居中标题「家庭成员」+ 左侧返回箭头「<」
4. 点击返回箭头可回到上一页

### 修复点 2：新增用药计划

1. 在「AI 主页 → 用药计划」中点击「新增用药计划」按钮
2. **现在**：进入新增页面后，顶部标题「新增用药计划」居中显示，文字颜色为主题蓝（#1677FF），左侧返回箭头「‹」也是主题蓝
3. 标题不再顶满整行，与其它 App 标准页面标题样式一致

### 修复点 3：成员 Tab 显示完整 + 已解绑灰色标记

1. 进入任何使用「家庭成员 Tab」的页面（如「健康档案」、「居家安全」、「用药计划」、「血压详情」等）
2. **现在**：顶部 Tab 会显示与入口卡「已管理 N 人」完全一致的成员列表，不再被过滤
3. 已解绑/已退出的成员会以**灰色字徽 + 「已解绑」小字** 显示，与正常成员加以区分
4. 点击灰色「已解绑」成员仍可查看其历史档案数据，但功能受限（如无法发送 AI 关怀）

## Bug 修复说明（问题 3 根因与修复）

### 根因
同一份家庭成员数据，在两个接口中使用了不一致的过滤口径：

| 位置 | 用的接口 | 过滤规则 |
|---|---|---|
| 入口卡人数（"已管理 5"） | `count_managed_family_members` | `status != 'deleted'`（除软删除外都算） |
| 顶部切换 Tab | `/api/family/members`（老接口） | `status == 'active'`（只取严格 active） |

中间态成员（如 `cancelled_by_target` 已退出 / `pending` 邀请中等）被入口卡算入但被 Tab 过滤掉，从而出现「显示 5 人，Tab 只切 3 人」的 BUG。

### 修复
将 `/api/family/members` 的过滤口径统一为「排除已软删除」（`status NOT IN ('deleted','removed')`），与官方权威状态机接口 `/api/family/member/state/list`、入口卡 `count_managed_family_members` 完全对齐。

修复后：
- ✅ Tab 与入口卡数量完全一致
- ✅ 已删除（含 DELETE 接口写入的 'removed'）成员仍正确从 Tab 中排除
- ✅ 中间态成员（已退出、邀请中、待处理）以「灰色 + 已解绑」标记显示，体验更清晰

## 注意事项

- 本次仅涉及 H5 + 后端代码改动，**不涉及微信小程序、安卓、iOS 端**，无需重新下载安装包，浏览器直接访问 H5 即可看到效果
- 如果您之前看到的 Tab 仍是 3 个旧成员，建议刷新页面或清空浏览器缓存后再次进入即可看到完整 5 个成员
- 已解绑成员上的「已解绑」灰标只是状态提示，并不会自动清除该成员的档案数据；如需彻底删除该成员，请进入「健康档案 → 家庭成员列表」执行「移除」操作

## 测试覆盖

后端新增专项回归测试 `backend/tests/test_family_member_tab_unify_v1_20260602.py`，3 个用例全部通过：
- `test_list_members_includes_cancelled_by_target`：已退出成员仍显示在 Tab
- `test_list_members_includes_pending_state`：邀请中成员仍显示在 Tab
- `test_list_members_excludes_removed`：已软删除（removed）成员从 Tab 中排除

并跑通 `test_family.py`（12 个）+ `test_family_member_state_machine_v1_20260529.py` 的现有用例，无回归。

## 访问链接

以下是当前项目的体验链接，点击即可打开：

> ⚠️ 所有链接均使用域名 80/443 端口（无端口号），由 Nginx 反向代理到容器内部端口。

| 服务 | 链接 | 说明 |
|------|------|------|
| H5 主入口 | [https://newbb.test.bangbangvip.com/autodev/6b099ed3-7175-4a78-91f4-44570c84ed27/](https://newbb.test.bangbangvip.com/autodev/6b099ed3-7175-4a78-91f4-44570c84ed27/) | 项目 H5 主页面入口 |
| 健康档案 - 家庭成员列表 | [https://newbb.test.bangbangvip.com/autodev/6b099ed3-7175-4a78-91f4-44570c84ed27/health-profile/archive-list](https://newbb.test.bangbangvip.com/autodev/6b099ed3-7175-4a78-91f4-44570c84ed27/health-profile/archive-list) | 本次修复点 1：顶部标题 + 返回箭头 |
| 新增用药计划 | [https://newbb.test.bangbangvip.com/autodev/6b099ed3-7175-4a78-91f4-44570c84ed27/ai-home/medication-plans/new](https://newbb.test.bangbangvip.com/autodev/6b099ed3-7175-4a78-91f4-44570c84ed27/ai-home/medication-plans/new) | 本次修复点 2：标题居中 + 主题蓝 |
| 居家安全（成员 Tab） | [https://newbb.test.bangbangvip.com/autodev/6b099ed3-7175-4a78-91f4-44570c84ed27/home-safety](https://newbb.test.bangbangvip.com/autodev/6b099ed3-7175-4a78-91f4-44570c84ed27/home-safety) | 本次修复点 3：成员显示完整 |
| AI 主页 | [https://newbb.test.bangbangvip.com/autodev/6b099ed3-7175-4a78-91f4-44570c84ed27/ai-home](https://newbb.test.bangbangvip.com/autodev/6b099ed3-7175-4a78-91f4-44570c84ed27/ai-home) | 顶部成员 Tab 同样受益 |
