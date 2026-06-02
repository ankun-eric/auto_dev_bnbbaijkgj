// [PRD-CARE-MODE-OPTIM-V4 2026-05-31] 关怀模式首页优化
// 顶栏照搬标准模式（☰历史 + 宾尼小康标题 + 「宾尼小康 模式切换」胶囊 + 🎁 + ⋯更多），去掉会报错的 ⊕
// 主体（绿色大卡 + 竖排功能卡片）保持原样；右下角新增悬浮 SOS
const { get } = require('../../utils/request');
const { checkLogin } = require('../../utils/util');

function getGreeting(now) {
  const h = now.getHours();
  if (h >= 5 && h < 11) return { text: '早上好', icon: '☀️' };
  if (h >= 11 && h < 18) return { text: '中午好', icon: '🌤️' };
  return { text: '晚上好', icon: '🌙' };
}

// 24 小时制时间格式化（如 20:00），兼容多种入参形态
function to24h(raw) {
  if (!raw) return '';
  const s = String(raw).trim();
  // 已是 HH:mm 形式
  const m = s.match(/(\d{1,2}):(\d{2})/);
  if (m) {
    const hh = String(parseInt(m[1], 10)).padStart(2, '0');
    return `${hh}:${m[2]}`;
  }
  return s;
}

Page({
  data: {
    statusBarHeight: 20,
    greetingText: '',
    greetingIcon: '',
    medText: '加载中…',
    medReminderPlanId: null,
    modeDropdownOpen: false,
    moreMenuShow: false,
    // [PRD-CARE-OPTIM-FINAL-V1 2026-06-01 §优化2/§优化3]
    showScrollHint: false,
    sharePanelShow: false,
    posterShow: false,
    showNewBadge: Date.now() < new Date('2026-06-25T00:00:00Z').getTime(),
    logoUrl: '',
    cards: [
      { key: 'medication', icon: '💊', title: '用药提醒', desc: '查看今日完整用药提醒列表', bg: 'linear-gradient(135deg,#42A5F5,#1E88E5)' },
      { key: 'health-record', icon: '📈', title: '健康记录', desc: '血压、血糖、心率、血氧、睡眠', bg: 'linear-gradient(135deg,#66BB6A,#43A047)' },
      { key: 'home-safety', icon: '🛡️', title: '居家安全', desc: '紧急呼叫、烟雾报警、水浸报警', bg: 'linear-gradient(135deg,#FFA726,#FB8C00)' },
      { key: 'sos', icon: '🆘', title: '紧急呼叫', desc: '一键 SOS 求助、联系家人与急救', bg: 'linear-gradient(135deg,#EF5350,#E53935)' },
      { key: 'info-card', icon: '🪪', title: '个人信息卡', desc: '身份与健康名片，便于出示与求助', bg: 'linear-gradient(135deg,#AB47BC,#8E24AA)' },
    ],
  },

  onLoad() {
    const g = getGreeting(new Date());
    const app = getApp();
    const base = (app && app.globalData && app.globalData.baseUrl) || '';
    let statusBarHeight = 20;
    try {
      const sys = wx.getSystemInfoSync();
      statusBarHeight = sys.statusBarHeight || 20;
    } catch (e) {}
    this.setData({
      statusBarHeight,
      greetingText: g.text,
      greetingIcon: g.icon,
      logoUrl: `${base}/binni-xiaokang-logo.png`,
    });
    this.loadMedication();
  },

  onShow() {
    this.loadMedication();
    // [PRD-CARE-OPTIM-FINAL-V1 2026-06-01 §优化3] 启用页面右上角原生分享菜单（微信好友转发能力）
    try { wx.showShareMenu({ withShareTicket: true, menus: ['shareAppMessage', 'shareTimeline'] }); } catch (e) { /* ignore */ }
    // [PRD-CARE-OPTIM-FINAL-V1 2026-06-01 §优化2] 渲染完成后判定内容是否超一屏，决定向下箭头是否显示
    setTimeout(() => this.evalScrollHint(), 500);
  },

  // [PRD-CARE-OPTIM-FINAL-V1 2026-06-01 §优化4] 今日提醒智能轮转
  //  - /api/medication-reminder/today 每条返回 checked（打卡状态）+ scheduled_time + plan_id
  //  - 优先显示「最近一条未打卡」（按 scheduled_time 升序首条 checked=false）
  //  - 当前条打卡完成后下次 onShow 刷新自动跳下一条；全部完成给兜底「今天都打完啦 🎉」
  //  - 跨凌晨 12 点：接口按当天日期返回，刷新即从第二天首条重新开始
  loadMedication() {
    get('/api/medication-reminder/today')
      .then((res) => {
        let items = [];
        if (Array.isArray(res)) items = res;
        else if (res && res.data && Array.isArray(res.data.items)) items = res.data.items;
        else if (res && Array.isArray(res.items)) items = res.items;
        else if (res && res.data && Array.isArray(res.data)) items = res.data;
        if (items.length > 0) {
          const isChecked = (it) => it.checked === true || it.done === true;
          const sorted = items.slice().sort((a, b) =>
            String(a.scheduled_time || a.remind_time || a.schedule || '').localeCompare(
              String(b.scheduled_time || b.remind_time || b.schedule || '')
            )
          );
          const next = sorted.find((it) => !isChecked(it));
          if (!next) {
            this.setData({ medText: '今天都打完啦 🎉', medReminderPlanId: null });
          } else {
            const time = to24h(next.scheduled_time || next.remind_time || next.schedule || '');
            const drug = next.drug_name || next.name || '药品';
            this.setData({
              medText: `${time ? time + ' ' : ''}请按时服用"${drug}"`,
              medReminderPlanId: next.plan_id != null ? next.plan_id : (next.id != null ? next.id : null),
            });
          }
        } else {
          this.setData({ medText: '今日暂无用药提醒', medReminderPlanId: null });
        }
      })
      .catch(() => this.setData({ medText: '今日暂无用药提醒', medReminderPlanId: null }));
  },

  // [PRD-CARE-OPTIM-FINAL-V1 2026-06-01 §优化4] 点击今日提醒卡片 → 直达打卡页（本人用药提醒）
  onTapMedReminder() {
    wx.navigateTo({ url: '/pages/care-medication/index', fail: () => {} });
  },

  // [PRD-CARE-OPTIM-FINAL-V1 2026-06-01 §优化2] 页面滚动监听：内容超一屏且未下滑(<40)时显示向下箭头
  onPageScroll(e) {
    const top = (e && e.scrollTop) || 0;
    const show = top < 40;
    if (show !== this.data.showScrollHint && this._canScroll) {
      this.setData({ showScrollHint: show });
    }
  },

  // 进入后判定是否内容超一屏（用于初次展示向下箭头）
  evalScrollHint() {
    const query = wx.createSelectorQuery().in(this);
    query.select('.care-home').boundingClientRect();
    query.selectViewport().boundingClientRect();
    query.exec((rects) => {
      if (!rects || rects.length < 2 || !rects[0] || !rects[1]) return;
      const contentH = rects[0].height || 0;
      const viewH = rects[1].height || 0;
      this._canScroll = contentH - viewH > 40;
      this.setData({ showScrollHint: this._canScroll });
    });
  },

  // ───── 分享面板 ─────
  openSharePanel() {
    this.setData({ sharePanelShow: true });
  },
  closeSharePanel() {
    this.setData({ sharePanelShow: false });
  },
  onShareWechat() {
    // 微信好友：button open-type="share" 会拉起转发，此处仅关面板
    this.setData({ sharePanelShow: false });
  },
  onSharePoster() {
    this.setData({ sharePanelShow: false, posterShow: true });
  },
  closePoster() {
    this.setData({ posterShow: false });
  },
  onShareCopy() {
    const app = getApp();
    const base = (app && app.globalData && app.globalData.h5BaseUrl) || (app && app.globalData && app.globalData.baseUrl) || '';
    const link = `${base}/invite`;
    wx.setClipboardData({
      data: link,
      success: () => wx.showToast({ title: '链接已复制', icon: 'success' }),
      fail: () => wx.showToast({ title: '复制失败', icon: 'none' }),
    });
    this.setData({ sharePanelShow: false });
  },

  // 微信转发：纯拉新分享文案 + 落地注册引导页
  onShareAppMessage() {
    return {
      title: '我在用 宾尼小康 守护家人健康，推荐您也来试试~',
      path: '/pages/ai/index',
    };
  },

  // ───── 模式切换胶囊 ─────
  toggleModeDropdown() {
    this.setData({ modeDropdownOpen: !this.data.modeDropdownOpen });
  },

  closeModeDropdown() {
    this.setData({ modeDropdownOpen: false });
  },

  switchToStandard() {
    this.setData({ modeDropdownOpen: false });
    try {
      wx.setStorageSync('app_mode_preference', 'standard');
    } catch (e) {}
    wx.showToast({ title: '已切换到标准模式 ✓', icon: 'none' });
    setTimeout(() => {
      wx.navigateTo({ url: '/pages/ai/index', fail: () => wx.switchTab({ url: '/pages/ai/index' }) });
    }, 300);
  },

  // ───── 左上角 ← 返回（[BUGFIX-AI-HOME-CARE-BACK-V1 2026-06-01 §问题2]） ─────
  // 旧版此处为 ☰，点击跳标准首页并自动弹历史抽屉，会顺带把模式带回标准模式（BUG）。
  // 现改为返回箭头：退出关怀模式，统一退回标准 AI 主页。
  // 复用 switchToStandard 的"存 standard 偏好 + 跳标准首页"，但去掉切换 Toast，做"干净返回"。
  goBackStandard() {
    try {
      wx.setStorageSync('app_mode_preference', 'standard');
    } catch (e) {}
    wx.navigateTo({
      url: '/pages/ai/index',
      fail: () => wx.switchTab({ url: '/pages/ai/index' }),
    });
  },

  // [PRD-AIHOME-UNIFY-V1 2026-06-01 §需求1] 顶栏「档案/咨询/服务」三 Tab
  // 档案 → /pages/health-profile；服务 → /pages/services；咨询 = 当前页停留
  onTopTab(e) {
    const key = e.currentTarget.dataset.key;
    if (key === 'consult') return; // 咨询：关怀版咨询首页停留
    if (key === 'profile') {
      wx.navigateTo({ url: '/pages/health-profile/index', fail: () => wx.switchTab({ url: '/pages/health-profile/index' }) });
      return;
    }
    if (key === 'service') {
      wx.switchTab({ url: '/pages/services/index', fail: () => wx.navigateTo({ url: '/pages/services/index' }) });
      return;
    }
  },

  // [PRD-AIHOME-UNIFY-V1 2026-06-01 §需求1] 顶栏 🔔 铃铛 → 今日待办（本人用药提醒）
  openBell() {
    wx.navigateTo({ url: '/pages/care-medication/index', fail: () => {} });
  },

  // ───── 右上角 🎁 邀请 ─────
  goInvite() {
    wx.navigateTo({ url: '/pages/invite/index', fail: () => {} });
  },

  // ───── 右上角 ⊕ 更多菜单（与标准模式统一为 8 项） ─────
  openMoreMenu() {
    this.setData({ moreMenuShow: true });
  },

  closeMoreMenu() {
    this.setData({ moreMenuShow: false });
  },

  // [PRD-AIHOME-UNIFY-V1 2026-06-01 §需求2] ⊕ 菜单项①：💬 发起新对话（关怀版开新会话）
  onTapNewChat() {
    this.setData({ moreMenuShow: false });
    wx.navigateTo({ url: '/pages/chat/index?type=health_qa', fail: () => {} });
  },

  // [PRD-AIHOME-UNIFY-V1 2026-06-01 §需求2] ⊕ 菜单项②：🔀 切换模式（与欢迎区胶囊并存）→ 切到标准模式
  onTapSwitchMode() {
    this.setData({ moreMenuShow: false });
    this.switchToStandard();
  },

  // [PRD-AIHOME-UNIFY-V1 2026-06-01 §需求2] ⊕ 菜单项④：🎁 邀请好友
  onTapInvite() {
    this.setData({ moreMenuShow: false });
    this.goInvite();
  },

  // [PRD-AIHOME-UNIFY-V1 2026-06-01 §需求2] ⊕ 菜单项⑧：❓ 帮助与反馈
  onTapHelpFeedback() {
    this.setData({ moreMenuShow: false });
    wx.navigateTo({ url: '/pages/feedback/index', fail: () => wx.showToast({ title: '反馈入口开发中', icon: 'none' }) });
  },

  onTapMemberCenter() {
    this.setData({ moreMenuShow: false });
    if (!checkLogin()) return;
    wx.navigateTo({ url: '/pages/member-center/index' });
  },

  onTapScan() {
    this.setData({ moreMenuShow: false });
    wx.scanCode({
      onlyFromCamera: false,
      success: () => wx.showToast({ title: '扫码成功', icon: 'success' }),
      fail: () => wx.showToast({ title: '已取消扫码', icon: 'none' }),
    });
  },

  onTapFontSize() {
    this.setData({ moreMenuShow: false });
    wx.showToast({ title: '字体大小设置开发中', icon: 'none' });
  },

  // [PRD-AIHOME-OPTIM-SHARE-V1 2026-06-02 §需求1] 「🎁 分享好友」统一入口
  //   合并原「立即分享」，弹出分享面板（与底部「分享好友」大按钮、标准模式行为一致）。
  onTapShareFriend() {
    this.setData({ moreMenuShow: false });
    this.openSharePanel();
  },

  // ───── 右下角悬浮 SOS = 点「紧急呼叫」卡片 ─────
  onSosFabTap() {
    this.goSos();
  },

  goSos() {
    wx.navigateTo({ url: '/pages/care-sos/index' });
  },

  onCardTap(e) {
    const key = e.currentTarget.dataset.key;
    switch (key) {
      case 'medication':
        // [需求4] 直接进入本人独立的「用药提醒」页面（health-plan/medications，本人 Tab 数据）
        wx.navigateTo({ url: '/pages/care-medication/index' });
        break;
      case 'health-record':
        wx.navigateTo({ url: '/pages/care-today-health/index' });
        break;
      case 'home-safety':
        wx.navigateTo({ url: '/pages/health-profile/index?tab=self&focus=devices' });
        break;
      case 'sos':
        this.goSos();
        break;
      case 'info-card':
        wx.navigateTo({ url: '/pages/care-info-card/index' });
        break;
      default:
        break;
    }
  },
});
