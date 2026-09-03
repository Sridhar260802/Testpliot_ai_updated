// src/pages/ForgotPassword.jsx
// UI for the "Forgot password?" flow, styled to match the AuthCard theme.
// Calls authService.requestPasswordReset, which will 404/network-error
// until the backend endpoint exists — expected, not faked as success.

import { useState } from "react";
import { Link } from "react-router-dom";
import { requestPasswordReset, AuthError } from "../services/authService";
import { validateEmail } from "../utils/validation";

const BRAND_NAME = "TestPilot";

export default function ForgotPassword() {
  const [email, setEmail] = useState("");
  const [error, setError] = useState("");
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [submitted, setSubmitted] = useState(false);

  async function handleSubmit(e) {
    e.preventDefault();
    if (isSubmitting) return;

    const emailError = validateEmail(email);
    if (emailError) {
      setError(emailError);
      return;
    }

    setIsSubmitting(true);
    setError("");
    try {
      await requestPasswordReset({ email: email.trim() });
      setSubmitted(true);
    } catch (err) {
      setError(err instanceof AuthError ? err.message : "Unable to send reset link. Please try again.");
    } finally {
      setIsSubmitting(false);
    }
  }

  return (
    <div className="flex min-h-screen items-center justify-center bg-[#0b3327] px-4 py-10">
      <div className="w-full max-w-sm">
        <p className="mb-4 text-center text-xs font-semibold uppercase tracking-[0.25em] text-[#d4af37]">
          {BRAND_NAME}
        </p>

        <div className="rounded-3xl bg-[#F7F1E1] p-8 shadow-2xl">
          <h1 className="mb-1 inline-block border-b-2 border-[#d4af37] pb-2 text-lg font-semibold text-[#0b3327]">
            Reset password
          </h1>
          {!submitted && (
            <p className="mt-3 text-sm text-[#0b3327]/60">Enter your email and we'll send you a reset link.</p>
          )}

          {submitted ? (
            <div role="status" className="mt-6 rounded-md border border-green-200 bg-green-50 px-3.5 py-3 text-sm text-green-700">
              If an account exists for <strong>{email}</strong>, a reset link is on its way.
            </div>
          ) : (
            <form onSubmit={handleSubmit} noValidate className="mt-6 space-y-5">
              {error && (
                <div role="alert" className="rounded-md border border-red-200 bg-red-50 px-3 py-2 text-xs text-red-700">
                  {error}
                </div>
              )}

              <div className="border-b border-[#0b3327]/20 pb-2 focus-within:border-[#0b3327]">
                <input
                  id="forgot-email"
                  type="email"
                  autoComplete="email"
                  placeholder="Email address"
                  value={email}
                  onChange={(e) => {
                    setEmail(e.target.value);
                    if (error) setError("");
                  }}
                  disabled={isSubmitting}
                  aria-invalid={Boolean(error)}
                  className="w-full border-0 bg-transparent p-0 text-sm text-[#0b3327] outline-none placeholder:text-[#0b3327]/40 disabled:opacity-50"
                />
              </div>

              <button
                type="submit"
                disabled={isSubmitting}
                className="w-full rounded-full bg-gradient-to-r from-[#0f4436] to-[#061f17] py-3 text-sm font-semibold text-white shadow-md transition hover:shadow-lg disabled:cursor-not-allowed disabled:opacity-60"
              >
                {isSubmitting ? "Sending…" : "Send reset link"}
              </button>
            </form>
          )}
        </div>

        <div className="mt-6 text-center text-sm text-white/80">
          <Link to="/login" className="font-semibold text-[#d4af37] hover:text-white">
            Back to sign in
          </Link>
        </div>
      </div>
    </div>
  );
}
