/** @type {import('tailwindcss').Config} */
export default {
  content: ["./index.html", "./src/**/*.{js,ts,jsx,tsx}"],
  theme: {
    extend: {
      fontFamily: {
        display: ["Space Grotesk", "sans-serif"],
        body:    ["Inter", "sans-serif"],
        mono:    ["DM Mono", "monospace"],
      },
      colors: {
        brand:    { 400: "#818cf8", 500: "#6366f1", 600: "#4f46e5", 700: "#4338ca" },
        surface:  { base: "#08080f", 1: "#0f0f1a", 2: "#141422", 3: "#1a1a2e", 4: "#1f1f38" },
      },
      borderRadius: {
        "2xl": "20px", "3xl": "28px",
      },
      animation: {
        "fade-in":    "fadeIn 300ms var(--ease-out-quart) both",
        "slide-down": "slideDown 400ms var(--ease-out-expo) both",
      },
      keyframes: {
        fadeIn:    { from: { opacity:0, transform:"translateY(8px)" }, to: { opacity:1, transform:"translateY(0)" } },
        slideDown: { from: { opacity:0, transform:"translateY(-12px)" }, to: { opacity:1, transform:"translateY(0)" } },
      },
    },
  },
  plugins: [],
};
