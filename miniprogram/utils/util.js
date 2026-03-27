function formatTime(date) {
  const year = date.getFullYear();
  const month = date.getMonth() + 1;
  const day = date.getDate();
  const hour = date.getHours();
  const minute = date.getMinutes();
  const second = date.getSeconds();
  return `${pad(year)}-${pad(month)}-${pad(day)} ${pad(hour)}:${pad(minute)}:${pad(second)}`;
}

function formatDate(date) {
  const year = date.getFullYear();
  const month = date.getMonth() + 1;
  const day = date.getDate();
  return `${pad(year)}-${pad(month)}-${pad(day)}`;
}

function formatRelativeTime(timestamp) {
  const now = Date.now();
  const diff = now - timestamp;
  const minute = 60 * 1000;
  const hour = 60 * minute;
  const day = 24 * hour;

  if (diff < minute) return '刚刚';
  if (diff < hour) return `${Math.floor(diff / minute)}分钟前`;
  if (diff < day) return `${Math.floor(diff / hour)}小时前`;
  if (diff < 7 * day) return `${Math.floor(diff / day)}天前`;
  return formatDate(new Date(timestamp));
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

module.exports = {
  formatTime,
  formatDate,
  formatRelativeTime,
  throttle,
  debounce,
  generateId,
  checkLogin
};
