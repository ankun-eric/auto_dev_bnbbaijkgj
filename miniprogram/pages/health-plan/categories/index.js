const { get, post } = require('../../../utils/request');

Page({
  data: {
    categories: [],
    myPlans: [],
    loading: false,
    aiGenerating: false
  },

  onShow() {
    this.loadData();
  },

  onPullDownRefresh() {
    this.loadData().finally(() => wx.stopPullDownRefresh());
  },

  async loadData() {
    this.setData({ loading: true });
    try {
      const [catRes, planRes] = await Promise.all([
        get('/api/health-plan/template-categories', {}, { showLoading: false, suppressErrorToast: true }),
        get('/api/health-plan/user-plans', {}, { showLoading: false, suppressErrorToast: true })
      ]);
      const categories = Array.isArray(catRes) ? catRes : (catRes && catRes.items ? catRes.items : []);
      const rawPlans = Array.isArray(planRes) ? planRes : (planRes && planRes.items ? planRes.items : []);
      const myPlans = rawPlans.map(function(p) {
        return Object.assign({}, p, {
          name: p.plan_name || p.name,
        });
      });
      this.setData({ categories, myPlans });
    } catch (e) {
      // partial failure is ok
    } finally {
      this.setData({ loading: false });
    }
  },

  onCategoryTap(e) {
    const id = e.currentTarget.dataset.id;
    wx.navigateTo({ url: `/pages/health-plan/category-detail/index?id=${id}` });
  },

  onPlanTap(e) {
    const id = e.currentTarget.dataset.id;
    wx.navigateTo({ url: `/pages/health-plan/my-plan/index?id=${id}` });
  },

  goCreatePlan() {
    wx.navigateTo({ url: '/pages/health-plan/create-plan/index' });
  },

  async onAiGenerate(e) {
    const categoryId = e.currentTarget.dataset.id;
    if (this.data.aiGenerating) return;
    this.setData({ aiGenerating: true });
    try {
      await post(`/api/health-plan/ai-generate-category/${categoryId}`, {});
      wx.showToast({ title: 'AI计划已生成', icon: 'success' });
      this.loadData();
    } catch (e) {
      // error handled by request
    } finally {
      this.setData({ aiGenerating: false });
    }
  }
});
