import type { Config } from 'tailwindcss';

const config: Config = {
  content: [
    './src/pages/**/*.{js,ts,jsx,tsx,mdx}',
    './src/components/**/*.{js,ts,jsx,tsx,mdx}',
    './src/app/**/*.{js,ts,jsx,tsx,mdx}',
  ],
  theme: {
    extend: {
      colors: {
        primary: '#52c41a',
        'primary-light': '#95de64',
        'primary-dark': '#389e0d',
        secondary: '#13c2c2',
        'secondary-light': '#5cdbd3',
        'secondary-dark': '#08979c',
      },
      fontSize: {
        // v6 视觉一致性：全局基准 14 -> 16 提升一档
        // text-xs 保持 12px（角标/时间戳标准）
        'xs': ['12px', { lineHeight: '16px' }],
        'sm': ['16px', { lineHeight: '22px' }],
        'base': ['17px', { lineHeight: '24px' }],
        'lg': ['19px', { lineHeight: '26px' }],
        'xl': ['22px', { lineHeight: '28px' }],
      },
    },
  },
  plugins: [],
};

export default config;
