const { get, post } = require('../../utils/request');
const { checkLogin, ensureMerchantEntry, syncTabBar } = require('../../utils/util');
// [BUG_FIX_TIMEZONE_GLOBAL_20260517] 统一时间解析/格式化
const { parseServerTime, formatDateTime, formatDate, formatTime, formatRelativeTime, formatFriendlyTime } = require('../../utils/datetime');

// [PRD-AIHOME-WELCOME-UNIFY-V1 2026-06-02] 时段问候（与关怀模式同口径）
function getGreeting(now) {
  const h = now.getHours();
  if (h >= 5 && h < 11) return { text: '早上好', icon: '☀️' };
  if (h >= 11 && h < 18) return { text: '中午好', icon: '🌤️' };
  return { text: '晚上好', icon: '🌙' };
}

Page({
  data: {
    pageMode: 'user',
    // [PRD-AIHOME-WELCOME-UNIFY-V1 2026-06-02] 欢迎区问候语 + 机器人 LOGO（照搬关怀模式风格）
    greetingText: '',
    greetingIcon: '',
    logoUrl: '',
    consultTypes: [
      { id: 'health_qa', name: '健康问答', desc: 'AI健康顾问在线解答', icon: '💬', bgColor: 'rgba(82,196,26,0.12)' },
      { id: 'symptom_check', name: '健康自查', desc: '智能健康自查参考', icon: '🔍', bgColor: 'rgba(19,194,194,0.12)' },
      { id: 'tcm', name: '中医养生', desc: '中医养生体质调理', icon: '🌿', bgColor: 'rgba(114,46,209,0.12)' },
      { id: 'drug_query', name: '用药参考', desc: '用药参考与注意事项', icon: '💊', bgColor: 'rgba(250,173,20,0.12)' }
    ],
    quickQuestions: [
      '最近经常头痛怎么办？',
      '感冒了吃什么药好？',
      '失眠有什么好的调理方法？',
      '血压偏高该注意什么？'
    ],
    chatHistory: [],
    drawerShow: false,
    allSessions: [],
    orderInfo: null,
    verifying: false,
    brandLogoUrl: '',
    // [Bug 修复 v1.0 §3.1.3] 「更多」菜单可见态 + 「新」角标可见期（30 天）
    moreMenuShow: false,
    showNewBadge: Date.now() < new Date('2026-06-25T00:00:00Z').getTime(),
    // [PRD-MODE-CAPSULE-V1 2026-05-31] 模式切换下拉胶囊展开态 + 切换中防重复点击
    modeDropdownShow: false,
    modeSwitching: false
  },

  onLoad(options) {
    // [PRD-AIHOME-WELCOME-UNIFY-V1 2026-06-02] 初始化欢迎区问候语与机器人 LOGO
    const g = getGreeting(new Date());
    const app0 = getApp();
    const base = (app0 && app0.globalData && app0.globalData.baseUrl) || '';
    this.setData({
      greetingText: g.text,
      greetingIcon: g.icon,
      logoUrl: `${base}/binni-xiaokang-logo.png`,
    });
    // [PRD-CARE-MODE-OPTIM-V4 2026-05-31] 关怀模式 ☰ 历史入口：携带 openDrawer 标记进入即弹出历史对话抽屉
    if (options && options.openDrawer) {
      this.setData({ drawerShow: true });
      this.loadChatHistory();
    }
  },

  onShow() {
    syncTabBar(this, '/pages/ai/index');
    const app = getApp();
    const pageMode = app.getCurrentRole() || 'user';
    this.setData({ pageMode, brandLogoUrl: app.globalData.brandLogoUrl || '' });
    if (pageMode === 'merchant') {
      if (!ensureMerchantEntry()) return;
      this.setData({ orderInfo: null });
      return;
    }
    this.loadChatHistory();
    // [PRD-AI-HOME-OPTIM-V4 M1 · 2026-05-21] 60 分钟定时自动刷新机制
    // 进入页面时根据距上次会话 updated_at 是否 ≥ 阈值，决定是否清空"最近会话"展示并触发埋点
    this.runV4RefreshCheck();
  },

  // [PRD-AI-HOME-OPTIM-V4 M1] 60 分钟刷新检测
  // - 拉后端阈值（失败兜底 60min）
  // - 取最近一条会话的 updated_at，若距今 >= 阈值 → 清空 chatHistory 展示 + 上报 refresh_triggered
  // - 否则 → 上报 refresh_skipped
  async runV4RefreshCheck() {
    let thresholdMs = 60 * 60 * 1000;
    try {
      const cfg = await get('/api/ai-home/refresh-config', {}, { showLoading: false, suppressErrorToast: true });
      if (cfg && typeof cfg.session_refresh_ms === 'number' && cfg.session_refresh_ms > 0) {
        thresholdMs = cfg.session_refresh_ms;
      }
    } catch (e) { /* 静默 */ }
    try {
      const list = this.data.allSessions || [];
      if (list.length === 0) return;
      const latest = list[0];
      const ts = parseServerTime(latest.updated_at || latest.created_at);
      if (!ts) return;
      const idleMs = Date.now() - ts.getTime();
      if (idleMs >= thresholdMs) {
        this.setData({ chatHistory: [] });
        this.reportV4Track('refresh_triggered', {
          trigger_source: 'onShow',
          idle_minutes: Math.round(idleMs / 60000),
        });
      } else {
        this.reportV4Track('refresh_skipped', {
          last_active_minutes: Math.round(idleMs / 60000),
        });
      }
    } catch (e) { /* 静默 */ }
  },

  reportV4Track(event, payload) {
    try {
      post('/api/ai-home/track', { event, platform: 'miniprogram', payload: payload || {} },
        { showLoading: false, suppressErrorToast: true }).catch(() => {});
    } catch (e) { /* 静默 */ }
  },

  async loadChatHistory() {
    try {
      const res = await get('/api/chat-sessions', { page: 1, page_size: 100 }, { showLoading: false, suppressErrorToast: true });
      const sessions = Array.isArray(res) ? res : (res.items || res.data || []);
      this.setData({
        allSessions: sessions,
        chatHistory: sessions.slice(0, 3).map(s => ({
          id: s.id,
          type: this._getTypeLabel(s.session_type),
          summary: s.title || '未命名对话',
          time: this._formatSessionTime(s.updated_at || s.created_at)
        }))
      });
    } catch (e) {
      console.log('loadChatHistory error', e);
    }
  },

  _getTypeLabel(type) {
    const map = {
      health_qa: '健康问答', general: '健康问答',
      symptom_check: '健康自查', symptom: '健康自查',
      tcm: '中医养生',
      drug_query: '用药参考', nutrition: '用药参考',
      customer_service: '在线客服'
    };
    return map[type] || type || '对话';
  },

  _formatSessionTime(dateStr) {
    if (!dateStr) return '';
    const d = parseServerTime(dateStr);
    if (!d) return '';
    const now = new Date();
    const todayStart = new Date(now.getFullYear(), now.getMonth(), now.getDate()).getTime();
    const ts = d.getTime();
    const pad = n => String(n).padStart(2, '0');
    const timeStr = `${pad(d.getHours())}:${pad(d.getMinutes())}`;
    if (ts >= todayStart) return `今天 ${timeStr}`;
    if (ts >= todayStart - 86400000) return `昨天 ${timeStr}`;
    return `${pad(d.getMonth() + 1)}-${pad(d.getDate())} ${timeStr}`;
  },

  openDrawer() {
    if (!checkLogin()) return;
    this.setData({ drawerShow: true });
  },

  // [PRD-AIHOME-UNIFY-V1 2026-06-01 §需求1] 顶栏「档案/咨询/服务」三 Tab
  // 档案 → /pages/health-profile；服务 → /pages/services；咨询 = 当前页停留
  onTopTab(e) {
    const key = e.currentTarget.dataset.key;
    if (key === 'consult') return; // 咨询：本页停留
    if (key === 'profile') {
      wx.navigateTo({ url: '/pages/health-profile/index', fail: () => wx.switchTab({ url: '/pages/health-profile/index' }) });
      return;
    }
    if (key === 'service') {
      wx.switchTab({ url: '/pages/services/index', fail: () => wx.navigateTo({ url: '/pages/services/index' }) });
      return;
    }
  },

  // [PRD-AIHOME-UNIFY-V1 2026-06-01 §需求1] 顶栏 🔔 铃铛 → 今日待办/消息提醒（复用历史抽屉入口）
  openBell() {
    if (!checkLogin()) return;
    this.setData({ drawerShow: true });
  },

  // [Bug 修复 v1.0 §3.1.3] 「更多」菜单交互
  // [PRD-MODE-CAPSULE-V1 2026-05-31] 模式下拉胶囊：展开/收起切换
  toggleModeDropdown() {
    this.setData({ modeDropdownShow: !this.data.modeDropdownShow });
  },

  // [PRD-MODE-CAPSULE-V1 2026-05-31] 收起模式下拉面板（点当前模式 / 点面板外）
  closeModeDropdown() {
    this.setData({ modeDropdownShow: false });
  },

  // [PRD-MODE-CAPSULE-V1 2026-05-31] 切换到关怀模式：保存偏好 → 提示 → 跳转（沿用现有逻辑）
  async switchToCareMode() {
    if (this.data.modeSwitching) return;
    this.setData({ modeSwitching: true, modeDropdownShow: false });
    try {
      await post('/api/user/mode-preference', { mode: 'care' }, { showLoading: false, suppressErrorToast: true });
    } catch (e) {
      // 静默：偏好保存失败不阻塞跳转
      console.warn('[mode-capsule] 保存偏好失败', e);
    }
    try { wx.setStorageSync('app_mode_preference', 'care'); } catch (e) { /* ignore */ }
    wx.showToast({ title: '已切换到关怀模式 ✓', icon: 'none', duration: 2000 });
    wx.navigateTo({
      url: '/pages/care-ai-home/index',
      complete: () => this.setData({ modeSwitching: false })
    });
  },

  // [PRD-MODE-CAPSULE-V1 2026-05-31] 🎁 邀请好友入口
  goInvite() {
    if (!checkLogin()) return;
    wx.navigateTo({ url: '/pages/invite/index' });
  },

  openMoreMenu() {
    this.setData({ moreMenuShow: true });
  },

  closeMoreMenu() {
    this.setData({ moreMenuShow: false });
  },

  // [PRD-AIHOME-UNIFY-V1 2026-06-01 §需求2] ⊕ 菜单项①：💬 发起新对话
  onTapNewChat() {
    this.setData({ moreMenuShow: false });
    if (!checkLogin()) return;
    wx.navigateTo({ url: '/pages/chat/index?type=health_qa' });
  },

  // [PRD-AIHOME-UNIFY-V1 2026-06-01 §需求2] ⊕ 菜单项②：🔀 切换模式（与欢迎区胶囊并存）→ 切到关怀模式
  onTapSwitchMode() {
    this.setData({ moreMenuShow: false });
    this.switchToCareMode();
  },

  // [PRD-AIHOME-UNIFY-V1 2026-06-01 §需求2] ⊕ 菜单项④：🎁 邀请好友
  onTapInvite() {
    this.setData({ moreMenuShow: false });
    this.goInvite();
  },

  // [PRD-AIHOME-UNIFY-V1 2026-06-01 §需求2] ⊕ 菜单项⑧：❓ 帮助与反馈
  onTapHelpFeedback() {
    this.setData({ moreMenuShow: false });
    if (!checkLogin()) return;
    wx.navigateTo({ url: '/pages/feedback/index', fail: () => wx.showToast({ title: '反馈入口开发中', icon: 'none' }) });
  },

  onTapMemberCenter() {
    this.setData({ moreMenuShow: false });
    if (!checkLogin()) return;
    wx.navigateTo({ url: '/pages/member-center/index' });
  },

  onTapScan() {
    this.setData({ moreMenuShow: false });
    wx.scanCode({
      onlyFromCamera: false,
      success: (res) => {
        wx.showToast({ title: '扫码成功', icon: 'success' });
        console.log('[scan]', res);
      },
      fail: () => {
        wx.showToast({ title: '已取消扫码', icon: 'none' });
      }
    });
  },

  onTapFontSize() {
    this.setData({ moreMenuShow: false });
    wx.showToast({ title: '字体大小设置开发中', icon: 'none' });
  },

  onTapShare() {
    this.setData({ moreMenuShow: false });
    wx.showShareMenu({ withShareTicket: true });
    wx.showToast({ title: '请点击右上角分享', icon: 'none' });
  },

  onDrawerClose() {
    this.setData({ drawerShow: false });
  },

  onSessionTap(e) {
    const { session } = e.detail;
    this.setData({ drawerShow: false });
    wx.navigateTo({ url: `/pages/chat/index?chatId=${session.id}&type=${session.session_type || 'health_qa'}` });
  },

  onDrawerNewChat() {
    this.setData({ drawerShow: false });
    wx.navigateTo({ url: '/pages/chat/index?type=health_qa' });
  },

  onDrawerRefresh() {
    this.loadChatHistory();
  },

  onDrawerShare(e) {
    const { session, shareToken, shareUrl } = e.detail;
    wx.setClipboardData({
      data: shareUrl || shareToken,
      success: () => wx.showToast({ title: '分享链接已复制', icon: 'success' })
    });
  },

  startConsult(e) {
    if (this.data.pageMode !== 'user') {
      this.startScan();
      return;
    }
    if (!checkLogin()) return;
    const type = e.currentTarget.dataset.type;
    if (type.id === 'drug_query') {
      wx.navigateTo({ url: '/pages/drug/index' });
      return;
    }
    wx.navigateTo({ url: `/pages/chat/index?type=${type.id}` });
  },

  quickAsk(e) {
    if (!checkLogin()) return;
    const question = e.currentTarget.dataset.question;
    wx.navigateTo({ url: `/pages/chat/index?type=health_qa&question=${encodeURIComponent(question)}` });
  },

  continueChat(e) {
    const id = e.currentTarget.dataset.id;
    wx.navigateTo({ url: `/pages/chat/index?chatId=${id}` });
  },

  newChat() {
    if (!checkLogin()) return;
    wx.navigateTo({ url: '/pages/chat/index?type=health_qa' });
  },

  viewAllChats() {
    if (!checkLogin()) return;
    this.setData({ drawerShow: true });
  },

  startScan() {
    if (!ensureMerchantEntry()) return;
    this.setData({ orderInfo: null });
    wx.scanCode({
      onlyFromCamera: false,
      scanType: ['qrCode', 'barCode'],
      success: (res) => {
        this.queryOrder(res.result);
      },
      fail: (err) => {
        if (err.errMsg && err.errMsg.indexOf('cancel') === -1) {
          wx.showToast({ title: '扫码失败，请重试', icon: 'none' });
        }
      }
    });
  },

  async queryOrder(code) {
    const app = getApp();
    const currentStore = app.getCurrentStore();
    if (!currentStore) return;
    wx.showLoading({ title: '查询订单中...' });
    try {
      const res = await get(`/api/merchant/orders/verify-code/${encodeURIComponent(code)}`, {
        store_id: currentStore.id
      }, { showLoading: false });
      this.setData({ orderInfo: res });
    } catch (e) {
      wx.showToast({ title: e.detail || '未找到对应订单', icon: 'none' });
    } finally {
      wx.hideLoading();
    }
  },

  handleVerify() {
    const orderInfo = this.data.orderInfo;
    if (!orderInfo || !orderInfo.id) return;
    wx.showModal({
      title: '确认核销',
      content: `确定要核销订单 ${orderInfo.order_no} 吗？`,
      confirmColor: '#52c41a',
      success: (res) => {
        if (res.confirm) {
          this.doVerify(orderInfo.id);
        }
      }
    });
  },

  async doVerify(orderId) {
    const app = getApp();
    const currentStore = app.getCurrentStore();
    const orderInfo = this.data.orderInfo;
    if (!currentStore || !orderInfo) return;
    this.setData({ verifying: true });
    try {
      await post(`/api/merchant/orders/${orderId}/verify`, {
        store_id: currentStore.id,
        code: orderInfo.verification_code
      }, { showLoading: false });
      wx.showToast({ title: '核销成功', icon: 'success' });
      this.setData({
        orderInfo: {
          ...orderInfo,
          status: 'verified'
        }
      });
    } catch (e) {
      wx.showToast({ title: e.detail || '核销失败', icon: 'none' });
    } finally {
      this.setData({ verifying: false });
    }
  }
});
