import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { fetchJson, patchJson, postJson } from "../../lib/api";
import type {
  ActionKind,
  ActionStatus,
  PreventiveAction,
  PreventiveActionCreatePayload,
  PreventiveActionSummary,
  PreventiveActionUpdatePayload,
} from "./types";

interface ActionFilters {
  status?: ActionStatus | "todos";
  kind?: ActionKind | "todos";
  zoneId?: number | null;
}

export function useActions({ status, kind, zoneId }: ActionFilters = {}) {
  const params = new URLSearchParams({ limit: "200" });
  if (status && status !== "todos") params.set("status", status);
  if (kind && kind !== "todos") params.set("kind", kind);
  if (zoneId) params.set("zone_id", String(zoneId));
  return useQuery({
    queryKey: ["actions", status ?? "todos", kind ?? "todos", zoneId ?? "todas"],
    queryFn: () => fetchJson<PreventiveAction[]>(`/api/v1/actions?${params.toString()}`),
    refetchInterval: 30_000,
  });
}

export function useActionSummary() {
  return useQuery({
    queryKey: ["actions", "summary"],
    queryFn: () => fetchJson<PreventiveActionSummary>("/api/v1/actions/summary"),
    refetchInterval: 30_000,
  });
}

export function useCreateAction() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (payload: PreventiveActionCreatePayload) =>
      postJson<PreventiveAction>("/api/v1/actions", undefined, payload),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: ["actions"] });
    },
  });
}

export function useUpdateAction() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({ id, payload }: { id: number; payload: PreventiveActionUpdatePayload }) =>
      patchJson<PreventiveAction>(`/api/v1/actions/${id}`, undefined, payload),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: ["actions"] });
    },
  });
}
