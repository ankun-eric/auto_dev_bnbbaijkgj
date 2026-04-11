const { get } = require('../../utils/request');

Component({
  properties: {
    refreshKey: { type: Number, value: 0 }
  },

  data: {
    show: false,
    enabled: false,
    earnedToday: 0,
    dailyLimit: 50,
    isLimitReached: false,
    percent: 0
  },

  observers: {
    refreshKey() {
      this.loadProgress();
    }
  },

  lifetimes: {
    attached() {
      this.loadProgress();
    }
  },

  methods: {
    async loadProgress() {
      try {
        const res = await get('/api/points/checkin/today-progress', {}, {
          showLoading: false,
          suppressErrorToast: true
        });
        if (!res) return;
        const enabled = !!res.enabled;
        const earnedToday = res.earned_today || 0;
        const dailyLimit = res.daily_limit || 50;
        const isLimitReached = !!res.is_limit_reached;
        const percent = dailyLimit > 0 ? Math.min(100, Math.round(earnedToday / dailyLimit * 100)) : 0;
        this.setData({ show: true, enabled, earnedToday, dailyLimit, isLimitReached, percent });
      } catch (e) {
        this.setData({ show: false });
      }
    }
  }
});
