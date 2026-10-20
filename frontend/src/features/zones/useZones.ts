import { useQuery } from "@tanstack/react-query";

import { useSession } from "../../components/session";
import { fetchJson } from "../../lib/api";
import { isAuthEnabled } from "../../lib/auth";
import type { HistoryPoint, Status, Zone } from "./types";

function useAuthReady() {
  const { token } = useSession();
  return { token, ready: !isAuthEnabled || Boolean(token) };
}

export function useZones() {
  const { token, ready } = useAuthReady();
  return useQuery({
    queryKey: ["zones", token ?? "anon"],
    queryFn: () => fetchJson<Zone[]>("/api/v1/zones", token),
    enabled: ready,
    refetchInterval: 15 * 60 * 1000,
  });
}

export function useZone(zoneId: number | null) {
  const { token, ready } = useAuthReady();
  return useQuery({
    queryKey: ["zone", zoneId, token ?? "anon"],
    queryFn: () => fetchJson<Zone>(`/api/v1/zones/${zoneId}`, token),
    enabled: ready && zoneId !== null,
  });
}

export function useHistory(zoneId: number | null) {
  const { token, ready } = useAuthReady();
  return useQuery({
    queryKey: ["history", zoneId, token ?? "anon"],
    queryFn: () => fetchJson<HistoryPoint[]>(`/api/v1/zones/${zoneId}/history?limit=30`, token),
    enabled: ready && zoneId !== null,
  });
}

export function useStatus() {
  const { token, ready } = useAuthReady();
  return useQuery({
    queryKey: ["status", token ?? "anon"],
    queryFn: () => fetchJson<Status>("/api/v1/status", token),
    enabled: ready,
    refetchInterval: 30_000,
  });
}
