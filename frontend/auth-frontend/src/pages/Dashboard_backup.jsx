// src/pages/Dashboard.jsx
import { useEffect, useRef, useState } from "react";
import { Link } from "react-router-dom";
import Navbar from "../components/Navbar";
import { getCurrentUser, getStoredUser, getToken } from "../services/authService";

const API_BASE_URL = import.meta.env?.VITE_API_BASE_URL || "http://localhost:8000";

/* ------------------------------------------------------------------ */
/* Design tokens (see comment block at bottom of file for the plan)    */
/*   ink    #14181B   paper  #F1ECDF   card  #FFFFFF                   */
/*   flag   #E4572E  (issues / primary CTA)                            */
/*   pass   #1F5C45  (checks / secondary accent)                       */
/*   line   rgba(20,24,27,.14)                                         */
/* ------------------------------------------------------------------ */

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

const SCAN_LOG = [
  "GET / 200",
  "meta[description] ✓",
  "img[alt] 12/14",
  "contrast AA ✓",
  "TLS 1.3 ✓",
  "LCP 1.8s",
  "sitemap.xml ✓",
  "console 0 err",
];

export default function Dashboard() {
  useReportFonts();

  const [user, setUser] = useState(getStoredUser());
  const [stats, setStats] = useState({ reportsGenerated: null, websitesTested: null });
  const [statsLoading, setStatsLoading] = useState(true);
  const [history, setHistory] = useState([]);
  const [historyLoading, setHistoryLoading] = useState(true);
  const [scrollProgress, setScrollProgress] = useState(0);

  useEffect(() => {
    // Refresh from the server in case the plan changed elsewhere.
    getCurrentUser()
      .then(setUser)
      .catch(() => {
        /* ignore — fall back to whatever's cached locally */
      });
  }, []);

  useEffect(() => {
    let cancelled = false;

    async function loadStats() {
      try {
        // GET /dashboard/stats is gated behind get_current_user on the
        // backend, so it needs the same Bearer token as /users/me.
        const token = getToken();
        if (!token) {
          if (!cancelled) setStats({ reportsGenerated: 0, websitesTested: 0 });
          return;
        }
        const res = await fetch(`${API_BASE_URL}/dashboard/stats`, {
          headers: { Authorization: `Bearer ${token}` },
        });
        if (!res.ok) throw new Error("stats request failed");
        const data = await res.json();
        if (!cancelled) {
          setStats({
            reportsGenerated: data.reports_generated ?? 0,
            websitesTested: data.website_tests ?? 0,
          });
        }
      } catch {
        if (!cancelled) setStats({ reportsGenerated: 0, websitesTested: 0 });
      } finally {
        if (!cancelled) setStatsLoading(false);
      }
    }

    loadStats();
    return () => {
      cancelled = true;
    };
  }, [user]);

  useEffect(() => {
    let cancelled = false;

    async function loadHistory() {
      try {
        const token = getToken();
        if (!token) {
          if (!cancelled) setHistory([]);
          return;
        }
        const res = await fetch(`${API_BASE_URL}/dashboard/history?limit=6`, {
          headers: { Authorization: `Bearer ${token}` },
        });
        if (!res.ok) throw new Error("history request failed");
        const data = await res.json();
        if (!cancelled) setHistory(Array.isArray(data) ? data : []);
      } catch {
        if (!cancelled) setHistory([]);
      } finally {
        if (!cancelled) setHistoryLoading(false);
      }
    }

    loadHistory();
    return () => {
      cancelled = true;
    };
  }, [user]);

  useEffect(() => {
    function onScroll() {
      const h = document.documentElement;
      const scrollable = h.scrollHeight - h.clientHeight;
      setScrollProgress(scrollable > 0 ? Math.min(1, h.scrollTop / scrollable) : 0);
    }
    onScroll();
    window.addEventListener("scroll", onScroll, { passive: true });
    return () => window.removeEventListener("scroll", onScroll);
  }, []);

  const plan = user?.plan || "basic";

  return (
    <div className="relative min-h-screen overflow-hidden bg-[#F1ECDF] text-[#14181B]">
      {/* Paper grid + noise field */}
      <div className="pointer-events-none fixed inset-0 -z-0" aria-hidden="true">
        <div
          className="absolute inset-0 opacity-[0.05]"
          style={{
            backgroundImage:
              "linear-gradient(#14181B 1px, transparent 1px), linear-gradient(90deg, #14181B 1px, transparent 1px)",
            backgroundSize: "36px 36px",
          }}
        />
        <div className="absolute right-[-8%] top-[8%] h-[420px] w-[420px] rounded-full bg-[#E4572E]/[0.06] blur-[100px]" />
        <div className="absolute left-[-10%] bottom-[10%] h-[380px] w-[380px] rounded-full bg-[#1F5C45]/[0.08] blur-[100px]" />
      </div>

      {/* Scroll meter — a readout, not a bar */}
      <div className="fixed left-0 top-0 z-50 h-[3px] w-full bg-[#14181B]/[0.06]">
        <div
          className="h-full bg-[#E4572E] transition-[width] duration-150 ease-out"
          style={{ width: `${scrollProgress * 100}%` }}
        />
      </div>

      <Navbar />

      <div className="relative mx-auto max-w-6xl px-4 py-10 sm:px-6">
        {/* ---------------------------------------------------------- */}
        {/* Hero — printed inspection-report header                    */}
        {/* ---------------------------------------------------------- */}
        <div className="relative overflow-hidden rounded-md border border-[#14181B]/12 bg-white shadow-[0_1px_0_#14181B14] animate-[cardRise_0.55s_cubic-bezier(0.22,1,0.36,1)_both]">
          <ScanSweep />

          <div className="relative flex flex-col justify-between gap-8 p-8 sm:flex-row sm:items-start sm:p-12">
            <div className="max-w-xl">
              <p
                className="flex items-center gap-2 text-[11px] font-semibold uppercase tracking-[0.3em] text-[#1F5C45]"
                style={{ fontFamily: "'IBM Plex Mono', monospace" }}
              >
                <span className="relative flex h-2 w-2">
                  <span className="absolute inline-flex h-full w-full animate-ping rounded-full bg-[#1F5C45]/60" />
                  <span className="relative inline-flex h-2 w-2 rounded-full bg-[#1F5C45]" />
                </span>
                Live audit console
              </p>

              <h1
                className="mt-4 text-3xl font-semibold leading-[1.1] tracking-tight sm:text-[2.6rem] animate-[fadeIn_0.4s_ease-out_0.12s_both]"
                style={{ fontFamily: "'Space Grotesk', sans-serif" }}
              >
                Welcome back{user?.username ? `, ${user.username}` : ""}.
              </h1>
              <p className="mt-3 max-w-md text-sm leading-relaxed text-[#14181B]/60 animate-[fadeIn_0.4s_ease-out_0.18s_both]">
                TestPilot runs a full inspection of your site — SEO, accessibility, performance,
                security — and files it as a report you can act on.
              </p>

              <div className="mt-7 flex flex-wrap gap-3 animate-[fadeIn_0.4s_ease-out_0.24s_both]">
                <Link
                  to="/test"
                  className="rounded-sm bg-[#14181B] px-5 py-2.5 text-sm font-semibold text-[#F1ECDF] transition-all duration-200 hover:bg-[#E4572E] hover:text-white focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-[#E4572E] active:scale-[0.98]"
                >
                  Test a website →
                </Link>
                <Link
                  to="/pricing"
                  className="rounded-sm border border-[#14181B]/25 px-5 py-2.5 text-sm font-semibold text-[#14181B] transition-all duration-200 hover:border-[#14181B] focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-[#14181B] active:scale-[0.98]"
                >
                  View plans
                </Link>
              </div>
            </div>

            {/* Live scan readout ticker */}
            <div className="w-full max-w-[280px] shrink-0 animate-[fadeIn_0.4s_ease-out_0.3s_both]">
              <div className="flex items-center justify-between border-b border-[#14181B]/10 pb-2">
                <span
                  className="text-[10px] font-semibold uppercase tracking-[0.2em] text-[#14181B]/40"
                  style={{ fontFamily: "'IBM Plex Mono', monospace" }}
                >
                  scan.log
                </span>
                <span
                  className="text-[10px] text-[#1F5C45]"
                  style={{ fontFamily: "'IBM Plex Mono', monospace" }}
                >
                  running
                </span>
              </div>
              <ul
                className="mt-2 space-y-1.5 text-[11px] leading-relaxed text-[#14181B]/55"
                style={{ fontFamily: "'IBM Plex Mono', monospace" }}
              >
                {SCAN_LOG.map((line, i) => (
                  <li
                    key={line}
                    className="flex items-center gap-2 animate-[fadeIn_0.35s_ease-out_both]"
                    style={{ animationDelay: `${0.4 + i * 0.08}s` }}
                  >
                    <span className="text-[#1F5C45]">✓</span>
                    {line}
                  </li>
                ))}
              </ul>
            </div>
          </div>

          <StampBadge plan={plan} />
        </div>

        {/* ---------------------------------------------------------- */}
        {/* Ticker — what's under the hood, scrolling like a log feed   */}
        {/* ---------------------------------------------------------- */}
        <MarqueeStrip />

        {/* ---------------------------------------------------------- */}
        {/* Ledger — stat row                                           */}
        {/* ---------------------------------------------------------- */}
        <p
          className="mt-9 text-[11px] font-semibold uppercase tracking-[0.25em] text-[#14181B]/40 animate-[fadeIn_0.4s_ease-out_0.3s_both]"
          style={{ fontFamily: "'IBM Plex Mono', monospace" }}
        >
          Account ledger
        </p>
        <div className="mt-3 grid grid-cols-1 divide-y divide-[#14181B]/10 rounded-md border border-[#14181B]/12 bg-white sm:grid-cols-3 sm:divide-x sm:divide-y-0">
          <LedgerCell label="Current plan" value={planLabel(plan)} delay={0.34} />
          <LedgerCell
            label="Reports generated"
            value={statsLoading ? null : stats.reportsGenerated}
            hint={!statsLoading && stats.reportsGenerated === 0 ? "Run a test to see your first report" : null}
            delay={0.4}
          />
          <LedgerCell
            label="Websites tested"
            value={statsLoading ? null : stats.websitesTested}
            hint={!statsLoading && stats.websitesTested === 0 ? "Run a test to see your first result" : null}
            delay={0.46}
          />
        </div>

        {/* ---------------------------------------------------------- */}
        {/* Report preview — what actually lands in your inbox          */}
        {/* ---------------------------------------------------------- */}
        <Reveal className="mt-12">
          <ReportPreviewCard />
        </Reveal>

        {/* ---------------------------------------------------------- */}
        {/* Recent audits — the websites this user has tested            */}
        {/* ---------------------------------------------------------- */}
        <Reveal className="mt-12">
          <div className="flex items-end justify-between gap-4">
            <div>
              <SectionEyebrow>Case file</SectionEyebrow>
              <h2 className="mt-1.5 text-2xl font-semibold tracking-tight" style={{ fontFamily: "'Space Grotesk', sans-serif" }}>
                Recent audits
              </h2>
              <p className="mt-1.5 text-sm text-[#14181B]/55">Every site you've run through TestPilot, most recent first.</p>
            </div>
            {history.length > 0 && (
              <Link
                to="/history"
                className="hidden shrink-0 text-xs font-semibold text-[#14181B] underline decoration-[#E4572E] decoration-2 underline-offset-4 transition-colors duration-200 hover:text-[#E4572E] sm:inline"
              >
                View full history →
              </Link>
            )}
          </div>

          <div className="mt-6 overflow-hidden rounded-md border border-[#14181B]/12 bg-white">
            {historyLoading && (
              <div className="p-5">
                {Array.from({ length: 3 }).map((_, i) => (
                  <div key={i} className="flex items-center gap-4 border-b border-[#14181B]/8 py-3 last:border-0">
                    <span className="h-2 w-2 rounded-full bg-[#14181B]/10" />
                    <span className="h-4 flex-1 animate-pulse rounded bg-[#14181B]/8" />
                    <span className="h-4 w-8 animate-pulse rounded bg-[#14181B]/8" />
                  </div>
                ))}
              </div>
            )}

            {!historyLoading && history.length === 0 && (
              <div className="p-8 text-center">
                <p className="text-sm font-semibold text-[#14181B]">No audits filed yet</p>
                <p className="mt-1 text-xs text-[#14181B]/50">Run your first test and it'll show up here.</p>
              </div>
            )}

            {!historyLoading && history.length > 0 && (
              <div className="divide-y divide-[#14181B]/10">
                {history.map((entry, i) => (
                  <HistoryRow key={entry.id} entry={entry} delay={0.04 * i} />
                ))}
              </div>
            )}
          </div>

          {history.length > 0 && (
            <Link
              to="/history"
              className="mt-3 inline-block text-xs font-semibold text-[#14181B] underline decoration-[#E4572E] decoration-2 underline-offset-4 sm:hidden"
            >
              View full history →
            </Link>
          )}
        </Reveal>

        {/* ---------------------------------------------------------- */}
        {/* Process log                                                 */}
        {/* ---------------------------------------------------------- */}
        <Reveal className="mt-12">
          <SectionEyebrow>Process log</SectionEyebrow>
          <h2 className="mt-1.5 text-2xl font-semibold tracking-tight" style={{ fontFamily: "'Space Grotesk', sans-serif" }}>
            How TestPilot works
          </h2>
          <p className="mt-1.5 text-sm text-[#14181B]/55">Three entries between you and a full audit of your site.</p>

          <div className="relative mt-8 grid grid-cols-1 gap-0 sm:grid-cols-3">
            <span className="pointer-events-none absolute left-0 right-0 top-[22px] hidden border-t border-dashed border-[#14181B]/20 sm:block" />
            <ProcessStep n="01" title="Drop your URL" text="Paste any live website — no setup, no code to install." delay={0.1} />
            <ProcessStep n="02" title="We run real checks" text="Automated tests crawl your site live and score it across every category." delay={0.18} />
            <ProcessStep n="03" title="Get your PDF report" text="A clear, filed report with scores and concrete recommendations." delay={0.26} />
          </div>
        </Reveal>

        {/* ---------------------------------------------------------- */}
        {/* Checklist — what we test                                    */}
        {/* ---------------------------------------------------------- */}
        <Reveal className="mt-12">
          <SectionEyebrow>Coverage</SectionEyebrow>
          <h2 className="mt-1.5 text-2xl font-semibold tracking-tight" style={{ fontFamily: "'Space Grotesk', sans-serif" }}>
            What we test
          </h2>
          <p className="mt-1.5 text-sm text-[#14181B]/55">Every audit checks these — depth scales with your plan.</p>

          <div className="mt-6 divide-y divide-[#14181B]/10 rounded-md border border-[#14181B]/12 bg-white">
            {FEATURES.map((f, i) => (
              <ChecklistRow key={f.title} {...f} delay={0.05 + i * 0.04} />
            ))}
          </div>
        </Reveal>

        {/* ---------------------------------------------------------- */}
        {/* FAQ — questions filed and answered                          */}
        {/* ---------------------------------------------------------- */}
        <Reveal className="mt-12">
          <SectionEyebrow>FAQ</SectionEyebrow>
          <h2 className="mt-1.5 text-2xl font-semibold tracking-tight" style={{ fontFamily: "'Space Grotesk', sans-serif" }}>
            Questions, answered
          </h2>
          <p className="mt-1.5 text-sm text-[#14181B]/55">Everything worth knowing before your first audit.</p>

          <FaqAccordion items={FAQ_ITEMS} />
        </Reveal>

        {/* ---------------------------------------------------------- */}
        {/* Pricing — audit tickets                                     */}
        {/* ---------------------------------------------------------- */}
        <Reveal className="mt-12">
          <div className="flex flex-wrap items-end justify-between gap-4">
            <div>
              <SectionEyebrow>Pricing</SectionEyebrow>
              <h2 className="mt-1.5 text-2xl font-semibold tracking-tight" style={{ fontFamily: "'Space Grotesk', sans-serif" }}>
                Plans built around your testing needs
              </h2>
              <p className="mt-1.5 text-sm text-[#14181B]/55">Upgrade any time — every plan includes a full PDF report.</p>
            </div>
            <Link
              to="/pricing"
              className="hidden shrink-0 text-xs font-semibold text-[#14181B] underline decoration-[#E4572E] decoration-2 underline-offset-4 transition-colors duration-200 hover:text-[#E4572E] sm:inline"
            >
              See full comparison →
            </Link>
          </div>

          <div className="mt-6 grid grid-cols-1 gap-5 sm:grid-cols-3 animate-[fadeIn_0.35s_ease-out_both]">
            {PRICING_PREVIEW.map((p, i) => (
              <TicketCard key={p.id} {...p} isCurrent={plan === p.id} delay={0.1 + i * 0.08} />
            ))}
          </div>

          <Link
            to="/pricing"
            className="mt-5 inline-block text-xs font-semibold text-[#14181B] underline decoration-[#E4572E] decoration-2 underline-offset-4 sm:hidden"
          >
            See full comparison →
          </Link>
        </Reveal>

        {/* ---------------------------------------------------------- */}
        {/* Contact — directory                                         */}
        {/* ---------------------------------------------------------- */}
        <Reveal className="mt-12 mb-6">
          <SectionEyebrow>Support</SectionEyebrow>
          <h2 className="mt-1.5 text-2xl font-semibold tracking-tight" style={{ fontFamily: "'Space Grotesk', sans-serif" }}>
            Get in touch
          </h2>
          <p className="mt-1.5 text-sm text-[#14181B]/55">Questions about a report or your plan? We're here to help.</p>

          <div className="mt-6 flex justify-center rounded-md border border-[#14181B]/12 bg-white">
            <DirectoryCell
              label="Email"
              value="support@TestPilot.com"
              href="mailto:support@TestPilot.com"
              delay={0.1}
              className="text-center"
            />
          </div>
        </Reveal>

        {/* ---------------------------------------------------------- */}
        {/* Closing stamp                                               */}
        {/* ---------------------------------------------------------- */}
        <Reveal className="mb-10">
          <div className="relative overflow-hidden rounded-md border border-[#14181B]/12 bg-[#14181B] p-8 text-center text-white sm:p-10">
            <div
              className="pointer-events-none absolute inset-0 opacity-[0.04]"
              style={{
                backgroundImage:
                  "linear-gradient(#fff 1px, transparent 1px), linear-gradient(90deg, #fff 1px, transparent 1px)",
                backgroundSize: "28px 28px",
              }}
              aria-hidden="true"
            />
            <p
              className="relative text-[11px] font-semibold uppercase tracking-[0.25em] text-[#E4572E]"
              style={{ fontFamily: "'IBM Plex Mono', monospace" }}
            >
              Get started
            </p>
            <h2 className="relative mt-2 text-2xl font-semibold tracking-tight" style={{ fontFamily: "'Space Grotesk', sans-serif" }}>
              Ready to see where your site stands?
            </h2>
            <p className="relative mx-auto mt-2 max-w-md text-sm text-white/60">
              Run your first test and get a full PDF report in minutes.
            </p>
            <div className="relative mt-5 flex flex-wrap items-center justify-center gap-3">
              <Link
                to="/test"
                className="inline-flex items-center gap-2 rounded-sm bg-[#E4572E] px-6 py-3 text-sm font-semibold text-white transition-all duration-200 hover:bg-[#F16A40] focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-white active:scale-[0.98]"
              >
                Test a website
                <svg width="14" height="14" viewBox="0 0 24 24" fill="none" aria-hidden="true">
                  <path d="M5 12h14M13 6l6 6-6 6" stroke="white" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" />
                </svg>
              </Link>
            </div>
          </div>
        </Reveal>
      </div>

      <Footer />

      <style>{`
        @keyframes fadeIn {
          from { opacity: 0; transform: translateY(8px); }
          to { opacity: 1; transform: translateY(0); }
        }
        @keyframes cardRise {
          from { opacity: 0; transform: translateY(16px) scale(0.99); }
          to { opacity: 1; transform: translateY(0) scale(1); }
        }
        @keyframes revealUp {
          from { opacity: 0; transform: translateY(22px); }
          to { opacity: 1; transform: translateY(0); }
        }
        @keyframes numberIn {
          from { opacity: 0; transform: translateY(4px); }
          to { opacity: 1; transform: translateY(0); }
        }
        @keyframes sweepDown {
          0% { transform: translateY(-100%); opacity: 0; }
          10% { opacity: 1; }
          90% { opacity: 1; }
          100% { transform: translateY(2200%); opacity: 0; }
        }
        @keyframes stampIn {
          0% { opacity: 0; transform: rotate(-14deg) scale(1.6); }
          60% { opacity: 1; transform: rotate(-8deg) scale(0.94); }
          100% { opacity: 1; transform: rotate(-8deg) scale(1); }
        }
        @keyframes marquee {
          from { transform: translateX(0); }
          to { transform: translateX(-50%); }
        }
        @keyframes barGrow {
          from { transform: scaleY(0); }
          to { transform: scaleY(1); }
        }
        @keyframes barGrowX {
          from { transform: scaleX(0); }
          to { transform: scaleX(1); }
        }
        @keyframes ringIn {
          from { stroke-dashoffset: var(--ring-circumference); }
          to { stroke-dashoffset: var(--ring-offset); }
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

function planLabel(plan) {
  if (plan === "premium") return "Premium";
  if (plan === "standard") return "Standard";
  if (plan === "basic") return "Basic";
  return "No active plan";
}

/** Thin horizontal beam that sweeps down the hero once on load — the signature moment. */
function ScanSweep() {
  return (
    <div className="pointer-events-none absolute inset-0 overflow-hidden" aria-hidden="true">
      <div
        className="absolute left-0 right-0 h-[2px] bg-gradient-to-r from-transparent via-[#1F5C45]/70 to-transparent"
        style={{ animation: "sweepDown 3.2s cubic-bezier(0.4,0,0.2,1) 0.3s 1 both" }}
      />
    </div>
  );
}

/** Rotated ink-stamp badge showing the user's plan tier — presses in on load. */
function StampBadge({ plan }) {
  const label = plan === "premium" ? "PREMIUM" : plan === "standard" ? "STANDARD" : plan === "basic" ? "BASIC" : "No Plan";
  const color = plan === "premium" ? "#E4572E" : "#1F5C45";
  return (
    <div
      className="pointer-events-none absolute right-6 top-6 hidden select-none rounded-full border-2 px-4 py-2 text-[11px] font-bold uppercase tracking-[0.2em] sm:block"
      style={{
        color,
        borderColor: color,
        fontFamily: "'IBM Plex Mono', monospace",
        animation: "stampIn 0.5s cubic-bezier(0.22,1,0.36,1) 1.1s both",
      }}
    >
      {label}
    </div>
  );
}

const TICKER_ITEMS = [
  "SEO", "Accessibility", "Performance", "Security", "Content & UX",
  "Browser compatibility",
];

/** Thin scrolling strip of what gets checked — reinforces the "live log" motif from the hero. */
function MarqueeStrip() {
  const loop = [...TICKER_ITEMS, ...TICKER_ITEMS];
  return (
    <div
      className="relative mt-6 overflow-hidden rounded-md border border-[#14181B]/12 bg-white py-3 animate-[fadeIn_0.4s_ease-out_0.36s_both]"
      aria-hidden="true"
    >
      <div className="pointer-events-none absolute inset-y-0 left-0 z-10 w-14 bg-gradient-to-r from-white to-transparent" />
      <div className="pointer-events-none absolute inset-y-0 right-0 z-10 w-14 bg-gradient-to-l from-white to-transparent" />
      <div className="flex w-max animate-[marquee_24s_linear_infinite] gap-10 whitespace-nowrap px-4 hover:[animation-play-state:paused]">
        {loop.map((item, i) => (
          <span
            key={i}
            className="flex items-center gap-2 text-[11px] font-semibold uppercase tracking-[0.2em] text-[#14181B]/40"
            style={{ fontFamily: "'IBM Plex Mono', monospace" }}
          >
            <span className="h-1.5 w-1.5 rounded-full bg-[#1F5C45]" />
            {item}
          </span>
        ))}
      </div>
    </div>
  );
}

/** Animated circular score ring — the overall audit score, drawn on load like a gauge filling in. */
function ScoreGauge({ score }) {
  const size = 76;
  const stroke = 7;
  const r = (size - stroke) / 2;
  const circumference = 2 * Math.PI * r;
  const offset = circumference * (1 - score / 100);
  const color = score >= 80 ? "#1F5C45" : score >= 50 ? "#E4572E" : "#E4572E";

  return (
    <div className="relative shrink-0" style={{ width: size, height: size }}>
      <svg width={size} height={size} viewBox={`0 0 ${size} ${size}`} className="-rotate-90">
        <circle cx={size / 2} cy={size / 2} r={r} fill="none" stroke="#14181B14" strokeWidth={stroke} />
        <circle
          cx={size / 2}
          cy={size / 2}
          r={r}
          fill="none"
          stroke={color}
          strokeWidth={stroke}
          strokeLinecap="round"
          strokeDasharray={circumference}
          style={{
            "--ring-circumference": circumference,
            "--ring-offset": offset,
            animation: "ringIn 1s cubic-bezier(0.22,1,0.36,1) 0.2s both",
          }}
        />
      </svg>
      <div
        className="absolute inset-0 flex flex-col items-center justify-center"
        style={{ fontFamily: "'IBM Plex Mono', monospace" }}
      >
        <span className="text-lg font-bold text-[#14181B] animate-[numberIn_0.3s_ease-out_0.6s_both]">
          <CountUp value={score} duration={900} />
        </span>
        <span className="text-[8px] font-semibold uppercase tracking-[0.15em] text-[#14181B]/40">score</span>
      </div>
    </div>
  );
}

/** A small illustrative mock of what a filed report actually looks like — score bars + summary lines. */
function ReportPreviewCard() {
  return (
    <div className="group relative overflow-hidden rounded-md border border-[#14181B]/12 bg-white p-6 transition-shadow duration-300 hover:shadow-[0_16px_36px_-16px_rgba(20,24,27,0.18)] sm:p-8">
      <div className="flex flex-col gap-8 sm:flex-row sm:items-center">
        <div className="flex-1">
          <SectionEyebrow>Inside every report</SectionEyebrow>
          <h3 className="mt-2 text-xl font-semibold tracking-tight" style={{ fontFamily: "'Space Grotesk', sans-serif" }}>
            A filed, scored, and readable PDF
          </h3>
          <p className="mt-2 max-w-sm text-sm leading-relaxed text-[#14181B]/60">
            Every audit closes out the same way — an overall score, a category-by-category
            breakdown, and a plain-English list of what to fix first.
          </p>
        </div>

        <div className="w-full max-w-[300px] shrink-0 rounded-sm border border-[#14181B]/12 bg-[#F1ECDF] p-5 transition-transform duration-300 group-hover:-translate-y-1.5 group-hover:rotate-[0.4deg]">
          <div className="flex items-center justify-between">
            <span
              className="text-[10px] font-semibold uppercase tracking-[0.2em] text-[#14181B]/40"
              style={{ fontFamily: "'IBM Plex Mono', monospace" }}
            >
              audit_report.pdf
            </span>
            <span className="h-2 w-2 rounded-full bg-[#1F5C45]" />
          </div>

          <div className="mt-4 flex items-center gap-4">
            <ScoreGauge score={82} />

            <div className="flex-1 space-y-2.5">
              {[
                { label: "SEO", w: 90, color: "#1F5C45" },
                { label: "A11y", w: 68, color: "#E4572E" },
                { label: "Perf", w: 78, color: "#1F5C45" },
                { label: "Sec", w: 95, color: "#1F5C45" },
              ].map((row, i) => (
                <div
                  key={row.label}
                  className="animate-[fadeIn_0.4s_ease-out_both]"
                  style={{ animationDelay: `${0.35 + i * 0.08}s` }}
                >
                  <div className="flex items-center justify-between text-[9px] font-semibold uppercase tracking-[0.15em] text-[#14181B]/45" style={{ fontFamily: "'IBM Plex Mono', monospace" }}>
                    <span>{row.label}</span>
                    <span>{row.w}</span>
                  </div>
                  <div className="mt-1 h-1.5 w-full overflow-hidden rounded-full bg-[#14181B]/10">
                    <span
                      className="block h-full origin-left rounded-full"
                      style={{
                        width: `${row.w}%`,
                        backgroundColor: row.color,
                        animation: `barGrowX 0.7s cubic-bezier(0.22,1,0.36,1) ${0.4 + i * 0.08}s both`,
                      }}
                    />
                  </div>
                </div>
              ))}
            </div>
          </div>

          <div className="mt-4 flex items-center gap-2 border-t border-dashed border-[#14181B]/15 pt-3 text-[10px] text-[#14181B]/50">
            <span className="text-[#1F5C45]">✓</span>
            3 checks passed · 2 flagged for review
          </div>
        </div>
      </div>
    </div>
  );
}

const FAQ_ITEMS = [
  {
    q: "What can I test?",
    a: "Run a full website audit with just a URL — no install or setup needed.",
  },
  {
    q: "How long does a scan take?",
    a: "Most website audits finish in a couple of minutes, depending on your plan depth.",
  },
  {
    q: "Can I re-download an old report?",
    a: "Yes — every scan is saved to your History page, and the original PDF stays downloadable there whenever you need it again.",
  },
  {
    q: "What happens if I switch plans?",
    a: "Your new plan applies to your very next scan — nothing else to reconfigure.",
  },
];

/** Single-open accordion, styled as filed questions rather than a generic FAQ widget. */
function FaqAccordion({ items }) {
  const [openIndex, setOpenIndex] = useState(0);

  return (
    <div className="mt-6 divide-y divide-[#14181B]/10 rounded-md border border-[#14181B]/12 bg-white">
      {items.map((item, i) => {
        const open = openIndex === i;
        return (
          <div key={item.q} style={{ animation: `fadeIn 0.4s ease-out ${0.05 + i * 0.05}s both` }}>
            <button
              type="button"
              onClick={() => setOpenIndex(open ? -1 : i)}
              aria-expanded={open}
              className="flex w-full items-center justify-between gap-4 p-5 text-left transition-colors duration-200 hover:bg-[#1F5C45]/[0.04]"
            >
              <span className="text-sm font-semibold text-[#14181B]" style={{ fontFamily: "'Space Grotesk', sans-serif" }}>
                {item.q}
              </span>
              <svg
                width="14"
                height="14"
                viewBox="0 0 24 24"
                fill="none"
                className="shrink-0 text-[#14181B]/40 transition-transform duration-300"
                style={{ transform: open ? "rotate(180deg)" : "rotate(0deg)" }}
              >
                <path d="M6 9l6 6 6-6" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" />
              </svg>
            </button>
            <div
              className="grid transition-[grid-template-rows] duration-300 ease-in-out"
              style={{ gridTemplateRows: open ? "1fr" : "0fr" }}
            >
              <div className="overflow-hidden">
                <p className="px-5 pb-5 text-xs leading-relaxed text-[#14181B]/60">{item.a}</p>
              </div>
            </div>
          </div>
        );
      })}
    </div>
  );
}

function SectionEyebrow({ children }) {
  return (
    <p
      className="text-[11px] font-semibold uppercase tracking-[0.25em] text-[#E4572E]"
      style={{ fontFamily: "'IBM Plex Mono', monospace" }}
    >
      {children}
    </p>
  );
}

function Reveal({ children, className = "" }) {
  const ref = useRef(null);
  const [visible, setVisible] = useState(false);

  useEffect(() => {
    const node = ref.current;
    if (!node) return;
    const observer = new IntersectionObserver(
      ([entry]) => {
        if (entry.isIntersecting) {
          setVisible(true);
          observer.disconnect();
        }
      },
      { threshold: 0.15 }
    );
    observer.observe(node);
    return () => observer.disconnect();
  }, []);

  return (
    <div
      ref={ref}
      className={className}
      style={{
        animation: visible ? "revealUp 0.6s cubic-bezier(0.22,1,0.36,1) both" : "none",
        opacity: visible ? undefined : 0,
      }}
    >
      {children}
    </div>
  );
}

function CountUp({ value, duration = 800 }) {
  const [display, setDisplay] = useState(0);
  const frameRef = useRef(null);

  useEffect(() => {
    if (value == null) return;
    const start = performance.now();
    const to = value;

    function tick(now) {
      const progress = Math.min(1, (now - start) / duration);
      const eased = 1 - Math.pow(1 - progress, 3);
      setDisplay(Math.round(to * eased));
      if (progress < 1) frameRef.current = requestAnimationFrame(tick);
    }

    frameRef.current = requestAnimationFrame(tick);
    return () => cancelAnimationFrame(frameRef.current);
  }, [value, duration]);

  return <>{display}</>;
}

function LedgerCell({ label, value, hint, delay = 0 }) {
  const isNumber = typeof value === "number";
  return (
    <div
      style={{ animation: `fadeIn 0.4s ease-out ${delay}s both` }}
      className="group p-6 transition-colors duration-200 hover:bg-[#1F5C45]/[0.03]"
    >
      <p
        className="text-[10px] font-semibold uppercase tracking-[0.2em] text-[#14181B]/40"
        style={{ fontFamily: "'IBM Plex Mono', monospace" }}
      >
        {label}
      </p>
      <p
        className="mt-2 text-2xl font-semibold text-[#14181B] transition-transform duration-200 group-hover:translate-x-0.5"
        style={{ fontFamily: "'IBM Plex Mono', monospace" }}
      >
        {value == null ? (
          <span className="inline-block h-6 w-10 animate-pulse rounded bg-[#14181B]/10 align-middle" />
        ) : isNumber ? (
          <span className="animate-[numberIn_0.3s_ease-out_both]">
            <CountUp value={value} />
          </span>
        ) : (
          value
        )}
      </p>
      {hint && <p className="mt-1 text-xs text-[#14181B]/40">{hint}</p>}
    </div>
  );
}

function shortUrl(url) {
  try {
    const u = new URL(url);
    return u.hostname.replace(/^www\./, "") + (u.pathname !== "/" ? u.pathname : "");
  } catch {
    return url;
  }
}

function relativeTime(iso) {
  if (!iso) return "";
  const then = new Date(iso).getTime();
  if (Number.isNaN(then)) return "";
  const diffMs = Date.now() - then;
  const mins = Math.round(diffMs / 60000);
  if (mins < 1) return "just now";
  if (mins < 60) return `${mins}m ago`;
  const hours = Math.round(mins / 60);
  if (hours < 24) return `${hours}h ago`;
  const days = Math.round(hours / 24);
  if (days < 30) return `${days}d ago`;
  return new Date(iso).toLocaleDateString();
}

function HistoryRow({ entry, delay = 0 }) {
  const score = entry.health_score ?? 0;
  const passed = score >= 70;
  const dotColor = passed ? "#1F5C45" : score >= 40 ? "#E4572E" : "#E4572E";

  return (
    <div
      style={{ animation: `fadeIn 0.35s ease-out ${delay}s both` }}
      className="flex items-center gap-4 p-4 sm:p-5"
    >
      <span
        className="h-2 w-2 shrink-0 rounded-full"
        style={{ backgroundColor: dotColor }}
        aria-hidden="true"
      />
      <div className="min-w-0 flex-1">
        <p
          className="truncate text-sm font-semibold text-[#14181B]"
          style={{ fontFamily: "'IBM Plex Mono', monospace" }}
          title={entry.url}
        >
          {shortUrl(entry.url)}
        </p>
        <p className="mt-0.5 text-xs text-[#14181B]/45">{relativeTime(entry.created_at)}</p>
      </div>
      {entry.plan && (
        <span
          className="hidden shrink-0 rounded-full border border-[#14181B]/15 px-2.5 py-1 text-[10px] font-semibold uppercase tracking-[0.15em] text-[#14181B]/60 sm:inline-block"
          style={{ fontFamily: "'IBM Plex Mono', monospace" }}
        >
          {entry.plan}
        </span>
      )}
      <span
        className="shrink-0 text-sm font-semibold"
        style={{ fontFamily: "'IBM Plex Mono', monospace", color: dotColor }}
      >
        {score}
      </span>
    </div>
  );
}

function ProcessStep({ n, title, text, delay = 0 }) {
  return (
    <div
      style={{ animation: `fadeIn 0.45s ease-out ${delay}s both` }}
      className="relative bg-[#F1ECDF] px-2 pt-0 pb-2 sm:px-6"
    >
      <span
        className="relative z-10 inline-flex h-11 w-11 items-center justify-center rounded-full border-2 border-[#14181B] bg-[#F1ECDF] text-xs font-bold text-[#14181B]"
        style={{ fontFamily: "'IBM Plex Mono', monospace" }}
      >
        {n}
      </span>
      <h3 className="mt-4 text-sm font-semibold text-[#14181B]" style={{ fontFamily: "'Space Grotesk', sans-serif" }}>
        {title}
      </h3>
      <p className="mt-1.5 text-xs leading-relaxed text-[#14181B]/55">{text}</p>
    </div>
  );
}

const FEATURES = [
  { title: "SEO", text: "Meta tags, headings, sitemap, and on-page signals that affect search visibility." },
  { title: "Accessibility", text: "Contrast, alt text, ARIA attributes, and keyboard navigation checks." },
  { title: "Performance", text: "Load times, Core Web Vitals, and render-blocking resources." },
  { title: "Security", text: "SSL setup, exposed headers, and common vulnerability patterns." },
  { title: "Content & UX", text: "Broken links, missing images, and copy or layout inconsistencies." },
  { title: "Browser compatibility", text: "Rendering checks across common browsers and screen sizes." },
];

function ChecklistRow({ title, text, delay = 0 }) {
  return (
    <div
      style={{ animation: `fadeIn 0.4s ease-out ${delay}s both` }}
      className="group flex items-start gap-4 p-5 transition-colors duration-200 hover:bg-[#1F5C45]/[0.04]"
    >
      <span className="mt-0.5 flex h-6 w-6 shrink-0 items-center justify-center rounded-full border-2 border-[#1F5C45] text-[11px] font-bold text-[#1F5C45] transition-transform duration-300 group-hover:rotate-[360deg] group-hover:scale-110">
        ✓
      </span>
      <div>
        <h3 className="flex items-center gap-2 text-sm font-semibold text-[#14181B]" style={{ fontFamily: "'Space Grotesk', sans-serif" }}>
          {title}
        </h3>
        <p className="mt-1 text-xs leading-relaxed text-[#14181B]/55">{text}</p>
      </div>
    </div>
  );
}

const PRICING_PREVIEW = [
  { id: "basic", name: "Basic", price: 499, features: ["Basic SEO & accessibility", "Availability check", "Basic PDF report"] },
  {
    id: "standard",
    name: "Standard",
    price: 999,
    features: ["Full functional testing", "Advanced SEO & accessibility", "AI recommendations"],
    highlighted: true,
  },
  { id: "premium", name: "Premium", price: 1999, features: ["Full security audit", "Content, UX & CRO audits", "Combined full audit report"] },
];

/** Pricing card styled like a perforated audit ticket / receipt stub. */
function TicketCard({ id, name, price, features, highlighted, isCurrent, delay = 0 }) {
  return (
    <div
      style={{ animation: `cardRise 0.5s cubic-bezier(0.22,1,0.36,1) ${delay}s both` }}
      className={`group relative flex flex-col rounded-md p-6 transition-all duration-300 hover:-translate-y-1.5 hover:rotate-[0.3deg] ${
        highlighted ? "border-2 border-[#E4572E] bg-white shadow-[0_8px_24px_-8px_rgba(228,87,46,0.35)]" : "border border-[#14181B]/12 bg-white"
      }`}
    >
      {/* perforation edge */}
      <div
        className="pointer-events-none absolute -top-[7px] left-0 right-0 flex justify-between px-2"
        aria-hidden="true"
      >
        {Array.from({ length: 14 }).map((_, i) => (
          <span key={i} className="h-3.5 w-3.5 rounded-full bg-[#F1ECDF]" />
        ))}
      </div>

      {highlighted && (
        <span
          className="absolute -top-3 right-4 rounded-full bg-[#E4572E] px-3 py-1 text-[10px] font-bold uppercase tracking-wide text-white"
          style={{ fontFamily: "'IBM Plex Mono', monospace" }}
        >
          Most popular
        </span>
      )}
      {isCurrent && (
        <span
          className="absolute -top-3 left-4 rounded-full bg-[#14181B] px-3 py-1 text-[10px] font-bold uppercase tracking-wide text-white"
          style={{ fontFamily: "'IBM Plex Mono', monospace" }}
        >
          Your plan
        </span>
      )}

      <h3 className="mt-2 text-sm font-semibold text-[#14181B]" style={{ fontFamily: "'Space Grotesk', sans-serif" }}>
        {name}
      </h3>
      <div className="mt-2 flex items-baseline gap-1">
        <span className="text-2xl font-bold text-[#14181B]" style={{ fontFamily: "'IBM Plex Mono', monospace" }}>
          ₹{price}
        </span>
        <span className="text-xs text-[#14181B]/40">/ report</span>
      </div>

      <ul className="mt-4 flex-1 space-y-2 border-t border-dashed border-[#14181B]/15 pt-4">
        {features.map((f) => (
          <li key={f} className="flex items-start gap-2 text-xs text-[#14181B]/70">
            <span className="mt-0.5 text-[#1F5C45]">✓</span>
            {f}
          </li>
        ))}
      </ul>

      <Link
        to={`/checkout?plan=${id}`}
        className={`mt-5 w-full rounded-sm py-2.5 text-center text-xs font-semibold transition-all duration-200 hover:scale-[1.02] active:scale-[0.98] ${
          highlighted ? "bg-[#E4572E] text-white hover:bg-[#F16A40]" : "bg-[#14181B] text-white hover:bg-black"
        }`}
      >
        {isCurrent ? "Current plan" : `Choose ${name}`}
      </Link>
    </div>
  );
}

function DirectoryCell({ label, value, href, delay = 0, className = "" }) {
  const Wrapper = href ? "a" : "div";
  return (
    <Wrapper
      {...(href ? { href } : {})}
      style={{ animation: `fadeIn 0.4s ease-out ${delay}s both` }}
      className={`group rounded-md p-6 transition-colors duration-200 hover:bg-[#1F5C45]/[0.04] ${className}`}
    >
      <p
        className="text-[10px] font-semibold uppercase tracking-[0.2em] text-[#14181B]/40"
        style={{ fontFamily: "'IBM Plex Mono', monospace" }}
      >
        {label}
      </p>
      <p className="mt-1 text-sm font-semibold text-[#14181B] transition-transform duration-200 group-hover:translate-x-0.5">
        {value}
      </p>
    </Wrapper>
  );
}

function Footer() {
  const year = new Date().getFullYear();

  return (
    <footer className="relative mt-4 border-t border-[#14181B]/10 bg-[#14181B] text-white">
      <div className="relative mx-auto max-w-6xl px-4 py-12 sm:px-6">
        <div className="grid grid-cols-2 gap-8 sm:grid-cols-4">
          <div className="col-span-2 sm:col-span-1">
            <p className="text-lg font-semibold text-white" style={{ fontFamily: "'Space Grotesk', sans-serif" }}>
              TestPilot
            </p>
            <p className="mt-2 max-w-[220px] text-xs leading-relaxed text-white/55">
              Automated website testing across SEO, accessibility, performance, and security.
            </p>
          </div>

          <div>
            <p
              className="text-[11px] font-semibold uppercase tracking-[0.2em] text-[#E4572E]"
              style={{ fontFamily: "'IBM Plex Mono', monospace" }}
            >
              Product
            </p>
            <ul className="mt-3 space-y-2 text-xs text-white/60">
              <li><Link to="/dashboard" className="transition-colors duration-200 hover:text-white">Dashboard</Link></li>
              <li><Link to="/test" className="transition-colors duration-200 hover:text-white">Test a website</Link></li>
              <li><Link to="/pricing" className="transition-colors duration-200 hover:text-white">Pricing</Link></li>
            </ul>
          </div>

          <div>
            <p
              className="text-[11px] font-semibold uppercase tracking-[0.2em] text-[#E4572E]"
              style={{ fontFamily: "'IBM Plex Mono', monospace" }}
            >
              Company
            </p>
            <ul className="mt-3 space-y-2 text-xs text-white/60">
              <li><Link to="/about" className="transition-colors duration-200 hover:text-white">About</Link></li>
              <li><Link to="/privacy" className="transition-colors duration-200 hover:text-white">Privacy Policy</Link></li>
              <li><Link to="/terms" className="transition-colors duration-200 hover:text-white">Terms of Service</Link></li>
            </ul>
          </div>

          <div>
            <p
              className="text-[11px] font-semibold uppercase tracking-[0.2em] text-[#E4572E]"
              style={{ fontFamily: "'IBM Plex Mono', monospace" }}
            >
              Contact
            </p>
            <ul className="mt-3 space-y-2 text-xs text-white/60">
              <li><a href="mailto:support@TestPilot.com" className="transition-colors duration-200 hover:text-white">support@TestPilot.com</a></li>             
            </ul>
          </div>
        </div>

        <div className="mt-10 flex flex-col items-center justify-between gap-3 border-t border-white/10 pt-6 text-xs text-white/40 sm:flex-row">
          <p style={{ fontFamily: "'IBM Plex Mono', monospace" }}>© {year} TestPilot. All rights reserved.</p>
          <p className="flex items-center gap-1">
            Made with <span className="text-[#E4572E]">♥</span> in India
          </p>
        </div>
      </div>
    </footer>
  );
}

/* ------------------------------------------------------------------ */
/* Design plan, for reference                                          */
/*                                                                      */
/* Subject: an automated website-audit tool. The old draft borrowed a   */
/* generic "premium spa" cream+gold palette that had nothing to do with */
/* testing software. This pass leans into the actual world of an audit: */
/* inspection reports, checklists, tickets, ink stamps, live logs.      */
/*                                                                      */
/* Color   ink #14181B · paper #F1ECDF · card #FFFFFF ·                 */
/*         flag #E4572E (issues/CTA) · pass #1F5C45 (checks) ·          */
/*         hairline rgba(20,24,27,.12)                                  */
/* Type    Space Grotesk (headlines, technical/confident) +             */
/*         IBM Plex Mono (scores, labels, log lines — reads like data)  */
/* Layout  ledger rows and dashed/perforated dividers instead of        */
/*         floating shadow cards; hairline borders throughout           */
/* Signature  a scan-line beam sweeps once down the hero on load, next  */
/*         to a live-updating mono "scan.log" readout, and a rotated    */
/*         ink stamp in the corner marks the account's plan tier —      */
/*         the page reads as a report being generated in front of you  */
/* ------------------------------------------------------------------ */