Page({
  data: {
    currentTab: 0,
    notifications: [
      { id: 1, title: '签到提醒', content: '今日签到可获得15积分，连续签到7天还有额外奖励哦~', icon: '📅', bgColor: 'rgba(82,196,26,0.12)', time: '10分钟前', read: false, type: 'system' },
      { id: 2, title: '订单完成', content: '您的"在线图文问诊"订单已完成，欢迎评价~', icon: '✅', bgColor: 'rgba(19,194,194,0.12)', time: '2小时前', read: false, type: 'order' },
      { id: 3, title: '健康提醒', content: '您已3天未测量血压，请注意定期监测', icon: '❤️', bgColor: 'rgba(255,77,79,0.12)', time: '昨天', read: false, type: 'health' },
      { id: 4, title: '系统通知', content: '宾尼小康新版本已发布，体验更流畅的AI问诊功能', icon: '📢', bgColor: 'rgba(24,144,255,0.12)', time: '2天前', read: true, type: 'system' },
      { id: 5, title: '积分到账', content: '恭喜您获得100积分，来自邀请好友奖励', icon: '🎯', bgColor: 'rgba(250,173,20,0.12)', time: '3天前', read: true, type: 'system' }
    ]
  },

  switchTab(e) {
    this.setData({ currentTab: e.currentTarget.dataset.index });
  },

  readNotify(e) {
    const index = e.currentTarget.dataset.index;
    this.setData({ [`notifications[${index}].read`]: true });
  },

  clearAll() {
    const notifications = this.data.notifications.map(n => ({ ...n, read: true }));
    this.setData({ notifications });
    wx.showToast({ title: '全部已读', icon: 'success' });
  }
});
