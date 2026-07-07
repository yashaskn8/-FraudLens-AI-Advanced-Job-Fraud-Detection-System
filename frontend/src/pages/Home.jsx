import { useState, useRef, useEffect } from "react";
import { useNavigate } from "react-router-dom";
import { Shield, Link2, FileText, ArrowRight, Zap, Lock, Globe, Building2, Brain, CheckCircle, TrendingUp, Users } from "lucide-react";
import ScanInput from "../components/ScanInput";
import LoadingState from "../components/LoadingState";
import { scanJob } from "../api/client";

// Phase 6 Custom Hook: Hacker Decode Text
function useHackerText(targetText, speed = 40, delay = 0) {
  const [text, setText] = useState("");
  const letters = "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789!@#$%^&*()_+";

  useEffect(() => {
    let iteration = 0;
    let interval = null;

    const startAnimation = () => {
      interval = setInterval(() => {
        setText((prev) =>
          targetText
            .split("")
            .map((letter, index) => {
              if (index < iteration) return targetText[index];
              return letters[Math.floor(Math.random() * letters.length)];
            })
            .join("")
        );
        if (iteration >= targetText.length) clearInterval(interval);
        iteration += 1 / 3;
      }, speed);
    };

    const timer = setTimeout(startAnimation, delay);
    return () => { clearTimeout(timer); clearInterval(interval); };
  }, [targetText, speed, delay]);

  return text;
}

const STAT_ITEMS = [
  { label: "Jobs Scanned", value: "124,810+", icon: TrendingUp },
  { label: "Scams Blocked", value: "18,392", icon: Shield },
  { label: "Accuracy", value: "94.7%", icon: Zap },
  { label: "Active Users", value: "31,200", icon: Users },
];

const HOW_IT_WORKS = [
  { step: "01", icon: Globe, title: "URL Deep Scan", desc: "Domain age, SSL, WHOIS, redirect chains, and live threat databases." },
  { step: "02", icon: Brain, title: "AI Classification", desc: "Fine-tuned BERT analyses language patterns across the description." },
  { step: "03", icon: Building2, title: "Company Verification", desc: "MCA21 India registry, email domain match, website existence." },
  { step: "04", icon: Lock, title: "Trust Score", desc: "Weighted fusion into a 0–100 score with plain-English explanation." },
];

function AnimatedStat({ value, label, icon: Icon, delay = 0 }) {
  const [visible, setVisible] = useState(false);
  const ref = useRef(null);

  useEffect(() => {
    const obs = new IntersectionObserver(([e]) => { if (e.isIntersecting) setVisible(true); }, { threshold: 0.1 });
    if (ref.current) obs.observe(ref.current);
    return () => obs.disconnect();
  }, []);

  return (
    <div ref={ref} style={{
      textAlign: "center", opacity: visible ? 1 : 0,
      transform: visible ? "translateY(0)" : "translateY(16px)",
      transition: `opacity 600ms ${delay}ms var(--ease-out-quart), transform 600ms ${delay}ms var(--ease-out-quart)`,
    }}>
      <div style={{
        width: "40px", height: "40px", background: "rgba(99,102,241,0.10)",
        border: "1px solid rgba(99,102,241,0.20)", borderRadius: "var(--radius-lg)",
        display: "flex", alignItems: "center", justifyContent: "center", margin: "0 auto 12px",
      }}>
        <Icon size={18} color="var(--brand-400)" />
      </div>
      <div style={{
        fontFamily: "var(--font-display)", fontWeight: 700, fontSize: "var(--text-3xl)",
        color: "var(--text-primary)", letterSpacing: "-0.04em", lineHeight: 1,
      }}>{value}</div>
      <div style={{ marginTop: "6px", fontSize: "var(--text-sm)", color: "var(--text-tertiary)", fontWeight: 500 }}>
        {label}
      </div>
    </div>
  );
}

export default function Home() {
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const navigate = useNavigate();

  const hackerJobScam = useHackerText("job scam", 30, 800);

  const handleScan = async (payload) => {
    if (!payload.url && !payload.description) {
      setError("Provide a job URL or description to begin scanning.");
      return;
    }
    setError(""); setLoading(true);
    try {
      const result = await scanJob(payload);
      // NOT_JOB_CONTENT is a valid response — navigate to results page
      const id = result.scan_id || "not_applicable";
      navigate(`/results/${id}`, { state: { result } });
    } catch {
      setError("Scan failed — check your connection and try again.");
    } finally { setLoading(false); }
  };

  if (loading) return <LoadingState />;

  return (
    <div style={{ background: "var(--surface-base)", minHeight: "100vh", overflowX: "hidden" }}>

      {/* ── Phase 6 Aurora Hero ─────────────────────────────────────────── */}
      <section style={{ position: "relative", overflow: "hidden", padding: "80px 24px 100px", minHeight: "80vh", display: "flex", alignItems: "center", justifyContent: "center" }}>
        
        {/* Breathing Aurora Effect Layer */}
        <div className="animate-aurora" style={{
          position: "absolute", top: "10%", left: "10%", width: "80%", height: "80%",
          pointerEvents: "none", zIndex: 0,
          background: `
            radial-gradient(circle at 20% 40%, rgba(99,102,241,0.15), transparent 40%),
            radial-gradient(circle at 80% 30%, rgba(139,92,246,0.1), transparent 40%),
            radial-gradient(circle at 50% 80%, rgba(59,130,246,0.12), transparent 50%)
          `,
          filter: "blur(60px)", mixBlendMode: "screen"
        }} />

        {/* Dense Laser Grid map */}
        <div style={{
          position: "absolute", inset: 0, pointerEvents: "none", zIndex: 0,
          backgroundImage: `
            linear-gradient(rgba(255,255,255,0.015) 1px, transparent 1px),
            linear-gradient(90deg, rgba(255,255,255,0.015) 1px, transparent 1px)
          `,
          backgroundSize: "40px 40px",
          maskImage: "radial-gradient(ellipse 70% 60% at 50% 30%, black 0%, transparent 80%)",
        }} />

        <div style={{ maxWidth: "800px", width: "100%", margin: "0 auto", textAlign: "center", position: "relative", zIndex: 1 }}>

          {/* Badge */}
          <div style={{
            display: "inline-flex", alignItems: "center", gap: "8px", background: "rgba(99,102,241,0.08)",
            border: "1px solid rgba(99,102,241,0.25)", borderRadius: "var(--radius-full)", padding: "6px 16px",
            marginBottom: "32px", animation: "fadeSlideDown 600ms var(--ease-out-expo) both",
          }}>
            <Zap size={12} color="var(--brand-400)" />
            <span style={{ fontSize: "var(--text-xs)", fontWeight: 600, color: "var(--brand-400)", letterSpacing: "0.08em", textTransform: "uppercase" }}>
              Enterprise Detection Engine
            </span>
          </div>

          {/* Headline with Hacker Effect */}
          <h1 style={{
            fontFamily: "var(--font-display)", fontWeight: 700, fontSize: "clamp(2.5rem, 7vw, 4rem)",
            lineHeight: 1.05, letterSpacing: "-0.04em", color: "var(--text-primary)", marginBottom: "20px",
            animation: "fadeSlideDown 700ms 100ms var(--ease-out-expo) both",
          }}>
            Never fall for a{" "}
            <span style={{
              background: "linear-gradient(135deg, var(--brand-400), var(--brand-600))",
              WebkitBackgroundClip: "text", WebkitTextFillColor: "transparent",
              position: "relative", display: "inline-block"
            }}>
              {hackerJobScam || <span style={{ opacity: 0 }}>job scam</span>}
              <span className="terminal-cursor" style={{ position: "absolute", right: "-12px", bottom: "4px" }} />
            </span>{" "}
            again
          </h1>

          <p style={{
            fontSize: "var(--text-lg)", color: "var(--text-secondary)", lineHeight: "var(--leading-relaxed)",
            maxWidth: "560px", margin: "0 auto 48px", animation: "fadeSlideDown 700ms 200ms var(--ease-out-expo) both",
          }}>
            TrustHire combines continuous intelligence and multi-modal AI models 
            to identify organized employment scams in less than 8 seconds.
          </p>

          {/* Scanner with Continuous Conic Pulse */}
          <div style={{ animation: "fadeSlideDown 700ms 300ms var(--ease-out-expo) both", position: "relative", padding: "1px", borderRadius: "var(--radius-3xl)" }}>
            
            {/* Phase 6: Conic Laser Border Rotation */}
            <div style={{
              position: "absolute", inset: "-2px", borderRadius: "inherit", zIndex: -1,
              background: "conic-gradient(from 0deg, transparent 70%, var(--brand-400) 80%, var(--brand-600) 100%)",
              animation: "spin-slow 4s linear infinite", opacity: 0.7
            }} />
            <div style={{
              position: "absolute", inset: "0", background: "var(--surface-base)", borderRadius: "inherit", zIndex: -1
            }} />
            
            <ScanInput onScan={handleScan} />
            {error && (
              <div style={{
                marginTop: "16px", padding: "10px 16px", background: "var(--critical-bg)",
                border: "1px solid var(--critical-border)", borderRadius: "var(--radius-lg)",
                fontSize: "var(--text-sm)", color: "var(--critical-400)", animation: "shake 300ms var(--ease-out-quart)",
              }}>{error}</div>
            )}
          </div>

          <div style={{
            marginTop: "32px", display: "flex", justifyContent: "center", gap: "24px", flexWrap: "wrap",
            animation: "fadeSlideDown 700ms 400ms var(--ease-out-expo) both",
          }}>
            {["No sign-up required", "Results in 8 seconds", "MCA21 India verified"].map(t => (
              <div key={t} style={{ display: "flex", alignItems: "center", gap: "6px", fontSize: "var(--text-sm)", color: "var(--text-tertiary)" }}>
                <CheckCircle size={13} color="var(--safe-500)" />
                {t}
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* ── Stats ────────────────────────────────────────────────────── */}
      <section style={{ maxWidth: "900px", margin: "0 auto 80px", padding: "0 24px" }}>
        <div style={{
          display: "grid", gridTemplateColumns: "repeat(4, 1fr)", gap: "1px", background: "var(--border-subtle)",
          borderRadius: "var(--radius-xl)", overflow: "hidden", border: "1px solid var(--border-default)",
        }}>
          {STAT_ITEMS.map(({ label, value, icon }, i) => (
            <div key={label} style={{ background: "var(--surface-1)", padding: "32px 24px" }}>
              <AnimatedStat value={value} label={label} icon={icon} delay={i * 80} />
            </div>
          ))}
        </div>
      </section>

      {/* ── How it works ──────────────────────────────────────────────── */}
      <section style={{ maxWidth: "1100px", margin: "0 auto 100px", padding: "0 24px" }}>
        <div style={{ textAlign: "center", marginBottom: "56px" }}>
          <div style={{
            fontSize: "var(--text-xs)", fontWeight: 600, letterSpacing: "0.12em", textTransform: "uppercase",
            color: "var(--brand-400)", marginBottom: "12px",
          }}>HOW IT WORKS</div>
          <h2 style={{
            fontFamily: "var(--font-display)", fontWeight: 700, fontSize: "var(--text-3xl)",
            letterSpacing: "-0.03em", color: "var(--text-primary)",
          }}>
            Four layers of fraud detection
          </h2>
        </div>

        <div style={{
          display: "grid", gridTemplateColumns: "repeat(4, 1fr)", gap: "1px", background: "var(--border-subtle)",
          border: "1px solid var(--border-default)", borderRadius: "var(--radius-xl)", overflow: "hidden",
        }}>
          {HOW_IT_WORKS.map(({ step, icon: Icon, title, desc }) => (
            <div key={step} style={{
              background: "var(--surface-1)", padding: "36px 28px", position: "relative",
              transition: "background var(--duration-normal)", cursor: "default",
            }}
            onMouseEnter={e => e.currentTarget.style.background = "var(--surface-2)"}
            onMouseLeave={e => e.currentTarget.style.background = "var(--surface-1)"}
            >
              <div style={{ fontSize: "var(--text-xs)", fontFamily: "var(--font-mono)", color: "var(--text-disabled)", letterSpacing: "0.08em", marginBottom: "20px" }}>
                {step}
              </div>
              <div style={{
                width: "44px", height: "44px", background: "rgba(99,102,241,0.08)", border: "1px solid rgba(99,102,241,0.16)",
                borderRadius: "var(--radius-lg)", display: "flex", alignItems: "center", justifyContent: "center", marginBottom: "18px",
              }}>
                <Icon size={20} color="var(--brand-400)" />
              </div>
              <h3 style={{ fontFamily: "var(--font-display)", fontWeight: 600, fontSize: "var(--text-base)", color: "var(--text-primary)", marginBottom: "10px", letterSpacing: "-0.02em" }}>{title}</h3>
              <p style={{ fontSize: "var(--text-sm)", color: "var(--text-tertiary)", lineHeight: "var(--leading-relaxed)" }}>{desc}</p>
            </div>
          ))}
        </div>
      </section>

      <style>{`
        @keyframes fadeSlideDown {
          from { opacity: 0; transform: translateY(-12px); }
          to   { opacity: 1; transform: translateY(0); }
        }
        @keyframes shake {
          0%, 100% { transform: translateX(0); }
          20% { transform: translateX(-6px); }
          40% { transform: translateX(6px); }
          60% { transform: translateX(-4px); }
          80% { transform: translateX(4px); }
        }
      `}</style>
    </div>
  );
}
