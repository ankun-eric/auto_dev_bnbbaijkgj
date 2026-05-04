/**
 * [2026-05-05 订单页地址导航按钮 PRD v1.0] 小程序端通用地址导航工具
 *
 * 行为：
 *   - 有经纬度（lat/lng）→ wx.openLocation（腾讯地图底图，含路线规划入口）
 *   - 无经纬度 → 把地址复制到剪贴板，提示用户在地图 App 内粘贴搜索
 *
 * 用法：
 *   const { navigateToAddress } = require('../../utils/map-nav');
 *   navigateToAddress({
 *     name: '门店名',
 *     address: '广东省深圳市福田区...',
 *     lat: 22.5,
 *     lng: 114.0,
 *   });
 *
 * 防抖 500ms（PRD E-09）：通过 lastClickTs 内部状态实现。
 */

let _lastClickTs = 0;

function navigateToAddress(target) {
  const now = Date.now();
  if (now - _lastClickTs < 500) return; // 防抖
  _lastClickTs = now;

  if (!target) {
    wx.showToast({ title: '地址信息缺失', icon: 'none' });
    return;
  }

  const name = (target.name || '目的地').toString();
  const address = (target.address || '').toString();
  const latRaw = target.lat;
  const lngRaw = target.lng;

  const hasLatLng =
    latRaw != null &&
    lngRaw != null &&
    !Number.isNaN(Number(latRaw)) &&
    !Number.isNaN(Number(lngRaw));

  if (hasLatLng) {
    wx.openLocation({
      latitude: Number(latRaw),
      longitude: Number(lngRaw),
      name: name,
      address: address || name,
      scale: 16,
      fail: () => wx.showToast({ title: '打开地图失败', icon: 'none' }),
    });
    return;
  }

  // 经纬度缺失降级：复制地址 + Toast 引导
  const fullText = address ? `${name} ${address}` : name;
  wx.setClipboardData({
    data: fullText,
    success: () => {
      wx.showModal({
        title: '地址已复制',
        content: `已复制「${fullText}」到剪贴板，请在高德/百度等地图 App 内粘贴搜索导航。`,
        showCancel: false,
        confirmText: '我知道了',
      });
    },
    fail: () => {
      wx.showToast({ title: '复制地址失败', icon: 'none' });
    },
  });
}

module.exports = {
  navigateToAddress,
};
