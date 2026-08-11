import { Flame } from "lucide-react";

export default function BrandMark({ className = "h-10 w-10" }: { className?: string }) {
  return (
    <div
      className={`grid shrink-0 place-items-center rounded-xl bg-gradient-to-br from-heat-warm via-heat-hot to-heat-peak shadow-[var(--shadow-glow)] ${className}`}
    >
      <Flame className="h-1/2 w-1/2 text-[#140a04]" strokeWidth={2.5} />
    </div>
  );
}
