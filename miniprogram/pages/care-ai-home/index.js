// [PRD-CARE-MODE-OPTIM-V1 2026-05-31] 关怀模式首页优化
// 三块结构：顶部固定栏（☰/小康/模式胶囊+🎁+⊕）+ 欢迎区（问候+小字+今日用药提醒+机器人LOGO窄白边）+ 5 张大字整行卡片
const { get } = require('../../utils/request');

function getGreeting(now) {
  const h = now.getHours();
  if (h >= 5 && h < 11) return { text: '早上好', icon: '☀️' };
  if (h >= 11 && h < 18) return { text: '中午好', icon: '🌤️' };
  return { text: '晚上好', icon: '🌙' };
}

Page({
  data: {
    statusBarHeight: 20,
    greetingText: '',
    greetingIcon: '',
    medText: '加载中…',
    modeDropdownOpen: false,
    logoUrl: '',
    cards: [
      { key: 'medication', icon: '💊', title: '用药提醒', desc: '查看今日完整用药提醒列表', bg: 'linear-gradient(135deg,#42A5F5,#1E88E5)' },
      { key: 'health-record', icon: '📈', title: '健康记录', desc: '血压、血糖、心率、血氧、睡眠', bg: 'linear-gradient(135deg,#66BB6A,#43A047)' },
      { key: 'home-safety', icon: '🛡️', title: '居家安全设备', desc: '紧急呼叫器 / 烟雾报警器 / 水浸报警器', bg: 'linear-gradient(135deg,#FFA726,#FB8C00)' },
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
          const time = next.scheduled_time || next.remind_time || next.schedule || '';
          const drug = next.drug_name || next.name || '药品';
          this.setData({ medText: `${time ? time + ' ' : ''}请按时服用"${drug}"` });
        } else {
          this.setData({ medText: '今日暂无用药提醒' });
        }
      })
      .catch(() => this.setData({ medText: '今日暂无用药提醒' }));
  },

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

  goMenu() {
    wx.navigateTo({ url: '/pages/profile/index', fail: () => {} });
  },

  goInvite() {
    wx.navigateTo({ url: '/pages/invite/index', fail: () => {} });
  },

  onCardTap(e) {
    const key = e.currentTarget.dataset.key;
    switch (key) {
      case 'medication':
        wx.navigateTo({ url: '/pages/health-profile/index?tab=self&focus=medication' });
        break;
      case 'health-record':
        wx.navigateTo({ url: '/pages/care-today-health/index' });
        break;
      case 'home-safety':
        wx.navigateTo({ url: '/pages/health-profile/index?tab=self&focus=devices' });
        break;
      case 'sos':
        wx.navigateTo({ url: '/pages/care-sos/index' });
        break;
      case 'info-card':
        wx.navigateTo({ url: '/pages/care-info-card/index' });
        break;
      default:
        break;
    }
  },
});
