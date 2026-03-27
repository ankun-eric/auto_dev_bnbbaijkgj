/** @type {import('next').NextConfig} */
const nextConfig = {
  output: 'standalone',
  basePath: process.env.NEXT_PUBLIC_BASE_PATH || '',
  trailingSlash: true,
  typescript: {
    ignoreBuildErrors: true,
  },
  async rewrites() {
    return [];
  },
};
module.exports = nextConfig;
