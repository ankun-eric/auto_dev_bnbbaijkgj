Page({
  data: {
    totalPoints: 1280,
    goods: [
      { id: 1, name: '体检优惠券', desc: '满300减50', icon: '🎫', bgColor: 'rgba(82,196,26,0.12)', points: 200, stock: 50 },
      { id: 2, name: '问诊优惠券', desc: '图文问诊8折', icon: '💬', bgColor: 'rgba(19,194,194,0.12)', points: 150, stock: 100 },
      { id: 3, name: '维生素C', desc: '60粒装', icon: '💊', bgColor: 'rgba(250,173,20,0.12)', points: 500, stock: 30 },
      { id: 4, name: '养生茶礼盒', desc: '精选12味', icon: '🍵', bgColor: 'rgba(114,46,209,0.12)', points: 800, stock: 20 },
      { id: 5, name: '运动手环', desc: '心率监测', icon: '⌚', bgColor: 'rgba(24,144,255,0.12)', points: 2000, stock: 10 },
      { id: 6, name: '会员月卡', desc: '尊享权益', icon: '👑', bgColor: 'rgba(235,47,150,0.12)', points: 1000, stock: 999 }
    ]
  },

  exchangeGoods(e) {
    const item = e.currentTarget.dataset.item;
    if (this.data.totalPoints < item.points) {
      wx.showToast({ title: '积分不足', icon: 'none' });
      return;
    }
    wx.showModal({
      title: '兑换确认',
      content: `确定使用 ${item.points} 积分兑换「${item.name}」吗？`,
      success: (res) => {
        if (res.confirm) {
          this.setData({ totalPoints: this.data.totalPoints - item.points });
          wx.showToast({ title: '兑换成功', icon: 'success' });
        }
      }
    });
  }
});
