# 档案管理 · 用药提醒模块三 Bug 修复 — 用户体验使用手册

> 修复编号：BUG-HEALTH-PROFILE-MED-20260525  
> 关联模块：档案管理 → 用药提醒；档案首页「用药计划」卡片  
> 发布日期：2026-05-25  
> 涉及端：H5 用户端

## 访问链接

以下是当前项目的体验链接，点击即可打开：

> ⚠️ 所有链接均使用宿主机 Nginx 代理端口（80/443），请勿使用 Docker 容器内部端口。

| 服务 | 链接 | 说明 |
|------|------|------|
| H5 项目主页 | [https://newbb.test.bangbangvip.com/autodev/6b099ed3-7175-4a78-91f4-44570c84ed27/](https://newbb.test.bangbangvip.com/autodev/6b099ed3-7175-4a78-91f4-44570c84ed27/) | H5 首页入口 |
| 档案管理首页 | [https://newbb.test.bangbangvip.com/autodev/6b099ed3-7175-4a78-91f4-44570c84ed27/health-profile](https://newbb.test.bangbangvip.com/autodev/6b099ed3-7175-4a78-91f4-44570c84ed27/health-profile) | 档案管理首页（用药计划 / 健康数据 / 家庭档案等） |
| 用药提醒-全部列表页 | [https://newbb.test.bangbangvip.com/autodev/6b099ed3-7175-4a78-91f4-44570c84ed27/ai-home/medication-plans](https://newbb.test.bangbangvip.com/autodev/6b099ed3-7175-4a78-91f4-44570c84ed27/ai-home/medication-plans) | 用药提醒「全部」三 Tab 列表（服药中 / 未开始 / 已结束） |
| 用药提醒-打卡详情页 | [https://newbb.test.bangbangvip.com/autodev/6b099ed3-7175-4a78-91f4-44570c84ed27/ai-home/medication-reminder](https://newbb.test.bangbangvip.com/autodev/6b099ed3-7175-4a78-91f4-44570c84ed27/ai-home/medication-reminder) | 今日用药打卡详情页 |

---

## 修复内容简介

本次针对档案管理「用药提醒」模块的 3 个真实用户反馈 Bug 进行修复：

- **Bug 1（功能问题）**：「用药提醒-全部」页打开时，三个 Tab（服药中 / 未开始 / 已结束）顶部的数字徽标全部显示 `0`，并且切到「已结束」时会弹出「加载失败」提示、列表空白。
- **Bug 2（视觉问题）**：「用药提醒-全部」页的顶部返回栏与「就医资料」等档案二级页样式不一致，看起来不像同一模板。
- **Bug 3（数据一致性问题）**：档案管理首页「今日健康数据 - 用药计划」卡片显示「还剩 5 次」，但点进详情页显示的却是「还有 7 次」，两边数字对不上。

---

## 本次客户端变更

本次更新涉及 **H5 用户端** 的代码改动：

| 终端 | 变更说明 | 新版本 |
|------|----------|--------|
| H5 用户端 | 用药提醒列表页顶部 NavBar 统一为 GreenNavBar、三 Tab 计数容错、详情页跳转携带 consultant_id、后端三 Tab 接口序列化容错 | [https://newbb.test.bangbangvip.com/autodev/6b099ed3-7175-4a78-91f4-44570c84ed27/](https://newbb.test.bangbangvip.com/autodev/6b099ed3-7175-4a78-91f4-44570c84ed27/) （在线版即最新版，无需安装） |

> ⚠️ 本次未涉及小程序 / 安卓 / iOS / Windows / macOS / CLI 等其他终端代码改动，对应端无需重新安装。

---

## 使用说明

### 一、Bug 1：三 Tab 数字徽标显示正确 + 「已结束」可正常加载

#### 场景

1. 打开 **档案管理首页** ：[https://newbb.test.bangbangvip.com/autodev/6b099ed3-7175-4a78-91f4-44570c84ed27/health-profile](https://newbb.test.bangbangvip.com/autodev/6b099ed3-7175-4a78-91f4-44570c84ed27/health-profile)
2. 在「今日健康数据 - 用药计划」卡片右上角，点击「全部 ›」进入用药提醒列表页。
3. 列表页顶部三个 Tab：**服药中 / 未开始 / 已结束**。

#### 修复后的行为

- 进入页面后，三个 Tab 的数字徽标会**分别**显示该 Tab 下属于当前家庭成员的真实条数，例如「服药中 3」「未开始 1」「已结束 8」。即使其中某一个 Tab 接口偶发失败，其他 Tab 的数字仍能正常显示（不会全部变 0）。
- 点击「已结束」Tab，可正常加载历史用药记录，不再弹出「加载失败」Toast。
- 如果接口确实因为历史脏数据返回 500，列表会显示更友好的提示：「该列数据异常，请联系客服」；普通网络错误则提示「加载失败，请稍后重试」。
- 后端会自动跳过单条字段异常的历史脏数据（不会因一条坏数据拖垮整个接口），并在后端日志中记录被跳过的 `reminder_id`，方便运营复盘。

### 二、Bug 2：顶部返回栏视觉与「就医资料」页一致

#### 场景

1. 同上进入「用药提醒-全部」列表页。
2. 观察顶部返回栏：标题、返回箭头、底色、高度。
3. 再返回档案首页，点击「就医资料」，对比两个页面的顶部返回栏。

#### 修复后的视觉

- 用药提醒-全部页顶部返回栏现在使用统一的 **GreenNavBar** 组件，与「就医资料」「体检报告」等档案二级页**像素级一致**：
  - 标题文字字号 17px / 字重 600 / 白色 / 居中
  - 底色为天蓝品牌色 `#0EA5E9`（纯色，不再是渐变）
  - 顶栏高度 46px
- 顶栏 `sticky` 固定：向下滚动列表时，顶栏始终吸附在顶部不动，方便随时返回。
- 三 Tab 区紧贴 NavBar 下方，下划线指示器使用品牌主色，与「就医资料」页 Tab 区一致。
- 标题文案已改为「**用药提醒**」（与档案首页入口名一致）。

### 三、Bug 3：首页和详情页「还剩 N 次」数字一致

#### 场景

1. 打开 **档案管理首页**，先在顶部成员选择器中切到任一家庭成员（例如「妈妈」）。
2. 查看「今日健康数据 - 用药计划」卡片上的「还剩 N 次」。
3. 点击该卡片进入「用药提醒-打卡详情页」，对比顶部 Banner 上的「还有 N 次用药」。

#### 修复后的行为

- **两个数字始终相等**。例如妈妈今日有 5 次未服 → 首页显示「还剩 5 次」，进入详情页 Banner 也显示「还有 5 次用药」。
- 切换不同家庭成员后再次进入，详情页只显示**该成员**的用药数据，与首页该成员卡片上的数字保持一致。
- 完成一次打卡后回到首页，两边数字会同步 -1。

---

## 注意事项

1. **本人 / 家庭成员切换**：所有「剩余次数」均按**当前选中的家庭成员**统计。请确认顶部成员选择器选中的是你想看的人。
2. **三 Tab 数字含义**：
   - 服药中：今天处于用药周期内、未结束的计划
   - 未开始：start_date 在未来的计划
   - 已结束：状态为 archived、或 end_date 已过且非长期的计划
3. **「该列数据异常」Toast**：如果你看到这条提示，是后端检测到该 Tab 下存在历史脏数据并已自动跳过。属于罕见情况，请联系客服反馈具体出现场景，后端会有日志辅助定位。
4. **iOS Safari / 微信 H5 / Android Chrome** 三大平台已统一回归通过。

---

## 修复后效果速览

| 模块 | 修复前 | 修复后 |
|------|-------|-------|
| 用药提醒-全部页 三 Tab 数字 | 全 0 | 显示真实条数（与 Tab 内列表数一致） |
| 用药提醒-全部页 「已结束」Tab | 加载失败 Toast、空白 | 正常加载历史用药 |
| 用药提醒-全部页 顶部返回栏 | 自定义渐变、字号 16、与就医资料不同 | GreenNavBar 统一组件、字号 17、天蓝纯色、sticky 固定 |
| 档案首页 vs 详情页 「剩余次数」 | 5 vs 7（不一致） | N vs N（始终一致） |

---

## 访问链接

以下是当前项目的体验链接，点击即可打开：

> ⚠️ 所有链接均使用宿主机 Nginx 代理端口（80/443），请勿使用 Docker 容器内部端口。

| 服务 | 链接 | 说明 |
|------|------|------|
| H5 项目主页 | [https://newbb.test.bangbangvip.com/autodev/6b099ed3-7175-4a78-91f4-44570c84ed27/](https://newbb.test.bangbangvip.com/autodev/6b099ed3-7175-4a78-91f4-44570c84ed27/) | H5 首页入口 |
| 档案管理首页 | [https://newbb.test.bangbangvip.com/autodev/6b099ed3-7175-4a78-91f4-44570c84ed27/health-profile](https://newbb.test.bangbangvip.com/autodev/6b099ed3-7175-4a78-91f4-44570c84ed27/health-profile) | 档案管理首页（用药计划 / 健康数据 / 家庭档案等） |
| 用药提醒-全部列表页 | [https://newbb.test.bangbangvip.com/autodev/6b099ed3-7175-4a78-91f4-44570c84ed27/ai-home/medication-plans](https://newbb.test.bangbangvip.com/autodev/6b099ed3-7175-4a78-91f4-44570c84ed27/ai-home/medication-plans) | 用药提醒「全部」三 Tab 列表（服药中 / 未开始 / 已结束） |
| 用药提醒-打卡详情页 | [https://newbb.test.bangbangvip.com/autodev/6b099ed3-7175-4a78-91f4-44570c84ed27/ai-home/medication-reminder](https://newbb.test.bangbangvip.com/autodev/6b099ed3-7175-4a78-91f4-44570c84ed27/ai-home/medication-reminder) | 今日用药打卡详情页 |
