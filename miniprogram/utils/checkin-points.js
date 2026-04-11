/**
 * 打卡积分反馈相关辅助函数
 */

function showCheckinPointsToast(result) {
  if (!result) {
    wx.showToast({ title: '打卡成功', icon: 'success' });
    return;
  }
  if (result.points_earned && result.points_earned > 0) {
    if (result.points_limit_reached) {
      wx.showToast({ title: '打卡成功！今日积分已达上限', icon: 'none' });
    } else {
      wx.showToast({ title: '打卡成功，获得' + result.points_earned + '积分！', icon: 'none' });
    }
  } else if (result.points_limit_reached) {
    wx.showToast({ title: '打卡成功！今日积分已达上限', icon: 'none' });
  } else {
    wx.showToast({ title: result.message || '打卡成功', icon: 'success' });
  }
}

module.exports = { showCheckinPointsToast };
