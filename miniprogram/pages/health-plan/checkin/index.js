const { get, post, del } = require('../../../utils/request');

Page({
  data: {
    items: [],
    loading: false,
    checkinDialog: false,
    checkinId: 0,
    checkinName: '',
    checkinTarget: 0,
    checkinUnit: '',
    checkinValue: ''
  },

  onShow() {
    this.loadList();
  },

  onPullDownRefresh() {
    this.loadList().finally(() => wx.stopPullDownRefresh());
  },

  async loadList() {
    this.setData({ loading: true });
    try {
      const res = await get('/api/health-plan/checkin-items', {}, { showLoading: false });
      const rawItems = Array.isArray(res) ? res : (res && res.items ? res.items : []);
      const items = rawItems.map(function(item) {
        return Object.assign({}, item, {
          today_checked: item.today_completed || item.today_checked || false,
        });
      });
      this.setData({ items });
    } catch (e) {
      this.setData({ items: [] });
    } finally {
      this.setData({ loading: false });
    }
  },

  goAdd() {
    wx.navigateTo({ url: '/pages/health-plan/checkin-form/index' });
  },

  goEdit(e) {
    const id = e.currentTarget.dataset.id;
    wx.navigateTo({ url: `/pages/health-plan/checkin-form/index?id=${id}` });
  },

  onCheckin(e) {
    const id = e.currentTarget.dataset.id;
    const targetValue = e.currentTarget.dataset.targetValue;
    const targetUnit = e.currentTarget.dataset.targetUnit;
    const name = e.currentTarget.dataset.name;
    if (targetValue && targetValue > 0) {
      this.setData({
        checkinDialog: true,
        checkinId: id,
        checkinName: name || '',
        checkinTarget: targetValue,
        checkinUnit: targetUnit || '',
        checkinValue: '',
      });
      return;
    }
    this.doCheckin(id, null);
  },

  onCheckinDialogInput(e) {
    this.setData({ checkinValue: e.detail.value });
  },

  onCheckinDialogCancel() {
    this.setData({ checkinDialog: false });
  },

  onCheckinDialogConfirm() {
    const val = this.data.checkinValue ? parseFloat(this.data.checkinValue) : null;
    this.setData({ checkinDialog: false });
    this.doCheckin(this.data.checkinId, val);
  },

  async doCheckin(id, value) {
    const body = {};
    if (value != null) body.actual_value = value;
    try {
      await post(`/api/health-plan/checkin-items/${id}/checkin`, body);
      wx.showToast({ title: '打卡成功', icon: 'success' });
      this.loadList();
    } catch (e) {
      // error handled by request
    }
  },

  onDelete(e) {
    const id = e.currentTarget.dataset.id;
    wx.showModal({
      title: '确认删除',
      content: '确定要删除这个打卡项目吗？',
      success: async (res) => {
        if (!res.confirm) return;
        try {
          await del(`/api/health-plan/checkin-items/${id}`);
          wx.showToast({ title: '已删除', icon: 'success' });
          this.loadList();
        } catch (e) {
          // error handled by request
        }
      }
    });
  }
});
