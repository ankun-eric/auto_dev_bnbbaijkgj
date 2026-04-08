const { get, post } = require('../../utils/request');

Page({
  data: {
    id1: '',
    id2: '',
    report1Name: '',
    report2Name: '',
    reportList: [],
    showPicker: false,
    pickerFor: '',

    compareData: null,
    aiSummary: '',
    scoreDiff: null,
    indicators: [],
    filteredIndicators: [],
    disclaimer: '',

    filter: 'all',
    loading: false,
    hasCompared: false
  },

  onLoad(options) {
    const id1 = options.id1 || '';
    const id2 = options.id2 || '';
    this.setData({ id1, id2 });
    this.loadReportList();
    if (id1 && id2) {
      this.doCompare();
    }
  },

  async loadReportList() {
    try {
      const res = await get('/api/report/list', { page: 1, page_size: 50 }, {
        showLoading: false,
        suppressErrorToast: true
      });
      const items = res.items || res.data || [];
      const list = items.map(item => ({
        id: item.id,
        name: item.name || item.title || '体检报告',
        date: (item.created_at || item.date || '').substring(0, 10),
        healthScore: item.health_score || 0
      }));
      this.setData({ reportList: list });
      this.updateReportNames();
    } catch (e) {
      console.log('loadReportList error', e);
    }
  },

  updateReportNames() {
    const { id1, id2, reportList } = this.data;
    const r1 = reportList.find(i => String(i.id) === String(id1));
    const r2 = reportList.find(i => String(i.id) === String(id2));
    this.setData({
      report1Name: r1 ? `${r1.date} ${r1.name}` : (id1 ? `报告 #${id1}` : ''),
      report2Name: r2 ? `${r2.date} ${r2.name}` : (id2 ? `报告 #${id2}` : '')
    });
  },

  openPicker(e) {
    const pickerFor = e.currentTarget.dataset.for;
    this.setData({ showPicker: true, pickerFor });
  },

  closePicker() {
    this.setData({ showPicker: false, pickerFor: '' });
  },

  selectReport(e) {
    const id = e.currentTarget.dataset.id;
    const field = this.data.pickerFor;
    if (field === 'id1' || field === 'id2') {
      this.setData({ [field]: String(id), showPicker: false, pickerFor: '' });
      this.updateReportNames();
    }
  },

  async doCompare() {
    const { id1, id2 } = this.data;
    if (!id1 || !id2) {
      wx.showToast({ title: '请选择两份报告', icon: 'none' });
      return;
    }
    if (id1 === id2) {
      wx.showToast({ title: '请选择不同的报告', icon: 'none' });
      return;
    }

    this.setData({ loading: true });
    try {
      const res = await post('/api/report/compare', {
        report_id_1: Number(id1),
        report_id_2: Number(id2)
      }, { suppressErrorToast: true });

      const data = res.data || res;
      const indicators = (data.indicators || []).map(ind => ({
        ...ind,
        directionIcon: ind.direction === 'worse' ? '↑' : (ind.direction === 'better' ? '↓' : (ind.direction === 'new' ? '★' : '→')),
        directionColor: ind.direction === 'worse' ? '#F44336'
          : (ind.direction === 'better' ? '#4CAF50'
            : (ind.direction === 'new' ? '#FF9800' : '#999')),
        changeStatus: this.getChangeStatus(ind)
      }));

      this.setData({
        compareData: data,
        aiSummary: data.aiSummary || '',
        scoreDiff: data.scoreDiff || null,
        indicators,
        filteredIndicators: indicators,
        disclaimer: data.disclaimer || '',
        loading: false,
        hasCompared: true,
        filter: 'all'
      });
    } catch (e) {
      console.log('compare error', e);
      this.setData({ loading: false });
      wx.showToast({ title: '对比分析失败', icon: 'none' });
    }
  },

  getChangeStatus(ind) {
    if (ind.direction === 'better') return 'better';
    if (ind.direction === 'worse') return 'worse';
    if (ind.direction === 'new') return 'new';
    if (ind.direction === 'unchanged' || ind.direction === 'same') return 'stable';
    if (ind.currentRiskLevel < ind.previousRiskLevel) return 'better';
    if (ind.currentRiskLevel > ind.previousRiskLevel) return 'worse';
    return 'stable';
  },

  setFilter(e) {
    const filter = e.currentTarget.dataset.filter;
    let filtered = this.data.indicators;
    if (filter === 'better') {
      filtered = this.data.indicators.filter(i => i.changeStatus === 'better');
    } else if (filter === 'worse') {
      filtered = this.data.indicators.filter(i => i.changeStatus === 'worse');
    }
    this.setData({ filter, filteredIndicators: filtered });
  }
});
