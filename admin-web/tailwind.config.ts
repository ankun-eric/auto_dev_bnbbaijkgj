import type { Config } from 'tailwindcss';

const config: Config = {
  content: [
    './src/**/*.{js,ts,jsx,tsx,mdx}',
  ],
  theme: {
    extend: {
      colors: {
        primary: '#52c41a',
        secondary: '#13c2c2',
      },
    },
  },
  plugins: [],
  corePlugins: {
    preflight: false,
  },
};

export default config;
