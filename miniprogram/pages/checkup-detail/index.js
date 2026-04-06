const { get, post } = require('../../utils/request');
const { checkLogin } = require('../../utils/util');

Page({
  data: {
    reportId: '',
    report: null,
    images: [],
    analysisResult: null,
    viewMode: 'category',
    categoryItems: [],
    abnormalItems: [],
    normalItems: [],
    loading: true,
    disclaimer: '⚠️ 免责声明：本解读结果由AI智能分析生成，仅供参考，不构成医疗诊断或治疗建议。如有健康疑问，请及时咨询专业医生。'
  },

  onLoad(options) {
    const { id } = options;
    if (!id) {
      wx.showToast({ title: '缺少报告ID', icon: 'none' });
      return;
    }
    this.setData({ reportId: id });
    this.loadDetail(id);
  },

  async loadDetail(id) {
    this.setData({ loading: true });
    try {
      const res = await get(`/api/report/detail/${id}`, {}, { suppressErrorToast: true });
      const report = res.data || res;
      const images = report.file_url && report.file_type !== 'pdf' ? [report.file_url] : [];
      const indicators = report.indicators || [];
      const analysisJson = report.ai_analysis_json || null;

      let categoryItems = [];
      let abnormalItems = [];
      let normalItems = [];

      const grouped = {};
      indicators.forEach(ind => {
        const cat = ind.category || '其他';
        if (!grouped[cat]) grouped[cat] = [];
        grouped[cat].push({
          name: ind.indicator_name,
          value: ind.value,
          unit: ind.unit,
          reference_range: ind.reference_range,
          status: ind.status,
          advice: ind.advice,
          is_abnormal: ind.status === 'abnormal' || ind.status === 'critical'
        });
      });

      Object.keys(grouped).forEach(cat => {
        categoryItems.push({ isCategory: true, categoryName: cat });
        grouped[cat].forEach(item => {
          categoryItems.push(item);
          if (item.is_abnormal) abnormalItems.push(item);
          else normalItems.push(item);
        });
      });

      this.setData({
        report,
        images: typeof images === 'string' ? [images] : images,
        analysisResult: analysisJson,
        categoryItems,
        abnormalItems,
        normalItems,
        loading: false
      });
    } catch (e) {
      console.log('loadDetail error', e);
      this.setData({ loading: false });
      wx.showToast({ title: '加载失败', icon: 'none' });
    }
  },

  switchView(e) {
    const mode = e.currentTarget.dataset.mode;
    this.setData({ viewMode: mode });
  },

  previewImage(e) {
    const url = e.currentTarget.dataset.url;
    wx.previewImage({ current: url, urls: this.data.images });
  },

  viewTrend(e) {
    const name = e.currentTarget.dataset.name;
    wx.navigateTo({
      url: `/pages/checkup-trend/index?name=${encodeURIComponent(name)}`
    });
  },

  async shareReport() {
    if (!checkLogin()) return;
    wx.showLoading({ title: '生成分享...', mask: true });
    try {
      const res = await post('/api/report/share', { report_id: parseInt(this.data.reportId) });
      wx.hideLoading();
      const shareUrl = res.share_url || res.url || '';
      const shareText = res.share_text || '';
      if (shareUrl) {
        wx.setClipboardData({
          data: shareUrl,
          success: () => wx.showToast({ title: '分享链接已复制', icon: 'success' })
        });
      } else if (shareText) {
        wx.setClipboardData({
          data: shareText,
          success: () => wx.showToast({ title: '分享内容已复制', icon: 'success' })
        });
      } else {
        wx.showToast({ title: '分享成功', icon: 'success' });
      }
    } catch (e) {
      wx.hideLoading();
      wx.showToast({ title: '分享失败', icon: 'none' });
    }
  }
});
