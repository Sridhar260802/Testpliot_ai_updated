// src/pages/WebsiteTest.jsx
import { useEffect, useRef, useState } from "react";
import { useNavigate } from "react-router-dom";
import Navbar from "../components/Navbar";
import { getStoredUser, getToken } from "../services/authService";

const API_BASE_URL = import.meta.env?.VITE_API_BASE_URL || "http://localhost:8000";

/* Same token system as Dashboard.jsx — ink / paper / flag / pass */
function useReportFonts() {
  useEffect(() => {
    if (document.getElementById("report-fonts")) return;
    const link = document.createElement("link");
    link.id = "report-fonts";
    link.rel = "stylesheet";
    link.href =
      "https://fonts.googleapis.com/css2?family=Space+Grotesk:wght@500;600;700&family=IBM+Plex+Mono:wght@400;500;600&display=swap";
    document.head.appendChild(link);
  }, []);
}

const PLAN_COPY = {
  basic: {
    label: "Basic",
    headline: "Give your site a quick health check",
    sub: "We'll scan your page for SEO, performance and content issues, then file a clean PDF report you can act on today.",
  },
  standard: {
    label: "Standard",
    headline: "Run a deeper diagnostic on your site",
    sub: "Functional checks, advanced SEO & accessibility, plus AI-written recommendations — packaged into one downloadable report.",
  },
  premium: {
    label: "Premium",
    headline: "Put your site through the full audit",
    sub: "Functional tests, a full security sweep, and a content & UX review — everything you need before you ship changes with confidence.",
  },
};

// Real generation time per tier — this drives the progress curve, not a fake timer.
// Basic ~3 min, Standard ~4 min, Premium ~5 min.
const PLAN_ESTIMATE_SECONDS = {
  basic: 180,
  standard: 240,
  premium: 300,
};

export default function WebsiteTest() {
  useReportFonts();

  const user = getStoredUser();
  const rawPlan = user?.plan || null;
  // Only treat it as an active plan if it actually matches a known tier —
  // guards against "", "null" (string), or any unexpected value crashing the page.
  const purchasedPlan = rawPlan && PLAN_COPY[rawPlan] ? rawPlan : null;

  // TEMP: while Razorpay isn't wired up, a user may have no purchased plan
  // yet (purchasedPlan === null — e.g. fresh Google sign-in). Instead of
  // hard-blocking them, let them pick a plan locally just to run a test.
  // This choice is NOT saved to their account/backend - it's only used to
  // pick which /plans/<x>/report endpoint this page calls, and the backend
  // is currently open to any logged-in user for any plan (see
  // TEMP_ALLOW_ALL_PLANS_NO_PAYMENT in app/core/plans.py).
  const [tempPlan, setTempPlan] = useState(null);
  const plan = purchasedPlan || tempPlan;
  const copy = plan ? PLAN_COPY[plan] : null;

  const [url, setUrl] = useState("");
  const [status, setStatus] = useState("idle"); // idle | running | done | error
  const [errorMessage, setErrorMessage] = useState("");
  const [reportBlobUrl, setReportBlobUrl] = useState(null);

  async function handleSubmit(e) {
    e.preventDefault();
    if (!url.trim() || !plan) return;

    setStatus("running");
    setErrorMessage("");
    setReportBlobUrl(null);

    try {
      const response = await fetch(`${API_BASE_URL}/plans/${plan}/report`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          Authorization: `Bearer ${getToken()}`,
        },
        body: JSON.stringify({ url: url.trim() }),
      });

      if (!response.ok) {
        let message = "Could not generate the report. Please try again.";
        try {
          const data = await response.json();
          message = data.detail || message;
        } catch {
          /* non-JSON error body */
        }
        throw new Error(message);
      }

      const blob = await response.blob();
      setReportBlobUrl(URL.createObjectURL(blob));
      setStatus("done");
    } catch (err) {
      setStatus("error");
      setErrorMessage(err.message || "Something went wrong running this test.");
    }
  }

  function handleRetry() {
    setStatus("idle");
    setErrorMessage("");
  }

  const [downloadPhase, setDownloadPhase] = useState("idle"); // idle | downloading | done

  function handleDownloadClick() {
    // Purely a visual beat — the actual download happens via the <a href download>.
    if (downloadPhase !== "idle") return;
    setDownloadPhase("downloading");

    setTimeout(() => setDownloadPhase("done"), 1300);
    setTimeout(() => setDownloadPhase("idle"), 3000);
  }

  return (
    <div className="relative min-h-screen overflow-hidden bg-[#F1ECDF] text-[#14181B]">
      {/* premium ambient background — slow gradient blobs + faint scattered icons,
          fills the dead space around the form instead of flat paper color */}
      <div aria-hidden="true" className="pointer-events-none fixed inset-0 -z-0 overflow-hidden">
        <div className="absolute -left-24 top-24 h-96 w-96 rounded-full bg-[#E4572E]/[0.07] blur-[90px] animate-[bgDriftA_14s_ease-in-out_infinite]" />
        <div className="absolute -right-32 top-1/2 h-[28rem] w-[28rem] rounded-full bg-[#1F5C45]/[0.06] blur-[100px] animate-[bgDriftB_17s_ease-in-out_infinite]" />
        <div className="absolute bottom-0 left-1/3 h-72 w-72 rounded-full bg-[#14181B]/[0.04] blur-[80px] animate-[bgDriftA_20s_ease-in-out_infinite]" />
        <FloatingIcons />
      </div>

      <div className="relative z-10">
        <Navbar />
      </div>

      {!plan ? (
        <div className="relative z-10">
          <NoPlanState onSelectPlan={setTempPlan} />
        </div>
      ) : (
        <div className="relative z-10 mx-auto max-w-xl px-4 py-14 sm:px-6">
          {/* Plan badge */}
          <div className="flex items-center gap-2 animate-[fadeSlideUp_0.5s_cubic-bezier(0.22,1,0.36,1)_both]">
            <span
              className="inline-flex items-center gap-2 rounded-full border border-[#14181B]/15 bg-white px-3 py-1 text-[10px] font-semibold uppercase tracking-[0.2em] text-[#14181B]/60"
              style={{ fontFamily: "'IBM Plex Mono', monospace" }}
            >
              <span className="h-1.5 w-1.5 rounded-full bg-[#1F5C45]" />
              {copy.label} plan
            </span>
          </div>

          {/* Heading */}
          <h1
            className="mt-4 text-3xl font-semibold leading-tight tracking-tight sm:text-[2.2rem] animate-[fadeSlideUp_0.5s_cubic-bezier(0.22,1,0.36,1)_0.06s_both]"
            style={{ fontFamily: "'Space Grotesk', sans-serif" }}
          >
            {copy.headline}
          </h1>
          <p className="mt-3 max-w-md text-sm leading-relaxed text-[#14181B]/60 animate-[fadeSlideUp_0.5s_cubic-bezier(0.22,1,0.36,1)_0.12s_both]">
            {copy.sub}
          </p>

          {/* URL form */}
          <form onSubmit={handleSubmit} className="mt-8 animate-[fadeSlideUp_0.5s_cubic-bezier(0.22,1,0.36,1)_0.18s_both]">
            <label
              htmlFor="site-url"
              className="mb-1.5 block text-[10px] font-semibold uppercase tracking-[0.2em] text-[#14181B]/45"
              style={{ fontFamily: "'IBM Plex Mono', monospace" }}
            >
              Website URL
            </label>
            <div
              className={`flex items-center gap-2 rounded-sm border bg-white px-4 py-3 transition-all duration-300 ${
                status === "running"
                  ? "border-[#1F5C45]/50 shadow-[0_0_0_3px_rgba(31,92,69,0.12)]"
                  : "border-[#14181B]/15 hover:border-[#14181B]/30 focus-within:border-[#14181B] focus-within:shadow-[0_0_0_3px_rgba(20,24,27,0.06)]"
              }`}
            >
              <svg width="16" height="16" viewBox="0 0 24 24" fill="none" className="shrink-0 text-[#14181B]/30">
                <path
                  d="M12 2a10 10 0 100 20 10 10 0 000-20zM2 12h20M12 2c2.5 2.7 4 6.2 4 10s-1.5 7.3-4 10c-2.5-2.7-4-6.2-4-10s1.5-7.3 4-10z"
                  stroke="currentColor"
                  strokeWidth="1.6"
                />
              </svg>
              <input
                id="site-url"
                type="url"
                required
                placeholder="https://example.com"
                value={url}
                onChange={(e) => setUrl(e.target.value)}
                disabled={status === "running"}
                className="w-full border-0 bg-transparent p-0 text-sm text-[#14181B] outline-none placeholder:text-[#14181B]/35 disabled:opacity-50"
                style={{ fontFamily: "'IBM Plex Mono', monospace" }}
              />
              <button
                type="submit"
                disabled={status === "running"}
                className="group shrink-0 rounded-sm bg-[#14181B] px-5 py-2 text-sm font-semibold text-white transition-all duration-200 hover:bg-[#E4572E] disabled:cursor-not-allowed disabled:opacity-60 disabled:hover:bg-[#14181B] active:scale-[0.97]"
              >
                <span className="flex items-center gap-1.5">
                  {status === "running" ? "Running…" : "Run test"}
                  {status !== "running" && (
                    <svg width="13" height="13" viewBox="0 0 24 24" fill="none" className="transition-transform duration-200 group-hover:translate-x-0.5">
                      <path d="M5 12h14m0 0l-6-6m6 6l-6 6" stroke="white" strokeWidth="2.2" strokeLinecap="round" strokeLinejoin="round" />
                    </svg>
                  )}
                </span>
              </button>
            </div>
            <p className="mt-2 text-xs text-[#14181B]/40">
              Full audits run for real — plan for a few minutes. We check the page live, no crawling your whole site.
            </p>
          </form>

          <div className="mt-6 grid" style={{ gridTemplateAreas: "stack" }}>
            {status === "idle" && (
              <div style={{ gridArea: "stack" }} className="animate-[fadeIn_0.4s_ease-out_0.24s_both]">
                <IdleHint plan={plan} />
              </div>
            )}

            {status === "running" && (
              <div style={{ gridArea: "stack" }}>
                <RunningState plan={plan} />
              </div>
            )}

            {status === "error" && (
              <div
                role="alert"
                style={{ gridArea: "stack" }}
                className="animate-[shakeIn_0.4s_cubic-bezier(0.22,1,0.36,1)_both] rounded-sm border border-[#E4572E]/35 bg-white px-5 py-4 text-sm"
              >
                <div className="flex items-start gap-3">
                  <span
                    className="mt-0.5 flex h-7 w-7 shrink-0 items-center justify-center rounded-full border-2 border-[#E4572E] text-[13px] font-bold text-[#E4572E]"
                    style={{ fontFamily: "'IBM Plex Mono', monospace" }}
                  >
                    !
                  </span>
                  <div className="flex-1">
                    <p className="font-semibold text-[#14181B]">We couldn't finish this test</p>
                    <p className="mt-0.5 text-[#14181B]/60">{errorMessage}</p>
                    <button
                      type="button"
                      onClick={handleRetry}
                      className="mt-3 inline-flex items-center gap-1.5 rounded-sm border border-[#14181B]/20 bg-white px-3.5 py-1.5 text-xs font-semibold text-[#14181B] transition-all duration-200 hover:border-[#E4572E] hover:text-[#E4572E] active:scale-[0.97]"
                    >
                      Try again
                    </button>
                  </div>
                </div>
              </div>
            )}

            {status === "done" && reportBlobUrl && (
              <div
                style={{ gridArea: "stack" }}
                className="relative animate-[cardIn_0.5s_cubic-bezier(0.22,1,0.36,1)_both] overflow-hidden rounded-sm border border-[#14181B]/12 bg-white p-6 text-center"
              >
                {/* perforation edge, echoing the pricing tickets on the dashboard */}
                <div className="pointer-events-none absolute -top-[7px] left-0 right-0 flex justify-between px-2" aria-hidden="true">
                  {Array.from({ length: 12 }).map((_, i) => (
                    <span key={i} className="h-3.5 w-3.5 rounded-full bg-[#F1ECDF]" />
                  ))}
                </div>

                <div
                  className="mx-auto mb-3 mt-2 flex h-14 w-14 items-center justify-center rounded-full border-2 border-[#1F5C45] animate-[stampPop_0.45s_cubic-bezier(0.22,1,0.36,1)_0.1s_both]"
                >
                  <svg width="24" height="24" viewBox="0 0 24 24" fill="none" aria-hidden="true">
                    <path
                      d="M5 13l4 4L19 7"
                      stroke="#1F5C45"
                      strokeWidth="2.6"
                      strokeLinecap="round"
                      strokeLinejoin="round"
                      style={{ strokeDasharray: 24, strokeDashoffset: 24, animation: "drawCheck 0.4s ease-out 0.32s forwards" }}
                    />
                  </svg>
                </div>

                <p
                  className="text-[11px] font-semibold uppercase tracking-[0.2em] text-[#1F5C45] animate-[fadeIn_0.35s_ease-out_0.26s_both]"
                  style={{ fontFamily: "'IBM Plex Mono', monospace" }}
                >
                  Report filed
                </p>
                <h2
                  className="mt-1 text-lg font-semibold text-[#14181B] animate-[fadeIn_0.35s_ease-out_0.3s_both]"
                  style={{ fontFamily: "'Space Grotesk', sans-serif" }}
                >
                  Your report is ready
                </h2>
                <p
                  className="mt-1 truncate text-xs text-[#14181B]/45 animate-[fadeIn_0.35s_ease-out_0.34s_both]"
                  style={{ fontFamily: "'IBM Plex Mono', monospace" }}
                >
                  {url}
                </p>

                <div className="mt-5 inline-block animate-[fadeIn_0.35s_ease-out_0.38s_both]">
                  <a
                    href={reportBlobUrl}
                    download={`TestPilot_${plan}_report.pdf`}
                    onClick={handleDownloadClick}
                    aria-disabled={downloadPhase !== "idle"}
                    className={`relative inline-flex items-center gap-2 overflow-hidden rounded-sm px-6 py-3 text-sm font-semibold text-white transition-all duration-200 ${
                      downloadPhase === "idle" ? "hover:bg-[#F16A40] active:scale-[0.97]" : ""
                    } ${downloadPhase === "done" ? "bg-[#1F5C45]" : "bg-[#E4572E]"}`}
                  >
                    {downloadPhase === "downloading" && (
                      <span className="absolute inset-y-0 left-0 bg-white/15" style={{ animation: "fillBar 1.2s ease-out forwards" }} />
                    )}

                    <span className="relative flex items-center gap-2">
                      {downloadPhase === "downloading" && (
                        <>
                          <span className="h-4 w-4 animate-spin rounded-full border-2 border-white/30 border-t-white" />
                          Preparing…
                        </>
                      )}
                      {downloadPhase === "done" && (
                        <>
                          <svg width="16" height="16" viewBox="0 0 24 24" fill="none" aria-hidden="true">
                            <path d="M5 13l4 4L19 7" stroke="white" strokeWidth="2.6" strokeLinecap="round" strokeLinejoin="round" />
                          </svg>
                          Downloaded
                        </>
                      )}
                      {downloadPhase === "idle" && (
                        <>
                          <svg width="16" height="16" viewBox="0 0 24 24" fill="none" aria-hidden="true">
                            <path d="M12 3v12m0 0l-4-4m4 4l4-4M4 21h16" stroke="white" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" />
                          </svg>
                          Download PDF report
                        </>
                      )}
                    </span>
                  </a>
                </div>

                <button
                  type="button"
                  onClick={() => {
                    setStatus("idle");
                    setUrl("");
                    setReportBlobUrl(null);
                  }}
                  className="mt-4 block w-full text-xs font-semibold text-[#14181B]/40 transition-colors duration-200 hover:text-[#14181B]"
                >
                  Test another URL
                </button>
              </div>
            )}
          </div>

          <style>{`
            @keyframes fadeIn {
              from { opacity: 0; transform: translateY(8px); }
              to { opacity: 1; transform: translateY(0); }
            }
            @keyframes fadeSlideUp {
              from { opacity: 0; transform: translateY(12px); }
              to { opacity: 1; transform: translateY(0); }
            }
            @keyframes cardIn {
              from { opacity: 0; transform: translateY(12px) scale(0.98); }
              to { opacity: 1; transform: translateY(0) scale(1); }
            }
            @keyframes stampPop {
              0% { opacity: 0; transform: scale(0.5) rotate(-8deg); }
              70% { opacity: 1; transform: scale(1.06) rotate(0deg); }
              100% { opacity: 1; transform: scale(1) rotate(0deg); }
            }
            @keyframes drawCheck {
              to { stroke-dashoffset: 0; }
            }
            @keyframes fillBar {
              from { width: 0%; }
              to { width: 100%; }
            }
            @keyframes shakeIn {
              0% { opacity: 0; transform: translateX(0); }
              30% { opacity: 1; transform: translateX(-6px); }
              50% { transform: translateX(5px); }
              70% { transform: translateX(-3px); }
              100% { transform: translateX(0); }
            }
            @keyframes bgDriftA {
              0%, 100% { transform: translate(0, 0) scale(1); }
              50% { transform: translate(30px, -20px) scale(1.12); }
            }
            @keyframes bgDriftB {
              0%, 100% { transform: translate(0, 0) scale(1); }
              50% { transform: translate(-24px, 24px) scale(1.08); }
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
      )}
    </div>
  );
}

/* ---------- Ambient decoration ---------- */
/* A handful of very faint line icons scattered across the page so the paper
   background doesn't read as empty — echoes the report/chart/shield concepts
   from the plan tiers without competing with the actual content. */
function FloatingIcons() {
  const icons = [
    { top: "14%", left: "8%", delay: "0s", dur: "9s", size: 26, path: "M4 19h16M8 19V9m4 10V5m4 14v-7" }, // bars
    { top: "70%", left: "5%", delay: "1.2s", dur: "11s", size: 22, path: "M12 2l7 4v6c0 5-3 8-7 10-4-2-7-5-7-10V6l7-4z" }, // shield
    { top: "22%", left: "88%", delay: "0.6s", dur: "10s", size: 24, path: "M12 3v18M3 12h18" }, // plus/scan
    { top: "60%", left: "90%", delay: "2s", dur: "12s", size: 28, path: "M12 21a9 9 0 100-18 9 9 0 000 18zm0-5v-4m0-4h.01" }, // info/report
    { top: "88%", left: "20%", delay: "0.9s", dur: "13s", size: 20, path: "M5 13l4 4L19 7" }, // check
  ];
  return (
    <>
      {icons.map((ic, i) => (
        <svg
          key={i}
          width={ic.size}
          height={ic.size}
          viewBox="0 0 24 24"
          fill="none"
          className="absolute opacity-[0.05] animate-[iconFloat_var(--dur)_ease-in-out_infinite]"
          style={{
            top: ic.top,
            left: ic.left,
            animationDelay: ic.delay,
            animationDuration: ic.dur,
            "--dur": ic.dur,
          }}
        >
          <path d={ic.path} stroke="#14181B" strokeWidth="1.6" strokeLinecap="round" strokeLinejoin="round" />
        </svg>
      ))}
      <style>{`
        @keyframes iconFloat {
          0%, 100% { transform: translateY(0) rotate(0deg); }
          50% { transform: translateY(-16px) rotate(6deg); }
        }
      `}</style>
    </>
  );
}

/* ---------- Report-analysis illustration ---------- */
/* Original brand-style illustration (not a copy of any stock/Lottie art) —
   a small "analyst" bot reading a report on a laptop, with an orbiting ring
   chart and rising bars. `mode="idle"` keeps it calm; `mode="active"` speeds
   the scan line and orbit to signal real work in progress. */
function ReportBot({ mode = "idle" }) {
  const active = mode === "active";
  return (
    <div className="relative mx-auto flex h-40 w-full max-w-[220px] items-center justify-center">
      <svg viewBox="0 0 220 170" width="100%" height="100%" fill="none">
        {/* orbiting dashed ring, chart-like */}
        <g style={{ transformOrigin: "168px 46px", animation: `spin ${active ? "3.5s" : "9s"} linear infinite` }}>
          <circle cx="168" cy="46" r="20" stroke="#E4572E" strokeWidth="2" strokeDasharray="4 6" opacity="0.55" />
        </g>
        <circle cx="168" cy="46" r="9" fill="#1F5C45" opacity="0.15" />
        <path
          d="M168 37a9 9 0 010 18"
          stroke="#1F5C45"
          strokeWidth="2.4"
          strokeLinecap="round"
          style={{ animation: `pulseOpacity ${active ? "1.4s" : "2.6s"} ease-in-out infinite` }}
        />

        {/* laptop base */}
        <rect x="46" y="96" width="112" height="70" rx="6" fill="white" stroke="#14181B" strokeOpacity="0.15" strokeWidth="1.6" />
        <rect x="54" y="104" width="96" height="54" rx="3" fill="#14181B" fillOpacity="0.04" />
        {/* screen scan line */}
        <rect
          x="54"
          y="104"
          width="96"
          height="3"
          rx="1.5"
          fill="#E4572E"
          opacity="0.7"
          style={{
            animation: `scanY ${active ? "1.6s" : "3.2s"} ease-in-out infinite`,
          }}
        />
        {/* bar chart on screen, growing/shrinking */}
        {[0, 1, 2, 3].map((i) => (
          <rect
            key={i}
            x={64 + i * 20}
            width="10"
            rx="2"
            fill="#1F5C45"
            fillOpacity="0.55"
            y={140}
            height="10"
            style={{
              transformOrigin: `${64 + i * 20 + 5}px 150px`,
              animation: `barGrow ${active ? "1.8s" : "3.4s"} ease-in-out ${i * 0.18}s infinite`,
            }}
          />
        ))}
        <rect x="40" y="164" width="124" height="5" rx="2.5" fill="#14181B" fillOpacity="0.12" />

        {/* bot head, gentle bob */}
        <g style={{ animation: `bob ${active ? "1.8s" : "3s"} ease-in-out infinite` }}>
          <rect x="82" y="40" width="46" height="36" rx="12" fill="#14181B" />
          <rect x="100" y="26" width="10" height="16" rx="4" fill="#14181B" />
          <circle cx="105" cy="24" r="4" fill="#E4572E" />
          {/* eyes blink */}
          <g style={{ animation: "blink 3.6s ease-in-out infinite" }}>
            <circle cx="96" cy="58" r="4.5" fill="#F1ECDF" />
            <circle cx="114" cy="58" r="4.5" fill="#F1ECDF" />
          </g>
          {/* arm pointing at laptop */}
          <rect x="66" y="66" width="20" height="7" rx="3.5" fill="#14181B" />
        </g>
      </svg>

      <style>{`
        @keyframes spin { to { transform: rotate(360deg); } }
        @keyframes bob {
          0%, 100% { transform: translateY(0); }
          50% { transform: translateY(-5px); }
        }
        @keyframes blink {
          0%, 92%, 100% { transform: scaleY(1); }
          96% { transform: scaleY(0.1); }
        }
        @keyframes scanY {
          0% { transform: translateY(0); opacity: 0.7; }
          50% { transform: translateY(48px); opacity: 1; }
          100% { transform: translateY(0); opacity: 0.7; }
        }
        @keyframes barGrow {
          0%, 100% { transform: scaleY(0.6); }
          50% { transform: scaleY(1.6); }
        }
        @keyframes pulseOpacity {
          0%, 100% { opacity: 0.5; }
          50% { opacity: 1; }
        }
      `}</style>
    </div>
  );
}

function NoPlanState({ onSelectPlan }) {
  const navigate = useNavigate();

  return (
    <div className="relative mx-auto max-w-xl overflow-hidden px-4 py-24 text-center sm:px-6">
      {/* soft ambient glow, drifts in behind the content */}
      <div
        aria-hidden="true"
        className="pointer-events-none absolute left-1/2 top-10 h-64 w-64 -translate-x-1/2 rounded-full bg-[#E4572E]/10 blur-3xl animate-[glowPulse_3.5s_ease-in-out_infinite]"
      />

      <div className="relative animate-[popIn_0.55s_cubic-bezier(0.22,1,0.36,1)_both]">
        <span
          className="inline-flex items-center gap-2 rounded-full border border-[#E4572E]/30 bg-white px-3 py-1 text-[10px] font-semibold uppercase tracking-[0.2em] text-[#E4572E]"
          style={{ fontFamily: "'IBM Plex Mono', monospace" }}
        >
          <span className="relative flex h-1.5 w-1.5">
            <span className="absolute inline-flex h-full w-full animate-ping rounded-full bg-[#E4572E]/60" />
            <span className="relative inline-flex h-1.5 w-1.5 rounded-full bg-[#E4572E]" />
          </span>
          No active plan
        </span>
      </div>

      {/* lock icon, draws itself in */}
      <div className="relative mx-auto mt-7 flex h-16 w-16 items-center justify-center rounded-full border-2 border-[#14181B]/15 bg-white animate-[popIn_0.55s_cubic-bezier(0.22,1,0.36,1)_0.08s_both]">
        <svg width="26" height="26" viewBox="0 0 24 24" fill="none" aria-hidden="true">
          <rect
            x="5" y="11" width="14" height="9" rx="2"
            stroke="#14181B" strokeWidth="1.8"
            style={{ strokeDasharray: 46, strokeDashoffset: 46, animation: "drawCheck 0.5s ease-out 0.35s forwards" }}
          />
          <path
            d="M8 11V7a4 4 0 118 0v4"
            stroke="#14181B" strokeWidth="1.8" strokeLinecap="round"
            style={{ strokeDasharray: 20, strokeDashoffset: 20, animation: "drawCheck 0.4s ease-out 0.55s forwards" }}
          />
        </svg>
      </div>

      <h1
        className="relative mt-6 text-3xl font-semibold leading-tight tracking-tight sm:text-[2.2rem] animate-[fadeSlideUp_0.5s_cubic-bezier(0.22,1,0.36,1)_0.12s_both]"
        style={{ fontFamily: "'Space Grotesk', sans-serif" }}
      >
        You don't have an active plan
      </h1>
      <p className="relative mx-auto mt-3 max-w-md text-sm leading-relaxed text-[#14181B]/60 animate-[fadeSlideUp_0.5s_cubic-bezier(0.22,1,0.36,1)_0.18s_both]">
        Recharge with Basic, Standard, or Premium to run a live test and get your PDF report.
      </p>

      <div className="relative mt-8 animate-[fadeSlideUp_0.5s_cubic-bezier(0.22,1,0.36,1)_0.26s_both]">
        <button
          type="button"
          onClick={() => navigate("/pricing")}
          className="group relative inline-flex items-center gap-2 overflow-hidden rounded-full bg-[#14181B] px-7 py-3.5 text-sm font-semibold text-white transition-all duration-300 hover:shadow-[0_0_0_6px_rgba(228,87,46,0.15)] active:scale-[0.97]"
        >
          <span className="absolute inset-0 -translate-x-full bg-[#E4572E] transition-transform duration-300 group-hover:translate-x-0" />
          <span className="relative flex items-center gap-2">
            Recharge — view pricing
            <svg width="14" height="14" viewBox="0 0 24 24" fill="none" className="transition-transform duration-200 group-hover:translate-x-1">
              <path d="M5 12h14m0 0l-6-6m6 6l-6 6" stroke="white" strokeWidth="2.2" strokeLinecap="round" strokeLinejoin="round" />
            </svg>
          </span>
        </button>
      </div>

      {/* TEMP: clickable plan chips — payments aren't live yet, so this lets
          the user try any tier's test right now. Selection is local only,
          nothing is saved to their account or charged. */}
      <p className="relative mt-8 text-[10px] font-semibold uppercase tracking-[0.2em] text-[#14181B]/35" style={{ fontFamily: "'IBM Plex Mono', monospace" }}>
        Or try a plan now (free while we set up payments)
      </p>
      <ul className="relative mt-3 flex flex-wrap items-center justify-center gap-2">
        {["basic", "standard", "premium"].map((p, i) => (
          <li key={p} style={{ animationDelay: `${0.32 + i * 0.06}s` }} className="animate-[fadeSlideUp_0.4s_cubic-bezier(0.22,1,0.36,1)_both]">
            <button
              type="button"
              onClick={() => onSelectPlan?.(p)}
              className="rounded-full border border-[#14181B]/12 bg-white px-3.5 py-1.5 text-xs font-medium capitalize text-[#14181B]/70 transition-all duration-200 hover:-translate-y-0.5 hover:border-[#1F5C45]/40 hover:text-[#1F5C45] active:scale-[0.97]"
            >
              {p}
            </button>
          </li>
        ))}
      </ul>

      <style>{`
        @keyframes popIn {
          0% { opacity: 0; transform: scale(0.85); }
          70% { opacity: 1; transform: scale(1.03); }
          100% { opacity: 1; transform: scale(1); }
        }
        @keyframes fadeSlideUp {
          from { opacity: 0; transform: translateY(12px); }
          to { opacity: 1; transform: translateY(0); }
        }
        @keyframes drawCheck {
          to { stroke-dashoffset: 0; }
        }
        @keyframes glowPulse {
          0%, 100% { opacity: 0.5; transform: translate(-50%, 0) scale(1); }
          50% { opacity: 0.9; transform: translate(-50%, 0) scale(1.15); }
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

function IdleHint({ plan }) {
  const items =
    plan === "premium"
      ? ["Functional tests", "Security audit", "SEO & accessibility", "Content, UX & CRO"]
      : plan === "standard"
      ? ["Functional tests", "SEO & accessibility", "AI recommendations"]
      : ["SEO & accessibility", "Performance", "Content & images"];

  const estimate = PLAN_ESTIMATE_SECONDS[plan] || 180;
  const estimateLabel = `${Math.max(1, Math.round(estimate / 60) - 1)}–${Math.round(estimate / 60) + 1} min`;

  return (
    <div className="overflow-hidden rounded-xl border border-[#14181B]/10 bg-white shadow-[0_1px_0_rgba(20,24,27,0.03)]">
      <div className="border-b border-dashed border-[#14181B]/12 bg-gradient-to-b from-[#14181B]/[0.02] to-transparent px-6 pb-2 pt-5">
        <ReportBot mode="idle" />
      </div>
      <div className="p-6">
        <div className="flex items-center justify-between">
          <p
            className="text-[10px] font-semibold uppercase tracking-[0.2em] text-[#14181B]/40"
            style={{ fontFamily: "'IBM Plex Mono', monospace" }}
          >
            What we'll check
          </p>
          <span
            className="rounded-full bg-[#14181B]/[0.05] px-2.5 py-1 text-[10px] font-semibold text-[#14181B]/50"
            style={{ fontFamily: "'IBM Plex Mono', monospace" }}
          >
            ~{estimateLabel}
          </span>
        </div>
        <ul className="mt-3 flex flex-wrap gap-2">
        {items.map((item, i) => (
          <li
            key={item}
            className="animate-[fadeSlideUp_0.35s_ease-out_both] rounded-sm border border-[#14181B]/12 px-3 py-1.5 text-xs font-medium text-[#14181B]/70"
            style={{ animationDelay: `${0.05 * i}s` }}
          >
            {item}
          </li>
        ))}
        </ul>
      </div>
    </div>
  );
}

/* ---------- Running state ---------- */
/*
 * Real report generation runs 3–5 minutes depending on plan, and the API only
 * resolves once — there's no server-sent progress. So instead of a fake timer
 * that finishes in a few seconds, this tracks real elapsed time and eases the
 * bar toward ~96% across the plan's expected duration, then holds there
 * (rather than looking "stuck" at 100%) until the fetch actually resolves and
 * the parent flips status to "done"/"error".
 */
function RunningState({ plan }) {
  const stepGroups =
    plan === "premium"
      ? [
          { label: "Running functional tests", detail: "20 modules across nav, forms, auth & sessions" },
          { label: "Full security audit", detail: "Headers, exposed endpoints & known misconfigurations" },
          { label: "SEO & accessibility sweep", detail: "Meta, semantics, contrast, keyboard nav" },
          { label: "Content, UX & CRO review", detail: "Copy clarity, funnels, conversion friction" },
          { label: "Compiling your PDF", detail: "Scoring, grading & formatting the report" },
        ]
      : plan === "standard"
      ? [
          { label: "Running functional tests", detail: "20 modules across nav, forms, auth & sessions" },
          { label: "Advanced SEO & accessibility", detail: "Meta, semantics, contrast, keyboard nav" },
          { label: "Generating AI recommendations", detail: "Turning findings into fix suggestions" },
          { label: "Compiling your PDF", detail: "Scoring, grading & formatting the report" },
        ]
      : [
          { label: "Checking SEO & accessibility", detail: "Meta tags, headings, alt text, contrast" },
          { label: "Checking performance", detail: "Load weight, render-blocking assets" },
          { label: "Validating content & images", detail: "Broken links, missing images, copy issues" },
          { label: "Compiling your PDF", detail: "Scoring, grading & formatting the report" },
        ];

  const totalSeconds = PLAN_ESTIMATE_SECONDS[plan] || 180;
  const [elapsed, setElapsed] = useState(0);

  useEffect(() => {
    const started = Date.now();
    const id = setInterval(() => {
      setElapsed(Math.floor((Date.now() - started) / 1000));
    }, 1000);
    return () => clearInterval(id);
  }, []);

  // Ease toward 96% using the plan's real expected duration as the time constant —
  // fast early progress, slowing down, never claiming "done" before the API says so.
  const progressFraction = 1 - Math.exp(-elapsed / (totalSeconds / 2.2));
  const displayPct = Math.min(96, Math.round(progressFraction * 96));

  const activeIndex = Math.min(
    stepGroups.length - 1,
    Math.floor((elapsed / totalSeconds) * stepGroups.length)
  );

  const mins = Math.floor(elapsed / 60);
  const secs = elapsed % 60;
  const elapsedLabel = `${mins}:${secs.toString().padStart(2, "0")}`;

  const size = 52;
  const stroke = 4;
  const radius = (size - stroke) / 2;
  const circumference = 2 * Math.PI * radius;
  const offset = circumference - (displayPct / 100) * circumference;

  return (
    <div className="relative overflow-hidden rounded-xl border border-[#14181B]/10 bg-white/70 p-6 shadow-[0_1px_0_rgba(20,24,27,0.04)] backdrop-blur-xl animate-[fadeIn_0.35s_ease-out]">
      {/* ambient gradient orbs, trend: soft glassmorphism */}
      <div
        aria-hidden="true"
        className="pointer-events-none absolute -left-10 -top-16 h-40 w-40 rounded-full bg-[#E4572E]/10 blur-3xl animate-[driftA_7s_ease-in-out_infinite]"
      />
      <div
        aria-hidden="true"
        className="pointer-events-none absolute -bottom-16 -right-10 h-44 w-44 rounded-full bg-[#1F5C45]/10 blur-3xl animate-[driftB_8.5s_ease-in-out_infinite]"
      />

      <div className="relative border-b border-[#14181B]/8 pb-2 -mt-1">
        <ReportBot mode="active" />
      </div>

      <div className="relative mt-4 flex items-center gap-4">
        <div className="relative shrink-0" style={{ width: size, height: size }}>
          {/* rotating conic glow ring behind the progress ring */}
          <div
            className="absolute inset-[-6px] rounded-full opacity-70 animate-[spin_3.2s_linear_infinite]"
            style={{
              background:
                "conic-gradient(from 0deg, rgba(228,87,46,0) 0deg, rgba(228,87,46,0.55) 90deg, rgba(228,87,46,0) 180deg)",
            }}
          />
          <svg width={size} height={size} className="-rotate-90 relative">
            <circle cx={size / 2} cy={size / 2} r={radius} fill="none" stroke="rgba(20,24,27,0.08)" strokeWidth={stroke} />
            <circle
              cx={size / 2}
              cy={size / 2}
              r={radius}
              fill="none"
              stroke="#E4572E"
              strokeWidth={stroke}
              strokeLinecap="round"
              strokeDasharray={circumference}
              strokeDashoffset={offset}
              style={{ transition: "stroke-dashoffset 0.8s ease-out" }}
            />
          </svg>
          <div
            className="absolute inset-0 flex items-center justify-center text-[11px] font-bold text-[#14181B]"
            style={{ fontFamily: "'IBM Plex Mono', monospace" }}
          >
            {displayPct}%
          </div>
        </div>

        <div className="flex-1">
          <div className="flex items-center gap-2">
            <p className="text-sm font-semibold text-[#14181B]" style={{ fontFamily: "'Space Grotesk', sans-serif" }}>
              Analyzing your site…
            </p>
            <span className="relative flex h-1.5 w-1.5">
              <span className="absolute inline-flex h-full w-full animate-ping rounded-full bg-[#1F5C45]/60" />
              <span className="relative inline-flex h-1.5 w-1.5 rounded-full bg-[#1F5C45]" />
            </span>
          </div>
          <p className="text-xs text-[#14181B]/45">
            Real audits take a few minutes — feel free to keep this tab open in the background.
          </p>
        </div>

        <div
          className="shrink-0 rounded-full border border-[#14181B]/10 bg-[#14181B]/[0.03] px-2.5 py-1 text-[10px] font-semibold tabular-nums text-[#14181B]/55"
          style={{ fontFamily: "'IBM Plex Mono', monospace" }}
        >
          {elapsedLabel}
        </div>
      </div>

      {/* shimmering progress bar, trend: gradient sheen instead of flat fill */}
      <div className="relative mt-5 h-1.5 w-full overflow-hidden rounded-full bg-[#14181B]/10">
        <div
          className="relative h-full rounded-full bg-gradient-to-r from-[#E4572E] via-[#F16A40] to-[#E4572E] transition-[width] duration-700 ease-out"
          style={{ width: `${displayPct}%`, backgroundSize: "200% 100%", animation: "sheen 2.2s linear infinite" }}
        />
      </div>

      <ul className="relative mt-5 divide-y divide-[#14181B]/8 border-t border-[#14181B]/8 text-xs" style={{ fontFamily: "'IBM Plex Mono', monospace" }}>
        {stepGroups.map((step, i) => {
          const isDone = i < activeIndex;
          const isActive = i === activeIndex;
          return (
            <li
              key={step.label}
              className={`flex items-start gap-2.5 px-1 py-2.5 transition-all duration-500 ${
                isActive ? "bg-[#1F5C45]/[0.05]" : ""
              } ${isDone ? "text-[#14181B]/35" : isActive ? "text-[#14181B]" : "text-[#14181B]/30"}`}
            >
              <span className="mt-0.5 flex h-5 w-5 shrink-0 items-center justify-center">
                {isDone ? (
                  <span className="flex h-5 w-5 items-center justify-center rounded-full border border-[#1F5C45] text-[#1F5C45] animate-[popIn_0.3s_cubic-bezier(0.22,1,0.36,1)_both]">
                    ✓
                  </span>
                ) : isActive ? (
                  <span className="relative flex h-2.5 w-2.5">
                    <span className="absolute inline-flex h-full w-full animate-ping rounded-full bg-[#E4572E]/60" />
                    <span className="relative inline-flex h-2.5 w-2.5 rounded-full bg-[#E4572E]" />
                  </span>
                ) : (
                  <span className="h-1.5 w-1.5 rounded-full bg-[#14181B]/20" />
                )}
              </span>
              <span className="flex-1">
                <span className={isActive ? "font-semibold" : ""}>{step.label}</span>
                {isActive && (
                  <span className="mt-0.5 block text-[10px] font-normal normal-case text-[#14181B]/40 animate-[fadeIn_0.4s_ease-out]">
                    {step.detail}
                  </span>
                )}
              </span>
            </li>
          );
        })}
      </ul>

      <style>{`
        @keyframes sheen {
          from { background-position: 200% 0; }
          to { background-position: 0 0; }
        }
        @keyframes driftA {
          0%, 100% { transform: translate(0, 0) scale(1); }
          50% { transform: translate(14px, 10px) scale(1.08); }
        }
        @keyframes driftB {
          0%, 100% { transform: translate(0, 0) scale(1); }
          50% { transform: translate(-12px, -8px) scale(1.1); }
        }
        @keyframes popIn {
          0% { opacity: 0; transform: scale(0.6); }
          70% { opacity: 1; transform: scale(1.12); }
          100% { opacity: 1; transform: scale(1); }
        }
        @keyframes fadeIn {
          from { opacity: 0; transform: translateY(4px); }
          to { opacity: 1; transform: translateY(0); }
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