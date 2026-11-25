import { useQuery } from "@tanstack/react-query";

import { fetchJson } from "../../lib/api";
import type { EvaluationSummary, RiskLevel } from "./types";

interface EvaluationFilters {
  zoneId?: number | null;
  riskLevel?: RiskLevel | null;
}

export function useEvaluations({ zoneId, riskLevel }: EvaluationFilters = {}) {
  const params = new URLSearchParams({ limit: "200" });
  if (zoneId) params.set("zone_id", String(zoneId));
  if (riskLevel) params.set("risk_level", riskLevel);
  return useQuery({
    queryKey: ["evaluations", zoneId ?? "todas", riskLevel ?? "todos"],
    queryFn: () => fetchJson<EvaluationSummary[]>(`/api/v1/evaluations?${params.toString()}`),
    refetchInterval: 30_000,
  });
}
