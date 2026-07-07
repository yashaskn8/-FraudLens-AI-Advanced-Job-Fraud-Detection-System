import { useEffect, useState } from "react";
import { Globe, Brain, Search, Building2, Cpu, CheckCircle } from "lucide-react";

const STEPS = [
  { icon: Globe,     label: "Fetching URL metadata",         sub: "WHOIS · SSL · DNS · Redirects"  },
  { icon: Search,    label: "Checking threat databases",      sub: "Safe Browsing · VirusTotal"     },
  { icon: Brain,     label: "Running AI fraud classifier",    sub: "DistilBERT · Scam phrases"      },
  { icon: Building2, label: "Verifying company registration", sub: "MCA21 India · Email domain"     },
  { icon: Cpu,       label: "Computing trust score",          sub: "Weighted signal fusion"         },
];

const RAW_LOGS = [
  "INITIALIZING NEURAL TENSORS [OK]",
  "LOADING TOKENIZER... 30522 TOKENS",
  "ALLOCATING VRAM FOR INFERENCE...",
  "FETCHING DOMAIN SSL CERTIFICATES",
  "DECODING BASE64 THREAT SIGNATURES",
  "COMPUTING COSINE SIMILARITY (FAISS)",
  "QUERYING MCA21 REGISTRY CACHE...",
  "EXTRACTING NAMED ENTITIES (SPACY)",
  "EVALUATING XGBOOST ENSEMBLE TREE",
  "FUSING MULTI-MODAL VECTORS...",
];

export default function LoadingState() {
  const [step, setStep] = useState(0);
  const [progress, setProgress] = useState(0);
  const [logs, setLogs] = useState([]);

  useEffect(() => {
    // Step progression
    const stepInterval = setInterval(() => {
      setStep(s => Math.min(s + 1, STEPS.length));
    }, 1600);
    
    // Smooth progress bar
    const progressInterval = setInterval(() => {
      setProgress(p => Math.min(p + 0.8, 98));
    }, 120);

    // Neural terminal logs stream
    let logIndex = 0;
    const logInterval = setInterval(() => {
      if (logIndex < RAW_LOGS.length) {
        setLogs(prev => [...prev.slice(-4), RAW_LOGS[logIndex]]);
        logIndex++;
      } else {
        logIndex = 0; // loop back to simulate ongoing process
      }
    }, 800);

    return () => { clearInterval(stepInterval); clearInterval(progressInterval); clearInterval(logInterval); };
  }, []);

  return (
    <div style={{
      minHeight: "100vh", background: "var(--surface-base)",
      display: "flex", flexDirection: "column",
      alignItems: "center", justifyContent: "center",
      padding: "40px 24px", position: "relative", overflow: "hidden"
    }}>
      {/* Background Neural Data Stream */}
      <div style={{
        position: "absolute", inset: 0, opacity: 0.04, pointerEvents: "none", zIndex: 0,
        fontFamily: "var(--font-mono)", fontSize: "10px", color: "var(--brand-400)",
        padding: "40px", overflow: "hidden", display: "flex", flexDirection: "column", gap: "8px"
      }}>
        {Array.from({ length: 50 }).map((_, i) => (
          <div key={i} style={{ whiteSpace: "nowrap" }}>
            {Math.random().toString(36).substring(2, 15).toUpperCase()} 0x{(Math.random()*1000000).toString(16).toUpperCase()}
            {" "}{Math.random().toString(36).substring(2, 15).toUpperCase()} {(Math.random() * 100).toFixed(4)}
          </div>
        ))}
      </div>

      <div style={{ position: "relative", zIndex: 1, display: "flex", flexDirection: "column", alignItems: "center" }}>
        
        {/* Advanced Rotating AI Core */}
        <div style={{ position: "relative", marginBottom: "50px", width: "120px", height: "120px", display: "flex", alignItems: "center", justifyContent: "center" }}>
          {/* Outer glowing orbital */}
          <div style={{
            position: "absolute", inset: 0, borderRadius: "50%",
            border: "1px dashed rgba(99,102,241,0.3)",
            animation: "spin 12s linear infinite"
          }} />
          
          {/* Middle solid orbital */}
          <div style={{
            position: "absolute", inset: "12px", borderRadius: "50%",
            border: "2px solid rgba(99,102,241,0.1)", borderTopColor: "var(--brand-400)",
            borderBottomColor: "var(--brand-600)",
            animation: "spin 3s cubic-bezier(0.68, -0.55, 0.265, 1.55) infinite"
          }} />

          {/* Inner core */}
          <div style={{
            width: "60px", height: "60px", borderRadius: "50%",
            background: "radial-gradient(circle at 30% 30%, var(--brand-400), var(--brand-700))",
            boxShadow: "0 0 40px rgba(99,102,241,0.6)",
            display: "flex", alignItems: "center", justifyContent: "center",
            animation: "pulseCore 2s ease-in-out infinite alternate"
          }}>
            <Brain size={28} color="#fff" />
          </div>
        </div>

        <h2 style={{
          fontFamily: "var(--font-display)", fontWeight: 700,
          fontSize: "var(--text-3xl)", letterSpacing: "-0.04em",
          color: "var(--text-primary)", marginBottom: "12px",
          background: "linear-gradient(135deg, #fff, var(--text-tertiary))",
          WebkitBackgroundClip: "text", WebkitTextFillColor: "transparent"
        }}>
          Threat Analysis Active
        </h2>

        {/* Neural Terminal Output */}
        <div style={{ 
          height: "20px", marginBottom: "36px", fontFamily: "var(--font-mono)", 
          fontSize: "11px", color: "var(--brand-400)", letterSpacing: "0.1em",
          opacity: 0.8, textTransform: "uppercase"
        }}>
          &gt; {logs[logs.length - 1] || "ESTABLISHING SECURE UPLINK..."}
          <span className="terminal-cursor" style={{ marginLeft: "6px" }} />
        </div>

        {/* Micro-Progress Bar */}
        <div style={{
          width: "380px", height: "4px", background: "var(--surface-2)",
          borderRadius: "var(--radius-full)", overflow: "hidden", marginBottom: "40px",
          position: "relative"
        }}>
          <div style={{
            position: "absolute", top: 0, left: 0, bottom: 0,
            width: `${progress}%`, background: "linear-gradient(90deg, var(--brand-600), var(--brand-300))",
            borderRadius: "var(--radius-full)", transition: "width 120ms ease-out",
            boxShadow: "0 0 12px var(--brand-500)"
          }} />
        </div>

        {/* Clean Step List (No Scratch, No Click Jerk) */}
        <div style={{ display: "flex", flexDirection: "column", gap: "16px", width: "400px" }}>
          {STEPS.map(({ icon: Icon, label, sub }, i) => {
            const done = i < step;
            const active = i === step;
            const pending = i > step;

            return (
              <div key={i} style={{
                display: "flex", alignItems: "center", gap: "16px",
                opacity: pending ? 0.3 : 1, transition: "opacity 600ms ease"
              }}>
                <div style={{
                  width: "28px", height: "28px", flexShrink: 0,
                  display: "flex", alignItems: "center", justifyContent: "center",
                  transition: "color 400ms ease",
                  color: done ? "var(--safe-500)" : active ? "var(--brand-400)" : "var(--text-disabled)"
                }}>
                  {done ? (
                    <div style={{ animation: "popIn 400ms cubic-bezier(0.175, 0.885, 0.32, 1.275) both" }}>
                      <CheckCircle size={22} color="var(--safe-500)" style={{ filter: "drop-shadow(0 0 8px rgba(34,197,94,0.4))" }} />
                    </div>
                  ) : (
                    <Icon size={20} style={{ animation: active ? "pulseOpacity 1.5s infinite" : "none" }} />
                  )}
                </div>
                <div>
                  <div style={{
                    fontSize: "var(--text-base)", fontWeight: 600, letterSpacing: "-0.01em",
                    color: done ? "var(--text-primary)" : active ? "var(--text-primary)" : "var(--text-tertiary)",
                    transition: "color 400ms ease"
                  }}>
                    {label}
                  </div>
                  <div style={{
                    fontSize: "13px", color: "var(--text-disabled)",
                    marginTop: "2px", transition: "color 400ms ease"
                  }}>
                    {sub}
                  </div>
                </div>
              </div>
            );
          })}
        </div>
      </div>

      <style>{`
        @keyframes spin { to { transform: rotate(360deg); } }
        @keyframes pulseCore { 0% { transform: scale(0.95); box-shadow: 0 0 20px var(--brand-600); } 100% { transform: scale(1.05); box-shadow: 0 0 50px var(--brand-400); } }
        @keyframes pulseOpacity { 0%, 100% { opacity: 1; } 50% { opacity: 0.5; } }
        @keyframes popIn { 0% { transform: scale(0.5); opacity: 0; } 100% { transform: scale(1); opacity: 1; } }
      `}</style>
    </div>
  );
}
