# AI 回答档案折叠卡片「永久加载中」Bug 修复 — 用户体验使用手册

> 版本：Bug-432-fix（基于 PRD-432）
> 上线时间：2026-05-09
> 涉及端：H5（Next.js）+ 微信小程序 + Flutter App（Android/iOS）
> 关联 PRD：`cursor_prompt_434_20260509183713.txt`（PRD-432「咨询对象档案折叠卡片」一直显示「加载档案中...」Bug 修复方案文档）
> 关联前置：PRD-432（AI 回答顶部「咨询对象档案」折叠卡片功能上线）

---

## 一、访问链接（已部署可体验）

> ⚠️ 所有链接均通过宿主机 Nginx（443）反向代理，请勿使用容器内部端口。所有 URL 必须以 `https://newbb.test.bangbangvip.com/autodev/6b099ed3-7175-4a78-91f4-44570c84ed27` 为基础前缀。

| 端 | 链接 / 入口 | 说明 |
|----|------------|------|
| H5 主页 | https://newbb.test.bangbangvip.com/autodev/6b099ed3-7175-4a78-91f4-44570c84ed27/ | H5 Next.js 项目入口 |
| AI 对话首页（ai-home）| https://newbb.test.bangbangvip.com/autodev/6b099ed3-7175-4a78-91f4-44570c84ed27/ai-home | 主验证页：AI 回答上方的档案卡片，应在 1 秒内展示档案摘要，**不再永久卡在「加载档案中...」** |
| AI 会话详情（chat-history）| https://newbb.test.bangbangvip.com/autodev/6b099ed3-7175-4a78-91f4-44570c84ed27/chat-history | 进入任意历史会话同样可见折叠卡片 |
| 健康档案完善入口 | https://newbb.test.bangbangvip.com/autodev/6b099ed3-7175-4a78-91f4-44570c84ed27/health-archive | 卡片提示「档案未完善」时跳转此处 |
| 长期用药管理入口 | https://newbb.test.bangbangvip.com/autodev/6b099ed3-7175-4a78-91f4-44570c84ed27/medication-plan | 用药 Drawer 中「去管理用药」跳转此处 |
| 后端档案卡接口 | `GET /api/v1/consultant/{id}/profile_card` | 返回 7 项档案 + 完善度 + 摘要 + 30 天更新标识（已确认接口本身正常） |
| 后端长期用药接口 | `GET /api/v1/consultant/{id}/medications` | 返回 Drawer 中需要展示的长期用药列表（已确认接口本身正常） |
| 小程序 zip 包 | https://newbb.test.bangbangvip.com/autodev/6b099ed3-7175-4a78-91f4-44570c84ed27/miniprogram/miniprogram_bug432fix_20260509_184817_1311.zip | 微信开发者工具导入即可预览 |
| Android APK 下载 | https://newbb.test.bangbangvip.com/autodev/6b099ed3-7175-4a78-91f4-44570c84ed27/apk/app_bug432fix_20260509_190050_09b9.apk | 84.7 MB；GH Release `android-bug432fix-v20260509-185202-e493` |
| iOS IPA 下载 | https://github.com/ankun-eric/auto_dev_bnbbaijkgj/releases/download/ios-bug432fix-v20260509-185203-12e5/bini_health_ios.ipa | 34.1 MB；GH Release `ios-bug432fix-v20260509-185203-12e5` |

---

## 二、Bug 现象回顾（修复前）

打开任意端的 AI 对话页（H5 ai-home / chat-history、小程序 chat 页、Flutter chat_screen），向 AI 发送任意问题。AI 回答消息正常出现，**但回答正上方的「咨询对象档案折叠卡片」永远卡在 loading 占位态**：

```
[👤] 加载档案中...
```

无论等待多久（30 秒、1 分钟、5 分钟），卡片都不会进入「已加载」分支，更无法点击展开 7 项档案，长期用药抽屉自然也无法触达。**100% 复现，所有端均存在该问题**。

---

## 三、本次修复内容（4 端一致）

### 3.1 H5（Next.js · React + Axios）

| 修复点 | 说明 |
|--------|------|
| 去掉二次脱壳 | `api.ts` 的响应拦截器已通过 `(response) => response.data` 自动脱壳；`ProfileCard.tsx` / `MedicationDrawer.tsx` 中**不再写 `res.data`**，直接把 `res` 作为业务数据使用 |
| Loading 兜底 | 拿到数据立即 `setLoading(false)`，无论数据是否为空；payload 不合法（缺 `fields` / `items` 字段）则进入失败分支 |
| 1 次自动重试 | 档案卡接口首次失败后，**3 秒后自动重试 1 次**；二次仍失败则隐藏卡片，不阻塞 AI 回答 |
| 长期用药点击重试 | 用药抽屉接口失败时显示灰字「**加载失败，点击重试**」，整行可点击重新请求；新增 `data-testid="ai-medication-drawer-retry"` 便于自动化测试 |

### 3.2 微信小程序（原生 + `wx.request`）

| 修复点 | 说明 |
|--------|------|
| 去掉二次脱壳 | `profile-card` / `medication-drawer` 自定义组件中，对 200 响应直接读 `res.data`（小程序原生只脱一层），**不再二次取 `.data.data`** |
| 数据校验 | 200 响应必须含 `res.data.fields`（档案）/ `res.data.items` 数组（用药），否则进失败分支 |
| 1 次自动重试 | `_fetch` + `_handleFetchFail` 内置 3 秒延迟自动重试；保证 `loading: false` 一定执行 |
| 用户手动重试 | `medication-drawer` 模板新增 `med-state-retry` 类 + `bindtap="onRetry"`，整行可点击重新加载 |

### 3.3 Flutter App（Android / iOS · Dio）

| 修复点 | 说明 |
|--------|------|
| 数据校验 | `ai_profile_card.dart` 在 `_fetch` 中校验 `m['fields'] is Map`，防止异常 payload 卡 loading |
| 1 次自动重试 | 档案卡首次失败 → 3 秒后自动重试 1 次；二次仍失败则隐藏卡片 |
| 长期用药点击重试 | `MedicationBottomSheet._buildBody` 失败态显示「**加载失败，点击重试**」，点击触发 `_fetch()` 再次请求 |

### 3.4 后端（FastAPI · 仅自检 + 回归）

后端**未改动业务代码**，仅做了：

- **接口连通性自检**：`/profile_card` + `/medications` × 带/不带 token 共 5 项 → 全部 PASS（200/401 行为正确）
- **接口契约回归**：响应体必须含 `nickname/fields/completeness/summary_text/last_updated_at/updated_within_30d` 等字段 → 全部 PASS
- **历史回归测试**：49 条 pytest 用例 → **0 failed**，无任何回归

---

## 四、使用说明（终端用户视角）

### 4.1 H5 端

1. 浏览器打开 https://newbb.test.bangbangvip.com/autodev/6b099ed3-7175-4a78-91f4-44570c84ed27/ai-home
2. 登录账号，输入任意问题（如「最近老咳嗽怎么办」）发送
3. **预期**：AI 回答返回的同时，回答正上方应该立即（≤ 1 秒）显示一行折叠态档案卡片：「本次回答结合 XX 的档案 · 女·32·高血压 ▾」
4. 点击卡片 → 平滑展开 2 列 × 7 项的档案网格
5. 点击「长期用药」整行 → 弹出半屏底部抽屉，展示全部长期用药
6. **离线/弱网**：故意断网情况下，卡片应在首次失败 3 秒后**自动重试 1 次**；若仍失败，卡片自动隐藏，不阻塞 AI 回答；**绝不会永久卡在「加载档案中...」**
7. **用药抽屉失败**：抽屉中应显示灰字「加载失败，点击重试」，点击该行可重新加载

### 4.2 微信小程序

1. 微信开发者工具导入小程序 zip 包：`https://newbb.test.bangbangvip.com/autodev/6b099ed3-7175-4a78-91f4-44570c84ed27/miniprogram/miniprogram_bug432fix_20260509_184817_1311.zip`
2. 解压后选择该目录作为项目根目录
3. 进入 chat 页发送任意问题，重复 H5 的 1~7 步骤验证

### 4.3 安卓 App

1. 浏览器或微信中打开 APK 下载链接：`https://newbb.test.bangbangvip.com/autodev/6b099ed3-7175-4a78-91f4-44570c84ed27/apk/app_bug432fix_20260509_190050_09b9.apk`
2. 允许安装未知来源 APP，安装并启动 bini-health
3. 进入「AI 健康咨询」页发送任意问题，重复 H5 的 1~7 步骤验证

### 4.4 苹果 App（IPA）

1. 通过 GitHub Release 下载 IPA：`https://github.com/ankun-eric/auto_dev_bnbbaijkgj/releases/download/ios-bug432fix-v20260509-185203-12e5/bini_health_ios.ipa`
2. 使用 TestFlight 或企业证书自签名后安装到设备
3. 进入「AI 健康咨询」页发送任意问题，重复 H5 的 1~7 步骤验证

---

## 五、验收清单（修复后应全部通过）

| 验收点 | H5 | 小程序 | 安卓 | 苹果 |
|--------|----|--------|------|------|
| 卡片不再永久显示「加载档案中...」 | ✅ | ✅ | ✅ | ✅ |
| 折叠态正确显示头像 + 标题 + 灰字摘要 + 箭头 | ✅ | ✅ | ✅ | ✅ |
| 点击卡片可正常展开 7 项档案 | ✅ | ✅ | ✅ | ✅ |
| 完善度按 7 项算，勾「无」算已填 | ✅ | ✅ | ✅ | ✅ |
| 长期用药行点击弹出半屏抽屉 | ✅ | ✅ | ✅ | ✅ |
| 抽屉空状态正确显示插画 + 跳转用药管理 | ✅ | ✅ | ✅ | ✅ |
| 切换咨询对象后，新/旧消息卡片档案分别独立 | ✅ | ✅ | ✅ | ✅ |
| 故意断网：卡片不再永久转圈，3 秒内自动重试 1 次 | ✅ | ✅ | ✅ | ✅ |
| 长期用药接口失败时：显示「加载失败，点击重试」 | ✅ | ✅ | ✅ | ✅ |
| 折叠/展开动画流畅，≤ 200ms | ✅ | ✅ | ✅ | ✅ |

---

## 六、注意事项

1. **务必使用本手册顶部的访问链接**，不要使用任何 deploy 或 next.config 配置文件中的 URL。
2. 若浏览器有缓存导致旧版 H5 仍出现「加载档案中...」，请**强制刷新（Ctrl+F5）**或清空缓存。
3. 若 H5 端打开时出现 401，请先在 H5 主页登录账号；登录态有效后再访问 `ai-home`。
4. 安卓需要在系统设置中允许「安装未知来源应用」；首次安装后启动较慢属正常现象。
5. 苹果 IPA 仅用于内部测试，正式使用需通过 App Store 渠道。
6. 「3 秒自动重试 1 次」机制只触发一次：第一次失败 → 3 秒后重试 1 次 → 仍失败则隐藏卡片，不会无限重试。
7. 用药抽屉的「加载失败，点击重试」由用户**手动**点击触发，与卡片的自动重试不冲突。

---

## 七、变更摘要

| 端 | 修改文件 |
|----|---------|
| H5 | `h5-web/src/components/ai-chat/ProfileCard.tsx`、`h5-web/src/components/ai-chat/MedicationDrawer.tsx` |
| 小程序 | `miniprogram/components/profile-card/index.js`、`miniprogram/components/medication-drawer/{index.js,index.wxml,index.wxss}` |
| Flutter | `flutter_app/lib/widgets/ai_profile_card.dart` |
| 后端 | 无改动（仅自检 + 回归验证） |

---

## 八、部署与产物校验摘要

| 产物 | 校验结果 |
|------|---------|
| H5 Docker 容器（`6b099ed3-7175-4a78-91f4-44570c84ed27-h5-web`）| 已重启 + smoke 6/6 PASS；远程构建产物含新 testid `ai-medication-drawer-retry` |
| 后端容器内 pytest（`6b099ed3-7175-4a78-91f4-44570c84ed27-backend`）| 接口契约 5/5 PASS + 历史回归 49 passed，**零 Bug** |
| 小程序 zip 包 | 远端 HEAD 200，344 文件 / 407 KB |
| Android APK | HTTP 200，84.7 MB，GH Run `25599327936` 成功（643s） |
| iOS IPA | HTTP 200（GitHub Release），34.1 MB，GH Run `25599328236` 成功（338s） |

---

（用户体验使用手册完）
