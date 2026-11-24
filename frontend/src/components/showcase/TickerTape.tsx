export function TickerTape() {
  const items = [
    "LIVE — DELHI BUSES",
    "OPERATIONAL 05:00 - 23:30",
    "5,465 BUS FLEET (DTC & CLUSTER)",
    "80,861+ MODELED CORRIDORS",
    "DTC DAILY PASS ₹50",
    "WOMEN PINK PASS FREE ₹0",
    "REAL-TIME TRAFFIC DELAY PREDICTION",
    "AI TRANSIT ASSISTANT ONLINE",
  ];

  return (
    <div className="w-full bg-black text-white overflow-hidden py-2 border-y border-neutral-800 select-none">
      <div className="animate-marquee flex items-center gap-8 whitespace-nowrap text-xs font-mono font-medium tracking-wider">
        {[...items, ...items].map((text, idx) => (
          <span key={idx} className="flex items-center gap-3">
            <span className="size-1.5 rounded-full bg-amber-400" />
            <span className={idx % 2 === 0 ? "text-neutral-200" : "text-neutral-400"}>{text}</span>
          </span>
        ))}
      </div>
    </div>
  );
}
