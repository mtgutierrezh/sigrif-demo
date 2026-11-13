import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { fetchJson, patchJson, postJson } from "../../lib/api";
import type {
  AlertDetail,
  AlertEvent,
  AlertEventPayload,
  AlertStatus,
  AlertSummary,
  AlertUpdatePayload,
  Alert,
} from "./types";

export function useAlerts(status?: AlertStatus | "todas") {
  const filter = status && status !== "todas" ? `&status=${status}` : "";
  return useQuery({
    queryKey: ["alerts", status ?? "todas"],
    queryFn: () => fetchJson<Alert[]>(`/api/v1/alerts?limit=100${filter}`),
    refetchInterval: 30_000,
  });
}

export function useAlert(alertId: number | null) {
  return useQuery({
    queryKey: ["alert", alertId],
    queryFn: () => fetchJson<AlertDetail>(`/api/v1/alerts/${alertId}`),
    enabled: alertId !== null,
  });
}

export function useAlertSummary() {
  return useQuery({
    queryKey: ["alerts", "summary"],
    queryFn: () => fetchJson<AlertSummary>("/api/v1/alerts/summary"),
    refetchInterval: 30_000,
  });
}

export function useUpdateAlert() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({ id, payload }: { id: number; payload: AlertUpdatePayload }) =>
      patchJson<AlertDetail>(`/api/v1/alerts/${id}`, undefined, payload),
    onSuccess: (alert) => {
      queryClient.setQueryData(["alert", alert.id], alert);
      void queryClient.invalidateQueries({ queryKey: ["alerts"] });
    },
  });
}

export function useCreateAlertEvent() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({ id, payload }: { id: number; payload: AlertEventPayload }) =>
      postJson<AlertEvent>(`/api/v1/alerts/${id}/events`, undefined, payload),
    onSuccess: (_event, variables) => {
      void queryClient.invalidateQueries({ queryKey: ["alert", variables.id] });
      void queryClient.invalidateQueries({ queryKey: ["alerts"] });
    },
  });
}
