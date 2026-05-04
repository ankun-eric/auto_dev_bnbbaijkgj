const { get, post } = require('../../utils/request');
const { checkLogin } = require('../../utils/util');
// [2026-05-05 全端图片附件 BasePath 治理 v1.0] 把后端裸 /uploads/... 补齐为带 baseUrl 的绝对 URL
const { resolveAssetUrls } = require('../../utils/asset-url');

const RISK_CONFIG = {
  1: { name: '优秀', color: '#1B8C3D', emoji: '✅', bg: 'rgba(27,140,61,0.08)' },
  2: { name: '正常', color: '#4CAF50', emoji: '🟢', bg: 'rgba(76,175,80,0.08)' },
  3: { name: '轻度异常', color: '#FFC107', emoji: '⚠️', bg: 'rgba(255,193,7,0.10)' },
  4: { name: '中度异常', color: '#FF9800', emoji: '🔶', bg: 'rgba(255,152,0,0.10)' },
  5: { name: '严重异常', color: '#F44336', emoji: '🔴', bg: 'rgba(244,67,54,0.10)' }
};

const ANALYZE_PHASES = [
  { from: 0, to: 30, duration: 2500, text: '🔍 AI 正在分析您的指标…' },
  { from: 30, to: 60, duration: 3500, text: '📊 正在评估各项指标的风险等级…' },
  { from: 60, to: 90, duration: 6500, text: '📝 正在生成个性化健康建议…' },
  { from: 90, to: 99, duration: 50000, text: '🧠 AI 正在深度分析中，请耐心等待…' }
];

const TIMEOUT_MS = 60000;

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

function getErrorMessage(err) {
  if (!err) return '分析失败，请重试';
  if (err.errMsg && /request:fail/.test(err.errMsg)) return '网络连接异常，请检查网络后重试';
  const sc = err.statusCode || (err.raw && err.raw.statusCode);
  if (sc === 500) return '服务器繁忙，请稍后重试';
  if (sc === 404) return '报告不存在或已被删除';
  return '分析失败，请重试';
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

    // [2026-04-23 多图九宫格] 报告原图列表
    reportImages: [],

    loading: true,
    analyzing: false,
    analyzePercent: 0,
    analyzeText: '',
    analyzeTimeout: false,
    analyzeError: '',

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
    // [2026-04-23 多图九宫格] 单独拉取报告元数据以获取 file_urls
    this.loadReportImages(id);
  },

  // [2026-04-23 多图九宫格] 拉取报告原图列表
  async loadReportImages(id) {
    try {
      const detail = await get(`/api/checkup/reports/${id}`, {}, { showLoading: false, suppressErrorToast: true });
      if (!detail) return;
      const rawUrls = Array.isArray(detail.file_urls) && detail.file_urls.length > 0
        ? detail.file_urls.filter(Boolean)
        : (detail.file_url ? [detail.file_url] : []);
      // [2026-05-05 全端图片附件 BasePath 治理 v1.0] resolveAssetUrls 处理裸 /uploads/...
      this.setData({ reportImages: resolveAssetUrls(rawUrls) });
    } catch (e) {
      console.log('loadReportImages error', e);
    }
  },

  // [2026-04-23 多图九宫格] 点击缩略图，原生多图预览（支持左右滑 + 缩放）
  onImageTap(e) {
    const { urls, current } = e.currentTarget.dataset;
    if (!urls || urls.length === 0) return;
    wx.previewImage({
      current: current || urls[0],
      urls
    });
  },

  onUnload() {
    this.clearAnalyzeTimer();
  },

  clearAnalyzeTimer() {
    if (this._phaseTimer) {
      clearInterval(this._phaseTimer);
      this._phaseTimer = null;
    }
    if (this._timeoutTimer) {
      clearTimeout(this._timeoutTimer);
      this._timeoutTimer = null;
    }
  },

  startAnalyzeAnimation() {
    this._analyzeStartTime = Date.now();
    this._phaseIdx = 0;
    this._analysisDone = false;
    this.setData({
      analyzing: true,
      analyzePercent: 0,
      analyzeText: ANALYZE_PHASES[0].text,
      analyzeTimeout: false,
      analyzeError: ''
    });
    this._runPhase(0);

    this._timeoutTimer = setTimeout(() => {
      if (!this._analysisDone) {
        this.clearAnalyzeTimer();
        this._analysisDone = true;
        this.setData({
          analyzing: false,
          analyzeTimeout: true,
          loading: false
        });
      }
    }, TIMEOUT_MS);
  },

  _runPhase(idx) {
    if (idx >= ANALYZE_PHASES.length || this._analysisDone) return;
    const phase = ANALYZE_PHASES[idx];
    this._phaseIdx = idx;
    this.setData({ analyzeText: phase.text });

    const TICK = 50;
    const totalTicks = Math.floor(phase.duration / TICK);
    let tick = 0;

    this._phaseTimer = setInterval(() => {
      tick++;
      const progress = tick / totalTicks;
      const eased = 1 - Math.pow(1 - progress, 3);
      const percent = Math.min(Math.floor(phase.from + (phase.to - phase.from) * eased), phase.to);
      this.setData({ analyzePercent: percent });

      if (tick >= totalTicks) {
        clearInterval(this._phaseTimer);
        this._phaseTimer = null;
        this._runPhase(idx + 1);
      }
    }, TICK);
  },

  completeAnalyzeAnimation() {
    this.clearAnalyzeTimer();
    this._analysisDone = true;
    this.setData({
      analyzePercent: 100,
      analyzeText: '✅ 分析完成！'
    });
    return new Promise(resolve => setTimeout(() => {
      this.setData({ analyzing: false });
      resolve();
    }, 500));
  },

  stopAnalyzeWithError(err) {
    this.clearAnalyzeTimer();
    this._analysisDone = true;
    this.setData({
      analyzing: false,
      analyzeError: getErrorMessage(err),
      loading: false
    });
  },

  retryAnalyze() {
    this.setData({ analyzeError: '', analyzeTimeout: false });
    this.loadDetail(this.data.reportId);
  },

  goBackToList() {
    const pages = getCurrentPages();
    if (pages.length > 1) {
      wx.navigateBack();
    } else {
      wx.redirectTo({ url: '/pages/checkup/index' });
    }
  },

  async loadDetail(id) {
    this.setData({ loading: true, analyzeError: '', analyzeTimeout: false });
    this.startAnalyzeAnimation();
    try {
      const res = await get(`/api/report/detail/${id}`, {}, { suppressErrorToast: true });
      const report = res.data || res;

      // [2026-04-23 多图九宫格] 若 AI 详情接口也返回了 file_urls/file_url，优先作为兜底
      if (!this.data.reportImages || this.data.reportImages.length === 0) {
        const rawUrls = Array.isArray(report.file_urls) && report.file_urls.length > 0
          ? report.file_urls.filter(Boolean)
          : (report.file_url ? [report.file_url] : []);
        // [2026-05-05 全端图片附件 BasePath 治理 v1.0] resolveAssetUrls 处理裸 /uploads/...
        if (rawUrls.length > 0) this.setData({ reportImages: resolveAssetUrls(rawUrls) });
      }

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

      await this.completeAnalyzeAnimation();
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
      console.log('loadDetail error', e);
      this.stopAnalyzeWithError(e);
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
