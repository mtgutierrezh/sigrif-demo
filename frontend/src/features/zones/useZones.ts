import { useQuery } from "@tanstack/react-query";

import { fetchJson } from "../../lib/api";
import type { HistoryPoint, Status, Zone } from "./types";

export function useZones() {
  return useQuery({
    queryKey: ["zones"],
    queryFn: () => fetchJson<Zone[]>("/api/v1/zones"),
    refetchInterval: 15 * 60 * 1000,
  });
}

export function useZone(zoneId: number | null) {
  return useQuery({
    queryKey: ["zone", zoneId],
    queryFn: () => fetchJson<Zone>(`/api/v1/zones/${zoneId}`),
    enabled: zoneId !== null,
  });
}

export function useHistory(zoneId: number | null) {
  return useQuery({
    queryKey: ["history", zoneId],
    queryFn: () => fetchJson<HistoryPoint[]>(`/api/v1/zones/${zoneId}/history?limit=30`),
    enabled: zoneId !== null,
  });
}

export function useStatus() {
  return useQuery({
    queryKey: ["status"],
    queryFn: () => fetchJson<Status>("/api/v1/status"),
    refetchInterval: 30_000,
  });
}
