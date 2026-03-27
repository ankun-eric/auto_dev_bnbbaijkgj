const { post } = require('../../utils/request');
const app = getApp();

Page({
  data: {
    phone: '',
    code: '',
    agreed: false,
    codeCooldown: 0
  },

  _timer: null,

  onUnload() {
    if (this._timer) clearInterval(this._timer);
  },

  onPhoneInput(e) {
    this.setData({ phone: e.detail.value });
  },

  onCodeInput(e) {
    this.setData({ code: e.detail.value });
  },

  toggleAgreement() {
    this.setData({ agreed: !this.data.agreed });
  },

  async sendCode() {
    const { phone, codeCooldown } = this.data;
    if (codeCooldown > 0) return;
    if (!phone || phone.length !== 11) {
      wx.showToast({ title: '请输入正确的手机号', icon: 'none' });
      return;
    }

    try {
      // await post('/api/auth/sms-code', { phone, type: 'login' });
      wx.showToast({ title: '验证码已发送', icon: 'success' });
      this.setData({ codeCooldown: 60 });
      this._timer = setInterval(() => {
        if (this.data.codeCooldown <= 1) {
          clearInterval(this._timer);
          this.setData({ codeCooldown: 0 });
        } else {
          this.setData({ codeCooldown: this.data.codeCooldown - 1 });
        }
      }, 1000);
    } catch (e) {
      console.log('sendCode error', e);
    }
  },

  async loginByPhone() {
    const { phone, code, agreed } = this.data;
    if (!agreed) {
      wx.showToast({ title: '请先同意用户协议', icon: 'none' });
      return;
    }
    if (!phone || phone.length !== 11) {
      wx.showToast({ title: '请输入正确的手机号', icon: 'none' });
      return;
    }
    if (!code || code.length < 4) {
      wx.showToast({ title: '请输入验证码', icon: 'none' });
      return;
    }

    wx.showLoading({ title: '登录中...' });
    try {
      // const res = await post('/api/auth/sms-login', { phone, code });
      const mockData = {
        token: 'mock_token_' + Date.now(),
        userInfo: { nickname: '健康用户', phone, avatar: '', memberLevel: '普通会员' }
      };
      app.setLoginInfo(mockData.token, mockData.userInfo);
      wx.hideLoading();
      wx.showToast({ title: '登录成功', icon: 'success' });
      setTimeout(() => {
        wx.switchTab({ url: '/pages/home/index' });
      }, 1500);
    } catch (e) {
      wx.hideLoading();
      console.log('login error', e);
    }
  },

  loginByWechat() {
    if (!this.data.agreed) {
      wx.showToast({ title: '请先同意用户协议', icon: 'none' });
      return;
    }

    wx.showLoading({ title: '登录中...' });
    wx.login({
      success: async (loginRes) => {
        try {
          // const res = await post('/api/auth/wx-login', { code: loginRes.code });
          const mockData = {
            token: 'wx_token_' + Date.now(),
            userInfo: { nickname: '微信用户', avatar: '', memberLevel: '普通会员' }
          };
          app.setLoginInfo(mockData.token, mockData.userInfo);
          wx.hideLoading();
          wx.showToast({ title: '登录成功', icon: 'success' });
          setTimeout(() => {
            wx.switchTab({ url: '/pages/home/index' });
          }, 1500);
        } catch (e) {
          wx.hideLoading();
          console.log('wx login error', e);
        }
      },
      fail() {
        wx.hideLoading();
        wx.showToast({ title: '微信登录失败', icon: 'none' });
      }
    });
  },

  showAgreement(e) {
    const type = e.currentTarget.dataset.type;
    wx.showModal({
      title: type === 'user' ? '用户服务协议' : '隐私政策',
      content: '协议内容正在完善中，请稍后查看。',
      showCancel: false
    });
  }
});
