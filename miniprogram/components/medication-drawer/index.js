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
      wx.request({
        url: `${baseUrl}/api/v1/consultant/${cid}/medications`,
        method: 'GET',
        header: token ? { Authorization: `Bearer ${token}` } : {},
        success: (res) => {
          if (res.statusCode === 200 && res.data) {
            this.setData({
              items: res.data.items || [],
              isNone: !!res.data.is_none,
              error: false
            });
          } else {
            this.setData({ error: true });
          }
        },
        fail: () => this.setData({ error: true }),
        complete: () => this.setData({ loading: false })
      });
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
