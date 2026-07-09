/** @type {import('tailwindcss').Config} */
export default {
  content: [
    "./index.html",
    "./src/**/*.{js,ts,jsx,tsx}",
    "../design-system/**/*.tsx"
  ],
  theme: {
    extend: {
      colors: {
        slate: {
          50: "hsl(210, 40%, 98%)",
          100: "hsl(210, 40%, 96.1%)",
          200: "hsl(214, 32%, 91%)",
          300: "hsl(213, 27%, 84%)",
          400: "hsl(215, 20%, 65%)",
          500: "hsl(215, 16%, 47%)",
          600: "hsl(215, 19%, 35%)",
          700: "hsl(215, 25%, 27%)",
          800: "hsl(217, 33%, 17%)",
          900: "hsl(222, 47%, 11.2%)",
          950: "hsl(222, 47%, 6%)",
        },
        violet: {
          50: "hsl(250, 100%, 97.5%)",
          100: "hsl(250, 95%, 94%)",
          500: "hsl(250, 95%, 60%)",
          600: "hsl(250, 90%, 55%)",
          700: "hsl(250, 85%, 45%)",
        },
      },
    },
  },
  plugins: [],
  darkMode: 'class',
}
