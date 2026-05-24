const { get } = require('../../utils/request');

Page({
  data: {
    userInfo: null,
    qrCodeUrl: '',
    qrExpireTime: 60,
    loading: true,
    // [付费会员体系 PRD v1.1] 付费会员套餐替代旧"积分会员等级"
    isPaidMember: false,
    membershipPlanName: ''
  },

  _timer: null,

  onLoad() {
    const app = getApp();
    this.setData({ userInfo: app.getUserInfo() });
    this.loadQrCode();
    this.loadMembership();
    this.startRefreshTimer();
  },

  /** [付费会员体系 PRD v1.1] 拉取当前付费会员套餐 */
  loadMembership() {
    get('/api/membership/me', {}, { showLoading: false, suppressErrorToast: true })
      .then(res => {
        const data = res.data || res;
        if (data && data.is_paid_member && data.plan_name) {
          this.setData({ isPaidMember: true, membershipPlanName: data.plan_name });
        } else {
          this.setData({ isPaidMember: false, membershipPlanName: '' });
        }
      })
      .catch(() => this.setData({ isPaidMember: false, membershipPlanName: '' }));
  },

  onUnload() {
    this.stopRefreshTimer();
  },

  onHide() {
    this.stopRefreshTimer();
  },

  onShow() {
    if (!this._timer) {
      this.startRefreshTimer();
    }
  },

  async loadQrCode() {
    try {
      const res = await get('/api/member/qrcode', {}, { showLoading: false });
      const data = res.data || res;
      this.setData({
        qrCodeUrl: data.qr_code_url || data.qrcode_url || '',
        qrExpireTime: 60,
        loading: false
      });
    } catch (e) {
      this.setData({ loading: false });
      console.log('loadQrCode error', e);
    }
  },

  startRefreshTimer() {
    this.stopRefreshTimer();
    this._timer = setInterval(() => {
      let t = this.data.qrExpireTime - 1;
      if (t <= 0) {
        this.loadQrCode();
        t = 60;
      }
      this.setData({ qrExpireTime: t });
    }, 1000);
  },

  stopRefreshTimer() {
    if (this._timer) {
      clearInterval(this._timer);
      this._timer = null;
    }
  },

  refreshQrCode() {
    this.loadQrCode();
  },

  previewQr() {
    if (!this.data.qrCodeUrl) return;
    wx.previewImage({ urls: [this.data.qrCodeUrl] });
  }
});
