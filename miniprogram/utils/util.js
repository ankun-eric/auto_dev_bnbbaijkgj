// [BUG_FIX_TIMEZONE_GLOBAL_20260517] 旧 formatTime/formatDate/formatRelativeTime
// 内部统一委托到 utils/datetime.js，对外保留旧签名（date 支持 Date / 字符串 / 时间戳）
const _dt = require('./datetime');

function formatTime(date) {
  return _dt.formatDateTime(date, 'YYYY-MM-DD HH:mm:ss');
}

function formatDate(date) {
  return _dt.formatDate(date);
}

function formatRelativeTime(timestamp) {
  return _dt.formatRelativeTime(timestamp);
}

function pad(n) {
  return String(n).padStart(2, '0');
}

function throttle(fn, delay = 500) {
  let timer = null;
  return function (...args) {
    if (timer) return;
    timer = setTimeout(() => {
      fn.apply(this, args);
      timer = null;
    }, delay);
  };
}

function debounce(fn, delay = 300) {
  let timer = null;
  return function (...args) {
    if (timer) clearTimeout(timer);
    timer = setTimeout(() => {
      fn.apply(this, args);
    }, delay);
  };
}

function generateId() {
  return Date.now().toString(36) + Math.random().toString(36).substr(2, 9);
}

function checkLogin() {
  const app = getApp();
  if (!app.globalData.isLoggedIn) {
    wx.navigateTo({ url: '/pages/login/index' });
    return false;
  }
  return true;
}

function getCurrentRole() {
  return getApp().getCurrentRole();
}

function hasMerchantIdentity() {
  return getApp().hasMerchantIdentity();
}

function hasUserIdentity() {
  return getApp().hasUserIdentity();
}

function isDualIdentity() {
  return getApp().isDualIdentity();
}

function syncTabBar(page, path) {
  if (!page || typeof page.getTabBar !== 'function') return;
  const tabBar = page.getTabBar();
  if (tabBar && typeof tabBar.refreshTabs === 'function') {
    tabBar.refreshTabs();
    tabBar.setData({ selected: path });
  }
}

function ensureMerchantEntry() {
  const app = getApp();
  if (!app.globalData.isLoggedIn) {
    wx.navigateTo({ url: '/pages/login/index' });
    return false;
  }
  if (!app.hasMerchantIdentity()) {
    wx.navigateTo({ url: '/pages/no-permission/index?scene=merchant' });
    return false;
  }
  if (!app.getCurrentStore()) {
    wx.navigateTo({ url: '/pages/store-select/index' });
    return false;
  }
  return true;
}

module.exports = {
  formatTime,
  formatDate,
  formatRelativeTime,
  throttle,
  debounce,
  generateId,
  checkLogin,
  getCurrentRole,
  hasMerchantIdentity,
  hasUserIdentity,
  isDualIdentity,
  syncTabBar,
  ensureMerchantEntry
};
