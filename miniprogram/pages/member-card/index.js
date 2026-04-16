const { get } = require('../../utils/request');

Page({
  data: {
    userInfo: null,
    qrCodeUrl: '',
    qrExpireTime: 60,
    loading: true
  },

  _timer: null,

  onLoad() {
    const app = getApp();
    this.setData({ userInfo: app.getUserInfo() });
    this.loadQrCode();
    this.startRefreshTimer();
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
