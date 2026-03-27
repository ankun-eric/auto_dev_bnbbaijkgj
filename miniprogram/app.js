// 默认指向当前项目部署根路径；request.js 中各接口自行追加 /api/...。
const DEFAULT_API_BASE_URL = 'https://newbb.bangbangvip.com/autodev/3b7b999d-e51c-4c0d-8f6e-baf90cd26857';

App({
  onLaunch() {
    this.checkLoginStatus();
  },

  checkLoginStatus() {
    const token = wx.getStorageSync('token');
    const userInfo = wx.getStorageSync('userInfo');
    if (token && userInfo) {
      this.globalData.token = token;
      this.globalData.userInfo = userInfo;
      this.globalData.isLoggedIn = true;
    }
  },

  getUserInfo() {
    return this.globalData.userInfo;
  },

  getToken() {
    return this.globalData.token;
  },

  setLoginInfo(token, userInfo) {
    this.globalData.token = token;
    this.globalData.userInfo = userInfo;
    this.globalData.isLoggedIn = true;
    wx.setStorageSync('token', token);
    wx.setStorageSync('userInfo', userInfo);
  },

  logout() {
    this.globalData.token = '';
    this.globalData.userInfo = null;
    this.globalData.isLoggedIn = false;
    wx.removeStorageSync('token');
    wx.removeStorageSync('userInfo');
  },

  globalData: {
    baseUrl: DEFAULT_API_BASE_URL,
    token: '',
    userInfo: null,
    isLoggedIn: false
  }
});
