// [PRD-TCM-CARD-MSG-PROTOCOL-V1 2026-05-20] 通用问卷结果卡片（AI 侧）
// [PRD-HSC-OPTIM-V3 2026-05-21] 新增 AI 解读状态轮询 + 按钮置灰联动
//
// 接收后端通用卡片协议 payload，渲染 AI 侧"测评结果汇总卡片"。
// 视觉风格：报告卡片化稿 2 —— 白底 + 顶部色条 + 主结论 + 雷达图 + 查看详情
const { get, post } = require('../../utils/request.js');

Component({
  properties: {
    payload: {
      type: Object,
      value: null,
    },
  },
  data: {
    radarPolygonPoints: '',
    radarAxisPoints: [],
    radarLabelPoints: [],
    coverColorBg: '#0EA5E91A',
    // [PRD-TIZHI-OPTIM-V1] 兼夹体质文本（WXML 不支持 .join，预处理）
    secondaryText: '',
    // [PRD-HSC-OPTIM-V3 2026-05-21] AI 解读状态
    aiStatus: 'done',
    _pollTimer: null,
    _pollStartedAt: 0,
  },
  observers: {
    'payload': function (payload) {
      if (!payload) return;
      const color = payload.cover_color || '#0EA5E9';
      const sec = Array.isArray(payload.secondary_types) ? payload.secondary_types.filter(Boolean) : [];
      this.setData({ coverColorBg: color + '1A', secondaryText: sec.join('、') });
      this._renderRadar(payload.scores || {});
      // 仅健康自查启动轮询
      this._maybeStartAiPoll(payload);
    },
  },
  detached() {
    this._stopAiPoll();
  },
  methods: {
    _renderRadar(scores) {
      const labels = Object.keys(scores || {});
      if (!labels.length) {
        this.setData({ radarPolygonPoints: '', radarAxisPoints: [], radarLabelPoints: [] });
        return;
      }
      const size = 160;
      const cx = size / 2;
      const cy = size / 2;
      const radius = size * 0.36;
      const max = 100;
      const angleStep = (Math.PI * 2) / labels.length;
      const polyPts = [];
      const axisPts = [];
      const labelPts = [];
      labels.forEach((k, i) => {
        const v = Math.min(max, Math.max(0, Number(scores[k]) || 0));
        const r = (v / max) * radius;
        const a = -Math.PI / 2 + i * angleStep;
        const x = (cx + Math.cos(a) * r).toFixed(1);
        const y = (cy + Math.sin(a) * r).toFixed(1);
        polyPts.push(`${x},${y}`);
        const ax = cx + Math.cos(a) * radius;
        const ay = cy + Math.sin(a) * radius;
        axisPts.push({ x1: cx, y1: cy, x2: ax.toFixed(1), y2: ay.toFixed(1) });
        const lx = cx + Math.cos(a) * (radius + 12);
        const ly = cy + Math.sin(a) * (radius + 12);
        labelPts.push({ x: lx.toFixed(1), y: ly.toFixed(1), label: k });
      });
      this.setData({
        radarPolygonPoints: polyPts.join(' '),
        radarAxisPoints: axisPts,
        radarLabelPoints: labelPts,
      });
    },
    onClickDetail() {
      // 分析中状态禁止点击
      if ((this.data.aiStatus || 'done') === 'pending') return;
      if ((this.data.aiStatus || 'done') === 'failed') {
        this._retryAi();
        return;
      }
      const payload = this.data.payload || {};
      const target = payload.detail_target || {};
      this.triggerEvent('viewdetail', { target, payload });
    },
    _maybeStartAiPoll(payload) {
      const code = (payload && payload.questionnaire_code) || '';
      const aid = (payload && (payload.answer_id || payload.result_id)) || null;
      if (code !== 'health_self_check' || !aid) {
        this.setData({ aiStatus: 'done' });
        return;
      }
      this._stopAiPoll();
      this.setData({ aiStatus: 'pending', _pollStartedAt: Date.now() });
      const pollOnce = () => {
        get(`/api/questionnaire/answers/${aid}/ai-status`).then((res) => {
          const s = (res && (res.ai_status || (res.data && res.data.ai_status))) || 'done';
          this.setData({ aiStatus: s });
          if (s !== 'pending') this._stopAiPoll();
          if (Date.now() - (this.data._pollStartedAt || 0) > 60000) {
            this._stopAiPoll();
            if ((this.data.aiStatus || 'done') === 'pending') {
              this.setData({ aiStatus: 'failed' });
            }
          }
        }).catch(() => {});
      };
      pollOnce();
      const t = setInterval(pollOnce, 3000);
      this.setData({ _pollTimer: t });
    },
    _stopAiPoll() {
      if (this.data._pollTimer) {
        clearInterval(this.data._pollTimer);
        this.setData({ _pollTimer: null });
      }
    },
    _retryAi() {
      const aid = (this.data.payload && (this.data.payload.answer_id || this.data.payload.result_id)) || null;
      if (!aid) return;
      post(`/api/questionnaire/answers/${aid}/retry-ai`, {}).then(() => {
        this._maybeStartAiPoll(this.data.payload);
      }).catch(() => {});
    },
  },
});
