/** @type {import('next').NextConfig} */
const nextConfig = {
  output: 'standalone',
  reactStrictMode: true,
  basePath: process.env.NEXT_PUBLIC_BASE_PATH || '',
  trailingSlash: true,
  typescript: {
    ignoreBuildErrors: true,
  },
  async rewrites() {
    return [];
  },
  // [2026-04-23 对话页统一化] 旧体检对话页路径 301 永久重定向到公共咨询页，外部/历史链接仍可访问
  // [PRD-AI-HOME-V1 2026-05-19] (tabs) 路由组已归档：/home、/ai 旧入口统一 301 重定向到 /ai-home，
  //   避免外部分享或浏览器历史命中已下线路由出现 404。
  //   /profile 因 app/profile 同名独立页仍在使用，**不**做重定向。
  async redirects() {
    return [
      {
        source: '/checkup/chat/:sid',
        destination: '/chat/:sid?type=report_interpret&auto_start=1',
        permanent: true,
      },
      {
        source: '/home',
        destination: '/ai-home',
        permanent: true,
      },
      {
        source: '/ai',
        destination: '/ai-home',
        permanent: true,
      },
      // [PRD-MSG-CENTER-UNIFY-V1 2026-06-02 F0-1 / §4.1] 旧「消息通知」页 /notifications 已下线，
      //   统一收敛到消息中心 /messages（接口 /api/messages/*）。旧链接/历史/分享 301 永久重定向，
      //   保证不出现 404，过渡期外部访问仍可达。
      {
        source: '/notifications',
        destination: '/messages',
        permanent: true,
      },
    ];
  },
};

module.exports = nextConfig;
