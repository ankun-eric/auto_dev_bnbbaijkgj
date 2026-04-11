import { Toast } from 'antd-mobile';

export function showCheckinPointsToast(result: {
  message?: string;
  points_earned?: number;
  points_limit_reached?: boolean;
}) {
  if (result.points_earned && result.points_earned > 0) {
    if (result.points_limit_reached) {
      Toast.show({ content: '打卡成功！今日打卡积分已达上限', icon: 'success' });
    } else {
      Toast.show({ content: `打卡成功，获得 ${result.points_earned} 积分！`, icon: 'success' });
    }
  } else if (result.points_limit_reached) {
    Toast.show({ content: '打卡成功！今日打卡积分已达上限', icon: 'success' });
  } else {
    Toast.show({ content: result.message || '打卡成功', icon: 'success' });
  }
}
