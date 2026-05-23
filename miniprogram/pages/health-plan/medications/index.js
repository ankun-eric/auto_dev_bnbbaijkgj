const { get, post, put, del } = require('../../../utils/request');
const { showCheckinPointsToast } = require('../../../utils/checkin-points');

// [PRD-MED-PLAN-OPTIM-V1 2026-05-17] 服用周期展示工具
function _parseISO(s) {
  if (!s) return null;
  var m = /^(\d{4})-(\d{2})-(\d{2})/.exec(s);
  if (!m) return null;
  return new Date(Number(m[1]), Number(m[2]) - 1, Number(m[3]));
}
function buildCycleText(item) {
  var s = item.start_date || '';
  if (item.long_term) return s ? (s + ' 至 长期') : '长期服用';
  var e = item.end_date || '';
  if (!s || !e) return s || e || '';
  var sd = _parseISO(s);
  var ed = _parseISO(e);
  if (!sd || !ed) return s + ' 至 ' + e;
  var d = Math.round((ed.getTime() - sd.getTime()) / 86400000) + 1;
  if (d <= 0) return s + ' 至 ' + e;
  return s + ' 至 ' + e + ' · 共 ' + d + ' 天';
}

// 服用时机老数据兜底
var TIMING_LEGACY_MAP = {
  '早上': '饭前', '中午': '饭后', '下午': '饭后', '晚上': '饭后', '睡前': '睡前',
  morning: '饭前', noon: '饭后', afternoon: '饭后', evening: '饭后', bedtime: '睡前',
};
function migrateTiming(raw) {
  if (!raw) return '';
  var valid = ['饭前', '饭后', '空腹', '随餐', '睡前'];
  if (valid.indexOf(raw) >= 0) return raw;
  return TIMING_LEGACY_MAP[raw] || raw;
}

function decorate(item) {
  return Object.assign({}, item, {
    name: item.medicine_name || item.name,
    frequency: item.time_period || item.frequency,
    remind_times: Array.isArray(item.custom_times) && item.custom_times.length
      ? item.custom_times.join(' / ')
      : (item.remind_time || item.remind_times),
    cycle_text: buildCycleText(item),
    guidance_text: migrateTiming(item.guidance),
  });
}

Page({
  data: {
    consultantId: null,
    medications: [],
    medGroups: [],
    loading: false,
    pointsRefreshKey: 0
  },

  onLoad(options) {
    if (options.target) {
      this.setData({ consultantId: options.target });
    }
  },

  onShow() {
    this._loadWhenReady();
  },

  _loadWhenReady() {
    const cid = this.data.consultantId;
    if (cid !== null && cid !== undefined) {
      this.loadList();
      return;
    }
    const app = getApp();
    if (app && app.globalData && app.globalData.token) {
      this.loadList();
      return;
    }
    setTimeout(() => { this.loadList(); }, 300);
  },

  onPullDownRefresh() {
    this.loadList().finally(() => wx.stopPullDownRefresh());
  },

  async loadList() {
    this.setData({ loading: true });
    try {
      const params = {};
      if (this.data.consultantId) {
        params.consultant_id = this.data.consultantId;
      }
      const res = await get('/api/health-plan/medications', params, { showLoading: false });
      let items = [];
      let medGroups = [];
      if (res && res.groups && typeof res.groups === 'object') {
        var groupKeys = Object.keys(res.groups);
        groupKeys.forEach(function(period) {
          var groupItems = res.groups[period];
          if (!Array.isArray(groupItems)) return;
          var mapped = groupItems.map(decorate);
          items = items.concat(mapped);
          medGroups.push({ period: period, items: mapped });
        });
      } else {
        var raw = Array.isArray(res) ? res : (res && res.items ? res.items : []);
        items = raw.map(decorate);
      }
      this.setData({ medications: items, medGroups: medGroups });
    } catch (e) {
      this.setData({ medications: [], medGroups: [] });
    } finally {
      this.setData({ loading: false });
    }
  },

  goAdd() {
    wx.navigateTo({ url: '/pages/health-plan/medication-form/index' });
  },

  goEdit(e) {
    const id = e.currentTarget.dataset.id;
    wx.navigateTo({ url: `/pages/health-plan/medication-form/index?id=${id}` });
  },

  async onCheckin(e) {
    const id = e.currentTarget.dataset.id;
    try {
      const result = await post(`/api/health-plan/medications/${id}/checkin`, {});
      showCheckinPointsToast(result);
      this.setData({ pointsRefreshKey: this.data.pointsRefreshKey + 1 });
      this.loadList();
    } catch (e) {
      // error handled by request
    }
  },

  async onTogglePause(e) {
    const id = e.currentTarget.dataset.id;
    try {
      await put(`/api/health-plan/medications/${id}/pause`, {});
      wx.showToast({ title: '操作成功', icon: 'success' });
      this.loadList();
    } catch (e) {
      // error handled by request
    }
  },

  onDelete(e) {
    const id = e.currentTarget.dataset.id;
    wx.showModal({
      title: '确认删除',
      content: '确定要删除这条用药提醒吗？',
      success: async (res) => {
        if (!res.confirm) return;
        try {
          await del(`/api/health-plan/medications/${id}`);
          wx.showToast({ title: '已删除', icon: 'success' });
          this.loadList();
        } catch (e) {
          // error handled by request
        }
      }
    });
  }
});
