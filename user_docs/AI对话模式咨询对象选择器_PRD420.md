# AI 对话模式 - 咨询对象选择器（PRD-420）

> 上线日期：2026-05-08  
> 关联：PRD-411（AI 对话首页 Tab 化）/ PRD-414（AI 对话页优化 v1.1）/ Bug-419（首页白屏 + 422 修复）  
> 类型：新功能开发（H5 / 微信小程序 / iOS / Android 全端同步）

---

## 1. 一句话总结

把菜单模式（`/chat/[sessionId]`）已经成熟稳定的「咨询对象选择器」整套交互——**底部抽屉 + 已有家庭成员 + 新建家庭成员（关系九宫格 + 7 字段表单）**——完整搬到 AI 对话模式（`/ai-home`）头部「为本人咨询」按钮，让用户在 AI 对话首页直接切换/新增家庭成员，**两个模式共用一份家庭成员数据，跨模式即时可见**。

---

## 2. 核心交互（用户视角）

### 入口

打开 H5「AI 对话」首页（路径 `/ai-home`），头部居左有一个椭圆胶囊：

```
为 [关系·昵称]   ▼
```

- 当未选择特定家庭成员时显示 **"为本人 ▼"**
- 选择后变为 **"为儿子·苏俊林 ▼"**「为老婆·朱小妹 ▼」等

### 切换咨询对象

1. 点击胶囊 → 底部弹出半透明遮罩 + 抽屉
2. 抽屉内**第一行永远是「本人」**（带头像/默认头像 + 绿色对勾标记选中态）
3. 下方按"创建时间正序"列出其他成员
4. 抽屉最底有 **"+ 新建家庭成员"** 入口

### 新建家庭成员（双层抽屉）

点击 "+ 新建家庭成员"：

**第一层 - 关系九宫格**

| | | |
|---|---|---|
| 爸爸 | 妈妈 | 老公 |
| 老婆 | 儿子 | 女儿 |
| 哥哥 | 弟弟 | 姐姐 |
| 妹妹 | 爷爷 | 奶奶 |
| 外公 | 外婆 | 其他 |

**第二层 - 信息表单**（点击关系卡片后展开）

- 姓名/昵称（必填，1~20 字符）
- 性别（必填，男 / 女）
- 出生日期（必填，日期选择器）
- 身高 cm（选填，30~250）
- 体重 kg（选填，1~300，1 位小数）
- 既往病史（选填，多选 + 自定义文字）
- 过敏史（选填，多选 + 自定义文字）

点击「保存」→ 后端落库 → 自动选中该成员 → 关闭抽屉。

### 切换会话归属人

| 场景 | 行为 |
|---|---|
| 当前 AI 会话**还没有任何消息** | 直接复用当前会话，仅切换 `family_member_id`（调 `POST /api/chat/sessions/:id/switch-member`） |
| 当前 AI 会话**已发出消息** | 自动**新建一个会话**，新会话 `family_member_id` = 选中成员，AI 上下文严格隔离不串档 |
| 切换为非空会话后 | 屏幕底部弹出**5 秒灰色 Toast**「已为新对象新建对话，5 秒内可点击返回上一对话」，超时自动消失，5 秒内点击则回到原会话 |

### 默认值

- 进入 `/ai-home` 默认始终是 **"本人"**（即使上次选择了别的成员，再次进入也回归本人）。

---

## 3. 全端同步（PRD F7：数据完全打通）

| 端 | 入口 | 实现方式 |
|---|---|---|
| **H5** | `/ai-home` 头部胶囊 | 抽取公共组件 `ConsultTargetPicker.tsx`（关系九宫格 + 表单完整复刻菜单模式） |
| **微信小程序** | `pages/chat` 顶部"为 X 咨询"胶囊 | 在原有简易选择器基础上叠加"+ 新建家庭成员"入口 + 关系九宫格 + 7 字段表单 + 病史/过敏史标签 |
| **Android App** | AI Chat 页头部胶囊 | 抽屉新增「+ 新建家庭成员」按钮，点击跳到「健康档案」页（`/health-profile`），添加完毕返回时自动刷新成员列表 |
| **iOS App** | 同 Android（Flutter 代码同份） | 同上 |
| **后端** | 不变 | PRD F7 明确：本次需求"无需任何后端接口新增或改造"。所有端调用既有的 `/api/family/members`（GET/POST）和 `/api/chat/sessions/:id/switch-member` 即可 |

> 任意一端在 AI 对话模式新建的家庭成员，菜单模式（健康档案、其他对话页面）下次打开抽屉/列表都能立即看到。

---

## 4. 测试访问入口（请打开浏览器逐个验证）

> 测试基础地址：`https://newbb.test.bangbangvip.com/autodev/6b099ed3-7175-4a78-91f4-44570c84ed27/`

### 4.1 H5 用户端（核心入口）

| 验证场景 | 入口路径 | 期望结果 |
|---|---|---|
| AI 对话首页 | `/ai-home` | 欢迎语下方头部出现胶囊「为本人 ▼」 |
| 打开抽屉 | 点击胶囊 | 半透明遮罩 + 底部抽屉，第一行「本人」带绿色对勾 |
| 切换为其他成员（先创建一个） | 点击成员行 | 胶囊文案变更为「为 关系·昵称 ▼」，会话归属同步更新 |
| 新建家庭成员 - 第一层 | 抽屉底部点「+ 新建家庭成员」 | 弹出关系九宫格（15 个关系卡片，含「其他」） |
| 新建家庭成员 - 第二层 | 点击任一关系卡片 | 关系九宫格上方高亮所选关系，下方展开姓名/性别/出生日期/身高/体重/病史/过敏史表单 |
| 表单校验 - 姓名空 | 留空姓名点保存 | 顶部 Toast「请填写姓名」，无法提交 |
| 表单校验 - 重复关系 | 选已有过的关系（如已有"老婆"再选老婆） | 提示「您已添加过此关系，是否继续？」（柔性提示，可继续） |
| 表单提交成功 | 填齐必填项点保存 | Toast「已添加家庭成员」，抽屉关闭，胶囊自动切换到新成员 |
| 默认本人 | 重新打开 `/ai-home` | 胶囊回归「为本人 ▼」（不记忆上次选择，PRD F6） |
| 切换归属人 - 空会话 | 进入 `/ai-home` 不发消息直接换成员 | 默默切换不新建会话 |
| 切换归属人 - 非空会话 | 在 AI 首页发一条消息后再换成员 | 自动新建会话 + 5 秒灰色 Toast「已为新对象新建对话，5 秒内可点击返回上一对话」 |
| 5 秒撤销 | Toast 出现期间点 Toast | 立即返回原会话（含原家庭成员 + 历史消息） |

### 4.2 后端 API（直接验证契约）

> 全部需要 `Authorization: Bearer <token>` + `Client-Type: h5-user` 请求头

| 接口 | URL | 期望 |
|---|---|---|
| 列出家庭成员 | `GET /api/family/members` | `200`，`{items:[...], total:N}`，本人 (`is_self:true`) 永远第一个 |
| 关系字典 | `GET /api/relation-types` | `200`，包含「爸爸/妈妈/老公/老婆/儿子/女儿/...」共 15 个关系，按 `sort_order` 升序 |
| 添加家庭成员 | `POST /api/family/members` 带 `{nickname,name,relationship_type,gender,birthday,height,weight,medical_histories[],allergies[]}` | `200`，返回成员对象 |
| 创建会话指定咨询对象 | `POST /api/chat/sessions` 带 `{session_type:"health_qa",family_member_id:N}` | `200`，返回 session（带 `family_member_id`） |
| 切换会话归属人 | `POST /api/chat/sessions/:id/switch-member` 带 `{family_member_id:N}`（或 `null`） | `200`，返回 `{family_member_id, message:"已切换为给 老婆 咨询"}` |

### 4.3 微信小程序

> 通过 IDE 导入小程序源码（参见下方"打包与上传 / 微信小程序"章节），或下载体验版 zip 包：  
> `https://newbb.test.bangbangvip.com/autodev/6b099ed3-7175-4a78-91f4-44570c84ed27/miniprogram/miniprogram_prd420_20260508_173532_91c8.zip`

| 验证场景 | 期望 |
|---|---|
| 进入「AI 对话」 tab | 顶部胶囊「为 X 咨询 ▼」可见 |
| 点击胶囊 | 弹出选择抽屉，含本人 + 已有成员 + "+ 新建家庭成员" |
| 点 "+ 新建家庭成员" | 进入关系选择页 → 选关系后展开 7 字段表单 |
| 保存新成员 | 自动选中该成员，回到对话页 |
| 切换归属人非空会话 | 自动创建新会话 |

### 4.4 Android / iOS（Flutter）

> Android APK 和 iOS IPA 通过 GitHub Actions 远程构建后下载链接如下（链接在构建完成后注入）。

- **Android APK**：`https://newbb.test.bangbangvip.com/autodev/6b099ed3-7175-4a78-91f4-44570c84ed27/apk/`（取最新 PRD-420 版本）
- **iOS IPA**（TestFlight 上传）：构建完成后 `https://newbb.test.bangbangvip.com/autodev/6b099ed3-7175-4a78-91f4-44570c84ed27/ipa/`

| 验证场景 | 期望 |
|---|---|
| 进入 AI Chat 页 | 头部胶囊可见，可点击 |
| 抽屉选择 | 列出本人 + 已有成员，最底有「新建家庭成员」按钮 |
| 点「新建家庭成员」| 跳转到「健康档案」页（既有页面，已有完整添加流程） |
| 在健康档案添加后返回 | 抽屉自动刷新，新成员可见可选 |

> 设计取舍：Flutter 端复用既有「健康档案」页的「添加家庭成员」UI，避免重复造轮子；用户体验等价（数据全部打通）。

---

## 5. 后端契约回归测试（容器内 pytest）

```text
PRD-420 行为契约测试：
backend/tests/test_prd420_consult_target_picker.py
  T01 列出家庭成员返回结构 (items + total)
  T02 排序：本人优先 + 其他按 created_at 正序
  T03 添加家庭成员 - F4 全字段（关系/姓名/性别/出生/身高/体重/病史/过敏）
  T04 必填关系缺失 → 400 或 422 + 中文提示
  T05 同一关系（如「老婆」）允许重复添加（前端柔性提示）
  T06 创建会话携带 family_member_id 建立归属
  T07 空会话直接切换归属人
  T08 切换回本人（family_member_id=null）
  T09 数据共享：菜单模式与 AI 模式共用同一份成员数据
  T10 跨入口隔离：不同咨询对象的会话独立
  T11 未登录访问 → 401/403
  T12 跨用户越权防护：A 不可见 B 的成员
  T13 add → list 立即可见

→ 13 passed in 9.06s

关键回归（确保 PRD-411 / PRD-414 / Bug-419 不退化）：
backend/tests/test_bug419_chat_sessions.py + test_ai_home_config.py
→ 36 passed in 22.40s
```

---

## 6. 端到端 smoke 验证（生产环境真实链路）

```
T1  注册新用户          OK
T2  列出家庭成员（本人）  OK
T3  关系字典含 15 关系   OK
T4  AI 模式新建老婆     OK
T5  列表中能看到老婆     OK
T6  创建会话 + 老婆     OK
T7  切换为本人          OK
T8  切回老婆            OK
T9  AI 模式新建儿子（全字段含病史/过敏） OK
T10 创建儿子专属会话    OK
T11 F7 数据共享        OK
T12 ai-home-config 可达 OK
```

---

## 7. 改动文件清单

### 新增

- `h5-web/src/components/ai-chat/ConsultTargetPicker.tsx` —— 公共组件，封装「已有成员列表 + 关系九宫格 + 7 字段表单 + DatePicker + Discard 确认」
- `backend/tests/test_prd420_consult_target_picker.py` —— 13 个契约回归测试

### 修改

- `h5-web/src/app/(ai-chat)/ai-home/page.tsx` —— 集成 ConsultTargetPicker + F5 切换会话逻辑 + 5 秒撤销 Toast + F6 默认本人
- `miniprogram/pages/chat/index.{wxml,js,wxss}` —— 在原选择器上叠加新建成员双层抽屉
- `flutter_app/lib/screens/ai/chat_screen.dart` —— 抽屉新增「新建家庭成员」按钮跳转到健康档案页

### 部署 / 打包脚本

- `_deploy_prd420.py` —— SFTP 上传 + docker compose build h5-web + 容器内 pytest + 远程 smoke
- `_pack_upload_miniprogram_prd420.py` —— 小程序 zip 打包 + SFTP 上传
- `_smoke_prd420.py` —— 注册新用户 → AI 模式新建成员 → 切换归属人 → F7 数据共享 全链路 smoke

---

## 8. 注意事项

1. **缓存清理**：H5 用户若访问过旧版本，请按 `Ctrl + Shift + R` 强制刷新。
2. **AI 上下文严格隔离**：医疗咨询场景下 AI 上下文严禁串档（PRD §4.2 安全要求），切换咨询对象后**必须新建会话**。本次实现严格遵守，已通过 T10 自动测试。
3. **同一关系反复添加**：后端不强制拦截（用户家庭场景复杂，后妻、再婚等都合法）；前端 UI 给柔性提示「您已添加过此关系，是否继续？」让用户自决定。
4. **移除/编辑成员**：本次 PRD 未涉及，仍走「健康档案」页（`/health-profile`）的既有删除/编辑流程，所有端共用一份接口。
5. **5 秒撤销 Toast**：仅在「非空会话被新建」时弹出，5 秒后自动消失；若用户在 5 秒内手动选择了第三个成员，前一次的撤销机会自动失效（始终只保留最新一次撤销点）。

---

## 9. 关键技术决策

- **公共组件 vs 复制粘贴**：H5 端选择「抽取公共组件 `ConsultTargetPicker`」，老的菜单模式 chat 页也可以平滑迁移到此组件（本次不动菜单模式以减少风险），未来 PRD 可统一收口。
- **小程序 vs Flutter 的 UI 复刻深度**：小程序选择 100% UI 复刻（弹层 + 关系九宫格 + 7 字段表单），保持与 H5 一致体验；Flutter 选择「跳健康档案页」的轻量集成方案，复用既有页面，规避 Flutter 端重复造表单的高成本。两种方案最终用户体验都是「能在 AI 对话模式新建家庭成员并立即可选」，符合 PRD F2 + F3 + F4 + F7 的功能要求。
- **F6 默认本人**：进入 `/ai-home` 始终回归「本人」，确保用户每次开局都在最熟悉的上下文，避免上次切到「老婆」后下次进首页一脸懵。
- **5 秒撤销而非 confirm 弹窗**：医疗场景对操作流畅性要求高，撤销 Toast 比阻塞式 confirm 弹窗体验更顺滑；5 秒足够大多数用户反应过来"我点错了"。
- **后端零改动**：本次最大的工程红利是「PRD F7 已经把数据全部打通」，菜单模式和 AI 模式共用 `/api/family/members` 和 `/api/chat/sessions/:id/switch-member`，前端只需把 UI 拼接到位即可。

---

## 10. 回滚方式（如需）

```bash
ssh ubuntu@newbb.test.bangbangvip.com
cd /home/ubuntu/6b099ed3-7175-4a78-91f4-44570c84ed27/
git log --oneline -5                    # 找到 PRD-420 提交前的 commit
git reset --hard <PRD-420 之前的 commit>
docker compose -f docker-compose.prod.yml down
docker compose -f docker-compose.prod.yml build h5-web
docker compose -f docker-compose.prod.yml up -d
```

> 后端无任何改动，无需重建后端容器；只需回滚 h5-web。

---

如有任何使用问题，请将「访问的具体链接 + 浏览器开发者工具 Network/Console 截图」反馈给后台支持人员。
