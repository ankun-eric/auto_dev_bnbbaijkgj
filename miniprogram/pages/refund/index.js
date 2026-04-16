const { post, uploadFile } = require('../../utils/request');

Page({
  data: {
    orderId: '',
    reasons: ['不想要了', '商品质量问题', '服务不满意', '未按约定时间', '商品与描述不符', '其他'],
    selectedReason: 0,
    description: '',
    images: [],
    submitting: false,
    maxImages: 4
  },

  onLoad(options) {
    this.setData({ orderId: options.order_id });
  },

  selectReason(e) {
    this.setData({ selectedReason: e.detail.value });
  },

  onDescInput(e) {
    this.setData({ description: e.detail.value });
  },

  chooseImage() {
    const remaining = this.data.maxImages - this.data.images.length;
    if (remaining <= 0) return;
    wx.chooseMedia({
      count: remaining,
      mediaType: ['image'],
      sizeType: ['compressed'],
      sourceType: ['album', 'camera'],
      success: (res) => {
        const newImages = res.tempFiles.map(f => f.tempFilePath);
        this.setData({ images: this.data.images.concat(newImages) });
      }
    });
  },

  removeImage(e) {
    const idx = e.currentTarget.dataset.index;
    const images = this.data.images.filter((_, i) => i !== idx);
    this.setData({ images });
  },

  async submitRefund() {
    if (this.data.submitting) return;

    this.setData({ submitting: true });
    try {
      let imageUrls = [];
      for (const img of this.data.images) {
        try {
          const res = await uploadFile('/api/upload', img, 'file', {}, { showLoading: false });
          imageUrls.push(res.url || res.data?.url || '');
        } catch (e) {
          console.log('upload image error', e);
        }
      }

      await post(`/api/orders/unified/${this.data.orderId}/refund`, {
        reason: this.data.reasons[this.data.selectedReason],
        description: this.data.description,
        images: imageUrls.filter(Boolean)
      });

      wx.showToast({ title: '退款申请已提交', icon: 'success' });
      setTimeout(() => wx.navigateBack(), 1500);
    } catch (e) {
      console.log('submitRefund error', e);
    } finally {
      this.setData({ submitting: false });
    }
  }
});
