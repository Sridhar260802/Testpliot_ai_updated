// src/components/Navbar.jsx
import { Link, useNavigate, useLocation } from "react-router-dom";
import { logout, getStoredUser } from "../services/authService";

const BRAND_NAME = "TestPilot";

export default function Navbar() {
  const navigate = useNavigate();
  const location = useLocation();
  const user = getStoredUser();

  async function handleLogout() {
    await logout();
    navigate("/login");
  }

  const links = [
    { to: "/dashboard", label: "Home" },
    { to: "/test", label: "Website Test" },
    { to: "/history", label: "History" },
    { to: "/pricing", label: "Pricing" },
    { to: "/contact", label: "Contact Us" },
  ];

  return (
    <nav className="sticky top-0 z-20 border-b border-black/5 bg-[#0b3327]">
      <div className="mx-auto flex max-w-6xl items-center justify-between px-4 py-4 sm:px-6">
        <Link to="/dashboard" className="flex items-center gap-2">
          <svg width="20" height="20" viewBox="0 0 24 24" fill="none" aria-hidden="true">
            <path d="M12 2 3 7v6c0 5 4 8.5 9 9 5-.5 9-4 9-9V7l-9-5Z" stroke="#d4af37" strokeWidth="1.8" strokeLinejoin="round" />
            <path d="M8.5 12.5l2.5 2.5 4.5-5" stroke="#d4af37" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round" />
          </svg>
          <span className="text-sm font-semibold uppercase tracking-[0.15em] text-[#d4af37]">{BRAND_NAME}</span>
        </Link>

        <div className="hidden items-center gap-8 sm:flex">
          {links.map((link) => (
            <Link
              key={link.to}
              to={link.to}
              className={`text-sm font-medium transition ${
                location.pathname === link.to ? "text-[#d4af37]" : "text-white/80 hover:text-white"
              }`}
            >
              {link.label}
            </Link>
          ))}
        </div>

        <div className="flex items-center gap-4">
          {user && (
            <span className="hidden text-xs text-white/60 sm:block">
              {user.username} · <span className="uppercase text-[#d4af37]">{user.plan}</span>
            </span>
          )}
          <button
            type="button"
            onClick={handleLogout}
            className="rounded-full border border-white/20 px-4 py-1.5 text-xs font-medium text-white/80 transition hover:border-[#d4af37] hover:text-[#d4af37]"
          >
            Log out
          </button>
        </div>
      </div>

      {/* Mobile nav links */}
      <div className="flex items-center justify-center gap-6 border-t border-white/10 py-2 sm:hidden">
        {links.map((link) => (
          <Link
            key={link.to}
            to={link.to}
            className={`text-xs font-medium ${location.pathname === link.to ? "text-[#d4af37]" : "text-white/70"}`}
          >
            {link.label}
          </Link>
        ))}
      </div>
    </nav>
  );
}