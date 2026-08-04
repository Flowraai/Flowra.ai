import type { RiskLevel } from "../api/types";
import { RISK_LABEL } from "../lib/format";

export function RiskBadge({ level, label }: { level: RiskLevel; label?: string }) {
  return (
    <span className={`risk ${level}`}>
      <span className="dot" />
      {label ?? RISK_LABEL[level]}
    </span>
  );
}
