const { del, put, post } = require('../../utils/request');

const SESSION_TYPE_MAP = {
  general: '综合问诊',
  symptom: '症状分析',
  tcm: '中医问诊',
  nutrition: '营养咨询'
};

Component({
  properties: {
    show: { type: Boolean, value: false },
    sessions: { type: Array, value: [] }
  },

  observers: {
    'sessions': function (list) {
      this.setData({ groupedSessions: this._groupByDate(list || []) });
    }
  },

  data: {
    groupedSessions: []
  },

  methods: {
    onClose() {
      this.triggerEvent('close');
    },

    preventBubble() {},

    onSessionTap(e) {
      const session = e.currentTarget.dataset.session;
      this.triggerEvent('sessiontap', { session });
    },

    onNewChat() {
      this.triggerEvent('newchat');
    },

    onLongPress(e) {
      const session = e.currentTarget.dataset.session;
      const pinText = session.is_pinned ? '取消置顶' : '置顶';
      wx.showActionSheet({
        itemList: [pinText, '重命名', '分享', '删除'],
        success: (res) => {
          switch (res.tapIndex) {
            case 0: this._togglePin(session); break;
            case 1: this._rename(session); break;
            case 2: this._share(session); break;
            case 3: this._delete(session); break;
          }
        }
      });
    },

    async _togglePin(session) {
      try {
        await put(`/api/chat-sessions/${session.id}/pin`, {
          is_pinned: !session.is_pinned
        });
        this.triggerEvent('refresh');
        wx.showToast({ title: session.is_pinned ? '已取消置顶' : '已置顶', icon: 'success' });
      } catch (e) {
        wx.showToast({ title: '操作失败', icon: 'none' });
      }
    },

    _rename(session) {
      wx.showModal({
        title: '重命名对话',
        editable: true,
        placeholderText: '请输入新标题',
        content: session.title || '',
        success: async (res) => {
          if (!res.confirm || !res.content || !res.content.trim()) return;
          try {
            await put(`/api/chat-sessions/${session.id}`, {
              title: res.content.trim()
            });
            this.triggerEvent('refresh');
            wx.showToast({ title: '已重命名', icon: 'success' });
          } catch (e) {
            wx.showToast({ title: '重命名失败', icon: 'none' });
          }
        }
      });
    },

    async _share(session) {
      try {
        const res = await post(`/api/chat-sessions/${session.id}/share`);
        this.triggerEvent('share', {
          session,
          shareToken: res.share_token,
          shareUrl: res.share_url
        });
        wx.showToast({ title: '分享链接已生成', icon: 'success' });
      } catch (e) {
        wx.showToast({ title: '生成分享失败', icon: 'none' });
      }
    },

    _delete(session) {
      wx.showModal({
        title: '删除对话',
        content: '确定要删除这条对话记录吗？删除后不可恢复。',
        confirmColor: '#ff4d4f',
        success: async (res) => {
          if (!res.confirm) return;
          try {
            await del(`/api/chat-sessions/${session.id}`);
            this.triggerEvent('refresh');
            wx.showToast({ title: '已删除', icon: 'success' });
          } catch (e) {
            wx.showToast({ title: '删除失败', icon: 'none' });
          }
        }
      });
    },

    getTypeLabel(type) {
      return SESSION_TYPE_MAP[type] || type || '对话';
    },

    _groupByDate(sessions) {
      if (!sessions || !sessions.length) return [];

      const now = new Date();
      const todayStart = new Date(now.getFullYear(), now.getMonth(), now.getDate()).getTime();
      const yesterdayStart = todayStart - 86400000;
      const week7Start = todayStart - 7 * 86400000;
      const day30Start = todayStart - 30 * 86400000;

      const groups = {
        pinned: [],
        today: [],
        yesterday: [],
        week7: [],
        day30: [],
        earlier: []
      };

      sessions.forEach(s => {
        const item = {
          ...s,
          typeLabel: SESSION_TYPE_MAP[s.session_type] || s.session_type || '对话'
        };

        if (s.is_pinned) {
          groups.pinned.push(item);
          return;
        }

        const ts = new Date(s.updated_at || s.created_at).getTime();
        if (ts >= todayStart) {
          groups.today.push(item);
        } else if (ts >= yesterdayStart) {
          groups.yesterday.push(item);
        } else if (ts >= week7Start) {
          groups.week7.push(item);
        } else if (ts >= day30Start) {
          groups.day30.push(item);
        } else {
          groups.earlier.push(item);
        }
      });

      const result = [];
      if (groups.pinned.length) result.push({ label: '已置顶', items: groups.pinned });
      if (groups.today.length) result.push({ label: '今天', items: groups.today });
      if (groups.yesterday.length) result.push({ label: '昨天', items: groups.yesterday });
      if (groups.week7.length) result.push({ label: '近7天', items: groups.week7 });
      if (groups.day30.length) result.push({ label: '近30天', items: groups.day30 });
      if (groups.earlier.length) result.push({ label: '更早', items: groups.earlier });
      return result;
    }
  }
});
