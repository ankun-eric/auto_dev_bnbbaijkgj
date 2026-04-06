const { get, post } = require('../../utils/request');

Page({
  data: {
    indicatorName: '',
    trendData: [],
    aiAnalysis: '',
    refMin: null,
    refMax: null,
    unit: '',
    loading: true,
    canvasWidth: 0,
    canvasHeight: 0
  },

  onLoad(options) {
    const name = decodeURIComponent(options.name || '');
    if (!name) {
      wx.showToast({ title: '缺少指标名称', icon: 'none' });
      return;
    }
    wx.setNavigationBarTitle({ title: name + ' - 趋势' });
    this.setData({ indicatorName: name });
    this.initCanvas();
    this.loadTrendData(name);
  },

  initCanvas() {
    const sysInfo = wx.getSystemInfoSync();
    const canvasWidth = sysInfo.windowWidth - 48;
    const canvasHeight = 220;
    this.setData({ canvasWidth, canvasHeight });
  },

  parseRefRange(ref) {
    if (!ref) return { min: null, max: null };
    const match = ref.match(/([\d.]+)\s*[-~～]\s*([\d.]+)/);
    if (match) return { min: parseFloat(match[1]), max: parseFloat(match[2]) };
    return { min: null, max: null };
  },

  async loadTrendData(name) {
    this.setData({ loading: true });
    try {
      const res = await get(`/api/report/trend/${encodeURIComponent(name)}`, {}, { suppressErrorToast: true });
      const data = res.data || res;
      const rawPoints = data.data_points || data.points || data.items || data.trend || [];
      const points = rawPoints.map(p => ({
        date: p.report_date || (p.created_at ? p.created_at.substring(0, 10) : ''),
        value: p.value,
        status: p.status,
        created_at: p.created_at
      }));
      const range = this.parseRefRange(data.reference_range);
      const unit = data.unit || '';

      this.setData({
        trendData: points,
        refMin: range.min,
        refMax: range.max,
        unit,
        loading: false
      });

      this.drawChart();
      this.loadAnalysis(name);
    } catch (e) {
      console.log('loadTrend error', e);
      this.setData({ loading: false });
      wx.showToast({ title: '加载失败', icon: 'none' });
    }
  },

  async loadAnalysis(name) {
    try {
      const res = await post('/api/report/trend/analysis', { indicator_name: name }, { showLoading: false, suppressErrorToast: true });
      const analysis = res.analysis || res.data || res.text || '';
      this.setData({ aiAnalysis: typeof analysis === 'string' ? analysis : (analysis.text || '') });
    } catch (e) {
      console.log('loadAnalysis error', e);
    }
  },

  drawChart() {
    const { trendData, refMin, refMax, canvasWidth, canvasHeight } = this.data;
    if (!trendData.length) return;

    const query = wx.createSelectorQuery().in(this);
    query.select('#trendCanvas')
      .fields({ node: true, size: true })
      .exec((res) => {
        if (!res[0]) {
          this.drawWithOldApi();
          return;
        }
        const canvas = res[0].node;
        const ctx = canvas.getContext('2d');
        const dpr = wx.getSystemInfoSync().pixelRatio;
        canvas.width = canvasWidth * dpr;
        canvas.height = canvasHeight * dpr;
        ctx.scale(dpr, dpr);

        this.renderChart(ctx, canvasWidth, canvasHeight);
      });
  },

  drawWithOldApi() {
    const ctx = wx.createCanvasContext('trendCanvasOld', this);
    const { canvasWidth, canvasHeight } = this.data;
    this.renderChartOld(ctx, canvasWidth, canvasHeight);
    ctx.draw();
  },

  renderChart(ctx, width, height) {
    const { trendData, refMin, refMax } = this.data;
    const padding = { top: 30, right: 30, bottom: 50, left: 55 };
    const chartW = width - padding.left - padding.right;
    const chartH = height - padding.top - padding.bottom;

    const values = trendData.map(p => parseFloat(p.value));
    let dataMin = Math.min(...values);
    let dataMax = Math.max(...values);
    if (refMin != null) dataMin = Math.min(dataMin, refMin);
    if (refMax != null) dataMax = Math.max(dataMax, refMax);
    const range = dataMax - dataMin || 1;
    const yMin = dataMin - range * 0.1;
    const yMax = dataMax + range * 0.1;
    const yRange = yMax - yMin;

    ctx.clearRect(0, 0, width, height);

    // background
    ctx.fillStyle = '#ffffff';
    ctx.fillRect(0, 0, width, height);

    // normal range band
    if (refMin != null && refMax != null) {
      const y1 = padding.top + chartH - ((refMax - yMin) / yRange) * chartH;
      const y2 = padding.top + chartH - ((refMin - yMin) / yRange) * chartH;
      ctx.fillStyle = 'rgba(82, 196, 26, 0.1)';
      ctx.fillRect(padding.left, y1, chartW, y2 - y1);

      // ref lines
      ctx.setLineDash([4, 4]);
      ctx.strokeStyle = 'rgba(82, 196, 26, 0.4)';
      ctx.lineWidth = 1;
      ctx.beginPath();
      ctx.moveTo(padding.left, y1);
      ctx.lineTo(padding.left + chartW, y1);
      ctx.stroke();
      ctx.beginPath();
      ctx.moveTo(padding.left, y2);
      ctx.lineTo(padding.left + chartW, y2);
      ctx.stroke();
      ctx.setLineDash([]);

      // ref labels
      ctx.fillStyle = '#52c41a';
      ctx.font = '10px sans-serif';
      ctx.textAlign = 'right';
      ctx.fillText(refMax.toString(), padding.left - 5, y1 + 4);
      ctx.fillText(refMin.toString(), padding.left - 5, y2 + 4);
    }

    // Y axis grid
    ctx.strokeStyle = '#f0f0f0';
    ctx.lineWidth = 0.5;
    const gridCount = 4;
    for (let i = 0; i <= gridCount; i++) {
      const y = padding.top + (chartH / gridCount) * i;
      ctx.beginPath();
      ctx.moveTo(padding.left, y);
      ctx.lineTo(padding.left + chartW, y);
      ctx.stroke();

      ctx.fillStyle = '#bbb';
      ctx.font = '10px sans-serif';
      ctx.textAlign = 'right';
      const val = yMax - (yRange / gridCount) * i;
      ctx.fillText(val.toFixed(1), padding.left - 5, y + 4);
    }

    // X axis labels
    ctx.fillStyle = '#bbb';
    ctx.font = '9px sans-serif';
    ctx.textAlign = 'center';
    const step = Math.max(1, Math.floor(trendData.length / 5));
    trendData.forEach((p, i) => {
      if (i % step === 0 || i === trendData.length - 1) {
        const x = padding.left + (i / (trendData.length - 1 || 1)) * chartW;
        const label = (p.date || p.created_at || '').substring(5, 10);
        ctx.fillText(label, x, height - padding.bottom + 18);
      }
    });

    // data line
    ctx.beginPath();
    ctx.strokeStyle = '#52c41a';
    ctx.lineWidth = 2;
    ctx.lineJoin = 'round';
    trendData.forEach((p, i) => {
      const x = padding.left + (i / (trendData.length - 1 || 1)) * chartW;
      const y = padding.top + chartH - ((parseFloat(p.value) - yMin) / yRange) * chartH;
      if (i === 0) ctx.moveTo(x, y);
      else ctx.lineTo(x, y);
    });
    ctx.stroke();

    // gradient fill
    const grad = ctx.createLinearGradient(0, padding.top, 0, padding.top + chartH);
    grad.addColorStop(0, 'rgba(82, 196, 26, 0.15)');
    grad.addColorStop(1, 'rgba(82, 196, 26, 0.02)');
    ctx.lineTo(padding.left + chartW, padding.top + chartH);
    ctx.lineTo(padding.left, padding.top + chartH);
    ctx.closePath();
    ctx.fillStyle = grad;
    ctx.fill();

    // data points
    trendData.forEach((p, i) => {
      const x = padding.left + (i / (trendData.length - 1 || 1)) * chartW;
      const y = padding.top + chartH - ((parseFloat(p.value) - yMin) / yRange) * chartH;
      const val = parseFloat(p.value);
      const isAbnormal = (refMin != null && val < refMin) || (refMax != null && val > refMax);

      ctx.beginPath();
      ctx.arc(x, y, 4, 0, 2 * Math.PI);
      ctx.fillStyle = isAbnormal ? '#ff4d4f' : '#52c41a';
      ctx.fill();
      ctx.strokeStyle = '#fff';
      ctx.lineWidth = 2;
      ctx.stroke();

      // value label for abnormal points
      if (isAbnormal) {
        ctx.fillStyle = '#ff4d4f';
        ctx.font = 'bold 10px sans-serif';
        ctx.textAlign = 'center';
        ctx.fillText(val.toString(), x, y - 10);
      }
    });
  },

  renderChartOld(ctx, width, height) {
    const { trendData, refMin, refMax } = this.data;
    const padding = { top: 30, right: 30, bottom: 50, left: 55 };
    const chartW = width - padding.left - padding.right;
    const chartH = height - padding.top - padding.bottom;

    const values = trendData.map(p => parseFloat(p.value));
    let dataMin = Math.min(...values);
    let dataMax = Math.max(...values);
    if (refMin != null) dataMin = Math.min(dataMin, refMin);
    if (refMax != null) dataMax = Math.max(dataMax, refMax);
    const range = dataMax - dataMin || 1;
    const yMin = dataMin - range * 0.1;
    const yMax = dataMax + range * 0.1;
    const yRange = yMax - yMin;

    ctx.setFillStyle('#ffffff');
    ctx.fillRect(0, 0, width, height);

    if (refMin != null && refMax != null) {
      const y1 = padding.top + chartH - ((refMax - yMin) / yRange) * chartH;
      const y2 = padding.top + chartH - ((refMin - yMin) / yRange) * chartH;
      ctx.setFillStyle('rgba(82, 196, 26, 0.1)');
      ctx.fillRect(padding.left, y1, chartW, y2 - y1);

      ctx.setLineDash([4, 4]);
      ctx.setStrokeStyle('rgba(82, 196, 26, 0.4)');
      ctx.setLineWidth(1);
      ctx.beginPath();
      ctx.moveTo(padding.left, y1);
      ctx.lineTo(padding.left + chartW, y1);
      ctx.stroke();
      ctx.beginPath();
      ctx.moveTo(padding.left, y2);
      ctx.lineTo(padding.left + chartW, y2);
      ctx.stroke();
      ctx.setLineDash([]);
    }

    ctx.setStrokeStyle('#f0f0f0');
    ctx.setLineWidth(0.5);
    const gridCount = 4;
    for (let i = 0; i <= gridCount; i++) {
      const y = padding.top + (chartH / gridCount) * i;
      ctx.beginPath();
      ctx.moveTo(padding.left, y);
      ctx.lineTo(padding.left + chartW, y);
      ctx.stroke();

      ctx.setFillStyle('#bbb');
      ctx.setFontSize(10);
      ctx.setTextAlign('right');
      const val = yMax - (yRange / gridCount) * i;
      ctx.fillText(val.toFixed(1), padding.left - 5, y + 4);
    }

    ctx.setFillStyle('#bbb');
    ctx.setFontSize(9);
    ctx.setTextAlign('center');
    const step = Math.max(1, Math.floor(trendData.length / 5));
    trendData.forEach((p, i) => {
      if (i % step === 0 || i === trendData.length - 1) {
        const x = padding.left + (i / (trendData.length - 1 || 1)) * chartW;
        const label = (p.date || p.created_at || '').substring(5, 10);
        ctx.fillText(label, x, height - padding.bottom + 18);
      }
    });

    ctx.beginPath();
    ctx.setStrokeStyle('#52c41a');
    ctx.setLineWidth(2);
    ctx.setLineJoin('round');
    trendData.forEach((p, i) => {
      const x = padding.left + (i / (trendData.length - 1 || 1)) * chartW;
      const y = padding.top + chartH - ((parseFloat(p.value) - yMin) / yRange) * chartH;
      if (i === 0) ctx.moveTo(x, y);
      else ctx.lineTo(x, y);
    });
    ctx.stroke();

    trendData.forEach((p, i) => {
      const x = padding.left + (i / (trendData.length - 1 || 1)) * chartW;
      const y = padding.top + chartH - ((parseFloat(p.value) - yMin) / yRange) * chartH;
      const val = parseFloat(p.value);
      const isAbnormal = (refMin != null && val < refMin) || (refMax != null && val > refMax);

      ctx.beginPath();
      ctx.arc(x, y, 4, 0, 2 * Math.PI);
      ctx.setFillStyle(isAbnormal ? '#ff4d4f' : '#52c41a');
      ctx.fill();
      ctx.setStrokeStyle('#fff');
      ctx.setLineWidth(2);
      ctx.stroke();

      if (isAbnormal) {
        ctx.setFillStyle('#ff4d4f');
        ctx.setFontSize(10);
        ctx.setTextAlign('center');
        ctx.fillText(val.toString(), x, y - 10);
      }
    });
  }
});
