// 默认指向当前项目部署根路径；request.js 中各接口自行追加 /api/...。
const DEFAULT_API_BASE_URL = 'https://newbb.bangbangvip.com/autodev/3b7b999d-e51c-4c0d-8f6e-baf90cd26857';

App({
  onLaunch() {
    this.checkLoginStatus();
  },

  checkLoginStatus() {
    const token = wx.getStorageSync('token');
    const userInfo = wx.getStorageSync('userInfo');
    const sessionContext = wx.getStorageSync('sessionContext');
    const currentRole = wx.getStorageSync('currentRole');
    const merchantProfile = wx.getStorageSync('merchantProfile');
    if (token && userInfo) {
      this.globalData.token = token;
      this.globalData.userInfo = userInfo;
      this.globalData.sessionContext = sessionContext || null;
      this.globalData.currentRole = currentRole || this.getDefaultRole(sessionContext || null);
      this.globalData.merchantProfile = merchantProfile || null;
      this.globalData.isLoggedIn = true;
    }
  },

  getDefaultRole(sessionContext) {
    if (!sessionContext) return 'user';
    if (sessionContext.is_dual_identity) return 'user';
    if (sessionContext.can_access_merchant && !sessionContext.can_access_user) return 'merchant';
    return 'user';
  },

  getUserInfo() {
    return this.globalData.userInfo;
  },

  getMerchantProfile() {
    return this.globalData.merchantProfile;
  },

  getToken() {
    return this.globalData.token;
  },

  getSessionContext() {
    return this.globalData.sessionContext || {};
  },

  hasUserIdentity() {
    const sessionContext = this.getSessionContext();
    return !!sessionContext.can_access_user;
  },

  hasMerchantIdentity() {
    const sessionContext = this.getSessionContext();
    return !!sessionContext.can_access_merchant;
  },

  isDualIdentity() {
    const sessionContext = this.getSessionContext();
    return !!sessionContext.is_dual_identity;
  },

  getCurrentRole() {
    const currentRole = this.globalData.currentRole;
    if (currentRole === 'merchant' && !this.hasMerchantIdentity()) {
      return this.hasUserIdentity() ? 'user' : '';
    }
    if (currentRole === 'user' && !this.hasUserIdentity()) {
      return this.hasMerchantIdentity() ? 'merchant' : '';
    }
    return currentRole || this.getDefaultRole(this.getSessionContext());
  },

  setCurrentRole(role, options = {}) {
    const { persist = true } = options;
    this.globalData.currentRole = role;
    if (persist) {
      wx.setStorageSync('currentRole', role);
    }
    if (role !== 'merchant') {
      this.clearCurrentStore();
    }
  },

  setCurrentStore(store) {
    this.globalData.currentStore = store || null;
  },

  getCurrentStore() {
    return this.globalData.currentStore;
  },

  clearCurrentStore() {
    this.globalData.currentStore = null;
  },

  setMerchantProfile(profile) {
    this.globalData.merchantProfile = profile || null;
    if (profile) {
      wx.setStorageSync('merchantProfile', profile);
    } else {
      wx.removeStorageSync('merchantProfile');
    }
  },

  setLoginInfo(token, userInfo, options = {}) {
    const {
      sessionContext = null,
      merchantProfile = null,
      currentRole = ''
    } = options;
    this.globalData.token = token;
    this.globalData.userInfo = userInfo;
    this.globalData.sessionContext = sessionContext;
    this.globalData.currentRole = currentRole || this.getDefaultRole(sessionContext);
    this.globalData.merchantProfile = merchantProfile || null;
    this.globalData.isLoggedIn = true;
    wx.setStorageSync('token', token);
    wx.setStorageSync('userInfo', userInfo);
    if (sessionContext) {
      wx.setStorageSync('sessionContext', sessionContext);
    } else {
      wx.removeStorageSync('sessionContext');
    }
    if (this.globalData.currentRole) {
      wx.setStorageSync('currentRole', this.globalData.currentRole);
    }
    if (merchantProfile) {
      wx.setStorageSync('merchantProfile', merchantProfile);
    } else {
      wx.removeStorageSync('merchantProfile');
    }
    this.clearCurrentStore();
  },

  logout() {
    this.globalData.token = '';
    this.globalData.userInfo = null;
    this.globalData.sessionContext = null;
    this.globalData.currentRole = '';
    this.globalData.currentStore = null;
    this.globalData.merchantProfile = null;
    this.globalData.isLoggedIn = false;
    wx.removeStorageSync('token');
    wx.removeStorageSync('userInfo');
    wx.removeStorageSync('sessionContext');
    wx.removeStorageSync('currentRole');
    wx.removeStorageSync('merchantProfile');
  },

  globalData: {
    baseUrl: DEFAULT_API_BASE_URL,
    token: '',
    userInfo: null,
    sessionContext: null,
    currentRole: '',
    currentStore: null,
    merchantProfile: null,
    isLoggedIn: false
  }
});
