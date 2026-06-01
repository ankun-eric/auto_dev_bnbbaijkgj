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
    modeDropdownOpen: false,
    moreMenuShow: false,
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
  },

  loadMedication() {
    get('/api/medication-reminder/today')
      .then((res) => {
        let items = [];
        if (Array.isArray(res)) items = res;
        else if (res && res.data && Array.isArray(res.data.items)) items = res.data.items;
        else if (res && Array.isArray(res.items)) items = res.items;
        else if (res && res.data && Array.isArray(res.data)) items = res.data;
        if (items.length > 0) {
          const next = items.find((it) => !it.done) || items[0];
          const time = to24h(next.scheduled_time || next.remind_time || next.schedule || '');
          const drug = next.drug_name || next.name || '药品';
          this.setData({ medText: `${time ? time + ' ' : ''}请按时服用"${drug}"` });
        } else {
          this.setData({ medText: '今日暂无用药提醒' });
        }
      })
      .catch(() => this.setData({ medText: '今日暂无用药提醒' }));
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

  // ───── 左上角 ☰ 历史（与标准模式一致：进入历史对话记录） ─────
  // 复用标准模式 AI 首页的历史对话抽屉（携带 openDrawer 标记，进入即弹出）
  openHistory() {
    wx.navigateTo({
      url: '/pages/ai/index?openDrawer=1',
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

  onTapShare() {
    this.setData({ moreMenuShow: false });
    wx.showShareMenu({ withShareTicket: true });
    wx.showToast({ title: '请点击右上角分享', icon: 'none' });
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
