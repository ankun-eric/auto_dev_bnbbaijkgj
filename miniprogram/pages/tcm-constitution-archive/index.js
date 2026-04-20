const { get } = require('../../utils/request');

Page({
  data: { items: [], loading: true },

  onLoad() { this.fetchList(); },
  onShow() { this.fetchList(); },

  async fetchList() {
    this.setData({ loading: true });
    try {
      const res = await get('/api/constitution/archive', {}, { showLoading: false, suppressErrorToast: true });
      const data = res && (res.data || res);
      const items = (data && data.items) || [];
      // 本地格式化时间
      items.forEach(it => {
        if (it.created_at) {
          const d = new Date(it.created_at);
          if (!isNaN(d.getTime())) {
            const y = d.getFullYear();
            const m = String(d.getMonth() + 1).padStart(2, '0');
            const day = String(d.getDate()).padStart(2, '0');
            const h = String(d.getHours()).padStart(2, '0');
            const min = String(d.getMinutes()).padStart(2, '0');
            it.created_at_text = `${y}-${m}-${day} ${h}:${min}`;
          }
        }
      });
      this.setData({ items });
    } catch (e) {
      this.setData({ items: [] });
    } finally {
      this.setData({ loading: false });
    }
  },

  goDetail(e) {
    const id = e.currentTarget.dataset.id;
    wx.navigateTo({ url: `/pages/tcm-constitution-result/index?id=${id}` });
  },

  goTest() {
    wx.navigateBack({ fail: () => wx.switchTab({ url: '/pages/index/index' }) });
  }
});
