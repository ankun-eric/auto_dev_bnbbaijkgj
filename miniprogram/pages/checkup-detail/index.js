const { get, post } = require('../../utils/request');
const { checkLogin } = require('../../utils/util');

Page({
  data: {
    reportId: '',
    report: null,
    images: [],
    aiData: null,
    aiRawText: '',
    abnormalCards: [],
    categories: [],
    expandedCategories: {},
    loading: true,
    disclaimer: '免责声明：本解读结果由AI智能分析生成，仅供参考，不构成医疗诊断或治疗建议。如有健康疑问，请及时咨询专业医生。'
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

      let aiData = null;
      let aiRawText = '';

      const rawJson = report.ai_analysis_json;
      if (rawJson) {
        try {
          aiData = typeof rawJson === 'string' ? JSON.parse(rawJson) : rawJson;
        } catch (e) {
          aiRawText = typeof rawJson === 'string' ? rawJson : (report.ai_result || '');
        }
      } else if (report.ai_result) {
        try {
          aiData = typeof report.ai_result === 'string' ? JSON.parse(report.ai_result) : report.ai_result;
        } catch (e) {
          aiRawText = typeof report.ai_result === 'string' ? report.ai_result : '';
        }
      }

      let abnormalCards = [];
      let categories = [];
      let expandedCategories = {};

      if (aiData && aiData.categories) {
        const abnormalNames = Array.isArray(aiData.abnormal_items) ? aiData.abnormal_items : [];

        aiData.categories.forEach((cat, catIdx) => {
          const items = Array.isArray(cat.items) ? cat.items : [];
          let catAbnormalCount = 0;

          items.forEach(item => {
            const isAbnormal = item.status && item.status !== '正常' && item.status !== 'normal';
            if (isAbnormal) {
              catAbnormalCount++;
              abnormalCards.push({
                name: item.name,
                value: item.value,
                unit: item.unit || '',
                reference: item.reference || '',
                status: item.status,
                suggestion: item.suggestion || '',
                statusColor: item.status && item.status.includes('高') ? 'high' : 'low'
              });
            }
          });

          categories.push({
            name: cat.name,
            abnormalCount: catAbnormalCount,
            items: items.map(item => {
              const isAbnormal = item.status && item.status !== '正常' && item.status !== 'normal';
              return {
                name: item.name,
                value: item.value,
                unit: item.unit || '',
                reference: item.reference || '',
                status: item.status || '正常',
                isAbnormal,
                statusColor: isAbnormal ? (item.status && item.status.includes('高') ? 'high' : 'low') : 'normal'
              };
            })
          });

          expandedCategories[catIdx] = false;
        });
      }

      this.setData({
        report,
        images: typeof images === 'string' ? [images] : images,
        aiData,
        aiRawText,
        abnormalCards,
        categories,
        expandedCategories,
        loading: false
      });
    } catch (e) {
      console.log('loadDetail error', e);
      this.setData({ loading: false });
      wx.showToast({ title: '加载失败', icon: 'none' });
    }
  },

  toggleCategory(e) {
    const idx = e.currentTarget.dataset.idx;
    const key = `expandedCategories.${idx}`;
    this.setData({ [key]: !this.data.expandedCategories[idx] });
  },

  previewImage(e) {
    const url = e.currentTarget.dataset.url;
    wx.previewImage({ current: url, urls: this.data.images });
  },

  async shareReport() {
    if (!checkLogin()) return;
    const id = this.data.reportId;
    wx.showLoading({ title: '生成分享...', mask: true });
    try {
      const res = await post(`/api/report/${id}/share`, {});
      wx.hideLoading();
      const token = res.share_token || res.token || '';
      const shareUrl = res.share_url || res.url || (token ? `${getApp().globalData.baseUrl}/share/report/${token}` : '');
      if (shareUrl) {
        wx.setClipboardData({
          data: shareUrl,
          success: () => wx.showToast({ title: '链接已复制', icon: 'success' })
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
