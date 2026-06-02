// [PRD-HEALTH-PLAN-CHECKIN-V1 2026-06-02] 健康打卡落地页（重做版）
const { get, post, del, put } = require('../../utils/request');

function freqLabel(item) {
  if (item.repeat_frequency === 'weekly' && item.weekly_target_count) {
    return `每周 ${item.weekly_target_count} 次`;
  }
  return '每天';
}

function periodLabel(item) {
  if (!item.start_date && !item.end_date) return '长期';
  const s = item.start_date || '今起';
  const e = item.end_date || '不限期';
  return `${s} ~ ${e}`;
}

Page({
  data: {
    loading: true,
    items: [],
    overview: { active_count: 0, today_done_count: 0, week_completion_rate: 0 },
    actionMenuId: 0,
    actionMenuVisible: false,
  },

  onShow() {
    this.load();
  },

  onPullDownRefresh() {
    this.load().finally(() => wx.stopPullDownRefresh());
  },

  async load() {
    try {
      const [listRes, ovRes] = await Promise.all([
        get('/api/health-plan/checkin-items', {}, { showLoading: false, suppressErrorToast: true }),
        get('/api/health-plan/checkin-overview', {}, { showLoading: false, suppressErrorToast: true }),
      ]);
      const list = (listRes && listRes.items) ? listRes.items : [];
      const items = list.map((it) => Object.assign({}, it, {
        _freq: freqLabel(it),
        _period: periodLabel(it),
      }));
      this.setData({
        items,
        overview: ovRes || { active_count: 0, today_done_count: 0, week_completion_rate: 0 },
        loading: false,
      });
    } catch (e) {
      this.setData({ loading: false });
    }
  },

  async onCheckin(e) {
    const id = e.currentTarget.dataset.id;
    const item = this.data.items.find((x) => x.id === id);
    if (!item || item.today_completed) return;
    try {
      await post(`/api/health-plan/checkin-items/${id}/checkin`, {});
      wx.showToast({ title: '打卡成功', icon: 'success' });
      this.load();
    } catch (err) {
      // already toasted
    }
  },

  onMoreTap(e) {
    const id = e.currentTarget.dataset.id;
    this.setData({ actionMenuId: id, actionMenuVisible: true });
  },

  onActionMenuCancel() {
    this.setData({ actionMenuVisible: false });
  },

  onEdit() {
    const id = this.data.actionMenuId;
    this.setData({ actionMenuVisible: false });
    wx.navigateTo({ url: `/pages/health-plan/edit/index?id=${id}` });
  },

  onDelete() {
    const id = this.data.actionMenuId;
    this.setData({ actionMenuVisible: false });
    wx.showModal({
      title: '删除计划',
      content: '确定删除该计划吗？该计划的打卡记录也会一并清除。',
      confirmText: '删除',
      confirmColor: '#ff4d4f',
      success: async (r) => {
        if (!r.confirm) return;
        try {
          await del(`/api/health-plan/checkin-items/${id}`);
          wx.showToast({ title: '已删除', icon: 'success' });
          this.load();
        } catch (err) {}
      },
    });
  },

  onCreate() {
    wx.navigateTo({ url: '/pages/health-plan/edit/index' });
  },

  onGoResult() {
    wx.navigateTo({ url: '/pages/health-plan/result/index' });
  },
});
