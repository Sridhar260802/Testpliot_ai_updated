// src/pages/Pricing.jsx
import { useNavigate } from "react-router-dom";
import Navbar from "../components/Navbar";
import { getStoredUser } from "../services/authService";

const WEB_PLANS = [
  {
    id: "basic",
    name: "Basic",
    price: 499,
    tagline: "Essential checks to get started.",
    features: [
      "Basic SEO testing",
      "Basic accessibility testing",
      "Website availability check",
      "Basic performance check",
      "Basic content & image validation",
      "Basic PDF report",
    ],
  },
  {
    id: "standard",
    name: "Standard",
    price: 999,
    tagline: "Full functional testing, automated.",
    features: [
      "Full functional testing suite",
      "Advanced SEO & accessibility",
      "Browser compatibility checks",
      "AI-generated recommendations",
      "Detailed PDF report",
    ],
    highlighted: true,
  },
  {
    id: "premium",
    name: "Premium",
    price: 1999,
    tagline: "The complete website audit.",
    features: [
      "Full security audit",
      "All Standard-level testing capabilities",
      "Content, UX & CRO audits",
      "Technical audit (Core Web Vitals, etc.)",
      "AI-generated recommendations",
      "Combined full audit PDF report",
    ],
  },
];

export default function Pricing() {
  const navigate = useNavigate();
  const user = getStoredUser();
  const currentPlan = user?.plan || null;
  const plans = WEB_PLANS;

  return (
    <div className="min-h-screen bg-[#F7F1E1]">
      <Navbar />

      <div className="mx-auto max-w-6xl px-4 py-12 sm:px-6">
        <div className="text-center animate-[fadeIn_0.5s_ease-out_both]">
          <p className="text-xs font-semibold uppercase tracking-[0.25em] text-[#0b3327]/50">Pricing</p>
          <h1 className="mt-2 font-serif text-3xl font-medium text-[#0b3327] sm:text-4xl">Choose your plan</h1>
          <p className="mx-auto mt-3 max-w-md text-sm text-[#0b3327]/60">
            Every plan includes a full PDF report. Upgrade any time — Premium unlocks everything.
          </p>
        </div>

        <p className="mt-3 text-center text-xs text-[#0b3327]/45 animate-[fadeIn_0.5s_ease-out_0.15s_both]">
          Automated audits for your website — SEO, accessibility, performance & security.
        </p>

        {/* ------------------------------------------------------------ */}
        {/* Plan cards                                                    */}
        {/* ------------------------------------------------------------ */}
        <div className="mt-10 grid grid-cols-1 gap-6 lg:grid-cols-3 animate-[fadeIn_0.35s_ease-out_both]">
          {plans.map((plan, idx) => (
            <div
              key={plan.id}
              style={{ animation: `cardRise 0.5s cubic-bezier(0.22,1,0.36,1) ${idx * 0.08}s both` }}
              className={`group relative rounded-3xl p-8 shadow-sm transition-all duration-300 hover:-translate-y-1.5 hover:shadow-xl border border-transparent ${
                plan.highlighted
                  ? "bg-gradient-to-br from-[#0f4436] via-[#0b3327] to-[#061f17] text-white shadow-xl lg:-translate-y-3 lg:hover:-translate-y-4"
                  : "bg-white text-[#0b3327] hover:border-[#d4af37]/40"
              }`}
            >
              {plan.highlighted && (
                <span className="absolute -top-3 left-1/2 -translate-x-1/2 rounded-full bg-[#d4af37] px-3 py-1 text-[10px] font-bold uppercase tracking-wide text-[#0b3327] animate-[popIn_0.4s_cubic-bezier(0.22,1,0.36,1)_0.3s_both]">
                  Most popular
                </span>
              )}

              <div className="flex items-center gap-2">
                <h2 className={`text-lg font-semibold ${plan.highlighted ? "text-white" : "text-[#0b3327]"}`}>{plan.name}</h2>
                <span
                  className={`rounded-full px-2 py-0.5 text-[9px] font-bold uppercase tracking-wide ${
                    plan.highlighted ? "bg-white/15 text-white/70" : "bg-[#0b3327]/8 text-[#0b3327]/50"
                  }`}
                >
                  Web
                </span>
              </div>
              <p className={`mt-1 text-xs ${plan.highlighted ? "text-white/60" : "text-[#0b3327]/50"}`}>{plan.tagline}</p>

              <div className="mt-5 flex items-baseline gap-1">
                <span className={`text-3xl font-bold transition-transform duration-300 group-hover:scale-105 ${plan.highlighted ? "text-[#d4af37]" : "text-[#0b3327]"}`}>
                  ₹{plan.price}
                </span>
                <span className={`text-xs ${plan.highlighted ? "text-white/50" : "text-[#0b3327]/40"}`}>/ report</span>
              </div>

              <ul className="mt-6 space-y-3">
                {plan.features.map((feature, fIdx) => (
                  <li
                    key={feature}
                    style={{ animation: `fadeIn 0.4s ease-out ${idx * 0.08 + fIdx * 0.04 + 0.15}s both` }}
                    className="group/item flex items-start gap-2 text-sm transition-colors duration-200 hover:translate-x-0.5"
                  >
                    <svg
                      width="16"
                      height="16"
                      viewBox="0 0 24 24"
                      fill="none"
                      aria-hidden="true"
                      className="mt-0.5 shrink-0 transition-transform duration-200 group-hover/item:scale-125"
                    >
                      <path
                        d="M5 13l4 4L19 7"
                        stroke={plan.highlighted ? "#d4af37" : "#0b3327"}
                        strokeWidth="2.4"
                        strokeLinecap="round"
                        strokeLinejoin="round"
                      />
                    </svg>
                    <span
                      className={`transition-colors duration-200 ${
                        plan.highlighted
                          ? "text-white/85 group-hover/item:text-white"
                          : "text-[#0b3327]/80 group-hover/item:text-[#0b3327]"
                      }`}
                    >
                      {feature}
                    </span>
                  </li>
                ))}
              </ul>

              <button
                type="button"
                onClick={() => navigate(`/checkout?plan=${plan.id}`)}
                disabled={currentPlan === plan.id}
                className={`mt-8 w-full rounded-full py-3 text-sm font-semibold transition-all duration-300 hover:scale-[1.02] active:scale-[0.98] disabled:cursor-not-allowed disabled:opacity-50 disabled:hover:scale-100 ${
                  plan.highlighted
                    ? "bg-[#d4af37] text-[#0b3327] hover:brightness-95 hover:shadow-[0_0_0_6px_rgba(212,175,55,0.18)]"
                    : "bg-[#0b3327] text-white hover:bg-black hover:shadow-[0_0_0_6px_rgba(11,51,39,0.1)]"
                }`}
              >
                {currentPlan === plan.id ? "Current plan" : `Choose ${plan.name}`}
              </button>
            </div>
          ))}
        </div>

        <p className="mt-6 text-center text-xs text-[#0b3327]/40 animate-[fadeIn_0.5s_ease-out_0.3s_both]">
          Every tier covers unlimited website audits at that plan's depth.
        </p>
      </div>

      <style>{`
        @keyframes fadeIn {
          from { opacity: 0; transform: translateY(8px); }
          to { opacity: 1; transform: translateY(0); }
        }
        @keyframes cardRise {
          from { opacity: 0; transform: translateY(20px) scale(0.98); }
          to { opacity: 1; transform: translateY(0) scale(1); }
        }
        @keyframes popIn {
          0% { opacity: 0; transform: translateX(-50%) scale(0.5); }
          70% { opacity: 1; transform: translateX(-50%) scale(1.08); }
          100% { opacity: 1; transform: translateX(-50%) scale(1); }
        }
        @media (prefers-reduced-motion: reduce) {
          *, *::before, *::after {
            animation-duration: 0.01ms !important;
            animation-iteration-count: 1 !important;
            transition-duration: 0.01ms !important;
          }
        }
      `}</style>
    </div>
  );
}