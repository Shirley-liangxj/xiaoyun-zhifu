/** @type {import('tailwindcss').Config} */
export default {
  content: [
    "./index.html",
    "./src/**/*.{js,ts,jsx,tsx}",
  ],
  theme: {
    extend: {
      colors: {
        // 小云智服品牌色
        primary: {
          DEFAULT: '#1D9E75',
          dark: '#0F6E56',
          light: '#E1F5EE',
        },
        background: '#F0F4F8',
        sidebar: '#1F2937',
      },
    },
  },
  plugins: [],
}
