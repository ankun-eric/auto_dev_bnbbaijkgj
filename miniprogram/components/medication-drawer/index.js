// [PRD-432] 长期用药半屏抽屉 - 小程序组件
const app = getApp();

Component({
  properties: {
    consultantId: { type: Number, value: 0 },
    consultantName: { type: String, value: '' }
  },
  data: {
    items: [],
    loading: true,
    error: false,
    isNone: false
  },
  lifetimes: {
    attached() {
      this._fetch();
    }
  },
  methods: {
    _fetch() {
      const cid = this.data.consultantId;
      const baseUrl = (app && app.globalData && app.globalData.baseUrl) || '';
      const token = (app && app.globalData && app.globalData.token) || wx.getStorageSync('token') || '';
      this.setData({ loading: true, error: false });
      const that = this;
      wx.request({
        url: `${baseUrl}/api/v1/consultant/${cid}/medications`,
        method: 'GET',
        header: token ? { Authorization: `Bearer ${token}` } : {},
        success: (res) => {
          if (res.statusCode === 200 && res.data && Array.isArray(res.data.items)) {
            that.setData({
              items: res.data.items,
              isNone: !!res.data.is_none,
              error: false,
              loading: false,
            });
          } else {
            that.setData({ error: true, loading: false });
          }
        },
        fail: () => that.setData({ error: true, loading: false }),
      });
    },

    // [Bug-432-fix 2026-05-09] 暴露给 wxml「加载失败，点击重试」整行点击使用
    onRetry() {
      this._fetch();
    },
    onMaskTap(e) {
      if (e.target === e.currentTarget) {
        this.triggerEvent('close');
      }
    },
    onClose() {
      this.triggerEvent('close');
    },
    onGoManage() {
      this.triggerEvent('gomanage');
    },
    onGoCreate() {
      this.triggerEvent('gocreate');
    }
  }
});
