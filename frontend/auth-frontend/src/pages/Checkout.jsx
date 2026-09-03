// src/pages/Checkout.jsx
import { useState } from "react";
import { useSearchParams, useNavigate, Link } from "react-router-dom";
import Navbar from "../components/Navbar";
import { openRazorpayCheckout } from "../services/paymentService";
import { updatePlan, getStoredUser } from "../services/authService";

const PLAN_DETAILS = {
  basic: { name: "Basic", price: 499 },
  standard: { name: "Standard", price: 999 },
  premium: { name: "Premium", price: 1999 },
};

// idle -> processing -> success | error
export default function Checkout() {
  const [searchParams] = useSearchParams();
  const navigate = useNavigate();
  const planId = searchParams.get("plan") || "basic";
  const plan = PLAN_DETAILS[planId] || PLAN_DETAILS.basic;
  const user = getStoredUser();

  const [status, setStatus] = useState("idle");
  const [errorMessage, setErrorMessage] = useState("");
  const [paidAt, setPaidAt] = useState(null);

  async function handlePay() {
    setStatus("processing");
    setErrorMessage("");
    try {
      await openRazorpayCheckout({
        amountInRupees: plan.price,
        planName: plan.name,
        userEmail: user?.email,
        userName: user?.username,
      });
      // Payment succeeded on Razorpay's side — now record the upgrade.
      await updatePlan(planId);
      setPaidAt(new Date());
      setStatus("success");
    } catch (err) {
      setStatus("error");
      setErrorMessage(err.message || "Payment could not be completed.");
    }
  }

  return (
    <div className="min-h-screen bg-[#F7F1E1]">
      <Navbar />

      <div className="mx-auto max-w-4xl px-4 py-12 sm:px-6">
        {status === "idle" && (
          <IdleCheckout plan={plan} user={user} onPay={handlePay} />
        )}

        {status === "processing" && <ProcessingScreen plan={plan} user={user} />}

        {status === "success" && (
          <SuccessScreen
            plan={plan}
            user={user}
            paidAt={paidAt}
            onContinue={() => navigate("/test")}
          />
        )}

        {status === "error" && (
          <ErrorScreen message={errorMessage} onRetry={() => setStatus("idle")} />
        )}

        {status === "idle" && (
          <div className="mt-8 text-center">
            <Link to="/pricing" className="text-xs font-medium text-[#0b3327]/50 underline underline-offset-2">
              Back to plans
            </Link>
          </div>
        )}
      </div>

      <style>{`
        @keyframes fadeIn { from { opacity: 0; transform: translateY(8px); } to { opacity: 1; transform: translateY(0); } }
        @keyframes checkPop { 0% { transform: scale(0.5); opacity: 0; } 70% { transform: scale(1.1); } 100% { transform: scale(1); opacity: 1; } }
        @keyframes cardGlow { 0%, 100% { box-shadow: 0 0 0 0 rgba(212,175,55,0.0), 0 20px 45px -15px rgba(11,51,39,0.5); } 50% { box-shadow: 0 0 40px 8px rgba(212,175,55,0.35), 0 20px 45px -15px rgba(11,51,39,0.5); } }
        @keyframes slipDrop { from { opacity: 0; transform: translateY(-14px); } to { opacity: 1; transform: translateY(0); } }
        @keyframes shimmer { 0% { background-position: -200% 0; } 100% { background-position: 200% 0; } }
      `}</style>
    </div>
  );
}

/* ---------------------------------- Idle ---------------------------------- */

function IdleCheckout({ plan, user, onPay }) {
  return (
    <div className="animate-[fadeIn_0.4s_ease-out]">
      <p className="text-center text-xs font-semibold uppercase tracking-[0.25em] text-[#0b3327]/50">Checkout</p>
      <h1 className="mt-2 text-center font-serif text-3xl font-medium text-[#0b3327]">Complete your purchase</h1>

      <div className="mt-10 grid grid-cols-1 gap-6 lg:grid-cols-2">
        {/* Left: order summary */}
        <div className="rounded-3xl bg-white p-6 shadow-sm sm:p-8">
          <h2 className="text-sm font-semibold uppercase tracking-wide text-[#0b3327]/50">Order summary</h2>

          <div className="mt-5 divide-y divide-[#0b3327]/8">
            <SummaryRow label="Plan" value={`${plan.name} Plan`} />
            <SummaryRow label="Billed to" value={user?.email || "your account"} />
            <SummaryRow label="Payment method" value="Razorpay Secure Checkout" />
          </div>

          <div className="mt-5 flex items-center justify-between rounded-2xl bg-[#F7F1E1] px-5 py-4">
            <span className="text-sm font-medium text-[#0b3327]/70">Total due</span>
            <span className="text-2xl font-bold text-[#0b3327]">₹{plan.price}</span>
          </div>

          <button
            type="button"
            onClick={onPay}
            className="mt-6 w-full rounded-full bg-gradient-to-r from-[#0f4436] to-[#061f17] py-3.5 text-sm font-semibold text-white shadow-md transition hover:scale-[1.01] hover:shadow-lg active:scale-[0.99]"
          >
            Pay ₹{plan.price}
          </button>

          <div className="mt-4 flex items-center justify-center gap-2 text-[11px] text-[#0b3327]/40">
            <ShieldIcon />
            Secured by Razorpay · Cards, UPI &amp; Netbanking supported
          </div>
        </div>

        {/* Right: live card preview */}
        <div className="flex flex-col items-center justify-center rounded-3xl bg-white p-6 shadow-sm sm:p-8">
          <h2 className="mb-6 self-start text-sm font-semibold uppercase tracking-wide text-[#0b3327]/50">
            Your TestPilot Pass
          </h2>
          <PaymentCard user={user} plan={plan} />
          <ul className="mt-8 w-full space-y-3 text-xs text-[#0b3327]/60">
            <PerkRow text="Instant activation after payment" />
            <PerkRow text="Full PDF report included" />
            <PerkRow text="Upgrade or cancel any time" />
          </ul>
        </div>
      </div>
    </div>
  );
}

function SummaryRow({ label, value }) {
  return (
    <div className="flex items-center justify-between py-3 text-sm">
      <span className="text-[#0b3327]/50">{label}</span>
      <span className="font-medium text-[#0b3327]">{value}</span>
    </div>
  );
}

function PerkRow({ text }) {
  return (
    <li className="flex items-center gap-2">
      <svg width="14" height="14" viewBox="0 0 24 24" fill="none" aria-hidden="true" className="shrink-0">
        <path d="M5 13l4 4L19 7" stroke="#d4af37" strokeWidth="2.6" strokeLinecap="round" strokeLinejoin="round" />
      </svg>
      {text}
    </li>
  );
}

/* ------------------------------- Card preview ------------------------------ */

function PaymentCard({ user, plan, glowing = false }) {
  const name = (user?.username || "CARDHOLDER").toUpperCase();
  return (
    <div
      className="relative h-52 w-full max-w-sm overflow-hidden rounded-2xl bg-gradient-to-br from-[#0f4436] via-[#0b3327] to-[#061f17] p-6 text-white"
      style={{ animation: glowing ? "cardGlow 1.8s ease-in-out infinite" : "none" }}
    >
      <div
        className="pointer-events-none absolute inset-0 opacity-20"
        style={{
          backgroundImage:
            "linear-gradient(120deg, transparent 30%, rgba(212,175,55,0.35) 45%, transparent 60%)",
          backgroundSize: "200% 100%",
          animation: "shimmer 3.5s ease-in-out infinite",
        }}
        aria-hidden="true"
      />

      <div className="relative flex items-start justify-between">
        <div className="h-8 w-10 rounded-md bg-gradient-to-br from-[#d4af37] to-[#a9812a]" aria-hidden="true" />
        <svg width="20" height="20" viewBox="0 0 24 24" fill="none" aria-hidden="true" className="opacity-70">
          <path
            d="M6 8a8.5 8.5 0 0112 0M8.3 10.7a5 5 0 017.4 0M10.6 13.3a1.7 1.7 0 012.8 0"
            stroke="white"
            strokeWidth="1.6"
            strokeLinecap="round"
          />
        </svg>
      </div>

      <p className="relative mt-6 text-[10px] uppercase tracking-[0.2em] text-white/40">Plan pass</p>
      <p className="relative mt-1 font-mono text-lg tracking-[0.2em] text-white/90">•••• •••• •••• ••••</p>

      <div className="relative mt-5 flex items-end justify-between">
        <div>
          <p className="text-[10px] uppercase tracking-[0.15em] text-white/40">Name</p>
          <p className="text-sm font-medium">{name}</p>
        </div>
        <div>
          <p className="text-[10px] uppercase tracking-[0.15em] text-white/40">Plan</p>
          <p className="text-sm font-medium">{plan.name}</p>
        </div>
        <p className="font-serif text-lg italic text-[#d4af37]">TestPilot</p>
      </div>
    </div>
  );
}

/* ------------------------------- Processing -------------------------------- */

function ProcessingScreen({ plan, user }) {
  return (
    <div className="flex flex-col items-center justify-center py-10 text-center animate-[fadeIn_0.4s_ease-out]">
      <PaymentCard user={user} plan={plan} glowing />
      <div className="mt-8 h-8 w-8 animate-spin rounded-full border-[3px] border-[#0b3327]/15 border-t-[#d4af37]" />
      <p className="mt-6 text-sm font-medium text-[#0b3327]">Processing secure transaction…</p>
      <p className="mt-1 text-xs text-[#0b3327]/50">Please don't close this window.</p>
    </div>
  );
}

/* --------------------------------- Success ---------------------------------- */

function SuccessScreen({ plan, user, paidAt, onContinue }) {
  const date = (paidAt || new Date()).toLocaleDateString();
  const time = (paidAt || new Date()).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" });

  return (
    <div className="flex flex-col items-center py-6 text-center animate-[fadeIn_0.4s_ease-out]">
      {/* Receipt slip */}
      <div
        className="mb-[-18px] w-full max-w-sm rounded-t-xl border border-b-0 border-[#0b3327]/10 bg-white px-5 pb-6 pt-4 text-left shadow-sm"
        style={{ animation: "slipDrop 0.5s cubic-bezier(0.22,1,0.36,1) both" }}
      >
        <p className="text-center text-xs font-bold uppercase tracking-[0.2em] text-[#0b3327]">Payment receipt</p>
        <div className="mt-3 space-y-1.5 text-xs text-[#0b3327]/60">
          <div className="flex justify-between">
            <span>Date</span>
            <span className="font-medium text-[#0b3327]">{date}</span>
          </div>
          <div className="flex justify-between">
            <span>Time</span>
            <span className="font-medium text-[#0b3327]">{time}</span>
          </div>
          <div className="flex justify-between">
            <span>Plan</span>
            <span className="font-medium text-[#0b3327]">{plan.name}</span>
          </div>
          <div className="flex justify-between">
            <span>Amount</span>
            <span className="font-medium text-[#0b3327]">₹{plan.price}</span>
          </div>
        </div>
      </div>

      <div className="relative z-10 w-full max-w-sm">
        <PaymentCard user={user} plan={plan} />
      </div>

      <div className="mt-8 flex h-16 w-16 items-center justify-center rounded-full bg-green-100">
        <svg width="28" height="28" viewBox="0 0 24 24" fill="none" aria-hidden="true" className="animate-[checkPop_0.5s_ease-out]">
          <path d="M5 13l4 4L19 7" stroke="#16a34a" strokeWidth="3" strokeLinecap="round" strokeLinejoin="round" />
        </svg>
      </div>
      <h2 className="mt-4 text-xl font-semibold text-[#0b3327]">Payment successful!</h2>
      <p className="mt-2 max-w-xs text-sm text-[#0b3327]/60">
        You're now on the <strong>{plan.name}</strong> plan. Let's run your first website test.
      </p>

      <button
        type="button"
        onClick={onContinue}
        className="mt-8 w-full max-w-sm rounded-full bg-gradient-to-r from-[#0f4436] to-[#061f17] py-3.5 text-sm font-semibold text-white shadow-md transition hover:shadow-lg"
      >
        Test your website now
      </button>
    </div>
  );
}

/* ---------------------------------- Error ----------------------------------- */

function ErrorScreen({ message, onRetry }) {
  return (
    <div className="mx-auto max-w-sm text-center animate-[fadeIn_0.4s_ease-out]">
      <div className="mx-auto mb-4 flex h-16 w-16 items-center justify-center rounded-full bg-red-100">
        <svg width="28" height="28" viewBox="0 0 24 24" fill="none" aria-hidden="true">
          <path d="M6 6l12 12M18 6L6 18" stroke="#dc2626" strokeWidth="2.4" strokeLinecap="round" />
        </svg>
      </div>
      <h2 className="text-lg font-semibold text-[#0b3327]">Payment not completed</h2>
      <p className="mt-2 text-sm text-[#0b3327]/60">{message}</p>
      <button
        type="button"
        onClick={onRetry}
        className="mt-6 rounded-full bg-[#0b3327] px-6 py-2.5 text-sm font-semibold text-white hover:bg-black"
      >
        Try again
      </button>
      <div className="mt-6">
        <Link to="/pricing" className="text-xs font-medium text-[#0b3327]/50 underline underline-offset-2">
          Back to plans
        </Link>
      </div>
    </div>
  );
}

function ShieldIcon() {
  return (
    <svg width="12" height="12" viewBox="0 0 24 24" fill="none" aria-hidden="true">
      <path
        d="M12 2l8 4v6c0 5-3.4 8.7-8 10-4.6-1.3-8-5-8-10V6l8-4z"
        stroke="currentColor"
        strokeWidth="1.8"
        strokeLinecap="round"
        strokeLinejoin="round"
      />
    </svg>
  );
}