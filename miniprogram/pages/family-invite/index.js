const { post } = require('../../utils/request');
// [2026-05-05 全端图片附件 BasePath 治理 v1.0] 把后端裸 /uploads/... 补齐为带 baseUrl 的绝对 URL
const { resolveAssetUrl } = require('../../utils/asset-url');
const app = getApp();

Page({
  data: {
    memberId: '',
    loading: true,
    invitation: null,
    error: ''
  },

  onLoad(options) {
    if (options.member_id) {
      this.setData({ memberId: options.member_id });
      this.createInvitation(options.member_id);
    } else {
      this.setData({ loading: false, error: '缺少成员参数' });
    }
  },

  async createInvitation(memberId) {
    try {
      const res = await post('/api/family/invitation', { member_id: parseInt(memberId, 10) });
      // [2026-05-05 全端图片附件 BasePath 治理 v1.0]
      // 后端可能返回裸 /uploads/... 形式的 qr_url（二维码图片），直接绑给 <image> 或 wx.downloadFile
      // 在 /autodev/<uuid>/ 子路径部署下会失效，这里统一补齐为绝对 URL。
      // 注意：qr_content_url 是二维码内部要编码的文本内容（通常已是完整 URL），同样安全 resolve 一次。
      if (res && typeof res === 'object') {
        if (res.qr_url) res.qr_url = resolveAssetUrl(res.qr_url);
        if (res.qr_content_url) res.qr_content_url = resolveAssetUrl(res.qr_content_url);
      }
      this.setData({ invitation: res, loading: false });
    } catch (e) {
      this.setData({
        loading: false,
        error: (e && e.detail) || '生成邀请失败，请重试'
      });
    }
  },

  onQRReady() {
    this._qrReady = true;
  },

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
          success() {
            wx.showToast({ title: '已保存到相册', icon: 'success' });
          },
          fail() {
            wx.showToast({ title: '保存失败，请授权相册权限', icon: 'none' });
          }
        });
      }).catch(() => {
        wx.showToast({ title: '生成图片失败', icon: 'none' });
      });
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
            success() {
              wx.showToast({ title: '已保存到相册', icon: 'success' });
            },
            fail() {
              wx.showToast({ title: '保存失败，请授权相册权限', icon: 'none' });
            }
          });
        }
      },
      fail() {
        wx.showToast({ title: '下载图片失败', icon: 'none' });
      }
    });
  },

  copyLink() {
    if (!this.data.invitation || !this.data.invitation.invite_code) {
      wx.showToast({ title: '暂无邀请信息', icon: 'none' });
      return;
    }
    const link = `${app.globalData.baseUrl}/family-auth?code=${this.data.invitation.invite_code}`;
    wx.setClipboardData({
      data: link,
      success() {
        wx.showToast({ title: '链接已复制', icon: 'success' });
      }
    });
  },

  onShareAppMessage() {
    if (!this.data.invitation) return {};
    return {
      title: '邀请你共管家庭健康档案',
      path: `/pages/family-auth/index?code=${this.data.invitation.invite_code}`,
      imageUrl: this.data.invitation.qr_url || ''
    };
  },

  retry() {
    this.setData({ loading: true, error: '' });
    this.createInvitation(this.data.memberId);
  }
});
