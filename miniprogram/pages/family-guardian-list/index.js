/**
 * [PRD-HEALTH-ARCHIVE-OPTIM-V1 2026-05-18] 家庭守护列表（小程序）
 */
const { get } = require('../../utils/request');

Page({
  data: {
    items: [],
    totalCount: 0,
    loading: true,
  },

  onLoad(options) {
    this.fetchItems();
    // 若 query 中带 target=xxx，则跳转到对应详情
    if (options && options.target) {
      const target = Number(options.target);
      if (target > 0) {
        wx.navigateTo({ url: `/pages/family-guardian-list/detail?target=${target}` });
      }
    }
  },

  onShow() {
    this.fetchItems();
  },

  async fetchItems() {
    this.setData({ loading: true });
    try {
      const res = await get('/api/health-archive/ai-call/settings', {}, { showLoading: false, suppressErrorToast: true });
      const data = (res && (res.data || res)) || {};
      const items = Array.isArray(data.items) ? data.items : [];
      this.setData({ items, totalCount: items.length, loading: false });
    } catch (_) {
      this.setData({ items: [], totalCount: 0, loading: false });
    }
  },

  onItemTap(e) {
    const target = Number(e.currentTarget.dataset.target);
    const isSelf = e.currentTarget.dataset.isSelf;
    wx.navigateTo({
      url: `/pages/family-guardian-list/detail?target=${target}&self=${isSelf ? 1 : 0}`,
    });
  },
});
