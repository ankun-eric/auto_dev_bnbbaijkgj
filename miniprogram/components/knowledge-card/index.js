const { post } = require('../../utils/request');

Component({
  properties: {
    hit: { type: Object, value: {} },
    hitLogId: { type: Number, value: 0 }
  },

  data: {
    feedback: '',
    displayQuestion: '',
    displayTitle: '',
    displayText: '',
    images: [],
    products: [],
    effectiveLogId: 0,
    previewUrls: []
  },

  observers: {
    hit() {
      this.syncFromHit();
    },
    hitLogId() {
      this.syncFromHit();
    }
  },

  lifetimes: {
    attached() {
      this.syncFromHit();
    }
  },

  methods: {
    syncFromHit() {
      const hit = this.properties.hit || {};
      const fromProp = this.properties.hitLogId;
      const effectiveLogId = fromProp || hit.hit_log_id || 0;
      const parsed = this.parseHit(hit);
      const previewUrls = parsed.images.filter((u) => typeof u === 'string' && u.length > 0);
      this.setData({
        effectiveLogId,
        previewUrls,
        ...parsed
      });
    },

    parseHit(hit) {
      const h = hit || {};
      let displayText = '';
      const images = [];
      const products = [];

      const cj = h.content_json;
      if (typeof cj === 'string') {
        displayText = cj;
      } else if (cj && typeof cj === 'object') {
        displayText = cj.text || cj.body || cj.content || cj.answer || '';
        const imgs = cj.images || cj.image_urls || cj.pics || [];
        if (Array.isArray(imgs)) {
          imgs.forEach((u) => {
            if (u && typeof u === 'string') images.push(u);
          });
        }
        const prods = cj.products || cj.goods || [];
        if (Array.isArray(prods)) {
          prods.forEach((p) => {
            if (!p || typeof p !== 'object') return;
            const price = p.price;
            products.push({
              name: p.name || p.title || '商品',
              image: p.image || p.cover || p.pic || '',
              price: price !== undefined && price !== null ? String(price) : '',
              url: p.url || p.link || p.detail_url || '',
              path: p.path || p.mini_path || ''
            });
          });
        }
      }

      if (!displayText && h.title) {
        displayText = h.title;
      }

      return {
        displayQuestion: h.question || '',
        displayTitle: h.title || '',
        displayText,
        images,
        products
      };
    },

    onLike() {
      if (this.data.feedback === 'like') return;
      this.submitFeedback('like');
    },

    onDislike() {
      if (this.data.feedback === 'dislike') return;
      this.submitFeedback('dislike');
    },

    async submitFeedback(type) {
      const hit_log_id = this.data.effectiveLogId;
      if (!hit_log_id) {
        wx.showToast({ title: '暂无法提交反馈', icon: 'none' });
        return;
      }
      try {
        await post(
          '/api/chat/feedback',
          { hit_log_id, feedback: type },
          { showLoading: false }
        );
        this.setData({ feedback: type });
        wx.showToast({ title: '感谢反馈', icon: 'success' });
        this.triggerEvent('submitted', { feedback: type, hit_log_id });
      } catch (e) {
        console.log('knowledge feedback error', e);
      }
    },

    onPreviewImage(e) {
      const { url } = e.currentTarget.dataset;
      const urls = this.data.previewUrls;
      if (!url || !urls.length) return;
      wx.previewImage({ current: url, urls });
    },

    onViewProduct(e) {
      const { path: miniPath, url } = e.currentTarget.dataset;
      if (miniPath) {
        const p = miniPath.startsWith('/') ? miniPath : `/${miniPath}`;
        wx.navigateTo({ url: p });
        return;
      }
      if (url && /^https?:\/\//.test(url)) {
        wx.setClipboardData({
          data: url,
          success: () => wx.showToast({ title: '链接已复制', icon: 'success' })
        });
        return;
      }
      wx.showToast({ title: '暂无详情链接', icon: 'none' });
    }
  }
});
