# 健康计划模块 Bug 修复 — 用户体验使用手册

## 访问链接

以下是当前项目的体验链接，点击即可打开：

> ⚠️ 所有链接均使用宿主机 Nginx 代理端口（80/443），请勿使用 Docker 容器内部端口。

| 服务 | 链接 | 说明 |
|------|------|------|
| H5 移动端 | [https://newbb.test.bangbangvip.com/autodev/3b7b999d-e51c-4c0d-8f6e-baf90cd26857/](https://newbb.test.bangbangvip.com/autodev/3b7b999d-e51c-4c0d-8f6e-baf90cd26857/) | H5 端主页面入口（经 Nginx 代理） |
| 管理后台 | [https://newbb.test.bangbangvip.com/autodev/3b7b999d-e51c-4c0d-8f6e-baf90cd26857/admin/](https://newbb.test.bangbangvip.com/autodev/3b7b999d-e51c-4c0d-8f6e-baf90cd26857/admin/) | 管理后台入口 |

---

## 功能简介

本次更新修复了 H5 移动端健康计划模块的 3 个 Bug，涉及以下功能改进：

1. **首页今日待办**：健康计划任务现在按所属计划名称进行分组显示，每个计划作为独立小标题
2. **健康打卡列表页**：编辑和删除按钮位置优化，移至状态标签同一行，操作更便捷
3. **自定义计划编辑页**：修复编辑页面空白问题，现可正常回填已有计划数据并编辑保存

---

## 使用说明

### Bug 1 修复：首页今日待办 — 健康计划按计划名称分组显示

**修复前**：今日待办中"健康计划"分组下只平铺显示所有任务名称，无法区分属于哪个计划。

**修复后**：自定义健康计划的任务按所属计划名称自动分组，每个计划名称作为小标题（带 📋 图标），一目了然。

**操作步骤**：
1. 打开 H5 端首页 [https://newbb.test.bangbangvip.com/autodev/3b7b999d-e51c-4c0d-8f6e-baf90cd26857/](https://newbb.test.bangbangvip.com/autodev/3b7b999d-e51c-4c0d-8f6e-baf90cd26857/)
2. 查看页面中部的「📋 今日待办」区域
3. 在用药提醒和健康打卡分组下方，可以看到每个自定义计划的名称作为独立标题
4. 每个计划标题下列出该计划的待办任务，可直接点击完成打卡

**效果示例**：
```
💊 用药提醒
   ☐ 阿莫西林 · 08:00

✅ 健康打卡
   ☐ 测血压 · 09:00

📋 我的减肥计划
   ☐ 每日跑步
   ☐ 控制饮食

📋 术后康复计划
   ☐ 按时做康复操
```

---

### Bug 2 修复：健康打卡列表页 — 编辑和删除按钮位置优化

**修复前**：编辑（✏️）和删除（🗑️）按钮在卡片右侧，与状态标签不在同一行。

**修复后**：编辑和删除按钮紧跟在"已完成/未完成"状态标签后面，位于同一行，打卡/已完成按钮保持在右侧。

**操作步骤**：
1. 进入健康打卡列表页 — 从首页点击「查看全部计划」，然后选择「健康打卡」
2. 或直接访问 [https://newbb.test.bangbangvip.com/autodev/3b7b999d-e51c-4c0d-8f6e-baf90cd26857/health-plan/checkin](https://newbb.test.bangbangvip.com/autodev/3b7b999d-e51c-4c0d-8f6e-baf90cd26857/health-plan/checkin)
3. 每条打卡记录中，第二行的状态标签（✅已完成 / ⬜未完成）后面紧跟编辑和删除图标
4. 点击 ✏️ 可编辑该打卡项，点击 🗑️ 可删除
5. 右侧的「打卡」或「已完成」按钮保持不变

---

### Bug 3 修复：自定义计划编辑功能恢复正常

**修复前**：点击自定义计划的编辑按钮后，页面完全空白，无法编辑。

**修复后**：编辑页面正常显示表单，所有字段（计划名称、描述、任务列表）回填已有数据，可修改后保存。

**操作步骤**：
1. 进入自定义计划列表页
2. 或直接访问 [https://newbb.test.bangbangvip.com/autodev/3b7b999d-e51c-4c0d-8f6e-baf90cd26857/health-plan/custom](https://newbb.test.bangbangvip.com/autodev/3b7b999d-e51c-4c0d-8f6e-baf90cd26857/health-plan/custom)
3. 找到需要编辑的计划，点击计划卡片上的 ✏️ 编辑图标（或左滑出现"编辑"按钮）
4. 页面跳转到「编辑计划」页面：
   - 页面标题显示"编辑计划"
   - 计划名称、描述、周期设置等已自动回填
   - 每日任务列表已回填该计划的所有任务
5. 修改所需内容后，点击底部「保存修改」按钮
6. 保存成功后自动返回计划列表页

---

## 注意事项

1. 本次更新仅涉及 H5 移动端网页，管理后台和其他客户端无变化
2. 如果页面显示异常，请尝试清除浏览器缓存后刷新页面
3. 编辑自定义计划时，目前仅支持修改计划基本信息（名称、描述、周期），任务列表的编辑为只读展示
4. 首页今日待办中，只有用户已创建并处于"进行中"状态的自定义计划才会在今日待办中显示

---

## 访问链接

以下是当前项目的体验链接，点击即可打开：

> ⚠️ 所有链接均使用宿主机 Nginx 代理端口（80/443），请勿使用 Docker 容器内部端口。

| 服务 | 链接 | 说明 |
|------|------|------|
| H5 移动端 | [https://newbb.test.bangbangvip.com/autodev/3b7b999d-e51c-4c0d-8f6e-baf90cd26857/](https://newbb.test.bangbangvip.com/autodev/3b7b999d-e51c-4c0d-8f6e-baf90cd26857/) | H5 端主页面入口（经 Nginx 代理） |
| 管理后台 | [https://newbb.test.bangbangvip.com/autodev/3b7b999d-e51c-4c0d-8f6e-baf90cd26857/admin/](https://newbb.test.bangbangvip.com/autodev/3b7b999d-e51c-4c0d-8f6e-baf90cd26857/admin/) | 管理后台入口 |
