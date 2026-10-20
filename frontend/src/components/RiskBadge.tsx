import type { RiskLevel } from "../features/zones/types";
import { riskClass } from "../lib/risk";

export function RiskBadge({ level }: { level: RiskLevel }) {
  return <span className={`badge ${riskClass(level)}`}>{level}</span>;
}
