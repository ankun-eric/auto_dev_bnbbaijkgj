/**
 * [PRD-469 M1] 旧版 /health-profile 路由下线
 *
 * 全平台入口已切换到 /health-profile-v2，旧路由直接返回 404，不做重定向。
 */
import { notFound } from 'next/navigation';

export default function HealthProfileLegacyPage() {
  notFound();
}
