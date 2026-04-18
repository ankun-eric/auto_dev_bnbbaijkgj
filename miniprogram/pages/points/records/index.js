const { get } = require('../../../utils/request');

const TYPE_LABEL = {
  signin: '每日签到',
  checkin: '健康打卡',
  completeProfile: '完善档案',
  invite: '邀请奖励',
  firstOrder: '首次下单',
  reviewService: '订单评价',
  exchange: '积分兑换',
  consume: '积分消费'
};

Page({
  data: {
    records: [],
    page: 1,
    pageSize: 20,
    noMore: false,
    loading: false
  },

  onLoad() {
    this.loadMore();
  },

  onPullDownRefresh() {
    this.setData({ records: [], page: 1, noMore: false });
    this.loadMore().finally(() => wx.stopPullDownRefresh());
  },

  onReachBottom() {
    if (!this.data.noMore && !this.data.loading) this.loadMore();
  },

  async loadMore() {
    if (this.data.loading) return;
    this.setData({ loading: true });
    try {
      const res = await get('/api/points/records', { page: this.data.page, page_size: this.data.pageSize }, { showLoading: false });
      const list = res.records || res.items || [];
      const items = list.map(r => ({
        ...r,
        type_label: TYPE_LABEL[r.type] || r.type,
        time: (r.created_at || '').replace('T', ' ').slice(0, 19)
      }));
      this.setData({
        records: this.data.records.concat(items),
        page: this.data.page + 1,
        noMore: items.length < this.data.pageSize
      });
    } catch (e) {
      this.setData({ noMore: true });
    } finally {
      this.setData({ loading: false });
    }
  }
});
