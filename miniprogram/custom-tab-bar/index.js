const userTabs = [
  { pagePath: '/pages/home/index', text: '首页', icon: '🏠' },
  { pagePath: '/pages/ai/index', text: 'AI健康咨询', icon: '🤖' },
  { pagePath: '/pages/services/index', text: '服务', icon: '🧰' },
  { pagePath: '/pages/profile/index', text: '我的', icon: '👤' }
];

const merchantTabs = [
  { pagePath: '/pages/home/index', text: '工作台', icon: '🏪' },
  { pagePath: '/pages/ai/index', text: '扫码核销', icon: '📷' },
  { pagePath: '/pages/services/index', text: '核销记录', icon: '📋' },
  { pagePath: '/pages/profile/index', text: '我的', icon: '👤' }
];

Component({
  data: {
    selected: '/pages/home/index',
    tabs: userTabs,
    currentRole: 'user'
  },

  methods: {
    refreshTabs() {
      const app = getApp();
      const currentRole = app.getCurrentRole() || 'user';
      this.setData({
        currentRole,
        tabs: currentRole === 'merchant' ? merchantTabs : userTabs
      });
    },

    switchTab(e) {
      const { path } = e.currentTarget.dataset;
      if (!path) return;
      wx.switchTab({ url: path });
    }
  },

  attached() {
    this.refreshTabs();
  }
});
