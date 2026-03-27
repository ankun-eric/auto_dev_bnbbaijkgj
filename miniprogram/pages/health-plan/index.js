Page({
  data: {
    completedCount: 2,
    tasks: [
      { id: 1, name: '喝水 2000ml', desc: '保持充足水分摄入', points: 10, completed: true },
      { id: 2, name: '步行 6000步', desc: '适量有氧运动', points: 15, completed: true },
      { id: 3, name: '睡前冥想 10分钟', desc: '放松身心', points: 10, completed: false },
      { id: 4, name: '摄入蔬果 5份', desc: '均衡营养', points: 10, completed: false },
      { id: 5, name: '血压测量', desc: '记录今日血压', points: 20, completed: false }
    ],
    tips: [
      '今天天气晴朗，适合户外散步30分钟',
      '建议午餐多食用深色蔬菜，补充维生素',
      '注意用眼卫生，每45分钟休息一次'
    ]
  },

  toggleTask(e) {
    const index = e.currentTarget.dataset.index;
    const completed = !this.data.tasks[index].completed;
    this.setData({
      [`tasks[${index}].completed`]: completed,
      completedCount: this.data.completedCount + (completed ? 1 : -1)
    });
    if (completed) {
      wx.showToast({ title: `+${this.data.tasks[index].points}积分`, icon: 'success' });
    }
  }
});
