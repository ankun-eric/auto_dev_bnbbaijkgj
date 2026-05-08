'use client';

/**
 * [Bug-419 2026-05-08] 页面区块级 ErrorBoundary
 *
 * 设计目的：在 H5 端 ai-home 等页面的关键区块（顶部菜单 / 欢迎语 /
 * 推荐问 / 功能宫格 / 健康贴士轮播）外层各自包一层，确保任意子树抛错
 * 时**只降级该子区块**，绝不让外层骨架（顶部标题栏 + 底部输入框）
 * 被 React 卸载，从而避免"422 → 整页白屏"事故。
 *
 * 使用：
 *   <SectionErrorBoundary name="welcome">
 *     <WelcomeBanner ... />
 *   </SectionErrorBoundary>
 */
import React from 'react';

interface Props {
  /** 区块名称，用于日志（避免开发者排查时多个 ErrorBoundary 混淆） */
  name?: string;
  /** 自定义降级渲染。未提供时显示一个 8 像素高的占位符（视觉无感） */
  fallback?: React.ReactNode;
  children?: React.ReactNode;
}

interface State {
  hasError: boolean;
  err?: any;
}

export default class SectionErrorBoundary extends React.Component<Props, State> {
  constructor(props: Props) {
    super(props);
    this.state = { hasError: false };
  }

  static getDerivedStateFromError(err: any): State {
    return { hasError: true, err };
  }

  componentDidCatch(error: any, errorInfo: any) {
    if (typeof console !== 'undefined') {
      // eslint-disable-next-line no-console
      console.error(
        `[SectionErrorBoundary:${this.props.name || 'unnamed'}] caught:`,
        error,
        errorInfo,
      );
    }
  }

  render() {
    if (this.state.hasError) {
      if (this.props.fallback !== undefined) return this.props.fallback;
      // 默认占位：保持一行轻微高度，让上下区块布局不塌陷
      return <div data-section-error={this.props.name || 'unnamed'} style={{ minHeight: 8 }} />;
    }
    return this.props.children;
  }
}
