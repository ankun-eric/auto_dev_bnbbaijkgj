const { get, post } = require('../../utils/request');
const app = getApp();

const DEFAULT_REGISTER_SETTINGS = {
  enable_self_registration: true,
  wechat_register_mode: 'authorize_member',
  douyin_register_mode: 'authorize_member',
  register_page_layout: 'vertical',
  show_profile_completion_prompt: true,
  member_card_no_rule: 'incremental'
};

function formatMemberLevel(level) {
  if (level === undefined || level === null) return '会员';
  const map = { 0: '普通会员', 1: '银卡会员', 2: '金卡会员', 3: '钻石会员' };
  return map[level] != null ? map[level] : `会员Lv.${level}`;
}

function mapUserFromApi(u) {
  if (!u) return {};
  return {
    id: u.id,
    phone: u.phone || '',
    nickname: u.nickname || '',
    avatar: u.avatar || '',
    role: u.role,
    member_card_no: u.member_card_no,
    member_level: u.member_level,
    memberLevel: formatMemberLevel(u.member_level),
    points: u.points,
    status: u.status
  };
}

Page({
  data: {
    phone: '',
    code: '',
    agreed: false,
    codeCooldown: 0,
    settingsLoading: true,
    registerSettings: DEFAULT_REGISTER_SETTINGS,
    layoutClass: 'layout-vertical',
    submitButtonText: '登录',
    registerHelperText: '',
    showRolePicker: false,
    pendingLoginResult: null
  },

  _timer: null,

  onLoad() {
    this.loadRegisterSettings();
  },

  onUnload() {
    if (this._timer) clearInterval(this._timer);
  },

  applyRegisterSettings(registerSettings) {
    const horizontal = registerSettings.register_page_layout === 'horizontal';
    const submitButtonText = registerSettings.enable_self_registration ? '登录 / 注册' : '登录';
    const registerHelperText = registerSettings.enable_self_registration
      ? '未注册手机号验证后将自动创建会员'
      : '当前未开放自助注册，仅支持已开通账号登录';
    this.setData({
      registerSettings,
      layoutClass: horizontal ? 'layout-horizontal' : 'layout-vertical',
      submitButtonText,
      registerHelperText
    });
  },

  async loadRegisterSettings() {
    try {
      const res = await get('/api/auth/register-settings', {}, {
        showLoading: false,
        suppressErrorToast: true
      });
      this.applyRegisterSettings({ ...DEFAULT_REGISTER_SETTINGS, ...res });
    } catch (e) {
      this.applyRegisterSettings(DEFAULT_REGISTER_SETTINGS);
    } finally {
      this.setData({ settingsLoading: false });
    }
  },

  onPhoneInput(e) {
    this.setData({ phone: e.detail.value });
  },

  onCodeInput(e) {
    this.setData({ code: e.detail.value });
  },

  toggleAgreement() {
    this.setData({ agreed: !this.data.agreed });
  },

  async sendCode() {
    const { phone, codeCooldown } = this.data;
    if (codeCooldown > 0) return;
    if (!phone || phone.length !== 11) {
      wx.showToast({ title: '请输入正确的手机号', icon: 'none' });
      return;
    }

    try {
      await post('/api/auth/sms-code', { phone, type: 'login' }, {
        showLoading: true,
        suppressErrorToast: true
      });
      wx.showToast({ title: '验证码已发送', icon: 'success' });
      this.setData({ codeCooldown: 60 });
      this._timer = setInterval(() => {
        if (this.data.codeCooldown <= 1) {
          clearInterval(this._timer);
          this.setData({ codeCooldown: 0 });
        } else {
          this.setData({ codeCooldown: this.data.codeCooldown - 1 });
        }
      }, 1000);
    } catch (e) {
      const detail = e.detail || '发送失败，请稍后重试';
      if (e.statusCode === 403) {
        wx.showModal({
          title: '无法发送验证码',
          content: detail,
          showCancel: false
        });
      } else {
        wx.showToast({ title: detail, icon: 'none', duration: 3000 });
      }
    }
  },

  async loginByPhone() {
    const { phone, code, agreed } = this.data;
    if (!agreed) {
      wx.showToast({ title: '请先同意用户协议', icon: 'none' });
      return;
    }
    if (!phone || phone.length !== 11) {
      wx.showToast({ title: '请输入正确的手机号', icon: 'none' });
      return;
    }
    if (!code || code.length < 4) {
      wx.showToast({ title: '请输入验证码', icon: 'none' });
      return;
    }

    wx.showLoading({ title: '登录中...', mask: true });
    try {
      const res = await post('/api/auth/sms-login', { phone, code }, {
        showLoading: false,
        suppressErrorToast: true
      });
      wx.hideLoading();
      this.handleLoginSuccess(res);
    } catch (e) {
      wx.hideLoading();
      const detail = e.detail || '登录失败，请检查验证码';
      if (e.statusCode === 403) {
        const closed =
          typeof detail === 'string' &&
          (detail.indexOf('自助注册') !== -1 || detail.indexOf('暂未开放') !== -1);
        wx.showModal({
          title: closed ? '无法注册' : '提示',
          content: detail,
          showCancel: false,
          confirmText: '我知道了'
        });
      } else {
        wx.showToast({ title: detail, icon: 'none', duration: 3000 });
      }
    }
  },

  handleLoginSuccess(res) {
    const accessToken = res.access_token;
    const userInfo = mapUserFromApi(res.user);
    const sessionContext = res.session_context || {};
    const merchantProfile = res.merchant_profile || null;
    if (!accessToken) {
      wx.showToast({ title: '登录响应异常', icon: 'none' });
      return;
    }

    app.setLoginInfo(accessToken, userInfo, {
      sessionContext,
      merchantProfile,
      currentRole: sessionContext.default_entry === 'merchant' ? 'merchant' : 'user'
    });

    if (sessionContext.is_dual_identity) {
      this.setData({
        showRolePicker: true,
        pendingLoginResult: res
      });
      return;
    }

    const targetRole = sessionContext.can_access_merchant && !sessionContext.can_access_user
      ? 'merchant'
      : 'user';
    app.setCurrentRole(targetRole);
    this.finishLoginFlow(targetRole, res);
  },

  finishLoginFlow(targetRole, res) {
    const { registerSettings } = this.data;
    const needProfilePrompt = targetRole === 'user'
      && res.needs_profile_completion
      && registerSettings.show_profile_completion_prompt;
    const cardNo = res.user && res.user.member_card_no;

    const goNext = () => {
      if (targetRole === 'merchant') {
        app.clearCurrentStore();
        wx.redirectTo({ url: '/pages/store-select/index' });
        return;
      }
      wx.switchTab({ url: '/pages/home/index' });
    };

    const promptProfileThen = () => {
      if (!needProfilePrompt) {
        goNext();
        return;
      }
      wx.showModal({
        title: '补充会员信息',
        content: '完善基础健康信息后，可获得更精准的 AI 健康建议，是否现在去完善？',
        confirmText: '立即完善',
        cancelText: '稍后再说',
        success: (r) => {
          if (r.confirm) {
            wx.navigateTo({ url: '/pages/health-profile/index' });
          } else {
            goNext();
          }
        }
      });
    };

    if (res.is_new_user && targetRole === 'user') {
      if (cardNo) {
        wx.showModal({
          title: '注册成功',
          content: `欢迎加入！您的会员卡号：${cardNo}`,
          showCancel: false,
          confirmText: '知道了',
          success: () => promptProfileThen()
        });
      } else {
        wx.showToast({ title: '注册成功，欢迎加入', icon: 'success', duration: 2000 });
        setTimeout(() => promptProfileThen(), 1800);
      }
      return;
    }

    wx.showToast({ title: '登录成功', icon: 'success' });
    setTimeout(() => promptProfileThen(), 1000);
  },

  chooseLoginRole(e) {
    const role = e.currentTarget.dataset.role;
    const res = this.data.pendingLoginResult;
    if (!res || !role) return;
    app.setCurrentRole(role);
    this.setData({
      showRolePicker: false,
      pendingLoginResult: null
    });
    this.finishLoginFlow(role, res);
  },

  loginByWechat() {
    if (!this.data.agreed) {
      wx.showToast({ title: '请先同意用户协议', icon: 'none' });
      return;
    }

    wx.showLoading({ title: '登录中...' });
    wx.login({
      success: async (loginRes) => {
        try {
          // const res = await post('/api/auth/wx-login', { code: loginRes.code });
          const mockData = {
            token: 'wx_token_' + Date.now(),
            userInfo: { nickname: '微信用户', avatar: '', memberLevel: '普通会员' }
          };
          app.setLoginInfo(mockData.token, mockData.userInfo);
          wx.hideLoading();
          wx.showToast({ title: '登录成功', icon: 'success' });
          setTimeout(() => {
            wx.switchTab({ url: '/pages/home/index' });
          }, 1500);
        } catch (e) {
          wx.hideLoading();
          console.log('wx login error', e);
        }
      },
      fail() {
        wx.hideLoading();
        wx.showToast({ title: '微信登录失败', icon: 'none' });
      }
    });
  },

  showAgreement(e) {
    const type = e.currentTarget.dataset.type;
    wx.showModal({
      title: type === 'user' ? '用户服务协议' : '隐私政策',
      content: '协议内容正在完善中，请稍后查看。',
      showCancel: false
    });
  }
});
