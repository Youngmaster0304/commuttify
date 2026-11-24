import { useState } from "react";
import { ArrowLeft, Check, Loader2, Sparkles, Star, User } from "lucide-react";
import { toast } from "sonner";
import { Dialog, DialogContent, DialogTitle } from "@/components/ui/dialog";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";

export interface AuthUser {
  name: string;
  email: string;
  avatar?: string;
  role?: string;
  savedRoutes?: string[];
}

interface AuthModalProps {
  isOpen: boolean;
  onClose: () => void;
  onSuccess?: (user: AuthUser) => void;
  initialMode?: "signin" | "signup";
}

export function AuthModal({ isOpen, onClose, onSuccess, initialMode = "signin" }: AuthModalProps) {
  const [mode, setMode] = useState<"signin" | "signup">(initialMode);
  const [name, setName] = useState("");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [isLoading, setIsLoading] = useState(false);

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (!email || !password) {
      toast.error("Please fill in all required fields.");
      return;
    }

    setIsLoading(true);
    setTimeout(() => {
      const user: AuthUser = {
        name: name.trim() || (email.split("@")[0] ?? "Delhi Commuter"),
        email: email.trim(),
        avatar: `https://images.unsplash.com/photo-1535713875002-d1d0cf377fde?w=100&auto=format&fit=crop&q=60`,
        role: "Verified Commuter",
        savedRoutes: ["Route 419 (Kashmere Gate ↔ AIIMS)", "Route 534 (Anand Vihar ↔ Mehrauli)"],
      };

      try {
        localStorage.setItem("commuttify_user", JSON.stringify(user));
      } catch (err) {
        console.error("Storage error:", err);
      }

      setIsLoading(false);
      toast.success(mode === "signin" ? `Welcome back, ${user.name}!` : `Account created for ${user.name}!`);
      onSuccess?.(user);
      onClose();
    }, 600);
  };

  const fillDemo = () => {
    setEmail("abhinav@delhicommute.in");
    setPassword("dtc-delhi-2026");
    setName("Abhinav Sharma");
    toast.info("Filled demo credentials!");
  };

  return (
    <Dialog open={isOpen} onOpenChange={(open) => !open && onClose()}>
      <DialogContent className="max-w-3xl p-0 overflow-hidden border-2 border-black rounded-2xl shadow-hard-xl sm:max-w-[820px] bg-white">
        <DialogTitle className="sr-only">Sign In to Commuttify</DialogTitle>
        <div className="grid grid-cols-1 md:grid-cols-12 min-h-[500px]">
          {/* Left Panel: Dark Console */}
          <div className="md:col-span-5 bg-[#121214] text-white p-6 sm:p-8 flex flex-col justify-between border-b md:border-b-0 md:border-r border-neutral-800 relative">
            <div>
              <button
                type="button"
                onClick={onClose}
                className="flex items-center gap-1.5 text-xs text-neutral-400 hover:text-white transition-colors mb-8 cursor-pointer"
              >
                <ArrowLeft className="size-3.5" /> Back to home
              </button>

              <div className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full bg-amber-500/10 border border-amber-500/30 text-amber-400 text-[11px] font-mono font-medium mb-6">
                <Star className="size-3 fill-amber-400 text-amber-400" />
                <span>COMMUTTIFY BUS CONSOLE</span>
              </div>

              <h2 className="text-2xl sm:text-3xl font-display font-bold leading-tight mb-4">
                The Delhi Buses, <br />
                <span className="font-serif italic font-normal text-amber-300">at your</span> fingertips.
              </h2>

              <p className="text-xs sm:text-sm text-neutral-400 leading-relaxed">
                Sign in to save favourite DTC corridors, track live route delays, receive bottleneck alerts, and let our
                AI plan the smartest transit commute for your day.
              </p>
            </div>

            <div className="pt-8">
              {/* Fleet Spectrum Color Bar */}
              <div className="h-1.5 w-full rounded-full flex overflow-hidden mb-3">
                <div className="flex-1 bg-rose-500" title="AC Fleet" />
                <div className="flex-1 bg-emerald-500" title="CNG Fleet" />
                <div className="flex-1 bg-blue-500" title="e-Bus Fleet" />
                <div className="flex-1 bg-purple-500" title="Express" />
                <div className="flex-1 bg-amber-500" title="Feeder" />
                <div className="flex-1 bg-cyan-500" title="Cluster" />
              </div>
              <div className="flex justify-between text-[10px] text-neutral-500 font-mono">
                <span>DTC · DIMTS · DMRC</span>
                <span>OPEN TRANSIT</span>
              </div>
            </div>
          </div>

          {/* Right Panel: Clean White Form */}
          <div className="md:col-span-7 p-6 sm:p-10 flex flex-col justify-center bg-white">
            <div className="max-w-sm mx-auto w-full">
              <div className="flex items-center justify-between mb-2">
                <span className="text-[11px] font-mono tracking-widest text-neutral-500 uppercase flex items-center gap-1">
                  <Sparkles className="size-3 text-amber-500" />
                  {mode === "signin" ? "Returning Commuter" : "New Commuter"}
                </span>
              </div>

              <h3 className="text-2xl font-display font-bold text-neutral-900 mb-6">
                {mode === "signin" ? "Sign in" : "Create Account"}
              </h3>

              <form onSubmit={handleSubmit} className="space-y-4">
                {mode === "signup" && (
                  <div className="space-y-1.5">
                    <Label htmlFor="auth-name" className="text-xs font-mono text-neutral-700">
                      FULL NAME
                    </Label>
                    <Input
                      id="auth-name"
                      placeholder="Abhinav Sharma"
                      value={name}
                      onChange={(e) => setName(e.target.value)}
                      className="h-10 text-sm border-neutral-300 focus:border-black rounded-lg"
                      required={mode === "signup"}
                    />
                  </div>
                )}

                <div className="space-y-1.5">
                  <Label htmlFor="auth-email" className="text-xs font-mono text-neutral-700">
                    EMAIL
                  </Label>
                  <Input
                    id="auth-email"
                    type="email"
                    placeholder="john@example.com"
                    value={email}
                    onChange={(e) => setEmail(e.target.value)}
                    className="h-10 text-sm border-neutral-300 focus:border-black rounded-lg"
                    required
                  />
                </div>

                <div className="space-y-1.5">
                  <div className="flex justify-between items-center">
                    <Label htmlFor="auth-password" className="text-xs font-mono text-neutral-700">
                      PASSWORD
                    </Label>
                    {mode === "signin" && (
                      <button
                        type="button"
                        onClick={() => toast.info("Enter any password for demo access")}
                        className="text-[11px] text-neutral-500 hover:text-black"
                      >
                        Forgot password?
                      </button>
                    )}
                  </div>
                  <Input
                    id="auth-password"
                    type="password"
                    placeholder="••••••••"
                    value={password}
                    onChange={(e) => setPassword(e.target.value)}
                    className="h-10 text-sm border-neutral-300 focus:border-black rounded-lg"
                    required
                  />
                </div>

                <Button
                  type="submit"
                  disabled={isLoading}
                  className="w-full h-11 bg-black text-white hover:bg-neutral-800 rounded-lg font-medium text-sm transition-all shadow-md mt-2"
                >
                  {isLoading ? (
                    <span className="flex items-center gap-2">
                      <Loader2 className="size-4 animate-spin" /> Authenticating…
                    </span>
                  ) : mode === "signin" ? (
                    "Sign in"
                  ) : (
                    "Create Account"
                  )}
                </Button>
              </form>

              <div className="mt-6 text-center text-xs text-neutral-600">
                {mode === "signin" ? (
                  <p>
                    Don't have an account?{" "}
                    <button
                      type="button"
                      onClick={() => setMode("signup")}
                      className="font-semibold text-black hover:underline cursor-pointer"
                    >
                      Sign up
                    </button>
                  </p>
                ) : (
                  <p>
                    Already have an account?{" "}
                    <button
                      type="button"
                      onClick={() => setMode("signin")}
                      className="font-semibold text-black hover:underline cursor-pointer"
                    >
                      Sign in
                    </button>
                  </p>
                )}
              </div>
            </div>
          </div>
        </div>
      </DialogContent>
    </Dialog>
  );
}
