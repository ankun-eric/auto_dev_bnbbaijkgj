// [PRD-HEALTH-PLAN-CHECKIN-V1 2026-06-02] 新建/编辑打卡计划页
const { get, post, put } = require('../../../utils/request');

function todayStr() {
  const d = new Date();
  return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}-${String(d.getDate()).padStart(2, '0')}`;
}

Page({
  data: {
    editId: 0,
    isEdit: false,
    name: '',
    freqType: 'daily', // daily / weekly
    weeklyCount: 3,
    startDate: '',
    endDate: '',
    submitting: false,
    fetching: false,
  },

  onLoad(query) {
    const editId = query && query.id ? Number(query.id) : 0;
    const t = todayStr();
    this.setData({ editId, isEdit: !!editId, startDate: t });
    wx.setNavigationBarTitle({ title: editId ? '编辑计划' : '新建计划' });
    if (editId) this.fetchData(editId);
  },

  async fetchData(id) {
    this.setData({ fetching: true });
    try {
      const data = await get(`/api/health-plan/checkin-items/${id}`);
      this.setData({
        name: data.name || '',
        freqType: data.repeat_frequency === 'weekly' ? 'weekly' : 'daily',
        weeklyCount: data.weekly_target_count || 3,
        startDate: data.start_date || '',
        endDate: data.end_date || '',
        fetching: false,
      });
    } catch (e) {
      this.setData({ fetching: false });
    }
  },

  onNameInput(e) { this.setData({ name: e.detail.value }); },
  onFreqTap(e) { this.setData({ freqType: e.currentTarget.dataset.v }); },
  onWeeklyCountChange(e) {
    const v = Math.max(1, Math.min(7, Number(e.detail.value || 1)));
    this.setData({ weeklyCount: v });
  },
  onStartDateChange(e) { this.setData({ startDate: e.detail.value }); },
  onEndDateChange(e) { this.setData({ endDate: e.detail.value }); },
  onClearEndDate() { this.setData({ endDate: '' }); },

  async onSubmit() {
    const { name, freqType, weeklyCount, startDate, endDate, isEdit, editId } = this.data;
    if (!name.trim()) {
      wx.showToast({ title: '请输入计划名称', icon: 'none' });
      return;
    }
    if (freqType === 'weekly' && (weeklyCount < 1 || weeklyCount > 7)) {
      wx.showToast({ title: '每周次数应在 1~7 之间', icon: 'none' });
      return;
    }
    if (startDate && endDate && startDate > endDate) {
      wx.showToast({ title: '开始日期不能晚于结束日期', icon: 'none' });
      return;
    }
    this.setData({ submitting: true });
    const payload = {
      name: name.trim(),
      repeat_frequency: freqType,
      weekly_target_count: freqType === 'weekly' ? weeklyCount : null,
      start_date: startDate || null,
      end_date: endDate || null,
    };
    try {
      if (isEdit) {
        await put(`/api/health-plan/checkin-items/${editId}`, payload);
        wx.showToast({ title: '修改成功', icon: 'success' });
      } else {
        await post('/api/health-plan/checkin-items', payload);
        wx.showToast({ title: '创建成功', icon: 'success' });
      }
      setTimeout(() => wx.navigateBack(), 600);
    } catch (e) {
      // already toasted
    } finally {
      this.setData({ submitting: false });
    }
  },
});
