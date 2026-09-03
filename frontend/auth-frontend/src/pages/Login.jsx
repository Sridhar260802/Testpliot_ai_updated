// src/pages/Login.jsx
import AuthCard from "../components/auth/AuthCard";

export default function Login() {
  return (
    <div className="flex min-h-screen items-center justify-center bg-[#0b3327] px-4 py-10">
      <div className="w-full">
        <p className="mb-4 text-center text-xs font-semibold uppercase tracking-[0.25em] text-[#d4af37]">
          TestPilot
        </p>
        <AuthCard initialMode="signin" />
      </div>
    </div>
  );
}
