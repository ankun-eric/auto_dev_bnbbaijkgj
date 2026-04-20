const { get, post } = require('../../utils/request');
const { syncTabBar } = require('../../utils/util');

// Bug-1/Bug-3 策略：移除默认 Banner 与硬编码菜单，完全以后端返回为准
const DEFAULT_CONFIG = {
  search_visible: true,
  search_placeholder: '想找什么服务/商品？',
  grid_columns: 3,
  font_switch_enabled: false,
  font_default_level: 'standard',
  font_standard_size: 28,
  font_large_size: 34,
  font_xlarge_size: 40
};

// 刷新节流（30s），用于 onShow 高频触发时避免重复拉取
const REFRESH_THROTTLE_MS = 30 * 1000;

Page({
  data: {
    pageMode: 'user',
    canSwitchRole: false,
    currentStore: null,
    merchantUserName: '',
    todayCount: 0,
    todayAmount: '0.00',
    banners: [],
    menuItems: [],
    homeConfig: DEFAULT_CONFIG,
    gridColumnWidth: '33.33%',
    cityName: '定位',
    cityId: null,
    locating: false,
    todoGroups: [],
    todoTotalCompleted: 0,
    todoTotalCount: 0,
    todayTodosLoading: false,
    checkinDialog: false,
    checkinDialogType: '',
    checkinDialogId: 0,
    checkinDialogSourceId: 0,
    checkinDialogName: '',
    checkinDialogTarget: 0,
    checkinDialogUnit: '',
    checkinDialogValue: '',
    healthTips: [
      { id: 1, content: '今日气温变化大，注意添衣保暖' },
      { id: 2, content: '建议每天饮水 2000ml 以上' }
    ],
    articles: [],
    unreadCount: 0,
    loading: false,
    statusBarHeight: 20,
    navBarHeight: 64,
    brandLogoUrl: ''
  },

  onLoad() {
    const sysInfo = wx.getSystemInfoSync();
    const statusBarHeight = sysInfo.statusBarHeight || 20;
    const navBarHeight = statusBarHeight + 44;
    this.setData({ statusBarHeight, navBarHeight });
    this._lastRefreshAt = 0;
    this.tryGPSLocate();
  },

  onShow() {
    syncTabBar(this, '/pages/home/index');
    this.loadSelectedCity();
    const app = getApp();
    this.setData({ brandLogoUrl: app.globalData.brandLogoUrl || '' });
    if (!this.syncRoleState()) return;
    // Bug-2 策略：onShow 触发刷新，但加 30s 节流避免频繁请求
    const now = Date.now();
    if (!this._lastRefreshAt || now - this._lastRefreshAt >= REFRESH_THROTTLE_MS) {
      this._lastRefreshAt = now;
      this.loadCurrentModeData();
    }
  },

  onPullDownRefresh() {
    if (!this.syncRoleState()) {
      wx.stopPullDownRefresh();
      return;
    }
    this._lastRefreshAt = Date.now();
    this.loadCurrentModeData().finally(() => wx.stopPullDownRefresh());
  },

  syncRoleState() {
    const app = getApp();
    const pageMode = app.getCurrentRole() || 'user';
    if (pageMode === 'merchant') {
      if (!app.hasMerchantIdentity()) {
        wx.navigateTo({ url: '/pages/no-permission/index?scene=merchant' });
        return false;
      }
      if (!app.getCurrentStore()) {
        wx.navigateTo({ url: '/pages/store-select/index' });
        return false;
      }
    } else if (app.globalData.isLoggedIn && !app.hasUserIdentity()) {
      wx.navigateTo({ url: '/pages/no-permission/index?scene=user' });
      return false;
    }

    const merchantProfile = app.getMerchantProfile() || {};
    this.setData({
      pageMode,
      canSwitchRole: app.isDualIdentity(),
      currentStore: app.getCurrentStore(),
      merchantUserName: merchantProfile.nickname || (app.getUserInfo() || {}).nickname || '工作人员'
    });
    return true;
  },

  loadCurrentModeData() {
    if (this.data.pageMode === 'merchant') {
      return this.loadMerchantDashboard();
    }
    return this.loadUserData();
  },

  async loadUserData() {
    this.setData({ loading: true });
    try {
      await Promise.all([
        this.loadHomeConfig(),
        this.loadBanners(),
        this.loadMenus(),
        this.loadArticles(),
        this.loadTodayTodos(),
        this.loadUnreadCount()
      ]);
    } finally {
      this.setData({ loading: false });
    }
  },

  async loadHomeConfig() {
    try {
      const res = await get('/api/home-config', {}, { showLoading: false, suppressErrorToast: true });
      const config = { ...DEFAULT_CONFIG, ...res };
      const gridColumnWidth = (100 / (config.grid_columns || 3)).toFixed(2) + '%';
      this.setData({ homeConfig: config, gridColumnWidth });
    } catch (e) {
      this.setData({ homeConfig: DEFAULT_CONFIG, gridColumnWidth: '33.33%' });
    }
  },

  async loadBanners() {
    try {
      const res = await get('/api/home-banners', {}, { showLoading: false, suppressErrorToast: true });
      const items = (res && Array.isArray(res.items)) ? res.items : [];
      this.setData({ banners: items });
    } catch (e) {
      this.setData({ banners: [] });
    }
  },

  async loadMenus() {
    try {
      const res = await get('/api/home-menus', {}, { showLoading: false, suppressErrorToast: true });
      const items = (res && Array.isArray(res.items)) ? res.items : [];
      this.setData({ menuItems: items });
    } catch (e) {
      this.setData({ menuItems: [] });
    }
  },

  async loadArticles() {
    try {
      const res = await get('/api/content/articles', { page: 1, page_size: 3 }, { showLoading: false, suppressErrorToast: true });
      const items = (res && Array.isArray(res.items)) ? res.items : [];
      const mapped = items.map((a) => ({
        id: a.id,
        title: a.title || '',
        tag: a.category || '健康',
        time: this._formatArticleTime(a.created_at),
        cover: a.cover_image || '',
        views: a.view_count || 0
      }));
      this.setData({ articles: mapped });
    } catch (e) {
      this.setData({ articles: [] });
    }
  },

  _formatArticleTime(createdAt) {
    if (!createdAt) return '';
    const t = new Date(createdAt);
    if (isNaN(t.getTime())) return '';
    const diffMs = Date.now() - t.getTime();
    const diffH = Math.floor(diffMs / (60 * 60 * 1000));
    if (diffH < 1) return '刚刚';
    if (diffH < 24) return `${diffH}小时前`;
    const diffD = Math.floor(diffH / 24);
    if (diffD < 30) return `${diffD}天前`;
    return t.toLocaleDateString();
  },

  onBannerTap(e) {
    const item = e.currentTarget.dataset.item;
    if (!item) return;
    this.handleLink(item);
  },

  onMenuTap(e) {
    if (this.data.pageMode !== 'user') return;
    const item = e.currentTarget.dataset.item;
    if (!item) return;
    this.handleLink(item);
  },

  handleLink(item) {
    const linkType = item.link_type;
    const linkUrl = item.link_url || item.path || '';
    if (linkType === 'internal' && linkUrl) {
      wx.navigateTo({
        url: linkUrl,
        fail() {
          wx.switchTab({ url: linkUrl });
        }
      });
    } else if (linkType === 'external' && linkUrl) {
      wx.setClipboardData({
        data: linkUrl,
        success() {
          wx.showToast({ title: '链接已复制', icon: 'success' });
        }
      });
    } else if (linkType === 'miniprogram' && item.miniprogram_appid) {
      wx.navigateToMiniProgram({
        appId: item.miniprogram_appid,
        path: linkUrl || '',
        fail() {
          wx.showToast({ title: '无法打开小程序', icon: 'none' });
        }
      });
    }
  },

  async loadTodayTodos() {
    this.setData({ todayTodosLoading: true });
    try {
      const res = await get('/api/health-plan/today-todos', {}, { showLoading: false, suppressErrorToast: true });
      if (res && res.groups) {
        this.setData({
          todoGroups: res.groups || [],
          todoTotalCompleted: res.total_completed || 0,
          todoTotalCount: res.total_count || 0,
        });
      } else {
        this.setData({ todoGroups: [], todoTotalCompleted: 0, todoTotalCount: 0 });
      }
    } catch (e) {
      this.setData({ todoGroups: [], todoTotalCompleted: 0, todoTotalCount: 0 });
    } finally {
      this.setData({ todayTodosLoading: false });
    }
  },

  onTodoCheckin(e) {
    const { type, id, sourceId, targetValue, targetUnit, name } = e.currentTarget.dataset;
    if (targetValue && targetValue > 0) {
      this.setData({
        checkinDialog: true,
        checkinDialogType: type,
        checkinDialogId: id,
        checkinDialogSourceId: sourceId,
        checkinDialogName: name || '',
        checkinDialogTarget: targetValue,
        checkinDialogUnit: targetUnit || '',
        checkinDialogValue: '',
      });
      return;
    }
    this.doCheckin(type, id, sourceId, null);
  },

  onCheckinDialogInput(e) {
    this.setData({ checkinDialogValue: e.detail.value });
  },

  onCheckinDialogCancel() {
    this.setData({ checkinDialog: false });
  },

  onCheckinDialogConfirm() {
    const { checkinDialogType, checkinDialogId, checkinDialogSourceId, checkinDialogValue } = this.data;
    const val = checkinDialogValue ? parseFloat(checkinDialogValue) : null;
    this.setData({ checkinDialog: false });
    this.doCheckin(checkinDialogType, checkinDialogId, checkinDialogSourceId, val);
  },

  async doCheckin(type, id, sourceId, value) {
    let url = '';
    let body = {};
    if (type === 'medication') {
      url = `/api/health-plan/medications/${id}/checkin`;
    } else if (type === 'checkin') {
      url = `/api/health-plan/checkin-items/${id}/checkin`;
      if (value != null) body.actual_value = value;
    } else if (type === 'plan_task') {
      url = `/api/health-plan/user-plans/${sourceId}/tasks/${id}/checkin`;
      if (value != null) body.actual_value = value;
    }
    if (!url) return;
    try {
      await post(url, body);
      wx.showToast({ title: '打卡成功', icon: 'success' });
      this.loadTodayTodos();
    } catch (e) {
      // error toast handled by request
    }
  },

  goHealthPlan() {
    wx.navigateTo({ url: '/pages/health-plan/index' });
  },

  async loadMerchantDashboard() {
    const currentStore = this.data.currentStore;
    if (!currentStore) return Promise.resolve();
    this.setData({ loading: true });
    try {
      const res = await get('/api/merchant/dashboard', { store_id: currentStore.id }, { showLoading: false });
      this.setData({
        todayCount: res.today_count || 0,
        todayAmount: Number(res.today_amount || 0).toFixed(2)
      });
    } catch (e) {
      wx.showToast({ title: e.detail || '商家数据加载失败', icon: 'none' });
    } finally {
      this.setData({ loading: false });
    }
  },

  switchRole() {
    const app = getApp();
    if (!app.isDualIdentity()) return;
    const currentRole = this.data.pageMode;
    const targetRole = currentRole === 'merchant' ? 'user' : 'merchant';
    const targetLabel = targetRole === 'merchant' ? '商家端' : '用户端';
    wx.showModal({
      title: '切换角色',
      content: `确认切换到${targetLabel}吗？`,
      success: (res) => {
        if (!res.confirm) return;
        app.setCurrentRole(targetRole);
        if (targetRole === 'merchant') {
          app.clearCurrentStore();
          wx.navigateTo({ url: '/pages/store-select/index' });
          return;
        }
        wx.switchTab({ url: '/pages/home/index' });
      }
    });
  },

  loadSelectedCity() {
    const savedId = wx.getStorageSync('selected_city_id');
    const savedName = wx.getStorageSync('selected_city_name');
    if (savedId && savedName) {
      this.setData({ cityId: savedId, cityName: savedName });
    }
  },

  tryGPSLocate() {
    const cached = wx.getStorageSync('gps_city_cache');
    if (cached && cached.expire > Date.now()) {
      if (!wx.getStorageSync('selected_city_id')) {
        this.setData({ cityId: cached.id, cityName: cached.name });
      }
      return;
    }

    this.setData({ locating: true });
    wx.getLocation({
      type: 'gcj02',
      success: (res) => {
        this.locateByCoords(res.longitude, res.latitude);
      },
      fail: () => {
        this.setData({ locating: false });
        if (!this.data.cityId) {
          this.setData({ cityName: '定位' });
        }
      }
    });
  },

  async locateByCoords(lng, lat) {
    try {
      const res = await get('/api/cities/locate', { lng, lat }, { showLoading: false, suppressErrorToast: true });
      const city = res && res.city ? res.city : res;
      if (city && city.id && city.name) {
        const cacheData = { id: city.id, name: city.name, expire: Date.now() + 30 * 60 * 1000 };
        wx.setStorageSync('gps_city_cache', cacheData);
        if (!wx.getStorageSync('selected_city_id')) {
          this.setData({ cityId: city.id, cityName: city.name });
        }
      }
    } catch (e) {
      // keep current city state
    } finally {
      this.setData({ locating: false });
    }
  },

  onCityTap() {
    wx.navigateTo({ url: '/pages/city-select/index' });
  },

  onSearchTap() {
    if (this.data.pageMode !== 'user') return;
    wx.navigateTo({ url: '/pages/search/index' });
  },

  goNotifications() {
    if (this.data.pageMode === 'merchant') {
      wx.navigateTo({ url: '/pages/merchant-messages/index' });
      return;
    }
    wx.navigateTo({ url: '/pages/notifications/index' });
  },

  goArticles() {
    wx.navigateTo({ url: '/pages/articles/index' });
  },

  goArticleDetail(e) {
    const id = e.currentTarget.dataset.id;
    wx.navigateTo({ url: `/pages/article-detail/index?id=${id}` });
  },

  async loadUnreadCount() {
    try {
      const res = await get('/api/messages/unread-count', {}, { showLoading: false, suppressErrorToast: true });
      if (res && typeof res.unread_count === 'number') {
        this.setData({ unreadCount: res.unread_count });
      }
    } catch (e) {
      // keep current count
    }
  },

  onScanTap() {
    wx.scanCode({
      onlyFromCamera: false,
      success: (res) => {
        const result = res.result || '';

        const familyAuthMatch = result.match(/\/family-auth\?code=([^&]+)/);
        if (familyAuthMatch && familyAuthMatch[1]) {
          wx.navigateTo({ url: `/pages/family-auth/index?code=${familyAuthMatch[1]}` });
          return;
        }

        const oldMatch = result.match(/type=family_invite&code=([^&]+)/);
        if (oldMatch && oldMatch[1]) {
          wx.navigateTo({ url: `/pages/family-auth/index?code=${oldMatch[1]}` });
          return;
        }

        wx.showToast({ title: '无法识别该二维码', icon: 'none' });
      },
      fail: () => {}
    });
  },

  goMessages() {
    wx.navigateTo({ url: '/pages/messages/index' });
  },

  goScan() {
    wx.switchTab({ url: '/pages/ai/index' });
  },

  goRecords() {
    wx.switchTab({ url: '/pages/services/index' });
  },

  goInvite() {
    wx.navigateTo({ url: '/pages/invite/index' });
  },

  onShareAppMessage() {
    const userInfo = getApp().getUserInfo() || {};
    const userNo = userInfo.user_no || '';
    return {
      title: '宾尼小康 — AI健康管家，守护你的健康',
      path: userNo ? `/pages/login/index?ref=${userNo}` : '/pages/home/index',
      imageUrl: ''
    };
  }
});
