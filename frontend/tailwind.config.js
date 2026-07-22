/** @type {import('tailwindcss').Config} */
export default {
  content: ["./index.html", "./src/**/*.{js,jsx}"],
  theme: {
    extend: {
      colors: {
        base: "#0D1012",
        panel: "#161A1D",
        raised: "#1E2327",
        hairline: "#282E32",
        ink: "#ECEEF0",
        muted: "#8E979E",
        haze: "#E8A853",
        tealx: "#4FD1C5",
        band: {
          good: "#3DDC84",
          satisfactory: "#A8D93E",
          moderate: "#F2C230",
          poor: "#F2914A",
          verypoor: "#E0483C",
          severe: "#8B1E2D",
        },
      },
      fontFamily: {
        display: ["Fraunces", "serif"],
        sans: ["Inter", "sans-serif"],
        mono: ["IBM Plex Mono", "monospace"],
      },
    },
  },
  plugins: [],
}
