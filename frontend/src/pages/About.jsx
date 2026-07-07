import { useRef, useEffect, useState } from "react";
import { Shield, Brain, Globe, Search, Building2, Lock, Zap, Database, Server, Code } from "lucide-react";
import MagicCard from "../components/MagicCard";

const card = {
  background: "var(--surface-1)",
  border: "1px solid var(--border-default)",
  borderRadius: "var(--radius-2xl)",
  padding: "32px",
  boxShadow: "var(--shadow-sm)",
  position: "relative",
  overflow: "hidden",
};

function StaggeredFadeIn({ children, delay = 0 }) {
  const [visible, setVisible] = useState(false);
  const ref = useRef(null);

  useEffect(() => {
    const obs = new IntersectionObserver(([e]) => { if (e.isIntersecting) setVisible(true); }, { threshold: 0.1 });
    if (ref.current) obs.observe(ref.current);
    return () => obs.disconnect();
  }, []);

  return (
    <div ref={ref} style={{
      opacity: visible ? 1 : 0,
      transform: visible ? "translateY(0)" : "translateY(24px)",
      transition: `opacity 800ms ${delay}ms var(--ease-out-quart), transform 800ms ${delay}ms var(--ease-out-quart)`,
    }}>{children}</div>
  );
}

export default function About() {
  const [mounted, setMounted] = useState(false);
  useEffect(() => setMounted(true), []);

  const PIPELINE_STEPS = [
    { icon: Globe, title: "URL Analysis", desc: "Checks domain age, SSL validity, WHOIS records, redirect chains, and cross-references against known phishing databases." },
    { icon: Brain, title: "NLP Classification", desc: "A fine-tuned DistilBERT model trained on 18,000 job postings classifies text as real or fraudulent." },
    { icon: Search, title: "Duplicate Detection", desc: "Sentence-BERT encodes job descriptions and FAISS searches for semantic similarity to known fake posts." },
    { icon: Building2, title: "Company Verification", desc: "Checks MCA21 India registry, validates recruiter email domains, and verifies company website existence." },
    { icon: Lock, title: "Scam Phrase Detection", desc: "Weighted dictionary of 30+ known fraud phrases like 'pay registration fee' and 'guaranteed income'." },
    { icon: Zap, title: "Consistency Check", desc: "Validates salary claims, contact methods, and requirement-title consistency." },
  ];

  const TECH_CATEGORIES = [
    { group: "Machine Learning Core", icon: Brain, bg: "rgba(99,102,241,0.1)", color: "var(--brand-400)", items: ["DistilBERT", "Sentence-BERT", "FAISS", "scikit-learn", "spaCy", "XGBoost"] },
    { group: "Backend Infrastructure", icon: Server, bg: "rgba(34,197,94,0.1)", color: "var(--safe-500)", items: ["FastAPI", "Python 3.10", "PostgreSQL", "Redis", "Celery", "Docker"] },
    { group: "Frontend Experience", icon: Code, bg: "rgba(234,179,8,0.1)", color: "var(--suspicious-500)", items: ["React", "Vite", "TailwindCSS", "Lucide Icons", "PostCSS"] },
  ];

  return (
    <div style={{
      minHeight: "100vh", paddingBottom: "120px", background: "var(--surface-base)",
      opacity: mounted ? 1 : 0, transition: "opacity 500ms ease"
    }}>

      {/* Hero Header */}
      <div style={{
        position: "relative", padding: "100px 24px 80px", marginBottom: "40px",
        overflow: "hidden", display: "flex", flexDirection: "column", alignItems: "center"
      }}>
        <div style={{
          position: "absolute", inset: 0, pointerEvents: "none", zIndex: 0,
          background: `
            radial-gradient(ellipse 70% 80% at 30% 0%, rgba(99,102,241,0.12) 0%, transparent 70%),
            radial-gradient(ellipse 60% 80% at 70% 10%, rgba(129,140,248,0.08) 0%, transparent 60%)
          `
        }} />
        <div style={{
          position: "absolute", inset: 0, pointerEvents: "none", zIndex: 0,
          backgroundImage: "linear-gradient(rgba(255,255,255,0.02) 1px, transparent 1px), linear-gradient(90deg, rgba(255,255,255,0.02) 1px, transparent 1px)",
          backgroundSize: "60px 60px",
          maskImage: "radial-gradient(ellipse 60% 80% at 50% 0%, black 0%, transparent 80%)",
          WebkitMaskImage: "radial-gradient(ellipse 60% 80% at 50% 0%, black 0%, transparent 80%)",
        }} />

        <div style={{ position: "relative", zIndex: 1, textAlign: "center", maxWidth: "800px" }}>
          <div style={{
            display: "inline-flex", alignItems: "center", gap: "8px",
            background: "rgba(99,102,241,0.08)", border: "1px solid rgba(99,102,241,0.25)",
            borderRadius: "var(--radius-full)", padding: "6px 16px", marginBottom: "28px",
            animation: "fadeSlideDown 600ms var(--ease-out-expo) both",
          }}>
            <Shield size={14} color="var(--brand-400)" />
            <span style={{ fontSize: "var(--text-xs)", fontWeight: 600, color: "var(--brand-400)", letterSpacing: "0.08em", textTransform: "uppercase" }}>
              About TrustHire
            </span>
          </div>

          <h1 style={{
            fontFamily: "var(--font-display)", fontWeight: 700, fontSize: "clamp(2.5rem, 6vw, 4rem)",
            letterSpacing: "-0.04em", marginBottom: "24px", color: "var(--text-primary)", lineHeight: 1.1,
            animation: "fadeSlideDown 600ms 100ms var(--ease-out-expo) both",
          }}>
            Fighting Job Fraud with{" "}
            <span style={{
              background: "linear-gradient(135deg, var(--brand-400), var(--brand-600))",
              WebkitBackgroundClip: "text", WebkitTextFillColor: "transparent"
            }}>
              Artificial Intelligence
            </span>
          </h1>

          <p style={{
            fontSize: "var(--text-lg)", color: "var(--text-secondary)", maxWidth: "600px", margin: "0 auto", lineHeight: "var(--leading-relaxed)",
            animation: "fadeSlideDown 600ms 200ms var(--ease-out-expo) both",
          }}>
            TrustHire is a unified AI threat-intelligence platform designed to protect applicants from organized employment scams through sub-second real-time behavioral and structural verification.
          </p>
        </div>
      </div>

      <div style={{ maxWidth: "1100px", margin: "0 auto", padding: "0 24px", display: "flex", flexDirection: "column", gap: "40px" }}>
        
        {/* Dataset Bento Box */}
        <StaggeredFadeIn delay={0}>
          <MagicCard style={{
            ...card, display: "flex", flexDirection: "column",
            background: "linear-gradient(180deg, var(--surface-1), var(--surface-base))"
          }}>
            <div style={{ position: "absolute", top: 0, right: 0, padding: "32px", opacity: 0.1, pointerEvents: "none" }}>
              <Database size={160} />
            </div>
            
            <h2 style={{ fontSize: "var(--text-xl)", fontWeight: 700, fontFamily: "var(--font-display)", marginBottom: "16px", position: "relative", zIndex: 1 }}>Training Telemetry</h2>
            <p style={{ color: "var(--text-secondary)", lineHeight: "var(--leading-relaxed)", maxWidth: "700px", marginBottom: "32px", position: "relative", zIndex: 1 }}>
              TrustHire's foundational intelligence models are trained across massive corpus datasets including the 
              Employment Scam Aegean Dataset (EMSCAD) containing verified authentic and fraudulent enterprise job postings. 
              The system operates on continuous unsupervised reinforcement queues.
            </p>
            
            <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(200px, 1fr))", gap: "24px", position: "relative", zIndex: 1 }}>
              {[
                { value: "17,880", label: "Training Samples" },
                { value: "94.7%", label: "F1 Score Inference" },
                { value: "0.8s", label: "P95 Latency" },
                { value: "7", label: "Diagnostic Signals" },
              ].map((stat, i) => (
                <div key={i} style={{ borderLeft: "2px solid var(--brand-500)", paddingLeft: "20px" }}>
                  <div style={{ fontSize: "2.5rem", fontWeight: 700, fontFamily: "var(--font-display)", color: "var(--brand-400)", lineHeight: 1, letterSpacing: "-0.04em", marginBottom: "8px" }}>
                    {stat.value}
                  </div>
                  <div style={{ fontSize: "var(--text-sm)", color: "var(--text-tertiary)", fontWeight: 500 }}>
                    {stat.label}
                  </div>
                </div>
              ))}
            </div>
          </MagicCard>
        </StaggeredFadeIn>

        <div style={{ display: "grid", gridTemplateColumns: "1fr", gap: "40px" }}>
          
          {/* Architecture Pipeline */}
          <StaggeredFadeIn delay={100}>
            <div>
              <div style={{ marginBottom: "24px" }}>
                <h2 style={{ fontSize: "var(--text-xl)", fontWeight: 700, fontFamily: "var(--font-display)", marginBottom: "8px" }}>Verification Pipeline</h2>
                <p style={{ color: "var(--text-secondary)" }}>The sequential evaluation stages of the detection engine.</p>
              </div>

              <div style={{
                display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(300px, 1fr))", gap: "16px"
              }}>
                {PIPELINE_STEPS.map(({ icon: Icon, title, desc }, i) => (
                  <MagicCard key={i} style={{
                    ...card, padding: "24px", transition: "all var(--duration-normal)",
                    cursor: "default"
                  }}>
                    <div style={{ display: "flex", gap: "16px", alignItems: "flex-start" }}>
                      <div style={{
                        width: "40px", height: "40px", borderRadius: "10px", background: "rgba(255,255,255,0.03)",
                        border: "1px solid var(--border-default)", display: "flex", alignItems: "center", justifyContent: "center", flexShrink: 0
                      }}>
                        <Icon size={18} color="var(--brand-400)" />
                      </div>
                      <div>
                        <h3 style={{ fontSize: "var(--text-base)", fontWeight: 600, color: "var(--text-primary)", marginBottom: "6px" }}>{title}</h3>
                        <p style={{ fontSize: "var(--text-sm)", color: "var(--text-tertiary)", lineHeight: 1.5 }}>{desc}</p>
                      </div>
                    </div>
                  </MagicCard>
                ))}
              </div>
            </div>
          </StaggeredFadeIn>

          {/* Tech Stack Bento */}
          <StaggeredFadeIn delay={200}>
            <div>
              <div style={{ marginBottom: "24px" }}>
                <h2 style={{ fontSize: "var(--text-xl)", fontWeight: 700, fontFamily: "var(--font-display)", marginBottom: "8px" }}>Platform Stack</h2>
                <p style={{ color: "var(--text-secondary)" }}>The open architecture powering the inference engine.</p>
              </div>

              <div style={{
                display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(320px, 1fr))", gap: "20px"
              }}>
                {TECH_CATEGORIES.map(({ group, icon: Icon, bg, color, items }, i) => (
                  <MagicCard key={i} style={{ ...card, padding: "28px", display: "flex", flexDirection: "column" }}>
                    <div style={{ display: "flex", alignItems: "center", gap: "12px", marginBottom: "24px" }}>
                      <div style={{
                        width: "36px", height: "36px", borderRadius: "8px", background: bg,
                        display: "flex", alignItems: "center", justifyContent: "center"
                      }}>
                        <Icon size={18} color={color} />
                      </div>
                      <h3 style={{ fontSize: "var(--text-base)", fontWeight: 600, color: "var(--text-primary)" }}>{group}</h3>
                    </div>
                    
                    <div style={{ display: "flex", flexWrap: "wrap", gap: "8px" }}>
                      {items.map(tech => (
                        <span key={tech} style={{
                          padding: "6px 12px", background: "rgba(255,255,255,0.03)",
                          border: "1px solid rgba(255,255,255,0.06)", borderRadius: "var(--radius-full)",
                          fontSize: "var(--text-sm)", color: "var(--text-secondary)", fontFamily: "var(--font-mono)",
                          position: "relative", zIndex: 1
                        }}>
                          {tech}
                        </span>
                      ))}
                    </div>
                  </MagicCard>
                ))}
              </div>
            </div>
          </StaggeredFadeIn>
        </div>
      </div>
      <style>{`
        @keyframes fadeSlideDown {
          from { opacity: 0; transform: translateY(-12px); }
          to   { opacity: 1; transform: translateY(0); }
        }
      `}</style>
    </div>
  );
}
