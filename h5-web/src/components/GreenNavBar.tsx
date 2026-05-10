'use client';

import { ReactNode } from 'react';
import { useRouter } from 'next/navigation';
import { NavBar } from 'antd-mobile';

/**
 * PRD-442 落地：旧绿色顶栏统一切换为「晴空诊室」天蓝品牌色
 * - PRIMARY_GREEN 名称保留以兼容外部引用，但实际值为 brand-500 天蓝
 * - 渐变改为 design-tokens 的 gradient-primary-btn（brand-400 → brand-600）
 */
export const PRIMARY_GREEN = '#0EA5E9';
export const PRIMARY_GREEN_GRADIENT =
  'linear-gradient(135deg, #38BDF8, #0284C7)';

interface GreenNavBarProps {
  children?: ReactNode;
  right?: ReactNode;
  back?: boolean | (() => void);
  showBack?: boolean;
  gradient?: boolean;
  className?: string;
}

/**
 * 统一主品牌色（晴空诊室天蓝）顶栏组件，标题白色加粗居中，箭头/右上图标统一白色。
 * 用于 H5 用户端 22 个二级页面顶栏一致性改造。
 * PRD-442 后：底色由旧绿色 #52c41a 切换至天蓝 brand-500 (#0EA5E9)。
 */
export default function GreenNavBar({
  children,
  right,
  back = true,
  showBack = true,
  gradient = false,
  className,
}: GreenNavBarProps) {
  const router = useRouter();

  const handleBack = () => {
    if (typeof back === 'function') {
      back();
    } else {
      try {
        router.back();
      } catch {
        router.push('/');
      }
    }
  };

  return (
    <div
      className={className}
      style={{
        background: gradient ? PRIMARY_GREEN_GRADIENT : PRIMARY_GREEN,
      }}
    >
      <NavBar
        onBack={showBack ? handleBack : undefined}
        backArrow={showBack}
        right={right}
        style={{
          background: 'transparent',
          color: '#fff',
          '--height': '46px',
        } as React.CSSProperties}
      >
        <span
          style={{
            color: '#fff',
            fontWeight: 600,
            fontSize: 17,
          }}
        >
          {children}
        </span>
      </NavBar>
      <style jsx global>{`
        .adm-nav-bar .adm-nav-bar-back-arrow,
        .adm-nav-bar .adm-nav-bar-back {
          color: #fff !important;
        }
        .adm-nav-bar .adm-nav-bar-title {
          color: #fff !important;
          font-weight: 600 !important;
        }
      `}</style>
    </div>
  );
}
