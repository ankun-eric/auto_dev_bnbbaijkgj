Page({
  data: {
    totalPoints: 1280,
    signDays: 5,
    signedToday: false,
    weekDays: [
      { day: '一', points: 5, signed: true },
      { day: '二', points: 5, signed: true },
      { day: '三', points: 5, signed: true },
      { day: '四', points: 10, signed: true },
      { day: '五', points: 10, signed: true },
      { day: '六', points: 15, signed: false, today: true },
      { day: '日', points: 20, signed: false }
    ],
    records: [
      { id: 1, title: '每日签到', amount: 10, time: '今天 08:30' },
      { id: 2, title: '完成健康任务', amount: 20, time: '昨天 15:20' },
      { id: 3, title: '积分兑换 - 体检优惠券', amount: -200, time: '3天前' },
      { id: 4, title: '邀请好友注册', amount: 100, time: '5天前' },
      { id: 5, title: '每日签到', amount: 5, time: '6天前' }
    ]
  },

  signIn() {
    if (this.data.signedToday) {
      wx.showToast({ title: '今日已签到', icon: 'none' });
      return;
    }
    const points = this.data.weekDays[5].points;
    this.setData({
      signedToday: true,
      totalPoints: this.data.totalPoints + points,
      signDays: this.data.signDays + 1,
      'weekDays[5].signed': true
    });
    wx.showToast({ title: `签到成功 +${points}积分`, icon: 'success' });
  },

  goMall() {
    wx.navigateTo({ url: '/pages/points-mall/index' });
  }
});
