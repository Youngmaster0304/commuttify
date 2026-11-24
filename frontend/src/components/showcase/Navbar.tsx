import { useState, useEffect } from "react";
import { Bus, LogOut, Menu, Radio, Sparkles, User, X } from "lucide-react";
import { Button } from "@/components/ui/button";
import type { AuthUser } from "@/components/auth/AuthModal";

interface NavbarProps {
  onOpenAuth: (mode?: "signin" | "signup") => void;
  onLaunchPlanner: () => void;
  onOpenAlerts: () => void;
  activeAlertsCount?: number;
  user: AuthUser | null;
  onLogout: () => void;
}

export function Navbar({
  onOpenAuth,
  onLaunchPlanner,
  onOpenAlerts,
  activeAlertsCount = 8,
  user,
  onLogout,
}: NavbarProps) {
  const [mobileMenuOpen, setMobileMenuOpen] = useState(false);

  const scrollToSection = (id: string) => {
    setMobileMenuOpen(false);
    const el = document.getElementById(id);
    if (el) {
      el.scrollIntoView({ behavior: "smooth" });
    }
  };

  return (
    <header className="sticky top-0 z-40 w-full bg-white/95 backdrop-blur-md border-b border-neutral-200">
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 h-16 flex items-center justify-between">
        {/* Brand Logo */}
        <div className="flex items-center gap-2.5">
          <div className="size-9 rounded-xl bg-black text-white flex items-center justify-center shadow-sm">
            <Bus className="size-5 text-amber-400" />
          </div>
          <div className="flex items-baseline gap-2">
            <span className="font-display font-black text-xl tracking-tight text-neutral-900">
              Commuttify
            </span>
            <span className="px-1.5 py-0.5 rounded bg-neutral-100 border border-neutral-200 text-[10px] font-mono font-medium text-neutral-600">
              DELHI · IN
            </span>
          </div>
        </div>

        {/* Desktop Navigation Links */}
        <nav className="hidden md:flex items-center gap-7 text-sm font-medium text-neutral-600">
          <button
            type="button"
            onClick={() => scrollToSection("features")}
            className="hover:text-black transition-colors cursor-pointer"
          >
            Features
          </button>
          <button
            type="button"
            onClick={() => scrollToSection("corridors")}
            className="hover:text-black transition-colors cursor-pointer"
          >
            Lines & Corridors
          </button>
          <button
            type="button"
            onClick={() => scrollToSection("fare-calculator")}
            className="hover:text-black transition-colors cursor-pointer"
          >
            Fare & Passes
          </button>
          <button
            type="button"
            onClick={onOpenAlerts}
            className="flex items-center gap-1.5 text-neutral-600 hover:text-black transition-colors cursor-pointer"
          >
            <Radio className="size-3.5 text-rose-500 animate-pulse" />
            <span>Live Alerts</span>
            <span className="px-1.5 py-0.2 rounded-full bg-rose-100 text-rose-700 text-[11px] font-mono">
              {activeAlertsCount}
            </span>
          </button>
        </nav>

        {/* Desktop Auth & CTAs */}
        <div className="hidden sm:flex items-center gap-3">
          {user ? (
            <div className="flex items-center gap-3">
              <div className="flex items-center gap-2 px-3 py-1.5 rounded-full bg-neutral-100 border border-neutral-200">
                <div className="size-6 rounded-full bg-amber-400 text-black flex items-center justify-center font-bold text-xs">
                  {user.name.charAt(0).toUpperCase()}
                </div>
                <span className="text-xs font-medium text-neutral-800 max-w-[120px] truncate">
                  {user.name}
                </span>
              </div>
              <button
                type="button"
                onClick={onLogout}
                title="Sign out"
                className="p-2 text-neutral-500 hover:text-rose-600 transition-colors cursor-pointer"
              >
                <LogOut className="size-4" />
              </button>
            </div>
          ) : (
            <>
              <button
                type="button"
                onClick={() => onOpenAuth("signin")}
                className="text-sm font-medium text-neutral-700 hover:text-black px-3 py-2 cursor-pointer"
              >
                Log in
              </button>
              <Button
                onClick={() => onOpenAuth("signup")}
                className="h-9 px-4 rounded-full bg-black text-white hover:bg-neutral-800 font-medium text-xs transition-all shadow-sm"
              >
                Get Started ↗
              </Button>
            </>
          )}

          <Button
            onClick={onLaunchPlanner}
            className="h-9 px-4 rounded-full bg-amber-400 text-black hover:bg-amber-300 font-bold text-xs transition-all shadow-sm flex items-center gap-1.5 cursor-pointer"
          >
            <span>Live Map</span>
            <span>↗</span>
          </Button>
        </div>

        {/* Mobile Menu Button */}
        <div className="flex items-center gap-2 md:hidden">
          <Button
            onClick={onLaunchPlanner}
            size="sm"
            className="h-8 px-3 rounded-full bg-amber-400 text-black font-bold text-xs"
          >
            Map ↗
          </Button>
          <button
            type="button"
            onClick={() => setMobileMenuOpen(!mobileMenuOpen)}
            className="p-2 text-neutral-700 hover:text-black cursor-pointer"
            aria-label="Toggle menu"
          >
            {mobileMenuOpen ? <X className="size-6" /> : <Menu className="size-6" />}
          </button>
        </div>
      </div>

      {/* Mobile Drawer */}
      {mobileMenuOpen && (
        <div className="md:hidden border-b border-neutral-200 bg-white px-4 pt-3 pb-6 space-y-3">
          <div className="flex flex-col space-y-2 text-sm font-medium text-neutral-800">
            <button
              type="button"
              onClick={() => scrollToSection("features")}
              className="py-2 text-left hover:text-black cursor-pointer"
            >
              Features
            </button>
            <button
              type="button"
              onClick={() => scrollToSection("corridors")}
              className="py-2 text-left hover:text-black cursor-pointer"
            >
              Lines & Corridors
            </button>
            <button
              type="button"
              onClick={() => scrollToSection("fare-calculator")}
              className="py-2 text-left hover:text-black cursor-pointer"
            >
              Fare & Passes
            </button>
            <button
              type="button"
              onClick={() => {
                setMobileMenuOpen(false);
                onOpenAlerts();
              }}
              className="py-2 text-left flex items-center gap-2 cursor-pointer"
            >
              <Radio className="size-3.5 text-rose-500 animate-pulse" />
              <span>Live Alerts ({activeAlertsCount})</span>
            </button>
          </div>

          <div className="pt-3 border-t border-neutral-100 flex flex-col gap-2">
            {user ? (
              <div className="flex items-center justify-between py-2">
                <span className="text-sm font-medium text-neutral-800">{user.name}</span>
                <Button variant="ghost" size="sm" onClick={onLogout} className="text-xs text-rose-600">
                  Sign out
                </Button>
              </div>
            ) : (
              <div className="grid grid-cols-2 gap-2">
                <Button
                  variant="outline"
                  onClick={() => {
                    setMobileMenuOpen(false);
                    onOpenAuth("signin");
                  }}
                  className="w-full text-xs"
                >
                  Log in
                </Button>
                <Button
                  onClick={() => {
                    setMobileMenuOpen(false);
                    onOpenAuth("signup");
                  }}
                  className="w-full text-xs bg-black text-white hover:bg-neutral-800"
                >
                  Get Started
                </Button>
              </div>
            )}
            <Button
              onClick={() => {
                setMobileMenuOpen(false);
                onLaunchPlanner();
              }}
              className="w-full bg-amber-400 text-black font-bold text-xs"
            >
              Open Bus Journey Planner ↗
            </Button>
          </div>
        </div>
      )}
    </header>
  );
}
