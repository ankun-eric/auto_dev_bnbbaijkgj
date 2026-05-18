// [PRD-FAMILY-AUTH-MP-V1] 小程序「接受守护邀请」页
// 实现完整状态机：未登录引导 / 失效态矩阵 / 邀请人卡片 / 关系说明 /
//                  健康档案合并预览 / 一次性授权协议 / 接受成功引导关注公众号
const { get, post } = require('../../utils/request');
const app = getApp();

// 关系标签映射（PRD §3.2）
const RELATIONSHIP_LABELS = {
  father: '父亲',
  mother: '母亲',
  spouse: '配偶',
  son: '儿子',
  daughter: '女儿',
  brother: '兄弟',
  sister: '姐妹',
  grandfather: '祖父',
  grandmother: '祖母',
  child: '子女',
  parent: '父母',
  other: '其他',
};

// 失效态文案矩阵（PRD §5）
const INVALID_REASON_MAP = {
  expired: {
    title: '邀请已过期',
    desc: '该邀请已过期，请联系邀请人重新生成',
    action: 'contact',
  },
  used: {
    title: '邀请已被接受',
    desc: '该邀请已被其他人接受',
    action: 'home',
  },
  cancelled: {
    title: '邀请已取消',
    desc: '邀请人已取消该邀请',
    action: 'home',
  },
  self: {
    title: '无法接受',
    desc: '不能接受自己发起的邀请',
    action: 'home',
  },
  limit: {
    title: '已达守护者上限',
    desc: '您已被 3 位家人守护，请先在「我的家庭」解除一位',
    action: 'bindlist',
  },
};

function trackEvent(name, extra) {
  // 简易埋点：开发期写 console，生产期可对接埋点 SDK
  try {
    console.info('[track]', name, extra || {});
  } catch (_) {}
}

function formatExpiresAt(iso) {
  if (!iso) return '';
  try {
    const d = new Date(iso);
    if (Number.isNaN(d.getTime())) return iso;
    const yyyy = d.getFullYear();
    const mm = String(d.getMonth() + 1).padStart(2, '0');
    const dd = String(d.getDate()).padStart(2, '0');
    const hh = String(d.getHours()).padStart(2, '0');
    const mi = String(d.getMinutes()).padStart(2, '0');
    return `${yyyy}-${mm}-${dd} ${hh}:${mi}`;
  } catch (_) {
    return iso;
  }
}

Page({
  data: {
    code: '',
    loading: true,
    error: '',
    networkError: false,

    // 邀请详情
    invitation: null,
    relationshipLabel: '',
    expiresAtText: '',

    // 失效态
    invalidReason: '',
    invalidTitle: '',
    invalidDesc: '',
    invalidAction: '',

    // 合并预览（每项 {key,label,acceptor_value,inviter_value,will_merge}）
    mergePreview: [],
    // mergeChoices[key] = 'merge' | 'keep'
    mergeChoices: {},

    // 协议
    agreed: false,

    processing: false,

    // 结果态
    resultStatus: '', // '' | 'success' | 'rejected' | 'error'
    resultMessage: '',
    showFollowMp: false,
  },

  onLoad(options) {
    const code = options.code || options.scene || '';
    trackEvent('family_auth_view', { code });
    if (!code) {
      this.setData({ loading: false, error: '无效的邀请链接' });
      return;
    }
    this.setData({ code });
    this._ensureLoginThenLoad(code);
  },

  onShow() {
    // 从登录页返回后会触发 onShow，做一次兜底重新拉取
    if (this.data.code && !this.data.invitation && !this.data.error && !this.data.invalidReason) {
      this._ensureLoginThenLoad(this.data.code);
    }
  },

  _ensureLoginThenLoad(code) {
    const token = (app && app.globalData && app.globalData.token) || '';
    if (!token) {
      wx.showModal({
        title: '需要登录',
        content: '接受守护邀请前需要登录或注册，是否前往登录？',
        confirmText: '去登录',
        success: (res) => {
          if (res.confirm) {
            const redirect = `/pages/family-auth/index?code=${encodeURIComponent(code)}`;
            wx.navigateTo({
              url: `/pages/login/index?redirect=${encodeURIComponent(redirect)}`,
            });
          } else {
            this.setData({ loading: false, error: '已取消登录' });
          }
        },
      });
      return;
    }
    this.loadInvitation(code);
  },

  async loadInvitation(code) {
    this.setData({ loading: true, error: '', networkError: false });
    try {
      const res = await get(`/api/family/invitation/${code}`, {}, { suppressErrorToast: true });

      // 失效原因优先于 status 判断（后端已做归一化）
      if (res.invalid_reason) {
        const meta = INVALID_REASON_MAP[res.invalid_reason] || {
          title: '邀请无效',
          desc: '该邀请暂时无法接受',
          action: 'home',
        };
        trackEvent(`family_auth_invalid_${res.invalid_reason}`);
        this.setData({
          loading: false,
          invitation: res,
          invalidReason: res.invalid_reason,
          invalidTitle: meta.title,
          invalidDesc: meta.desc,
          invalidAction: meta.action,
        });
        return;
      }

      // 兼容旧 status 字段
      if (res.status && res.status !== 'pending') {
        const reason =
          res.status === 'accepted'
            ? 'used'
            : res.status === 'expired'
            ? 'expired'
            : res.status === 'cancelled'
            ? 'cancelled'
            : null;
        if (reason) {
          const meta = INVALID_REASON_MAP[reason];
          trackEvent(`family_auth_invalid_${reason}`);
          this.setData({
            loading: false,
            invitation: res,
            invalidReason: reason,
            invalidTitle: meta.title,
            invalidDesc: meta.desc,
            invalidAction: meta.action,
          });
          return;
        }
      }

      const merge = Array.isArray(res.merge_preview) ? res.merge_preview : [];
      const mergeChoices = {};
      merge.forEach((item) => {
        mergeChoices[item.key] = item.will_merge ? 'merge' : 'keep';
      });

      this.setData({
        loading: false,
        invitation: res,
        relationshipLabel:
          RELATIONSHIP_LABELS[res.relationship_type] || res.relationship_type || '家人',
        expiresAtText: formatExpiresAt(res.expires_at),
        mergePreview: merge,
        mergeChoices,
      });
    } catch (e) {
      let msg = '获取邀请信息失败';
      let networkError = false;
      if (!e || e.statusCode === 0) {
        msg = '网络异常，请稍后重试';
        networkError = true;
      } else if (e.statusCode === 404) {
        msg = '邀请不存在或已过期';
      } else if (e.statusCode === 410) {
        msg = '邀请已过期';
      } else if (e.detail) {
        msg = e.detail;
      }
      this.setData({ loading: false, error: msg, networkError });
    }
  },

  onRetry() {
    if (!this.data.code) return;
    this.loadInvitation(this.data.code);
  },

  onToggleAgree() {
    this.setData({ agreed: !this.data.agreed });
  },

  onToggleMergeField(e) {
    const { key } = e.currentTarget.dataset;
    const current = this.data.mergeChoices[key] === 'merge' ? 'keep' : 'merge';
    this.setData({ [`mergeChoices.${key}`]: current });
  },

  onOpenAgreement() {
    wx.showModal({
      title: '家庭健康守护授权协议',
      content:
        '在守护期间，您授权邀请方查看您的健康档案与体检报告，并接收您的体检异常通知。' +
        '您可以随时在「我的-家庭」中解除守护。' +
        '我们仅在您本人许可的范围内共享数据，遵循相关隐私保护法律法规。',
      showCancel: false,
      confirmText: '我已阅读',
    });
  },

  async onAccept() {
    if (this.data.processing) return;
    if (!this.data.agreed) {
      wx.showToast({ title: '请先勾选授权协议', icon: 'none' });
      return;
    }
    trackEvent('family_auth_accept_click');
    const mergeFields = Object.keys(this.data.mergeChoices).filter(
      (k) => this.data.mergeChoices[k] === 'merge'
    );

    this.setData({ processing: true });
    try {
      await post(
        `/api/family/invitation/${this.data.code}/accept`,
        { merge_fields: mergeFields },
        { suppressErrorToast: true }
      );
      trackEvent('family_auth_accept_success');
      trackEvent('family_auth_mp_qr_view');
      this.setData({
        processing: false,
        resultStatus: 'success',
        resultMessage: '已成功成为「' + (this.data.invitation.inviter_nickname || '对方') + '」的被守护者',
        showFollowMp: true,
      });
    } catch (e) {
      this.setData({
        processing: false,
        resultStatus: 'error',
        resultMessage: (e && e.detail) || '接受失败，请重试',
      });
    }
  },

  onReject() {
    if (this.data.processing) return;
    trackEvent('family_auth_reject_click');
    wx.showModal({
      title: '确定拒绝吗？',
      content: '拒绝后该邀请将作废，无法恢复',
      confirmText: '确定拒绝',
      confirmColor: '#FA5151',
      success: async (res) => {
        if (!res.confirm) return;
        this.setData({ processing: true });
        try {
          await post(`/api/family/invitation/${this.data.code}/reject`, {}, { suppressErrorToast: true });
          this.setData({
            processing: false,
            resultStatus: 'rejected',
            resultMessage: '您已拒绝此守护邀请',
          });
        } catch (e) {
          this.setData({
            processing: false,
            resultStatus: 'error',
            resultMessage: (e && e.detail) || '操作失败，请重试',
          });
        }
      },
    });
  },

  onConfirmFollowMp() {
    this.setData({ showFollowMp: false });
  },

  // 失效态操作
  onInvalidAction() {
    const action = this.data.invalidAction;
    if (action === 'contact') {
      const phone = (this.data.invitation && this.data.invitation.inviter_phone) || '';
      if (phone) {
        wx.setClipboardData({
          data: phone,
          success: () => {
            wx.showToast({ title: '邀请人手机号已复制', icon: 'none' });
          },
        });
      } else {
        wx.showToast({ title: '暂无邀请人联系方式', icon: 'none' });
      }
    } else if (action === 'bindlist') {
      wx.navigateTo({ url: '/pages/family-bindlist/index' });
    } else {
      this.goHome();
    }
  },

  goHome() {
    wx.switchTab({
      url: '/pages/home/index',
      fail: () => {
        wx.reLaunch({ url: '/pages/home/index' });
      },
    });
  },

  goBindList() {
    wx.navigateTo({ url: '/pages/family-bindlist/index' });
  },

  onCallService() {
    wx.navigateTo({ url: '/pages/customer-service/index' });
  },
});
