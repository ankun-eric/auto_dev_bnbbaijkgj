// [PRD-AIHOME-CARE-V1 2026-05-27] 小程序关怀模式首页
const { get, post, put } = require('../../utils/request');

Page({
  data: {
    welcome: null,
    cards: null,
    showSwitch: false,
    sosStage: 0,
    sosCountdown: 5,
    sosEventId: null,
    sosCard: null,
    inputText: '',
  },

  onLoad() {
    this.loadAll();
  },

  onShow() {
    this.loadAll();
  },

  loadAll() {
    get('/api/care-v1/home/welcome')
      .then((r) => this.setData({ welcome: (r && r.data) || null }))
      .catch(() => {});
    get('/api/care-v1/home/proactive-cards')
      .then((r) => this.setData({ cards: (r && r.data) || null }))
      .catch(() => {});
  },

  goWelcome() {
    wx.navigateTo({ url: '/pages/welcome-mode/index' });
  },

  toggleSwitch() {
    this.setData({ showSwitch: !this.data.showSwitch });
  },

  switchMode(e) {
    const mode = e.currentTarget.dataset.mode;
    put('/api/care-v1/user-preferences/ui-mode', { ui_mode: mode })
      .catch(() => {});
    try { wx.setStorageSync('ui_mode', mode); } catch (_) {}
    this.setData({ showSwitch: false });
    if (mode === 'standard') {
      wx.switchTab({ url: '/pages/home/index' });
    }
  },

  goAi() {
    wx.switchTab({ url: '/pages/ai/index' });
  },

  goProfile() {
    wx.navigateTo({ url: '/pages/health-profile/index' });
  },

  goMed() {
    wx.navigateTo({ url: '/pages/health-plan/medications/index' });
  },

  goFamily() {
    wx.navigateTo({ url: '/pages/family/index' });
  },

  onQuickAsk(e) {
    const q = e.currentTarget.dataset.q;
    wx.switchTab({ url: '/pages/ai/index' });
  },

  onInput(e) {
    this.setData({ inputText: e.detail.value });
  },

  detectSosBlur() {
    const t = this.data.inputText;
    if (!t) return;
    post('/api/care-v1/sos/detect', { text: t })
      .then((r) => {
        const d = (r && r.data) || {};
        if (d.hit) {
          this.setData({
            sosCard: { keyword: (d.matched || []).join('、') },
          });
        }
      })
      .catch(() => {});
  },

  dismissSosCard() {
    this.setData({ sosCard: null });
  },

  confirmSosFromCard() {
    const kw = this.data.sosCard && this.data.sosCard.keyword;
    this.setData({ sosCard: null });
    this.startSos('keyword_combo', kw);
  },

  onSosBall() {
    this.startSos('floating_button', null);
  },

  startSos(source, keyword) {
    this.setData({ sosStage: 1, sosCountdown: 5 });
    post('/api/care-v1/sos/events', {
      trigger_source: source,
      trigger_keyword: keyword,
    })
      .then((r) => {
        const d = (r && r.data) || {};
        this.setData({ sosEventId: d.id || null });
      })
      .catch(() => {});
    this._countdownTimer = setInterval(() => {
      let c = this.data.sosCountdown - 1;
      if (c <= 0) {
        clearInterval(this._countdownTimer);
        this.setData({ sosStage: 2, sosCountdown: 0 });
      } else {
        this.setData({ sosCountdown: c });
      }
    }, 1000);
  },

  cancelSos() {
    if (this._countdownTimer) clearInterval(this._countdownTimer);
    const id = this.data.sosEventId;
    if (id) {
      put(`/api/care-v1/sos/events/${id}/resolve`, {
        status: 'cancelled',
        countdown_remaining_ms: this.data.sosCountdown * 1000,
      }).catch(() => {});
    }
    this.setData({ sosStage: 0, sosEventId: null });
  },

  dispatch120() {
    const id = this.data.sosEventId;
    if (id) {
      put(`/api/care-v1/sos/events/${id}/resolve`, { status: 'dispatched_120' }).catch(() => {});
    }
    this.setData({ sosStage: 3 });
    setTimeout(() => this.setData({ sosStage: 4 }), 2000);
  },

  dispatchFamily() {
    const id = this.data.sosEventId;
    if (id) {
      put(`/api/care-v1/sos/events/${id}/resolve`, { status: 'dispatched_family' }).catch(() => {});
    }
    this.setData({ sosStage: 3 });
    setTimeout(() => this.setData({ sosStage: 4 }), 2000);
  },

  closeSos() {
    const id = this.data.sosEventId;
    if (id) {
      put(`/api/care-v1/sos/events/${id}/resolve`, { status: 'closed' }).catch(() => {});
    }
    this.setData({ sosStage: 0, sosEventId: null });
  },

  onUnload() {
    if (this._countdownTimer) clearInterval(this._countdownTimer);
  },
});
