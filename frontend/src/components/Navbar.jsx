import { useState, useEffect } from "react";
import { Link, useLocation } from "react-router-dom";
import { Shield, Scan, BarChart2, Flag, Info, Menu, X } from "lucide-react";

const NAV_ITEMS = [
  { to: "/",          label: "Scanner",   icon: Scan       },
  { to: "/dashboard", label: "Dashboard", icon: BarChart2  },
  { to: "/reports",   label: "Reports",   icon: Flag       },
  { to: "/about",     label: "About",     icon: Info       },
];

export default function Navbar() {
  const { pathname } = useLocation();
  const [scrolled, setScrolled] = useState(false);
  const [mobileOpen, setMobileOpen] = useState(false);

  useEffect(() => {
    const fn = () => setScrolled(window.scrollY > 20);
    window.addEventListener("scroll", fn, { passive: true });
    return () => window.removeEventListener("scroll", fn);
  }, []);

  return (
    <>
      <nav style={{
        position: "fixed", top: 0, left: 0, right: 0, zIndex: 50,
        height: "60px",
        // Use a solid semi-transparent base that supports backdrop-filter
        backgroundColor: scrolled
          ? "rgba(8,8,15,0.92)"
          : "rgba(8,8,15,0.60)",
        backdropFilter: "blur(20px) saturate(180%)",
        WebkitBackdropFilter: "blur(20px) saturate(180%)",
        borderBottom: `1px solid ${scrolled
          ? "rgba(255,255,255,0.09)"
          : "rgba(255,255,255,0.03)"}`,
        transition: "background-color 300ms ease, border-color 300ms ease",
      }}>
        <div style={{
          maxWidth: "1200px", margin: "0 auto",
          height: "100%", padding: "0 24px",
          display: "flex", alignItems: "center", justifyContent: "space-between",
        }}>
          {/* Logo */}
          <Link to="/" style={{
            display: "flex", alignItems: "center", gap: "10px",
            textDecoration: "none",
          }}>
            <div style={{
              width: "34px", height: "34px",
              background: "linear-gradient(135deg, var(--brand-600), var(--brand-400))",
              borderRadius: "10px",
              display: "flex", alignItems: "center", justifyContent: "center",
              boxShadow: "0 0 16px rgba(99,102,241,0.35)",
            }}>
              <Shield size={18} color="white" />
            </div>
            <span style={{
              fontFamily: "var(--font-display)",
              fontWeight: 700, fontSize: "18px",
              color: "var(--text-primary)",
              letterSpacing: "-0.03em",
            }}>
              Trust<span style={{ color: "var(--brand-400)" }}>Hire</span>
            </span>
          </Link>

          {/* Desktop nav */}
          <div style={{
            display: "flex", alignItems: "center", gap: "2px",
            background: "var(--surface-2)",
            border: "1px solid var(--border-subtle)",
            borderRadius: "var(--radius-full)",
            padding: "4px",
          }}>
            {NAV_ITEMS.map(({ to, label, icon: Icon }) => {
              const active = pathname === to;
              return (
                <Link key={to} to={to} style={{
                  display: "flex", alignItems: "center", gap: "6px",
                  padding: "6px 14px",
                  borderRadius: "var(--radius-full)",
                  textDecoration: "none",
                  fontFamily: "var(--font-body)",
                  fontSize: "var(--text-sm)",
                  fontWeight: active ? 600 : 400,
                  color: active ? "var(--text-primary)" : "var(--text-tertiary)",
                  background: active
                    ? "linear-gradient(135deg, rgba(99,102,241,0.20), rgba(129,140,248,0.10))"
                    : "transparent",
                  border: active
                    ? "1px solid var(--border-brand)"
                    : "1px solid transparent",
                  transition: "all var(--duration-fast) var(--ease-out-quart)",
                }}>
                  <Icon size={13} />
                  {label}
                </Link>
              );
            })}
          </div>

          {/* CTA */}
          <div style={{ display: "flex", alignItems: "center", gap: "10px" }}>
            <div style={{
              display: "flex", alignItems: "center", gap: "6px",
              padding: "5px 10px",
              background: "rgba(34,197,94,0.08)",
              border: "1px solid rgba(34,197,94,0.20)",
              borderRadius: "var(--radius-full)",
            }}>
              <div style={{
                width: "6px", height: "6px",
                borderRadius: "50%",
                background: "var(--safe-500)",
                boxShadow: "0 0 6px var(--safe-500)",
                animation: "pulse 2s infinite",
              }} />
              <span style={{
                fontSize: "var(--text-xs)", fontWeight: 500,
                color: "var(--safe-400)",
                fontFamily: "var(--font-mono)",
              }}>
                LIVE
              </span>
            </div>
          </div>
        </div>
      </nav>

      {/* Spacer */}
      <div style={{ height: "60px" }} />

      <style>{`
        @keyframes pulse {
          0%, 100% { opacity: 1; }
          50% { opacity: 0.5; }
        }
      `}</style>
    </>
  );
}
