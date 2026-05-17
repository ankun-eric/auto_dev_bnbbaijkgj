const { get, put } = require('../../utils/request');
const { formatRelativeTime } = require('../../utils/util');
// [BUG_FIX_TIMEZONE_GLOBAL_20260517] 统一时间解析/格式化
const { parseServerTime, formatDateTime, formatDate, formatTime, formatRelativeTime: formatRelativeTimeUnified, formatFriendlyTime } = require('../../utils/datetime');

Page({
  data: {
    messages: [],
    loading: false,
    page: 1,
    pageSize: 20,
    total: 0,
    noMore: false
  },

  onLoad() {
    this.loadMessages();
  },

  onShow() {
    if (this.data.messages.length > 0) {
      this.setData({ page: 1, noMore: false });
      this.loadMessages();
    }
  },

  onPullDownRefresh() {
    this.setData({ page: 1, noMore: false });
    this.loadMessages().finally(() => wx.stopPullDownRefresh());
  },

  onReachBottom() {
    if (this.data.noMore || this.data.loading) return;
    this.setData({ page: this.data.page + 1 });
    this.loadMoreMessages();
  },

  async loadMessages() {
    this.setData({ loading: true });
    try {
      const res = await get('/api/messages', {
        page: 1,
        page_size: this.data.pageSize
      }, { showLoading: false, suppressErrorToast: true });

      const items = this.formatItems(res.items || []);
      this.setData({
        messages: items,
        total: res.total || 0,
        page: 1,
        noMore: items.length >= (res.total || 0)
      });
    } catch (e) {
      this.setData({ messages: [] });
    } finally {
      this.setData({ loading: false });
    }
  },

  async loadMoreMessages() {
    this.setData({ loading: true });
    try {
      const res = await get('/api/messages', {
        page: this.data.page,
        page_size: this.data.pageSize
      }, { showLoading: false, suppressErrorToast: true });

      const items = this.formatItems(res.items || []);
      const all = this.data.messages.concat(items);
      this.setData({
        messages: all,
        noMore: all.length >= (res.total || 0)
      });
    } catch (e) {
      // revert page on error
      this.setData({ page: this.data.page - 1 });
    } finally {
      this.setData({ loading: false });
    }
  },

  formatItems(items) {
    return items.map(item => {
      let timeLabel = '';
      if (item.created_at) {
        const _d = parseServerTime(item.created_at);
        if (_d) timeLabel = formatRelativeTime(_d.getTime());
      }
      return Object.assign({}, item, { timeLabel });
    });
  },

  async onMsgTap(e) {
    const item = e.currentTarget.dataset.item;
    if (!item) return;

    if (!item.is_read) {
      this.markRead(item.id);
    }

    if (item.click_action === 'family_accept') {
      wx.navigateTo({ url: '/pages/family-bindlist/index' });
    } else if (item.click_action === 'family_reject') {
      // show detail inline, already visible
    } else if (item.click_action === 'navigate' && item.click_action_params) {
      const params = typeof item.click_action_params === 'string'
        ? JSON.parse(item.click_action_params)
        : item.click_action_params;
      if (params && params.url) {
        wx.navigateTo({ url: params.url });
      }
    }
  },

  async markRead(id) {
    try {
      await put(`/api/messages/${id}/read`, {}, { showLoading: false, suppressErrorToast: true });
      const messages = this.data.messages.map(m =>
        m.id === id ? { ...m, is_read: true } : m
      );
      this.setData({ messages });
    } catch (e) {
      // silently fail
    }
  },

  async markAllRead() {
    try {
      await put('/api/messages/read-all', {}, { showLoading: false });
      const messages = this.data.messages.map(m => ({ ...m, is_read: true }));
      this.setData({ messages });
      wx.showToast({ title: '已全部标为已读', icon: 'success' });
    } catch (e) {
      // error handled by request
    }
  },

  onAcceptAuth(e) {
    const item = e.currentTarget.dataset.item;
    if (item && !item.is_read) this.markRead(item.id);
    wx.navigateTo({ url: '/pages/family-bindlist/index' });
  },

  onReinvite(e) {
    const item = e.currentTarget.dataset.item;
    if (!item) return;
    if (!item.is_read) this.markRead(item.id);
    const params = item.click_action_params;
    let memberId = '';
    if (params) {
      const p = typeof params === 'string' ? JSON.parse(params) : params;
      memberId = p.member_id || '';
    }
    if (memberId) {
      wx.navigateTo({ url: `/pages/family-invite/index?member_id=${memberId}` });
    } else {
      wx.navigateTo({ url: '/pages/family/index' });
    }
  }
});
