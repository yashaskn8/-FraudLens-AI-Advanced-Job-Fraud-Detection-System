import { Bot, Sparkles, CheckCircle } from "lucide-react";

export default function ExplainerPanel({ explanation, modelTrained }) {
  const paragraphs = explanation?.split("\n\n").filter(Boolean) || [];

  return (
    <div style={{
      background: "var(--surface-1)",
      border: "1px solid var(--border-default)",
      borderRadius: "var(--radius-2xl)",
      overflow: "hidden",
    }}>
      {/* Header */}
      <div style={{
        padding: "18px 24px",
        borderBottom: "1px solid var(--border-subtle)",
        display: "flex", alignItems: "center", gap: "12px",
        background: "rgba(99,102,241,0.03)",
      }}>
        <div style={{
          width: "32px", height: "32px",
          background: "rgba(99,102,241,0.10)",
          border: "1px solid rgba(99,102,241,0.20)",
          borderRadius: "var(--radius-md)",
          display: "flex", alignItems: "center", justifyContent: "center",
        }}>
          <Bot size={15} color="var(--brand-400)" />
        </div>
        <div>
          <div style={{
            fontSize: "var(--text-sm)", fontWeight: 600,
            color: "var(--text-primary)",
          }}>
            AI Analysis Explanation
          </div>
          <div style={{
            fontSize: "var(--text-xs)", color: "var(--text-tertiary)",
            display: "flex", alignItems: "center", gap: "4px",
          }}>
            {modelTrained
              ? <><CheckCircle size={10} color="var(--safe-500)" /> Powered by fine-tuned DistilBERT</>
              : <><Sparkles size={10} color="var(--brand-400)" /> Powered by Mistral-7B</>
            }
          </div>
        </div>
      </div>

      {/* Content */}
      <div style={{ padding: "24px" }}>
        {paragraphs.map((para, i) => (
          <p key={i} style={{
            fontSize: "var(--text-sm)",
            color: i === 0 ? "var(--text-primary)" : "var(--text-secondary)",
            lineHeight: "var(--leading-relaxed)",
            marginBottom: i < paragraphs.length - 1 ? "16px" : 0,
            fontWeight: i === 0 ? 500 : 400,
            animation: `fadeIn 300ms ${i * 80}ms var(--ease-out-quart) both`,
          }}>{para}</p>
        ))}
        <style>{`
          @keyframes fadeIn {
            from { opacity:0; transform:translateY(4px); }
            to   { opacity:1; transform:translateY(0); }
          }
        `}</style>
      </div>
    </div>
  );
}
