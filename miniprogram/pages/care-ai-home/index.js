// [PRD-CARE-AI-HOME 2026-05-27] 关怀模式 AI 主页 v1
const { get, post } = require('../../utils/request');

function getGreeting(now) {
  const h = now.getHours();
  if (h >= 5 && h < 11) return '早上好 ☀️';
  if (h >= 11 && h < 18) return '中午好 ☀️';
  return '晚上好 🌙';
}

function statusColor(status) {
  if (status === '偏高') return '#E53935';
  if (status === '偏低') return '#FB8C00';
  return '#43A047';
}

Page({
  data: {
    greeting: '',
    summary: null,
    metrics: [],
    alerts: [],
    medication: null,
    drawerOpen: false,
    toast: '',
    loading: true,
  },

  onLoad() {
    this.setData({ greeting: getGreeting(new Date()) });
    this.loadAll();
  },

  onShow() {
    this.loadAll();
  },

  loadAll() {
    this.setData({ loading: true });
    Promise.all([
      get('/api/care/daily-summary').catch(() => null),
      get('/api/care/alerts/active').catch(() => null),
      get('/api/medication-reminder/today').catch(() => null),
    ]).then(([sumR, alertR, medR]) => {
      const sum = sumR && sumR.data ? sumR.data : null;
      const metrics = (sum && sum.metrics) || [];
      metrics.forEach((m) => {
        m.statusColor = statusColor(m.status);
      });
      const alerts = (alertR && alertR.data && alertR.data.alerts) || [];
      const medItems = (medR && (medR.data && (medR.data.items || medR.items))) || [];
      const nextMed = medItems.find((it) => !it.done) || null;
      this.setData({
        summary: sum,
        metrics,
        alerts,
        medication: nextMed,
        loading: false,
      });
    });
  },

  navigate(e) {
    const url = e.currentTarget.dataset.url;
    if (!url) return;
    wx.navigateTo({ url, fail: () => wx.switchTab({ url }).catch(() => {}) });
  },

  takePhoto() {
    wx.chooseImage({
      count: 1,
      sourceType: ['camera'],
      success: () => {
        wx.navigateTo({ url: '/pages/ai/index?action=photo' });
      },
    });
  },

  openDrawer() {
    this.setData({ drawerOpen: true });
  },

  closeDrawer() {
    this.setData({ drawerOpen: false });
  },

  switchMode() {
    wx.navigateTo({ url: '/pages/welcome-mode/index' });
  },

  callFamily() {
    wx.makePhoneCall({ phoneNumber: '120', fail: () => {} });
  },

  showToast(msg) {
    wx.showToast({ title: msg, icon: 'none' });
  },

  onSosFabTap() {
    this.showToast('SOS 功能即将上线');
  },

  onMedDone() {
    const m = this.data.medication;
    if (m && m.id) {
      post(`/api/medication-reminder/items/${m.id}/check`, {}).catch(() => {});
    }
    this.setData({ medication: null });
    this.showToast('已记录');
  },

  onMedPostpone(e) {
    const minutes = e.currentTarget.dataset.minutes;
    this.showToast(`已推迟 ${minutes} 分钟`);
  },

  onDismissAlert(e) {
    const id = e.currentTarget.dataset.id;
    post(`/api/care/alerts/${id}/dismiss`, {}).catch(() => {});
    const remain = this.data.alerts.filter((a) => a.id !== id);
    this.setData({ alerts: remain });
  },

  goAiChat() {
    wx.navigateTo({ url: '/pages/ai/index' });
  },

  goHealthDashboard() {
    wx.navigateTo({ url: '/pages/checkup/index' });
  },

  goMedication() {
    wx.navigateTo({ url: '/pages/medication-reminder/index' }).catch(() => {
      wx.navigateTo({ url: '/pages/ai/index' });
    });
  },
});
