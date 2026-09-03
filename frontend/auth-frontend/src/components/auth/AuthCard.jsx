// src/components/auth/AuthCard.jsx
// Single card containing both Sign In and Sign Up forms with a sliding
// diagonal "blade" panel that travels between them (desktop). On mobile
// the blade is hidden and the active form is shown full-width with a
// simple toggle link, since the diagonal-slide effect needs the extra
// horizontal space to read well.
//
// Real forms are always mounted underneath — the blade only slides over
// whichever one is currently inactive. Submits go through the same
// authService used everywhere else in the app.

import { useState } from "react";
import { useNavigate, Link } from "react-router-dom";
import { login, signup, AuthError } from "../../services/authService";
import { validateEmail, validatePassword, validateConfirmPassword } from "../../utils/validation";
import GoogleSignInButton from "./GoogleSignInButton";

const BRAND_NAME = "TestPilot";

export default function AuthCard({ initialMode = "signin" }) {
  const [mode, setMode] = useState(initialMode);

  return (
    <div className="relative mx-auto w-full max-w-4xl overflow-hidden rounded-[2rem] bg-[#F7F1E1] shadow-2xl lg:flex lg:min-h-[560px]">
      <div className={`w-full p-8 sm:p-10 lg:w-1/2 lg:p-12 ${mode === "signin" ? "block" : "hidden lg:block"}`}>
        <SignInPanel onSwitch={() => setMode("signup")} />
      </div>

      <div className={`w-full p-8 sm:p-10 lg:w-1/2 lg:p-12 ${mode === "signup" ? "block" : "hidden lg:block"}`}>
        <SignUpPanel onSwitch={() => setMode("signin")} />
      </div>

      {/* Sliding blade — desktop only. A solid panel with a clip-path
          parallelogram: the OUTER edge (flush with the card's true left/right
          boundary) stays straight, only the INNER edge (facing the visible
          form) is slanted, and the inset is kept smaller than the form's own
          padding so no form content can ever peek through the cut. */}
      <div
        className="pointer-events-none absolute left-0 top-0 hidden h-full w-1/2 transition-transform duration-[750ms] ease-[cubic-bezier(0.65,0,0.35,1)] lg:block"
        style={{ transform: mode === "signin" ? "translateX(100%)" : "translateX(0%)" }}
      >
        <div
          className="pointer-events-auto flex h-full w-full flex-col justify-between bg-gradient-to-br from-[#0f4436] via-[#0b3327] to-[#061f17] p-10 text-white transition-[clip-path] duration-[750ms] ease-[cubic-bezier(0.65,0,0.35,1)]"
          style={{
            clipPath:
              mode === "signin"
                ? "polygon(6% 0%, 100% 0%, 100% 100%, 0% 100%)"
                : "polygon(0% 0%, 94% 0%, 100% 100%, 0% 100%)",
          }}
        >
          <div />

          <div className="max-w-[220px]">
            <h2 className="text-3xl font-serif font-medium leading-tight sm:text-4xl">
              {mode === "signin" ? (
                <>
                  Welcome
                  <br />
                  <span className="italic text-[#d4af37]">back.</span>
                </>
              ) : (
                <>
                  Join
                  <br />
                  <span className="italic text-[#d4af37]">us today.</span>
                </>
              )}
            </h2>
            <p className="mt-4 text-sm text-white/70">
              {mode === "signin"
                ? "Your boards, your drafts, and your people are exactly where you left them."
                : "Create an account and pick up right where you'll leave off, every time."}
            </p>
          </div>

          <button
            type="button"
            onClick={() => setMode(mode === "signin" ? "signup" : "signin")}
            className="self-start text-xs font-medium text-white/70 underline decoration-[#d4af37]/60 underline-offset-4 hover:text-white"
          >
            {mode === "signin" ? "New here? Create an account" : "Already have an account? Sign in"}
          </button>
        </div>
      </div>
    </div>
  );
}

function SignInPanel({ onSwitch }) {
  const navigate = useNavigate();
  const [values, setValues] = useState({ email: "", password: "" });
  const [errors, setErrors] = useState({ email: "", password: "", form: "" });
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [remember, setRemember] = useState(true);

  function handleChange(field) {
    return (e) => {
      setValues((v) => ({ ...v, [field]: e.target.value }));
      if (errors[field]) setErrors((er) => ({ ...er, [field]: "" }));
    };
  }

  async function handleSubmit(e) {
    e.preventDefault();
    if (isSubmitting) return;

    const emailError = validateEmail(values.email);
    const passwordError = values.password ? "" : "Password is required";
    if (emailError || passwordError) {
      setErrors({ email: emailError, password: passwordError, form: "" });
      return;
    }

    setIsSubmitting(true);
    setErrors({ email: "", password: "", form: "" });
    try {
      await login({ email: values.email.trim(), password: values.password });
      navigate("/dashboard");
    } catch (err) {
      const message = err instanceof AuthError ? err.message : "Unable to sign in. Please try again.";
      if (err instanceof AuthError && err.field) {
        setErrors((er) => ({ ...er, [err.field]: message }));
      } else {
        setErrors((er) => ({ ...er, form: message }));
      }
    } finally {
      setIsSubmitting(false);
    }
  }

  return (
    <div className="mx-auto flex h-full max-w-sm flex-col justify-center">
      <h1 className="mb-1 border-b-2 border-[#d4af37] pb-2 text-lg font-semibold text-[#0b3327]" style={{ display: "inline-block" }}>
        Sign in
      </h1>

      {errors.form && (
        <div role="alert" className="mt-4 rounded-md border border-red-200 bg-red-50 px-3 py-2 text-xs text-red-700">
          {errors.form}
        </div>
      )}

      <form onSubmit={handleSubmit} noValidate className="mt-6 space-y-5">
        <UnderlineInput
          id="signin-email"
          type="email"
          label="Username or email"
          value={values.email}
          onChange={handleChange("email")}
          error={errors.email}
          disabled={isSubmitting}
          autoComplete="email"
          icon={<PersonIcon />}
        />
        <UnderlinePasswordInput
          id="signin-password"
          label="Password"
          value={values.password}
          onChange={handleChange("password")}
          error={errors.password}
          disabled={isSubmitting}
        />

        <div className="flex items-center justify-between text-xs">
          <label className="flex items-center gap-2 text-[#0b3327]/70">
            <input
              type="checkbox"
              checked={remember}
              onChange={(e) => setRemember(e.target.checked)}
              className="h-3.5 w-3.5 rounded border-[#0b3327]/30 text-[#0b3327] focus:ring-[#d4af37]"
            />
            Keep me signed in
          </label>
          <Link to="/forgot-password" className="font-medium text-[#0b3327] underline underline-offset-2 hover:text-[#d4af37]">
            Forgot password?
          </Link>
        </div>

        <button
          type="submit"
          disabled={isSubmitting}
          className="w-full rounded-full bg-gradient-to-r from-[#0f4436] to-[#061f17] py-3 text-sm font-semibold text-white shadow-md transition hover:shadow-lg disabled:cursor-not-allowed disabled:opacity-60"
        >
          {isSubmitting ? "Signing in…" : "Sign in"}
        </button>
      </form>

      <div className="mt-4">
        <GoogleSignInButton
          disabled={isSubmitting}
          onSuccess={() => navigate("/dashboard")}
          onError={(message) => setErrors((er) => ({ ...er, form: message }))}
        />
      </div>

      <p className="mt-6 text-xs text-[#0b3327]/60 lg:hidden">
        New to {BRAND_NAME}?{" "}
        <button type="button" onClick={onSwitch} className="font-semibold text-[#0b3327] underline underline-offset-2">
          Create an account
        </button>
      </p>
    </div>
  );
}

function SignUpPanel({ onSwitch }) {
  const navigate = useNavigate();
  const [values, setValues] = useState({ username: "", email: "", password: "", confirmPassword: "" });
  const [errors, setErrors] = useState({ username: "", email: "", password: "", confirmPassword: "", form: "" });
  const [isSubmitting, setIsSubmitting] = useState(false);

  function handleChange(field) {
    return (e) => {
      setValues((v) => ({ ...v, [field]: e.target.value }));
      if (errors[field]) setErrors((er) => ({ ...er, [field]: "" }));
    };
  }

  async function handleSubmit(e) {
    e.preventDefault();
    if (isSubmitting) return;

    const usernameError = values.username.trim() ? "" : "Name is required";
    const emailError = validateEmail(values.email);
    const passwordError = validatePassword(values.password);
    const confirmError = validateConfirmPassword(values.password, values.confirmPassword);
    if (usernameError || emailError || passwordError || confirmError) {
      setErrors({ username: usernameError, email: emailError, password: passwordError, confirmPassword: confirmError, form: "" });
      return;
    }

    setIsSubmitting(true);
    setErrors({ username: "", email: "", password: "", confirmPassword: "", form: "" });
    try {
      await signup({ username: values.username.trim(), email: values.email.trim(), password: values.password });
      navigate("/dashboard");
    } catch (err) {
      const message = err instanceof AuthError ? err.message : "Unable to create your account. Please try again.";
      if (err instanceof AuthError && err.field) {
        setErrors((er) => ({ ...er, [err.field]: message }));
      } else {
        setErrors((er) => ({ ...er, form: message }));
      }
    } finally {
      setIsSubmitting(false);
    }
  }

  return (
    <div className="mx-auto flex h-full max-w-sm flex-col justify-center">
      <h1 className="mb-1 border-b-2 border-[#d4af37] pb-2 text-lg font-semibold text-[#0b3327]" style={{ display: "inline-block" }}>
        Create account
      </h1>

      {errors.form && (
        <div role="alert" className="mt-4 rounded-md border border-red-200 bg-red-50 px-3 py-2 text-xs text-red-700">
          {errors.form}
        </div>
      )}

      <form onSubmit={handleSubmit} noValidate className="mt-6 space-y-5">
        <UnderlineInput
          id="signup-username"
          type="text"
          label="Full name"
          value={values.username}
          onChange={handleChange("username")}
          error={errors.username}
          disabled={isSubmitting}
          autoComplete="name"
          icon={<PersonIcon />}
        />
        <UnderlineInput
          id="signup-email"
          type="email"
          label="Email address"
          value={values.email}
          onChange={handleChange("email")}
          error={errors.email}
          disabled={isSubmitting}
          autoComplete="email"
          icon={<PersonIcon />}
        />
        <UnderlinePasswordInput
          id="signup-password"
          label="Password"
          value={values.password}
          onChange={handleChange("password")}
          error={errors.password}
          disabled={isSubmitting}
          autoComplete="new-password"
        />
        <UnderlinePasswordInput
          id="signup-confirm"
          label="Confirm password"
          value={values.confirmPassword}
          onChange={handleChange("confirmPassword")}
          error={errors.confirmPassword}
          disabled={isSubmitting}
          autoComplete="new-password"
        />

        <button
          type="submit"
          disabled={isSubmitting}
          className="w-full rounded-full bg-gradient-to-r from-[#0f4436] to-[#061f17] py-3 text-sm font-semibold text-white shadow-md transition hover:shadow-lg disabled:cursor-not-allowed disabled:opacity-60"
        >
          {isSubmitting ? "Creating account…" : "Create account"}
        </button>
      </form>

      <div className="mt-4">
        <GoogleSignInButton
          disabled={isSubmitting}
          onSuccess={() => navigate("/dashboard")}
          onError={(message) => setErrors((er) => ({ ...er, form: message }))}
        />
      </div>

      <p className="mt-6 text-xs text-[#0b3327]/60 lg:hidden">
        Already have an account?{" "}
        <button type="button" onClick={onSwitch} className="font-semibold text-[#0b3327] underline underline-offset-2">
          Sign in
        </button>
      </p>
    </div>
  );
}

function UnderlineInput({ id, label, type = "text", value, onChange, error, disabled, autoComplete, icon }) {
  return (
    <div>
      <label htmlFor={id} className="sr-only">
        {label}
      </label>
      <div className="flex items-center gap-2 border-b border-[#0b3327]/20 pb-2 focus-within:border-[#0b3327]">
        <input
          id={id}
          type={type}
          value={value}
          onChange={onChange}
          disabled={disabled}
          autoComplete={autoComplete}
          placeholder={label}
          aria-invalid={Boolean(error)}
          className="w-full border-0 bg-transparent p-0 text-sm text-[#0b3327] outline-none placeholder:text-[#0b3327]/40 disabled:opacity-50"
        />
        <span className="text-[#0b3327]/40">{icon}</span>
      </div>
      {error && <p className="mt-1.5 text-xs text-red-600">{error}</p>}
    </div>
  );
}

function UnderlinePasswordInput({ id, label, value, onChange, error, disabled, autoComplete = "current-password" }) {
  const [visible, setVisible] = useState(false);
  return (
    <div>
      <label htmlFor={id} className="sr-only">
        {label}
      </label>
      <div className="flex items-center gap-2 border-b border-[#0b3327]/20 pb-2 focus-within:border-[#0b3327]">
        <input
          id={id}
          type={visible ? "text" : "password"}
          value={value}
          onChange={onChange}
          disabled={disabled}
          autoComplete={autoComplete}
          placeholder={label}
          aria-invalid={Boolean(error)}
          className="w-full border-0 bg-transparent p-0 text-sm text-[#0b3327] outline-none placeholder:text-[#0b3327]/40 disabled:opacity-50"
        />
        <button
          type="button"
          onClick={() => setVisible((v) => !v)}
          disabled={disabled}
          aria-label={visible ? "Hide password" : "Show password"}
          className="text-[#0b3327]/40 hover:text-[#0b3327]"
        >
          {visible ? <EyeOffIcon /> : <EyeIcon />}
        </button>
      </div>
      {error && <p className="mt-1.5 text-xs text-red-600">{error}</p>}
    </div>
  );
}

function PersonIcon() {
  return (
    <svg width="16" height="16" viewBox="0 0 24 24" fill="none" aria-hidden="true">
      <circle cx="12" cy="8" r="4" stroke="currentColor" strokeWidth="1.8" />
      <path d="M4 20c0-3.3 3.6-6 8-6s8 2.7 8 6" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" />
    </svg>
  );
}

function EyeIcon() {
  return (
    <svg width="16" height="16" viewBox="0 0 24 24" fill="none" aria-hidden="true">
      <path
        d="M1 12s4-7 11-7 11 7 11 7-4 7-11 7-11-7-11-7Z"
        stroke="currentColor"
        strokeWidth="1.8"
        strokeLinecap="round"
        strokeLinejoin="round"
      />
      <circle cx="12" cy="12" r="3" stroke="currentColor" strokeWidth="1.8" />
    </svg>
  );
}

function EyeOffIcon() {
  return (
    <svg width="16" height="16" viewBox="0 0 24 24" fill="none" aria-hidden="true">
      <path
        d="M17.94 17.94A10.94 10.94 0 0 1 12 19c-7 0-11-7-11-7a20.4 20.4 0 0 1 4.22-5.36M9.9 4.24A10.6 10.6 0 0 1 12 4c7 0 11 7 11 7a20.5 20.5 0 0 1-2.34 3.31M14.12 14.12a3 3 0 1 1-4.24-4.24"
        stroke="currentColor"
        strokeWidth="1.8"
        strokeLinecap="round"
        strokeLinejoin="round"
      />
      <path d="M1 1l22 22" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" />
    </svg>
  );
}
