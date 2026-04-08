const { get, post } = require('../../utils/request');
const { checkLogin } = require('../../utils/util');

const RISK_CONFIG = {
  1: { name: '优秀', color: '#1B8C3D', emoji: '✅', bg: 'rgba(27,140,61,0.08)' },
  2: { name: '正常', color: '#4CAF50', emoji: '🟢', bg: 'rgba(76,175,80,0.08)' },
  3: { name: '轻度异常', color: '#FFC107', emoji: '⚠️', bg: 'rgba(255,193,7,0.10)' },
  4: { name: '中度异常', color: '#FF9800', emoji: '🔶', bg: 'rgba(255,152,0,0.10)' },
  5: { name: '严重异常', color: '#F44336', emoji: '🔴', bg: 'rgba(244,67,54,0.10)' }
};

function getScoreColor(score) {
  if (score >= 90) return '#1B8C3D';
  if (score >= 75) return '#4CAF50';
  if (score >= 60) return '#FFC107';
  if (score >= 40) return '#FF9800';
  return '#F44336';
}

function getScoreLevel(score) {
  if (score >= 90) return '优秀';
  if (score >= 75) return '良好';
  if (score >= 60) return '一般';
  if (score >= 40) return '偏低';
  return '较差';
}

Page({
  data: {
    reportId: '',
    report: null,
    aiData: null,
    aiRawText: '',

    healthScore: 0,
    healthScoreColor: '#4CAF50',
    healthScoreLevel: '',
    healthScoreComment: '',

    totalItems: 0,
    abnormalCount: 0,
    excellentCount: 0,
    normalCount: 0,

    categories: [],
    expandedItems: {},

    loading: true,
    analyzing: false,
    analyzeText: 'AI正在分析...',
    analyzeTexts: ['AI正在分析...', '正在评估风险...', '正在生成建议...', '分析完成！'],
    analyzeTextIndex: 0,

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

  onUnload() {
    this.clearAnalyzeTimer();
  },

  clearAnalyzeTimer() {
    if (this._analyzeTimer) {
      clearInterval(this._analyzeTimer);
      this._analyzeTimer = null;
    }
  },

  startAnalyzeAnimation() {
    this.setData({ analyzing: true, analyzeTextIndex: 0, analyzeText: this.data.analyzeTexts[0] });
    let idx = 0;
    this._analyzeTimer = setInterval(() => {
      idx++;
      if (idx >= this.data.analyzeTexts.length) {
        this.clearAnalyzeTimer();
        return;
      }
      this.setData({ analyzeTextIndex: idx, analyzeText: this.data.analyzeTexts[idx] });
    }, 1500);
  },

  stopAnalyzeAnimation() {
    this.clearAnalyzeTimer();
    this.setData({
      analyzing: false,
      analyzeTextIndex: this.data.analyzeTexts.length - 1,
      analyzeText: this.data.analyzeTexts[this.data.analyzeTexts.length - 1]
    });
  },

  async loadDetail(id) {
    this.setData({ loading: true });
    this.startAnalyzeAnimation();
    try {
      const res = await get(`/api/report/detail/${id}`, {}, { suppressErrorToast: true });
      const report = res.data || res;

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

      let healthScore = 0;
      let healthScoreColor = '#4CAF50';
      let healthScoreLevel = '';
      let healthScoreComment = '';
      let totalItems = 0;
      let abnormalCount = 0;
      let excellentCount = 0;
      let normalCount = 0;
      let categories = [];
      let expandedItems = {};

      if (aiData) {
        if (aiData.healthScore) {
          healthScore = aiData.healthScore.score || report.health_score || 0;
          healthScoreLevel = aiData.healthScore.level || getScoreLevel(healthScore);
          healthScoreComment = aiData.healthScore.comment || '';
        } else {
          healthScore = report.health_score || 0;
          healthScoreLevel = getScoreLevel(healthScore);
        }
        healthScoreColor = getScoreColor(healthScore);

        if (aiData.summary) {
          totalItems = aiData.summary.totalItems || 0;
          abnormalCount = aiData.summary.abnormalCount || 0;
          excellentCount = aiData.summary.excellentCount || 0;
          normalCount = aiData.summary.normalCount || 0;
        }

        if (aiData.categories && Array.isArray(aiData.categories)) {
          categories = aiData.categories.map((cat, catIdx) => {
            const items = (cat.items || []).map((item, itemIdx) => {
              const rl = item.riskLevel || 2;
              const rc = RISK_CONFIG[rl] || RISK_CONFIG[2];
              const key = `${catIdx}_${itemIdx}`;
              const defaultExpanded = rl >= 3;
              if (defaultExpanded) {
                expandedItems[key] = true;
              }
              return {
                ...item,
                riskLevel: rl,
                riskName: item.riskName || rc.name,
                riskColor: rc.color,
                riskEmoji: rc.emoji,
                riskBg: rc.bg,
                detail: item.detail || {},
                expandKey: key
              };
            });
            return {
              name: cat.name || '其他',
              emoji: cat.emoji || '📋',
              items
            };
          });
        }
      }

      this.stopAnalyzeAnimation();
      this.setData({
        report,
        aiData,
        aiRawText,
        healthScore,
        healthScoreColor,
        healthScoreLevel,
        healthScoreComment,
        totalItems,
        abnormalCount,
        excellentCount,
        normalCount,
        categories,
        expandedItems,
        loading: false
      });

      if (aiData && healthScore > 0) {
        setTimeout(() => this.drawScoreRing(), 100);
      }
    } catch (e) {
      this.stopAnalyzeAnimation();
      console.log('loadDetail error', e);
      this.setData({ loading: false });
      wx.showToast({ title: '加载失败', icon: 'none' });
    }
  },

  drawScoreRing() {
    const query = wx.createSelectorQuery();
    query.select('#scoreCanvas').fields({ node: true, size: true }).exec((res) => {
      if (!res || !res[0]) return;
      const canvas = res[0].node;
      const ctx = canvas.getContext('2d');
      const sysInfo = wx.getWindowInfo ? wx.getWindowInfo() : wx.getSystemInfoSync();
      const dpr = sysInfo.pixelRatio || 2;
      canvas.width = res[0].width * dpr;
      canvas.height = res[0].height * dpr;
      ctx.scale(dpr, dpr);

      const w = res[0].width;
      const h = res[0].height;
      const cx = w / 2;
      const cy = h / 2;
      const radius = Math.min(w, h) / 2 - 12;
      const lineWidth = 14;
      const score = this.data.healthScore;
      const color = this.data.healthScoreColor;

      ctx.clearRect(0, 0, w, h);

      ctx.beginPath();
      ctx.arc(cx, cy, radius, 0, Math.PI * 2);
      ctx.strokeStyle = '#f0f0f0';
      ctx.lineWidth = lineWidth;
      ctx.lineCap = 'round';
      ctx.stroke();

      const startAngle = -Math.PI / 2;
      const endAngle = startAngle + (Math.PI * 2 * score / 100);
      ctx.beginPath();
      ctx.arc(cx, cy, radius, startAngle, endAngle);
      ctx.strokeStyle = color;
      ctx.lineWidth = lineWidth;
      ctx.lineCap = 'round';
      ctx.stroke();
    });
  },

  toggleItemDetail(e) {
    const key = e.currentTarget.dataset.key;
    const field = `expandedItems.${key}`;
    this.setData({ [field]: !this.data.expandedItems[key] });
  },

  goCompare() {
    const id = this.data.reportId;
    wx.navigateTo({ url: `/pages/checkup-compare/index?id1=${id}` });
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
