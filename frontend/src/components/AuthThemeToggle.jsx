import { useTheme } from "../theme/ThemeContext";
import { IconSun, IconMoon } from "./Icons";

// A small floating toggle for the login/register screens, where there's no
// sidebar yet to hold the full theme-toggle button.
export function AuthThemeToggle() {
  const { theme, toggleTheme } = useTheme();
  return (
    <button
      onClick={toggleTheme}
      aria-label={theme === "dark" ? "Switch to light mode" : "Switch to dark mode"}
      style={{
        position: "fixed", top: 18, right: 18,
        width: 36, height: 36, borderRadius: "50%",
        background: "rgba(255,255,255,0.08)", border: "1px solid rgba(255,255,255,0.15)",
        color: "#cfd6e0", display: "flex", alignItems: "center", justifyContent: "center",
        cursor: "pointer",
      }}
    >
      {theme === "dark" ? <IconSun width={16} height={16} /> : <IconMoon width={16} height={16} />}
    </button>
  );
}
