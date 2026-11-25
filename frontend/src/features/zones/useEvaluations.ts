import { useQuery } from "@tanstack/react-query";

import { fetchJson } from "../../lib/api";
import type { EvaluationSummary, RiskLevel } from "./types";

interface EvaluationFilters {
  zoneId?: number | null;
  riskLevel?: RiskLevel | null;
  sinceHours?: number | null;
}

export function useEvaluations({ zoneId, riskLevel, sinceHours }: EvaluationFilters = {}) {
  const params = new URLSearchParams({ limit: "200" });
  if (zoneId) params.set("zone_id", String(zoneId));
  if (riskLevel) params.set("risk_level", riskLevel);
  if (sinceHours) params.set("since_hours", String(sinceHours));
  return useQuery({
    queryKey: [
      "evaluations",
      zoneId ?? "todas",
      riskLevel ?? "todos",
      sinceHours ?? "todo",
    ],
    queryFn: () => fetchJson<EvaluationSummary[]>(`/api/v1/evaluations?${params.toString()}`),
    refetchInterval: 30_000,
  });
}

export function useZoneEvaluations(zoneId: number | null, limit = 14) {
  return useQuery({
    queryKey: ["zone-evaluations", zoneId, limit],
    queryFn: () =>
      fetchJson<EvaluationSummary[]>(`/api/v1/zones/${zoneId}/evaluations?limit=${limit}`),
    enabled: zoneId !== null,
    refetchInterval: 60_000,
  });
}
