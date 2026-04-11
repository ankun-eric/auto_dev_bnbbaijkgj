const { get, put } = require('../../utils/request');

const TAB_TYPE_MAP = ['', 'system', 'order', 'health'];
const TYPE_ICON_MAP = {
  system: { icon: '📢', bgColor: 'rgba(24,144,255,0.12)' },
  order: { icon: '✅', bgColor: 'rgba(19,194,194,0.12)' },
  health: { icon: '❤️', bgColor: 'rgba(255,77,79,0.12)' },
  promotion: { icon: '🎯', bgColor: 'rgba(250,173,20,0.12)' }
};

Page({
  data: {
    currentTab: 0,
    notifications: []
  },

  onShow() {
    this.loadData();
  },

  switchTab(e) {
    this.setData({ currentTab: e.currentTarget.dataset.index }, () => this.loadData());
  },

  async loadData() {
    try {
      const res = await get('/api/messages', {}, { showLoading: false });
      const targetType = TAB_TYPE_MAP[this.data.currentTab];
      const notifications = (res.items || [])
        .filter((item) => !targetType || item.message_type === targetType)
        .map((item) => {
          const style = TYPE_ICON_MAP[item.message_type] || { icon: '🔔', bgColor: 'rgba(82,196,26,0.12)' };
          return {
            ...item,
            read: item.is_read,
            time: item.created_at,
            icon: style.icon,
            bgColor: style.bgColor
          };
        });
      this.setData({ notifications });
    } catch (e) {
      wx.showToast({ title: e.detail || '消息加载失败', icon: 'none' });
    }
  },

  async readNotify(e) {
    const item = e.currentTarget.dataset.item;
    if (!item || item.read) return;
    try {
      await put(`/api/messages/${item.id}/read`, {});
      this.loadData();
    } catch (e2) {
      wx.showToast({ title: e2.detail || '操作失败', icon: 'none' });
    }
  },

  async clearAll() {
    try {
      await put('/api/messages/read-all', {});
      this.loadData();
      wx.showToast({ title: '全部已读', icon: 'success' });
    } catch (e) {
      wx.showToast({ title: e.detail || '操作失败', icon: 'none' });
    }
  }
});
