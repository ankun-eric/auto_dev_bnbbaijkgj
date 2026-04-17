const { get } = require('../../utils/request');

Page({
  data: {
    loading: true,
    detail: null,
    products: [],
    showAllProducts: false
  },

  onLoad(options) {
    const { id } = options;
    if (id) {
      this.loadDetail(id);
      this.loadProducts(id);
    }
  },

  async loadDetail(id) {
    this.setData({ loading: true });
    try {
      const res = await get(`/api/tcm/diagnosis/${id}`, {}, { showLoading: false, suppressErrorToast: true });
      if (res) {
        this.setData({
          detail: {
            id: res.id,
            constitution_type: res.constitution_type || '未知体质',
            description: res.description || '',
            traits: res.traits || [],
            advices: res.advices || [],
            family_member_name: res.family_member_name || res.family_member_relation || '',
            created_at: this._formatTime(res.created_at)
          }
        });
        if (res.constitution_type) {
          this._loadProductsByType(res.constitution_type);
        }
      }
    } catch (e) {
      wx.showToast({ title: '加载失败', icon: 'none' });
    } finally {
      this.setData({ loading: false });
    }
  },

  async loadProducts(diagnosisId) {
    // fallback: try loading products by diagnosis id
  },

  async _loadProductsByType(constitutionType) {
    try {
      const res = await get('/api/products', {
        constitution_type: constitutionType,
        page_size: 6
      }, { showLoading: false, suppressErrorToast: true });
      const list = Array.isArray(res) ? res : (res && (res.items || res.data) || []);
      this.setData({ products: list.slice(0, 6) });
    } catch (e) {
      console.log('loadProducts error', e);
    }
  },

  _formatTime(dateStr) {
    if (!dateStr) return '';
    const d = new Date(dateStr);
    if (isNaN(d.getTime())) return '';
    const y = d.getFullYear();
    const m = String(d.getMonth() + 1).padStart(2, '0');
    const day = String(d.getDate()).padStart(2, '0');
    return `${y}-${m}-${day}`;
  },

  goViewAllProducts() {
    const type = this.data.detail ? this.data.detail.constitution_type : '';
    wx.navigateTo({
      url: `/pages/products/index?constitution_type=${encodeURIComponent(type)}`
    });
  },

  goProductDetail(e) {
    const id = e.currentTarget.dataset.id;
    if (id) {
      wx.navigateTo({ url: `/pages/product-detail/index?id=${id}` });
    }
  },

  goAiConsult() {
    const detail = this.data.detail;
    if (!detail) return;
    const type = detail.constitution_type || '';
    const memberName = detail.family_member_name || '本人';
    const summary = encodeURIComponent(`体质调理 · ${type} · ${memberName}`);
    wx.navigateTo({
      url: `/pages/chat/index?type=constitution&summary=${summary}`
    });
  }
});
