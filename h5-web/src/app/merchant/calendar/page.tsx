'use client';

/**
 * [PRD-365 商家后台「预约看板」替换升级 v1.0]
 *
 * 旧路径 /merchant/calendar/ 重定向到新版预约看板 /merchant/order-dashboard/
 * 客户端立即 replace 跳转（保留浏览器历史不污染）。
 *
 * 备注：因服务器侧 Next.js 路由是文件系统路由，本目录下的旧组件
 * （DayView/WeekView/MonthView/etc.）保留作为内部依赖，
 * 但用户访问入口 page.tsx 已改为重定向。
 */
import { useEffect } from 'react';
import { useRouter } from 'next/navigation';
import { Spin, Typography } from 'antd';

const { Text } = Typography;

export default function MerchantCalendarRedirectPage() {
  const router = useRouter();

  useEffect(() => {
    router.replace('/merchant/order-dashboard');
  }, [router]);

  return (
    <div style={{ padding: 60, textAlign: 'center' }}>
      <Spin />
      <div style={{ marginTop: 16 }}>
        <Text type="secondary">
          【预约日历】已升级为【预约看板】，正在为您跳转…
        </Text>
      </div>
    </div>
  );
}
