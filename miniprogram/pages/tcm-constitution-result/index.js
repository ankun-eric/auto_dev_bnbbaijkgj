const { get, post } = require('../../utils/request');

Page({
  data: {
    diagnosisId: null,
    loading: true,
    data: null,
    claimingCoupon: false,
    statusBarHeight: 20,
    navBarHeight: 44,
    // 雷达图尺寸
    radarSize: 260,
    radarPoints: '',
    radarBgRings: [],
    radarAxes: [],
    radarDots: [],
    radarLabels: []
  },

  onLoad(options) {
    // 计算自定义顶栏高度（状态栏 + 导航栏）
    try {
      const sys = wx.getSystemInfoSync();
      const statusBarHeight = sys.statusBarHeight || 20;
      let navBarHeight = 44;
      if (wx.getMenuButtonBoundingClientRect) {
        const rect = wx.getMenuButtonBoundingClientRect();
        navBarHeight = (rect.top - statusBarHeight) * 2 + rect.height;
      }
      this.setData({ statusBarHeight, navBarHeight });
    } catch (e) { /* noop */ }

    const id = options && options.id;
    if (!id) {
      wx.showToast({ title: '参数错误', icon: 'none' });
      setTimeout(() => this.goAiHome(), 1200);
      return;
    }
    this.setData({ diagnosisId: id });
    this.fetchResult();
  },

  _shareCover() {
    const app = getApp();
    const base = (app && app.globalData && app.globalData.baseUrl) || '';
    return base ? `${base}/binni-xiaokang-logo.png` : '';
  },

  // [PRD-TIZHI-OPTIM-V1] 优化点4·形态一：原生一键转发，标题动态带体质，固定精美封面，好友点开直达测评
  onShareAppMessage() {
    const d = this.data.data;
    if (!d) return { title: '宾尼小康 · 中医体质测评', path: '/pages/tcm/index' };
    const share = d.screen6_share || {};
    return {
      title: share.share_title || `我的体质是「${d.screen1_card.type}」，快来测测你是什么体质？`,
      path: `/pages/tcm/index`,
      imageUrl: this._shareCover()
    };
  },

  onShareTimeline() {
    const d = this.data.data;
    const share = (d && d.screen6_share) || {};
    return {
      title: d ? (share.share_title || `我的体质是「${d.screen1_card.type}」，快来测测你是什么体质？`) : '宾尼小康 · 中医体质测评',
      query: '',
      imageUrl: this._shareCover()
    };
  },

  // [PRD-TIZHI-OPTIM-V1] 优化点3：右上角返回直接回到 AI 首页（不再回旧列表页）
  goAiHome() {
    wx.reLaunch({ url: '/pages/ai/index' });
  },

  async fetchResult() {
    this.setData({ loading: true });
    try {
      const res = await get(`/api/constitution/result/${this.data.diagnosisId}`, {}, { showLoading: false });
      const data = res && (res.data || res);
      if (data && data.screen1_card) {
        // 预处理：拼接饮食宜/忌文本，避免 WXML 调用 .join
        if (data.screen3_plan && data.screen3_plan.diet) {
          if (Array.isArray(data.screen3_plan.diet.good)) {
            data.screen3_plan.diet.good_text = data.screen3_plan.diet.good.join(' · ');
          }
          if (Array.isArray(data.screen3_plan.diet.avoid)) {
            data.screen3_plan.diet.avoid_text = data.screen3_plan.diet.avoid.join(' · ');
          }
        }
        this.setData({ data });
        this._renderRadar(data.screen1_card.radar, data.screen1_card.color || '#52c41a');
      } else {
        wx.showToast({ title: '加载结果失败', icon: 'none' });
      }
    } catch (e) {
      wx.showToast({ title: '加载失败', icon: 'none' });
    } finally {
      this.setData({ loading: false });
    }
  },

  // 计算雷达图的 SVG-like 点坐标（小程序使用 view 堆叠或 canvas，这里用 view + 绝对定位方式）
  _renderRadar(radar, color) {
    if (!radar || !radar.dimensions) return;
    const size = this.data.radarSize;
    const cx = size / 2;
    const cy = size / 2;
    const r = size * 0.36;
    const n = radar.dimensions.length;
    const angle = i => (Math.PI * 2 * i) / n - Math.PI / 2;

    const pts = radar.scores.map((v, i) => {
      const vv = Math.max(0, Math.min(100, v)) / 100;
      return {
        x: cx + r * vv * Math.cos(angle(i)),
        y: cy + r * vv * Math.sin(angle(i))
      };
    });

    // 数据多边形点串（SVG polygon 用）
    const polygonPoints = pts.map(p => `${p.x.toFixed(1)},${p.y.toFixed(1)}`).join(' ');

    // 背景 4 环
    const rings = [0.25, 0.5, 0.75, 1.0].map(ratio => {
      return Array.from({ length: n }, (_, i) => {
        const x = cx + r * ratio * Math.cos(angle(i));
        const y = cy + r * ratio * Math.sin(angle(i));
        return `${x.toFixed(1)},${y.toFixed(1)}`;
      }).join(' ');
    });

    // 轴线
    const axes = Array.from({ length: n }, (_, i) => ({
      x1: cx, y1: cy,
      x2: cx + r * Math.cos(angle(i)),
      y2: cy + r * Math.sin(angle(i))
    }));

    // 标签位置
    const labels = radar.dimensions.map((name, i) => ({
      name,
      x: cx + (r + 18) * Math.cos(angle(i)),
      y: cy + (r + 18) * Math.sin(angle(i))
    }));

    this.setData({
      radarPoints: polygonPoints,
      radarBgRings: rings,
      radarAxes: axes,
      radarDots: pts,
      radarLabels: labels,
      radarColor: color
    });
  },

  async handleClaimCoupon() {
    if (this.data.claimingCoupon) return;
    this.setData({ claimingCoupon: true });
    try {
      const res = await post('/api/constitution/coupon/claim', {}, { showLoading: false });
      const r = res && (res.data || res);
      if (r && r.success) {
        wx.showToast({ title: r.already_claimed ? '您已领取' : '领取成功', icon: 'success' });
        this.fetchResult();
      } else {
        wx.showToast({ title: '领取失败', icon: 'none' });
      }
    } catch (e) {
      const msg = (e && e.data && e.data.detail) || '领取失败';
      wx.showToast({ title: String(msg), icon: 'none' });
    } finally {
      this.setData({ claimingCoupon: false });
    }
  },

  goMyCoupons() {
    wx.navigateTo({ url: '/pages/my-coupons/index' });
  },

  // [PRD-TIZHI-OPTIM-V1] 运营配置内容卡点击跳转（按 link_type 分发）
  goCardLink(e) {
    const card = e.currentTarget.dataset.card;
    if (!card) return;
    const v = card.link_value || '';
    switch (card.link_type) {
      case 'product':
        if (v) wx.navigateTo({ url: `/pages/product-detail/index?id=${v}&source=tizhi_test` });
        break;
      case 'service':
        if (v) wx.navigateTo({ url: `/pages/service-detail/index?id=${v}&source=tizhi_test` });
        break;
      case 'order':
        wx.navigateTo({ url: `/pages/unified-orders/index?source=tizhi_test&project=${v || 'moxibustion'}` });
        break;
      case 'coupon':
        this.handleClaimCoupon();
        break;
      case 'url':
        if (v) wx.navigateTo({ url: `/pages/webview/index?url=${encodeURIComponent(v)}` });
        break;
      default:
        break;
    }
  },

  handleShareButton() {
    wx.showToast({ title: '请点击右上角「···」分享', icon: 'none' });
  }
});
