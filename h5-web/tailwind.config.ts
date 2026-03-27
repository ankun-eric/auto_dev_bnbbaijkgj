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
    },
  },
  plugins: [],
};

export default config;
