// [PRD-HEALTH-PLAN-CHECKIN-V1 2026-06-02] 打卡成果页
const { get, post } = require('../../../utils/request');

const RANK_COLORS = ['#6366F1', '#8B5CF6', '#A855F7', '#EC4899', '#0EA5E9', '#10B981', '#F59E0B'];

function pad(n) { return String(n).padStart(2, '0'); }

Page({
  data: {
    loading: true,
    summary: null,
    items: [],
    year: 0,
    month: 0,
    cells: [],
    todayStr: '',
    weekdayNames: ['日', '一', '二', '三', '四', '五', '六'],
    rankColors: RANK_COLORS,
  },

  onLoad() {
    const today = new Date();
    const t = `${today.getFullYear()}-${pad(today.getMonth() + 1)}-${pad(today.getDate())}`;
    this.setData({ year: today.getFullYear(), month: today.getMonth() + 1, todayStr: t });
    this.loadAll();
  },

  async loadAll() {
    await Promise.all([this.loadSummary(), this.loadCalendar()]);
    this.setData({ loading: false });
  },

  async loadSummary() {
    try {
      const [sum, list] = await Promise.all([
        get('/api/health-plan/checkin-stats-summary', {}, { showLoading: false, suppressErrorToast: true }),
        get('/api/health-plan/checkin-items', {}, { showLoading: false, suppressErrorToast: true }),
      ]);
      const plans = (sum && sum.plans) || [];
      const enrichedPlans = plans.map((p, idx) => Object.assign({}, p, {
        _color: RANK_COLORS[idx % RANK_COLORS.length],
        _rank: idx + 1,
        _rateInt: Math.round(p.completion_rate || 0),
      }));
      this.setData({
        summary: Object.assign({}, sum, { plans: enrichedPlans }),
        items: (list && list.items) ? list.items.map((i) => ({ id: i.id, name: i.name })) : [],
      });
    } catch (e) {}
  },

  async loadCalendar() {
    const { year, month, todayStr } = this.data;
    try {
      const res = await get(`/api/health-plan/checkin-calendar?year=${year}&month=${month}`, {}, { showLoading: false, suppressErrorToast: true });
      const dayMap = {};
      (res && res.days ? res.days : []).forEach((it) => { dayMap[it.date] = it.count || 0; });
      this.buildCells(year, month, dayMap, todayStr);
    } catch (e) {
      this.buildCells(year, month, {}, todayStr);
    }
  },

  buildCells(y, m, dayMap, todayStr) {
    const firstDay = new Date(y, m - 1, 1).getDay();
    const days = new Date(y, m, 0).getDate();
    const cells = [];
    const today = new Date(todayStr);
    for (let i = 0; i < firstDay; i++) cells.push({ day: '', dateStr: '', cnt: 0, isToday: false, canMakeup: false });
    for (let d = 1; d <= days; d++) {
      const ds = `${y}-${pad(m)}-${pad(d)}`;
      const cnt = dayMap[ds] || 0;
      const cd = new Date(ds);
      const diff = Math.floor((today.getTime() - cd.getTime()) / 86400000);
      cells.push({
        day: d,
        dateStr: ds,
        cnt,
        isToday: ds === todayStr,
        canMakeup: !cnt && diff >= 1 && diff <= 3,
      });
    }
    this.setData({ cells });
  },

  onPrevMonth() {
    let { year, month } = this.data;
    month -= 1;
    if (month < 1) { month = 12; year -= 1; }
    this.setData({ year, month });
    this.loadCalendar();
  },

  onNextMonth() {
    let { year, month } = this.data;
    const now = new Date();
    if (year === now.getFullYear() && month >= now.getMonth() + 1) return;
    month += 1;
    if (month > 12) { month = 1; year += 1; }
    this.setData({ year, month });
    this.loadCalendar();
  },

  onCellTap(e) {
    const idx = e.currentTarget.dataset.idx;
    const cell = this.data.cells[idx];
    if (!cell || !cell.dateStr) return;
    if (cell.isToday) {
      wx.showToast({ title: '请到主页执行今日打卡', icon: 'none' });
      return;
    }
    if (cell.cnt > 0) {
      wx.showToast({ title: `这天已有 ${cell.cnt} 次打卡`, icon: 'none' });
      return;
    }
    if (!cell.canMakeup) return;
    const items = this.data.items;
    if (!items.length) {
      wx.showToast({ title: '暂无可补打的计划', icon: 'none' });
      return;
    }
    wx.showActionSheet({
      itemList: items.map((it) => it.name),
      success: async (r) => {
        const target = items[r.tapIndex];
        if (!target) return;
        try {
          await post(`/api/health-plan/checkin-items/${target.id}/makeup`, { date: cell.dateStr });
          wx.showToast({ title: '补卡成功', icon: 'success' });
          this.loadAll();
        } catch (e) {}
      },
    });
  },
});
