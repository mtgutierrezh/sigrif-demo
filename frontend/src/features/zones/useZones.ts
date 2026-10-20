import { useQuery } from "@tanstack/react-query";

import { useSession } from "../../components/session";
import { fetchJson } from "../../lib/api";
import type { HistoryPoint, Status, Zone } from "./types";

export function useZones() {
  const { token } = useSession();
  return useQuery({
    queryKey: ["zones"],
    queryFn: () => fetchJson<Zone[]>("/api/v1/zones", token),
    refetchInterval: 15 * 60 * 1000,
  });
}

export function useZone(zoneId: number | null) {
  const { token } = useSession();
  return useQuery({
    queryKey: ["zone", zoneId],
    queryFn: () => fetchJson<Zone>(`/api/v1/zones/${zoneId}`, token),
    enabled: zoneId !== null,
  });
}

export function useHistory(zoneId: number | null) {
  const { token } = useSession();
  return useQuery({
    queryKey: ["history", zoneId],
    queryFn: () => fetchJson<HistoryPoint[]>(`/api/v1/zones/${zoneId}/history?limit=30`, token),
    enabled: zoneId !== null,
  });
}

export function useStatus() {
  const { token } = useSession();
  return useQuery({
    queryKey: ["status"],
    queryFn: () => fetchJson<Status>("/api/v1/status", token),
    refetchInterval: 30_000,
  });
}
