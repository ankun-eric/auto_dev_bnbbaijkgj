const { post, uploadFile } = require('../../utils/request');

Page({
  data: {
    orderId: '',
    rating: 5,
    content: '',
    images: [],
    submitting: false,
    maxImages: 6
  },

  onLoad(options) {
    this.setData({ orderId: options.order_id });
  },

  setRating(e) {
    const star = e.currentTarget.dataset.star;
    this.setData({ rating: star });
  },

  onContentInput(e) {
    this.setData({ content: e.detail.value });
  },

  chooseImage() {
    const remaining = this.data.maxImages - this.data.images.length;
    if (remaining <= 0) {
      wx.showToast({ title: `最多上传${this.data.maxImages}张图片`, icon: 'none' });
      return;
    }
    wx.chooseMedia({
      count: remaining,
      mediaType: ['image'],
      sizeType: ['compressed'],
      sourceType: ['album', 'camera'],
      success: (res) => {
        const newImages = res.tempFiles.map(f => f.tempFilePath);
        this.setData({
          images: this.data.images.concat(newImages)
        });
      }
    });
  },

  removeImage(e) {
    const idx = e.currentTarget.dataset.index;
    const images = this.data.images.filter((_, i) => i !== idx);
    this.setData({ images });
  },

  previewImage(e) {
    const current = e.currentTarget.dataset.src;
    wx.previewImage({ current, urls: this.data.images });
  },

  async submitReview() {
    if (this.data.submitting) return;
    if (!this.data.content.trim()) {
      wx.showToast({ title: '请输入评价内容', icon: 'none' });
      return;
    }

    this.setData({ submitting: true });
    try {
      let imageUrls = [];
      for (const img of this.data.images) {
        try {
          const res = await uploadFile('/api/upload/image', img, 'file', {}, { showLoading: false });
          imageUrls.push(res.url || res.data?.url || '');
        } catch (e) {
          console.log('upload image error', e);
        }
      }

      await post(`/api/orders/unified/${this.data.orderId}/review`, {
        rating: this.data.rating,
        content: this.data.content,
        images: imageUrls.filter(Boolean)
      });

      wx.showToast({ title: '评价成功', icon: 'success' });
      setTimeout(() => wx.navigateBack(), 1500);
    } catch (e) {
      console.log('submitReview error', e);
    } finally {
      this.setData({ submitting: false });
    }
  }
});
