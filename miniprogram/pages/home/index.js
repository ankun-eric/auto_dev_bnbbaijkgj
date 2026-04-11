const { get, post } = require('../../utils/request');
const { syncTabBar } = require('../../utils/util');

const DEFAULT_BANNERS = [
  { id: 1, title: 'AI健康咨询', desc: '24小时在线，专业健康咨询', bgColor: 'linear-gradient(135deg, #52c41a, #13c2c2)', image_url: '', link_type: 'none' },
  { id: 2, title: '体检报告解读', desc: '上传报告，AI秒级分析', bgColor: 'linear-gradient(135deg, #13c2c2, #1890ff)', image_url: '', link_type: 'none' },
  { id: 3, title: '中医智能辨证', desc: '舌诊面诊，科学辨体质', bgColor: 'linear-gradient(135deg, #722ed1, #eb2f96)', image_url: '', link_type: 'none' }
];

const DEFAULT_MENUS = [
  { id: 'ai', name: 'AI健康咨询', icon_type: 'emoji', icon_content: '🤖', link_type: 'internal', link_url: '/pages/chat/index?type=health_qa', sort_order: 0 },
  { id: 'checkup', name: '体检报告', icon_type: 'emoji', icon_content: '📋', link_type: 'internal', link_url: '/pages/checkup/index', sort_order: 1 },
  { id: 'symptom', name: '症状自查', icon_type: 'emoji', icon_content: '🩺', link_type: 'internal', link_url: '/pages/symptom/index', sort_order: 2 },
  { id: 'tcm', name: '中医辨证', icon_type: 'emoji', icon_content: '🌿', link_type: 'internal', link_url: '/pages/tcm/index', sort_order: 3 },
  { id: 'drug', name: '用药参考', icon_type: 'emoji', icon_content: '💊', link_type: 'internal', link_url: '/pages/drug/index', sort_order: 4 },
  { id: 'plan', name: '健康计划', icon_type: 'emoji', icon_content: '📅', link_type: 'internal', link_url: '/pages/health-plan/index', sort_order: 5 }
];

const DEFAULT_CONFIG = {
  search_visible: true,
  search_placeholder: '搜索症状、药品、健康知识...',
  grid_columns: 3,
  font_switch_enabled: false,
  font_default_level: 'standard',
  font_standard_size: 28,
  font_large_size: 34,
  font_xlarge_size: 40
};

Page({
  data: {
    pageMode: 'user',
    canSwitchRole: false,
    currentStore: null,
    merchantUserName: '',
    todayCount: 0,
    todayAmount: '0.00',
    banners: DEFAULT_BANNERS,
    menuItems: DEFAULT_MENUS,
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
    articles: [
      { id: 1, title: '春季养生：如何预防过敏性鼻炎', tag: '养生', time: '2小时前', cover: '' },
      { id: 2, title: '高血压患者饮食指南：这些食物要少吃', tag: '饮食', time: '5小时前', cover: '' },
      { id: 3, title: '运动健身：适合上班族的5分钟锻炼法', tag: '运动', time: '1天前', cover: '' }
    ],
    unreadCount: 0,
    loading: false,
    statusBarHeight: 20,
    navBarHeight: 64
  },

  onLoad() {
    const sysInfo = wx.getSystemInfoSync();
    const statusBarHeight = sysInfo.statusBarHeight || 20;
    const navBarHeight = statusBarHeight + 44;
    this.setData({ statusBarHeight, navBarHeight });
    this.tryGPSLocate();
  },

  onShow() {
    syncTabBar(this, '/pages/home/index');
    this.loadSelectedCity();
    if (!this.syncRoleState()) return;
    this.loadCurrentModeData();
  },

  onPullDownRefresh() {
    if (!this.syncRoleState()) {
      wx.stopPullDownRefresh();
      return;
    }
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
      if (res && res.items && res.items.length > 0) {
        this.setData({ banners: res.items });
      }
    } catch (e) {
      // keep default banners
    }
  },

  async loadMenus() {
    try {
      const res = await get('/api/home-menus', {}, { showLoading: false, suppressErrorToast: true });
      if (res && res.items && res.items.length > 0) {
        this.setData({ menuItems: res.items });
      }
    } catch (e) {
      // keep default menus
    }
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
        const match = result.match(/type=family_invite&code=([^&]+)/);
        if (match && match[1]) {
          wx.navigateTo({ url: `/pages/family-auth/index?code=${match[1]}` });
        } else {
          wx.showToast({ title: '无法识别该二维码', icon: 'none' });
        }
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
  }
});
