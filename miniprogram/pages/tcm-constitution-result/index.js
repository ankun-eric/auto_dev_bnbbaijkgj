const { get, post } = require('../../utils/request');

Page({
  data: {
    diagnosisId: null,
    loading: true,
    data: null,
    claimingCoupon: false,
    // 雷达图尺寸
    radarSize: 260,
    radarPoints: '',
    radarBgRings: [],
    radarAxes: [],
    radarDots: [],
    radarLabels: []
  },

  onLoad(options) {
    const id = options && options.id;
    if (!id) {
      wx.showToast({ title: '参数错误', icon: 'none' });
      setTimeout(() => wx.navigateBack(), 1200);
      return;
    }
    this.setData({ diagnosisId: id });
    this.fetchResult();
  },

  onShareAppMessage() {
    const d = this.data.data;
    if (!d) return { title: '中医体质测评', path: '/pages/tcm/index' };
    return {
      title: `我的体质是「${d.screen1_card.type}」${d.screen1_card.persona.emoji || '🌿'} 快来测测你的`,
      path: `/pages/tcm/index`,
      imageUrl: ''
    };
  },

  onShareTimeline() {
    const d = this.data.data;
    return {
      title: d ? `我是${d.screen1_card.type}，你呢？` : '中医体质测评',
      query: ''
    };
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

  goBookAppointment() {
    wx.navigateTo({ url: '/pages/unified-orders/index?source=tizhi_test&project=moxibustion' });
  },

  goMyCoupons() {
    wx.navigateTo({ url: '/pages/my-coupons/index' });
  },

  goPackageDetail(e) {
    const pkg = e.currentTarget.dataset.pkg;
    if (!pkg || !pkg.matched || !pkg.sku_id) {
      wx.showToast({ title: '敬请期待', icon: 'none' });
      return;
    }
    if (pkg.sku_kind === 'product') {
      wx.navigateTo({ url: `/pages/product-detail/index?id=${pkg.sku_id}&source=tizhi_test` });
    } else {
      wx.navigateTo({ url: `/pages/service-detail/index?id=${pkg.sku_id}&source=tizhi_test` });
    }
  },

  handleShareButton() {
    wx.showToast({ title: '请点击右上角「···」分享', icon: 'none' });
  }
});
