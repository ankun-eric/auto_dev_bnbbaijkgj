const { get, post } = require('../../utils/request');
const { resolveAssetUrl } = require('../../utils/asset-url');
const app = getApp();

// [PRD-GUARDIAN-CARD-OPTIM-V1 2026-06-02] 反向守护邀请：
// - 必填【关系 + 名字】后才生成二维码
// - 已达被守护上限（GUARDIAN_LIMIT_REACHED）弹升级提示框
// - 支持 ?code=xxx 直接查看已有邀请二维码（用于"查看邀请码"按钮）

const RELATION_OPTIONS = [
  '爸爸', '妈妈', '老公', '老婆',
  '儿子', '女儿', '哥哥', '姐姐', '弟弟', '妹妹',
  '爷爷', '奶奶', '外公', '外婆', '朋友', '其他',
];

Page({
  data: {
    loading: false,
    submitting: false,
    invitation: null,
    error: '',
    viewMode: false, // 查看已有邀请模式
    relationOptions: RELATION_OPTIONS,
    selectedRelation: '',
    customRelation: '',
    guardianName: '',
    canSave: false,
  },

  onLoad(options) {
    const code = options && options.code ? decodeURIComponent(options.code) : '';
    if (code) {
      this.setData({ viewMode: true });
      this.loadExistingInvite(code);
    }
  },

  async loadExistingInvite(code) {
    this.setData({ loading: true, error: '' });
    try {
      const res = await get(`/api/reverse-guardian/invite/${encodeURIComponent(code)}`, {}, { showLoading: false, suppressErrorToast: true });
      const data = (res && (res.data || res)) || {};
      // 拼装 qr_url（沿用 invite 接口的 URL 生成方式）
      const baseUrl = (app && app.globalData && app.globalData.baseUrl) || '';
      const qr_url = `${baseUrl}/family-auth?code=${data.invite_code}&type=reverse`;
      const invitation = {
        invite_code: data.invite_code,
        qr_url,
        qr_content_url: qr_url,
        expires_at: data.expires_at,
        guardian_name: data.guardian_name,
        relation_type: data.relation_type,
      };
      const rel = data.relation_type || '';
      const inOptions = RELATION_OPTIONS.includes(rel);
      this.setData({
        invitation,
        loading: false,
        viewMode: true,
        selectedRelation: inOptions ? rel : (rel ? '其他' : ''),
        customRelation: inOptions ? '' : (rel || ''),
        guardianName: data.guardian_name || '',
      });
    } catch (e) {
      this.setData({
        loading: false,
        error: (e && (e.detail || e.message)) || '邀请不存在或已失效',
      });
    }
  },

  onSelectRelation(e) {
    const rel = e.currentTarget.dataset.value;
    this.setData({
      selectedRelation: rel,
      customRelation: rel === '其他' ? this.data.customRelation : '',
      invitation: null,
    });
    this._refreshCanSave();
  },

  onCustomRelationInput(e) {
    const v = (e.detail.value || '').slice(0, 8);
    this.setData({ customRelation: v, invitation: null });
    this._refreshCanSave();
  },

  onGuardianNameInput(e) {
    const v = (e.detail.value || '').slice(0, 50);
    this.setData({ guardianName: v, invitation: null });
    this._refreshCanSave();
  },

  _refreshCanSave() {
    const { selectedRelation, customRelation, guardianName } = this.data;
    const relOK = selectedRelation && (selectedRelation !== '其他' || (customRelation || '').trim().length > 0);
    const nameOK = (guardianName || '').trim().length > 0;
    this.setData({ canSave: !!relOK && nameOK });
  },

  async onSave() {
    if (this.data.submitting) return;
    const name = (this.data.guardianName || '').trim();
    if (!name) {
      wx.showToast({ title: '请先填写名字', icon: 'none' });
      return;
    }
    const rel = this.data.selectedRelation === '其他'
      ? (this.data.customRelation || '').trim()
      : this.data.selectedRelation;
    if (!rel) {
      wx.showToast({ title: '请先选择关系', icon: 'none' });
      return;
    }
    this.setData({ submitting: true, error: '' });
    try {
      const res = await post('/api/reverse-guardian/invite', {
        guardian_name: name,
        relation_type: rel,
      }, { showLoading: false, suppressErrorToast: true });
      const data = (res && (res.data || res)) || {};
      if (data.qr_url) data.qr_url = resolveAssetUrl(data.qr_url);
      if (!data.qr_content_url && data.qr_url) data.qr_content_url = data.qr_url;
      this.setData({ invitation: data, submitting: false });
    } catch (e) {
      this.setData({ submitting: false });
      // [PRD-GUARDIAN-CARD-OPTIM-V1 2026-06-02] 上限错误弹升级提示框
      let detail = e && e.detail;
      // request 包装错误，e 可能是字符串或对象
      if (typeof detail === 'string') {
        try { detail = JSON.parse(detail); } catch (_) { /* keep string */ }
      }
      const code = detail && typeof detail === 'object' ? detail.code : '';
      if (code === 'GUARDIAN_LIMIT_REACHED' || code === 'WARD_LIMIT_REACHED') {
        const x = detail.x;
        const y = detail.y;
        wx.showModal({
          title: '已达被守护上限',
          content: `当前已有 ${x != null ? x : '-'} 位守护者（含邀请中），上限 ${y != null ? y : '-'} 位。升级会员可提升上限。`,
          cancelText: '稍后再说',
          confirmText: '去升级',
          confirmColor: '#16A34A',
          success: (r) => {
            if (r.confirm) {
              wx.navigateTo({
                url: '/pages/membership/index',
                fail: () => {
                  wx.switchTab({ url: '/pages/my/index', fail: () => {} });
                },
              });
            }
          },
        });
      } else {
        const msg = (detail && (detail.message || detail)) || (e && e.message) || '生成邀请失败';
        wx.showToast({ title: String(msg), icon: 'none' });
      }
    }
  },

  onQRReady() { this._qrReady = true; },

  saveToAlbum() {
    if (!this.data.invitation) {
      wx.showToast({ title: '暂无邀请图片', icon: 'none' });
      return;
    }
    const qrcodeComp = this.selectComponent('#qrcode');
    if (qrcodeComp && this._qrReady) {
      qrcodeComp.toTempFilePath().then((filePath) => {
        wx.saveImageToPhotosAlbum({
          filePath,
          success() { wx.showToast({ title: '已保存到相册', icon: 'success' }); },
          fail() { wx.showToast({ title: '保存失败，请授权相册权限', icon: 'none' }); },
        });
      }).catch(() => wx.showToast({ title: '生成图片失败', icon: 'none' }));
      return;
    }
    const url = this.data.invitation.qr_url;
    if (!url) {
      wx.showToast({ title: '暂无邀请图片', icon: 'none' });
      return;
    }
    wx.downloadFile({
      url: url.startsWith('http') ? url : app.globalData.baseUrl + url,
      success: (res) => {
        if (res.statusCode === 200) {
          wx.saveImageToPhotosAlbum({
            filePath: res.tempFilePath,
            success() { wx.showToast({ title: '已保存到相册', icon: 'success' }); },
            fail() { wx.showToast({ title: '保存失败，请授权相册权限', icon: 'none' }); },
          });
        }
      },
      fail() { wx.showToast({ title: '下载图片失败', icon: 'none' }); },
    });
  },

  copyLink() {
    if (!this.data.invitation || !this.data.invitation.invite_code) {
      wx.showToast({ title: '暂无邀请信息', icon: 'none' });
      return;
    }
    const link = `${app.globalData.baseUrl}/family-auth?code=${this.data.invitation.invite_code}&type=reverse`;
    wx.setClipboardData({
      data: link,
      success() { wx.showToast({ title: '链接已复制', icon: 'success' }); },
    });
  },

  onShareAppMessage() {
    if (!this.data.invitation) return {};
    return {
      title: '邀请你守护我的健康',
      path: `/pages/family-auth/index?code=${this.data.invitation.invite_code}&type=reverse`,
      imageUrl: this.data.invitation.qr_url || '',
    };
  },

  retry() {
    if (this.data.viewMode && this.data.invitation && this.data.invitation.invite_code) {
      this.loadExistingInvite(this.data.invitation.invite_code);
    } else {
      this.onSave();
    }
  },
});
