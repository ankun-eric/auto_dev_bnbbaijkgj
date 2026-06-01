/**
 * [PRD-HEALTH-ARCHIVE-OPTIM-V1 2026-05-18] 家庭守护列表（小程序）
 */
const { get } = require('../../utils/request');

Page({
  data: {
    items: [],
    totalCount: 0,
    // [PRD-HEALTH-ARCHIVE-FAMILY-MEMBER-V1 2026-06-01 改动点2]
    // 家庭成员总人数（含本人），口径与入口卡 / H5 列表完全一致：
    // 取 /api/family/member/quota 的 quota_used（= count_managed_family_members）。
    memberCount: 0,
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
    // [PRD-HEALTH-ARCHIVE-FAMILY-MEMBER-V1 2026-06-01 改动点2]
    // 头部「家庭成员」总人数以家庭成员配额口径（含本人）为准，与入口卡 / H5 列表保持一致。
    this.fetchMemberCount();
  },

  async fetchMemberCount() {
    try {
      const r = await get('/api/family/member/quota', {}, { showLoading: false, suppressErrorToast: true });
      const d = (r && (r.data || r)) || {};
      if (typeof d.quota_used === 'number') {
        this.setData({ memberCount: d.quota_used });
      }
    } catch (_) {
      // 接口异常时保持原值，不阻断列表展示
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
