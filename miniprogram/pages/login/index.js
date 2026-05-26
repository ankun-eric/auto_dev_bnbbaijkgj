/**
 * PRD-370 BUG-FIX-LOGIN-DESIGN-ALIGN-V1
 * 设计稿对齐版登录页：协议确认弹窗 + 半屏抽屉 + 三段渐变按钮 + 主色 #34C759
 */
const { get, post } = require('../../utils/request');
const app = getApp();

const DEFAULT_REGISTER_SETTINGS = {
  enable_self_registration: true,
  wechat_register_mode: 'authorize_member',
  register_page_layout: 'vertical',
  show_profile_completion_prompt: true,
  member_card_no_rule: 'incremental'
};

const SERVICE_AGREEMENT_CONTENT = `用户服务协议

生效日期：2026-05-07 ｜ 版本号：v1.0

一、协议说明
欢迎使用「宾尼小康 AI 健康管家」（以下简称"本服务"）。本协议是您与本服务运营方就使用本服务所订立的协议。

二、账号注册与登录
2.1 您在使用本服务前需通过手机号 + 短信验证码方式完成账号登录或注册。
2.2 您应当确保所提供的手机号信息真实、准确、完整。
2.3 您应妥善保管账号信息。

三、服务内容
本服务为您提供 AI 健康咨询、健康档案管理、健康计划生成、个性化健康建议等功能。
本服务所提供的健康建议仅供参考，不能替代专业医疗机构的诊疗意见。

四、用户行为规范
4.1 您承诺遵守中华人民共和国相关法律法规。
4.2 您不得对本服务进行任何形式的反向工程、反编译或非法访问。
4.3 您不得发布违法、淫秽、暴力、虚假内容。

五、知识产权
本服务所涉及的所有内容均归运营方或合法权利人所有。

六、服务变更与终止
运营方有权根据业务需要变更、暂停或终止本服务。

七、免责声明
本服务提供的健康建议仅供参考，您应在专业医生指导下进行健康决策。

— 本协议自您勾选同意之时起对您生效 —`;

const PRIVACY_POLICY_CONTENT = `隐私政策

生效日期：2026-05-07 ｜ 版本号：v1.0

一、我们收集的信息
1.1 账号信息：手机号码用于发送短信验证码及创建账号。
1.2 设备信息：设备型号、操作系统版本等技术信息。
1.3 健康信息：基于您的主动填写或上传的健康相关信息。
1.4 使用日志：访问日志、操作行为、停留时长等。

二、我们如何使用信息
2.1 提供、维护、改进我们的服务。
2.2 根据您的健康档案为您生成个性化健康建议。
2.3 在您授权的范围内向您推送服务通知。
2.4 防范欺诈、保障您的账号安全。
2.5 满足法律法规要求或配合行政、司法机关调查。

三、信息的存储与保护
3.1 您的信息将存储于中华人民共和国境内的合规云服务器。
3.2 我们采用加密传输（HTTPS）、加密存储等多重技术手段保护您的信息。
3.3 我们仅在实现服务目的所必需的最短期间内保留您的信息。

四、信息的共享、转让和披露
除以下情形外，我们不会向第三方共享、转让或披露您的个人信息：
4.1 取得您的明确同意；
4.2 法律法规要求或政府主管部门强制要求；
4.3 为维护本服务及其他用户的合法权益所必需。

五、您的权利
您有权查询、更正您的个人信息；有权撤回授权同意；有权申请注销账号。

六、儿童信息保护
本服务主要面向 18 周岁以上的成年用户。

七、政策更新与联系方式
本政策可能随业务需要进行更新。如有疑问，可通过应用内客服与我们联系。

— 本政策自您勾选同意之时起对您生效 —`;

/**
 * [付费会员体系 PRD v1.1] 旧"积分会员等级"已废弃。
 * 保留字段仅用于兼容旧版本接口返回，不再用于 UI 展示。
 * UI 展示请改用付费会员套餐（/api/membership/me 返回的 plan_name）。
 */
function formatMemberLevel(level) {
  // 不再生成"免费会员/银卡/金卡/钻石"等历史标签；返回空字符串避免 UI 误展示。
  if (level === undefined || level === null) return '';
  return '';
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
    status: u.status,
    user_no: u.user_no || '',
    referrer_no: u.referrer_no || ''
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
    submitButtonText: '登录',
    showRolePicker: false,
    pendingLoginResult: null,
    brandLogoUrl: '',
    referrerNo: '',
    phoneFocused: false,
    codeFocused: false,
    agreementDialogVisible: false,
    drawerVisible: false,
    drawerType: 'user',
    serviceAgreementContent: SERVICE_AGREEMENT_CONTENT,
    privacyPolicyContent: PRIVACY_POLICY_CONTENT
  },

  _timer: null,

  onLoad(options) {
    if (options.ref) {
      this.setData({ referrerNo: options.ref });
    }
    this.loadRegisterSettings();
    this.setData({ brandLogoUrl: app.globalData.brandLogoUrl || '' });
  },

  onUnload() {
    if (this._timer) clearInterval(this._timer);
  },

  applyRegisterSettings(registerSettings) {
    const submitButtonText = registerSettings.enable_self_registration ? '登录 / 注册' : '登录';
    this.setData({
      registerSettings,
      submitButtonText
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

  onPhoneFocus() { this.setData({ phoneFocused: true }); },
  onPhoneBlur() { this.setData({ phoneFocused: false }); },
  onCodeFocus() { this.setData({ codeFocused: true }); },
  onCodeBlur() { this.setData({ codeFocused: false }); },

  toggleAgreement() {
    this.setData({ agreed: !this.data.agreed });
  },

  noop() { /* 阻止冒泡占位 */ },

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
        wx.showModal({ title: '无法发送验证码', content: detail, showCancel: false });
      } else {
        wx.showToast({ title: detail, icon: 'none', duration: 3000 });
      }
    }
  },

  async loginByPhone() {
    const { phone, code, agreed } = this.data;
    if (!phone || phone.length !== 11) {
      wx.showToast({ title: '请输入正确的手机号', icon: 'none' });
      return;
    }
    if (!code || code.length < 4) {
      wx.showToast({ title: '请输入验证码', icon: 'none' });
      return;
    }
    if (!agreed) {
      // PRD-370 改造：未勾选时弹出居中确认弹窗
      this.setData({ agreementDialogVisible: true });
      return;
    }
    await this._doLoginRequest();
  },

  async agreeAndLogin() {
    this.setData({ agreementDialogVisible: false, agreed: true });
    await this._doLoginRequest();
  },

  rejectAgreement() {
    this.setData({ agreementDialogVisible: false });
  },

  openAgreementDrawer(e) {
    const type = (e.currentTarget && e.currentTarget.dataset && e.currentTarget.dataset.type) || 'user';
    this.setData({ drawerType: type, drawerVisible: true });
  },

  closeDrawer() {
    this.setData({ drawerVisible: false });
  },

  async _doLoginRequest() {
    const { phone, code } = this.data;
    wx.showLoading({ title: '登录中...', mask: true });
    try {
      const body = { phone, code };
      if (this.data.referrerNo) body.referrer_no = this.data.referrerNo;
      const res = await post('/api/auth/sms-login', body, {
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
          if (r.confirm) wx.navigateTo({ url: '/pages/health-profile/index' });
          else goNext();
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
    this.setData({ showRolePicker: false, pendingLoginResult: null });
    this.finishLoginFlow(role, res);
  },

  showAgreement(e) {
    const type = (e.currentTarget && e.currentTarget.dataset && e.currentTarget.dataset.type) || 'user';
    this.setData({ drawerType: type, drawerVisible: true });
  }
});
