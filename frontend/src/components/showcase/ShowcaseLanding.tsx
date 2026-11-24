import { useState, useEffect } from "react";
import { Navbar } from "./Navbar";
import { TickerTape } from "./TickerTape";
import { HeroSection } from "./HeroSection";
import { NetworkCorridors } from "./NetworkCorridors";
import { FareCalculator } from "./FareCalculator";
import { BottomBanner } from "./BottomBanner";
import { AuthModal, type AuthUser } from "@/components/auth/AuthModal";
import { toast } from "sonner";

interface ShowcaseLandingProps {
  onLaunchPlanner: (presetOriginId?: string, presetDestId?: string) => void;
  onOpenAlerts: () => void;
  activeAlertsCount?: number;
}

export function ShowcaseLanding({
  onLaunchPlanner,
  onOpenAlerts,
  activeAlertsCount = 8,
}: ShowcaseLandingProps) {
  const [authOpen, setAuthOpen] = useState(false);
  const [authMode, setAuthMode] = useState<"signin" | "signup">("signin");
  const [user, setUser] = useState<AuthUser | null>(null);

  useEffect(() => {
    try {
      const stored = localStorage.getItem("commuttify_user");
      if (stored) {
        setUser(JSON.parse(stored));
      }
    } catch (e) {
      console.error(e);
    }
  }, []);

  const handleOpenAuth = (mode: "signin" | "signup" = "signin") => {
    setAuthMode(mode);
    setAuthOpen(true);
  };

  const handleLogout = () => {
    try {
      localStorage.removeItem("commuttify_user");
    } catch {}
    setUser(null);
    toast.info("Signed out successfully");
  };

  const handleSelectCorridor = (corridorId: string) => {
    // Launches planner with relevant preset
    if (corridorId === "ashram-mathura") {
      onLaunchPlanner("ashram-chowk", "sarai-kale-khan");
    } else {
      onLaunchPlanner("kashmere-gate", "aiims");
    }
  };

  return (
    <div className="min-h-screen bg-white flex flex-col font-sans selection:bg-amber-300 selection:text-black">
      {/* Sticky Top Navbar */}
      <Navbar
        onOpenAuth={handleOpenAuth}
        onLaunchPlanner={() => onLaunchPlanner()}
        onOpenAlerts={onOpenAlerts}
        activeAlertsCount={activeAlertsCount}
        user={user}
        onLogout={handleLogout}
      />

      {/* Marquee Ticker Tape */}
      <TickerTape />

      <main className="flex-1">
        {/* Hero Section with Retro Boarding Pass */}
        <HeroSection
          onPlanJourney={(orig, dest) => onLaunchPlanner(orig, dest)}
          onExploreFeatures={() => {
            const el = document.getElementById("corridors");
            el?.scrollIntoView({ behavior: "smooth" });
          }}
        />

        {/* Major Network Corridors Section */}
        <NetworkCorridors
          onSelectCorridor={handleSelectCorridor}
          onLaunchPlanner={() => onLaunchPlanner()}
          onOpenAlerts={onOpenAlerts}
        />

        {/* Fare & Pass Calculator */}
        <FareCalculator />

        {/* Ready When You Are CTA & Footer */}
        <BottomBanner
          onPlanJourney={() => onLaunchPlanner()}
          onOpenAuth={() => handleOpenAuth("signup")}
        />
      </main>

      {/* Authentication Modal */}
      <AuthModal
        isOpen={authOpen}
        onClose={() => setAuthOpen(false)}
        initialMode={authMode}
        onSuccess={(newUser) => setUser(newUser)}
      />
    </div>
  );
}
