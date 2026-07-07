import { useRef } from "react";

export default function MagicCard({ children, style = {}, className = "", glowColor = "rgba(99,102,241,0.15)" }) {
  const ref = useRef(null);

  const handlePointerMove = (e) => {
    if (!ref.current) return;
    const rect = ref.current.getBoundingClientRect();
    const x = e.clientX - rect.left;
    const y = e.clientY - rect.top;
    ref.current.style.setProperty("--mouseX", `${x}px`);
    ref.current.style.setProperty("--mouseY", `${y}px`);
  };

  return (
    <div
      ref={ref}
      onPointerMove={handlePointerMove}
      className={`magic-card group ${className}`}
      style={{
        ...style,
        position: "relative",
        overflow: "hidden",
      }}
    >
      <div
        className="pointer-events-none absolute inset-0 opacity-0 mix-blend-screen transition-opacity duration-300 group-hover:opacity-100 z-0"
        style={{
          background: `radial-gradient(400px circle at var(--mouseX, 50%) var(--mouseY, 50%), ${glowColor}, transparent 50%)`,
        }}
      />
      <div style={{ position: "relative", zIndex: 1, height: "100%", width: "100%" }}>
        {children}
      </div>
    </div>
  );
}
