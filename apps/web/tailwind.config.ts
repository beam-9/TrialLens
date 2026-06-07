import type { Config } from "tailwindcss";

const config: Config = {
  content: ["./app/**/*.{ts,tsx}", "./components/**/*.{ts,tsx}", "./lib/**/*.{ts,tsx}"],
  theme: {
    extend: {
      fontFamily: {
        display: ["Canela", "Cormorant Garamond", "Georgia", "serif"],
        body: ["Aptos", "IBM Plex Sans", "Helvetica Neue", "ui-sans-serif", "system-ui"],
      },
      colors: {
        ink: "#10140f",
        paper: "#f7f3ea",
        slide: "#f3f0eb",
        fog: "#dbe4e2",
        moss: "#395f43",
        signal: "#b64a2d",
        clinical: "#164a55",
      },
    },
  },
  plugins: [],
};

export default config;
