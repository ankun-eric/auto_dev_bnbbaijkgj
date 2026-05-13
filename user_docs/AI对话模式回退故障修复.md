# AI 对话模式回退故障 · 修复完成报告与体验手册

> 故障编号：INCIDENT-20260513-01
> 故障定性：P0（测试服与正式服三端 AI 对话整体回退到 5 月初版本）
> 修复时间：2026-05-13
> 修复结果：测试服 22/22 自动化烟测 PASS ✅

---

## 访问链接

以下是当前项目（测试服）的体验链接，点击即可打开：

> ⚠️ 所有链接均经由测试服 Nginx 80 端口反向代理，请勿使用 Docker 容器内部端口。

| 服务 | 链接 | 说明 |
|------|------|------|
| H5 项目首页 | [https://newbb.test.bangbangvip.com/autodev/6b099ed3-7175-4a78-91f4-44570c84ed27/](https://newbb.test.bangbangvip.com/autodev/6b099ed3-7175-4a78-91f4-44570c84ed27/) | H5 主入口，登录后进入晴空诊室 AI 对话 |
| AI 对话首页 | [https://newbb.test.bangbangvip.com/autodev/6b099ed3-7175-4a78-91f4-44570c84ed27/ai-home](https://newbb.test.bangbangvip.com/autodev/6b099ed3-7175-4a78-91f4-44570c84ed27/ai-home) | AI 对话首页（ai-home），含「为本人 ▼」咨询对象胶囊、推荐问、功能宫格 |
| 登录页 | [https://newbb.test.bangbangvip.com/autodev/6b099ed3-7175-4a78-91f4-44570c84ed27/login](https://newbb.test.bangbangvip.com/autodev/6b099ed3-7175-4a78-91f4-44570c84ed27/login) | 用户登录入口 |
| 健康档案 v2 | [https://newbb.test.bangbangvip.com/autodev/6b099ed3-7175-4a78-91f4-44570c84ed27/health-profile-v2/](https://newbb.test.bangbangvip.com/autodev/6b099ed3-7175-4a78-91f4-44570c84ed27/health-profile-v2/) | 配套 PRD-469 v2 健康档案 v2 入口（重建后同步可达） |

---

## 一、本次修复做了什么

### 1.1 一句话总结

把测试服 `h5-web/` 源码目录全量同步到 git master HEAD 最新状态，再用 `docker compose build --no-cache` 完整重建 H5 镜像，让"晴空诊室"AI 对话最新版重新生效。

### 1.2 故障根因（用户视角的话）

- 今天发版的脚本只通过 SFTP 上传了 23 个文件（与 PRD-469 健康档案 v2 相关），但是 H5 镜像是**整体重建**。
- 服务器上 `h5-web/` 源码目录在 5 月初部署之后就一直没整体同步过，只靠一次次"增量上传"来打补丁。
- 这次重建相当于把"5 月初的 AI 对话老代码 + 最新的健康档案 v2 文件"一锅端打成新镜像，结果：
  - 顶部"为本人 ▼"咨询对象胶囊退回成简单下拉
  - 左侧抽屉"历史对话"老 Bug 重现
  - AI 回答又变回左右气泡
  - ai-home 首页推荐问 / 功能宫格退回旧版
  - 全局配色从天蓝色品牌回退成白底普通蓝
- H5、微信小程序、Flutter App 三端共用同一个 h5-web 产物，所以一锤子砸三端。

### 1.3 修复后的状态

| 维度 | 修复前 | 修复后 |
|------|--------|--------|
| 全局品牌色 | 白底 + 普通蓝（旧版） | 晴空诊室天蓝色（`#0ea5e9` brand-500）✅ |
| 顶部咨询对象 | 简单下拉 | 「为本人 ▼」胶囊（AdvisorCapsule v1.1 / PRD-448）✅ |
| AI 回答上方档案卡 | 无 | 「本次回答结合 XX 的档案」折叠胶囊（PRD-432 / ProfileCard）✅ |
| ai-home 推荐问 | 旧版 | PRD-426/467 升级版常驻横向胶囊 + 字号设置 ✅ |
| 历史对话抽屉 | 老 Bug | BUG-461/462/466/467 全部修复版 ✅ |
| 健康档案 v2 入口 | 已有 | 仍保留并可达 ✅ |
| 服务器源码 hash | 漂移 | 与 git master HEAD 完全一致 ✅ |
| 镜像构建 | 命中 cache | `--no-cache` 全新构建 ✅ |

---

## 二、自动化烟测结果（请放心查看）

修复执行后，自动化测试一次跑了 **22 项检查，全部 PASS**：

| 类别 | 通过 / 总数 | 关键证据 |
|------|------------|----------|
| 服务器源码标记 | 14 / 14 | PRD-442 / 448 / 432 / 426 / 467 + BUG-461/466 修复全部就位 |
| 容器构建产物 | 5 / 5 | 天蓝色变量 / 用户气泡渐变 / "本次回答结合" 文案 / "健康档案" 入口 全部编进新镜像 |
| 外部 HTTP 可达 | 3 / 3 | 首页 200 / ai-home 308 / login 308 |

容器创建时间已刷新：`2026-05-13T13:39:31Z`（北京时间约 21:39），证明确实是新镜像在跑。

---

## 三、用户人工双确认点检清单（建议在测试服跑一遍）

> 自动化烟测已经 PASS。下面这张清单是给您**人工二次确认**用的，建议三端各点一遍，全部勾上 ✅ 后再决定是否同步到正式服。

### 3.1 H5 浏览器端

打开：[https://newbb.test.bangbangvip.com/autodev/6b099ed3-7175-4a78-91f4-44570c84ed27/ai-home](https://newbb.test.bangbangvip.com/autodev/6b099ed3-7175-4a78-91f4-44570c84ed27/ai-home)（需先登录）

- [ ] **配色**：整体是不是回到了天蓝色品牌风格（不是白底 + 普通蓝的朴素版）
- [ ] **顶部**：能不能看到「为本人 ▼」的天蓝色胶囊（不是简单下拉）
- [ ] **推荐问**：首页有没有横向滚动的推荐问胶囊
- [ ] **功能宫格**：首页是不是新版功能宫格布局（含「健康档案」「我的设备」高频入口）
- [ ] **左上角抽屉**：点击进入「历史对话」抽屉
  - [ ] 抽屉不再被顶部菜单遮挡
  - [ ] 切换咨询人时会自动开新会话
  - [ ] 历史列表会按当前咨询人过滤
- [ ] **右上角「⋯」菜单**：点击能正常弹出（无 PRD-467 三 Bug）
- [ ] **进对话页**：随便发一条消息
  - [ ] AI 回答上方有一张「本次回答结合 XX 的档案」折叠胶囊
  - [ ] AI 文字是**纯文本流**（不是左右气泡）
  - [ ] 用户消息气泡是天蓝色渐变
- [ ] **切换咨询人**：从"本人"切换到一个家庭成员
  - [ ] 切换瞬间会开一个新会话
  - [ ] 新会话的档案胶囊上显示的是该成员名字

### 3.2 微信小程序端

扫码进入小程序 → 进入 AI 对话模式
- [ ] 重复 3.1 中的全部检查项

### 3.3 Flutter App

打开 App → 进入 AI 对话页
- [ ] 重复 3.1 中的全部检查项

---

## 四、注意事项

### 4.1 范围说明

- **本次修复仅作用于测试服**（`newbb.test.bangbangvip.com`）
- **未影响**：后端服务、数据库、用户数据、其他容器、其他端的原生代码
- h5-web 容器重启窗口约 30 秒

### 4.2 后续动作

1. **请先按上方点检清单在测试服三端各点一遍**
2. 三端全部 ✅ 后，再决定是否对正式服执行同样的同步动作（正式服 SOP 与测试服流程完全一致，只需把 SSH 目标换成正式服）
3. 短期内**严禁再用旧的"增量 SFTP + 整镜像 rebuild"模式**发版，否则会再次踩坑

### 4.3 长期改进建议（事后复盘项，本次不做）

1. 废弃"增量 SFTP + 整镜像 rebuild"模式（因为只要 rebuild，就必然用服务器目录里**全部**源码）
2. 统一改成"git pull + build"模式：服务器目录就是 git 工作区，发版前 `git fetch && git reset --hard origin/master` 再 build
3. build 前加一道"源码 hash 校验"：本地 git HEAD 与服务器对一遍，不一致直接报错中止
4. 镜像 label 中打入 commit hash，运行时可查

---

## 五、回滚预案（用户已选「不备份」，仅备查）

| 场景 | 回滚动作 |
|------|----------|
| 同步过程网络中断 | 重跑同步脚本，SFTP 幂等覆盖 |
| build 失败 | 不会进入 up 阶段，老容器仍在运行，线上不受影响，修源码后重跑 |
| 新镜像 up 后服务异常 | 通过镜像 tag 切回上一版：`docker tag <prev_image_id> 6b099ed3-...-h5-web:latest && docker compose up -d h5-web` |
| 人工验证不过 | 不放行正式服同步，在测试服修源码后重跑 |

---

## 六、本次执行 Checklist（已全部完成）

- [x] 用户审阅修复方案 PRD 后放行
- [x] 全量同步脚本落地并执行：**256/256 文件成功上传，耗时 202s**
- [x] `docker compose build --no-cache h5-web` 完成：**约 88 秒 next build + 镜像 layer 拷贝**
- [x] `docker compose up -d h5-web` 完成，新容器创建于 21:39:31
- [x] 自动化烟测：**22/22 PASS**
- [ ] **等待您人工点检（H5 / 小程序 / Flutter App 三端逐一确认）**
- [ ] 双 OK 后，输出「放行同步正式服」结论

---

## 访问链接

再次列出当前项目（测试服）的体验链接，方便点击：

| 服务 | 链接 | 说明 |
|------|------|------|
| H5 项目首页 | [https://newbb.test.bangbangvip.com/autodev/6b099ed3-7175-4a78-91f4-44570c84ed27/](https://newbb.test.bangbangvip.com/autodev/6b099ed3-7175-4a78-91f4-44570c84ed27/) | H5 主入口 |
| AI 对话首页 | [https://newbb.test.bangbangvip.com/autodev/6b099ed3-7175-4a78-91f4-44570c84ed27/ai-home](https://newbb.test.bangbangvip.com/autodev/6b099ed3-7175-4a78-91f4-44570c84ed27/ai-home) | 晴空诊室 AI 对话首页 |
| 登录页 | [https://newbb.test.bangbangvip.com/autodev/6b099ed3-7175-4a78-91f4-44570c84ed27/login](https://newbb.test.bangbangvip.com/autodev/6b099ed3-7175-4a78-91f4-44570c84ed27/login) | 登录入口 |
| 健康档案 v2 | [https://newbb.test.bangbangvip.com/autodev/6b099ed3-7175-4a78-91f4-44570c84ed27/health-profile-v2/](https://newbb.test.bangbangvip.com/autodev/6b099ed3-7175-4a78-91f4-44570c84ed27/health-profile-v2/) | 健康档案 v2（一并验证未被破坏） |
