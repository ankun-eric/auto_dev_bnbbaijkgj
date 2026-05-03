// [卡管理 v2.0 第 3 期] 小程序核销码页（极简版）
const request = require('../../../utils/request');

Page({
  data: {
    userCardId: null,
    code: null,
    remaining: 0,
    timer: null,
  },
  onLoad(options) {
    this.setData({ userCardId: Number(options && options.id) });
    this.issue();
  },
  onUnload() {
    if (this.data.timer) clearInterval(this.data.timer);
  },
  issue() {
    const that = this;
    request({
      url: `/api/cards/me/${this.data.userCardId}/redemption-code`,
      method: 'POST',
    }).then((res) => {
      that.setData({ code: res });
      that.startCountdown();
    });
  },
  startCountdown() {
    const that = this;
    if (that.data.timer) clearInterval(that.data.timer);
    const t = setInterval(() => {
      const exp = new Date(that.data.code.expires_at).getTime();
      const left = Math.max(0, Math.floor((exp - Date.now()) / 1000));
      that.setData({ remaining: left });
      if (left <= 0) {
        clearInterval(t);
        that.issue();
      }
    }, 1000);
    that.setData({ timer: t });
  },
});
