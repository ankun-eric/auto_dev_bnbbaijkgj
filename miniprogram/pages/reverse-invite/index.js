const { post } = require('../../utils/request');
const { resolveAssetUrl } = require('../../utils/asset-url');
const app = getApp();

Page({
  data: {
    loading: true,
    invitation: null,
    error: '',
  },

  onLoad() {
    this.createReverseInvite();
  },

  async createReverseInvite() {
    this.setData({ loading: true, error: '' });
    try {
      const res = await post('/api/reverse-guardian/invite', {});
      if (res && typeof res === 'object') {
        if (res.qr_url) res.qr_url = resolveAssetUrl(res.qr_url);
        if (res.qr_content_url) res.qr_content_url = resolveAssetUrl(res.qr_content_url);
      }
      this.setData({ invitation: res, loading: false });
    } catch (e) {
      this.setData({
        loading: false,
        error: (e && e.detail) || '生成邀请失败，请重试',
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
          success() { wx.showToast({ title: '已保存到相册', icon: 'success' }); },
          fail() { wx.showToast({ title: '保存失败，请授权相册权限', icon: 'none' }); },
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
    this.createReverseInvite();
  },
});
