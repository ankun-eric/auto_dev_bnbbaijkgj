const { get } = require('../../../utils/request');

Page({
  data: {
    id: '',
    category: null,
    plans: [],
    loading: false
  },

  onLoad(options) {
    if (options.id) {
      this.setData({ id: options.id });
      this.loadDetail(options.id);
    }
  },

  async loadDetail(id) {
    this.setData({ loading: true });
    try {
      const res = await get(`/api/health-plan/template-categories/${id}`, {}, { showLoading: false });
      if (res) {
        wx.setNavigationBarTitle({ title: res.name || '分类详情' });
        const plans = res.plans || res.recommended_plans || [];
        this.setData({ category: res, plans });
      }
    } catch (e) {
      wx.showToast({ title: '加载失败', icon: 'none' });
    } finally {
      this.setData({ loading: false });
    }
  },

  onPlanTap(e) {
    const id = e.currentTarget.dataset.id;
    wx.navigateTo({ url: `/pages/health-plan/plan-detail/index?id=${id}` });
  }
});
