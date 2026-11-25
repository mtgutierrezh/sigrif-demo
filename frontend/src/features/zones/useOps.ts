import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { fetchJson, postJson } from "../../lib/api";
import type {
  ExecutiveSummary,
  IngestionRun,
  ModelInfo,
  OpsOverview,
  ServicesStatus,
  ZoneAlert,
} from "./types";

export function useOpsOverview() {
  return useQuery({
    queryKey: ["ops", "overview"],
    queryFn: () => fetchJson<OpsOverview>("/api/v1/ops/overview"),
    refetchInterval: 30_000,
  });
}

export function useOpsExecutive() {
  return useQuery({
    queryKey: ["ops", "executive"],
    queryFn: () => fetchJson<ExecutiveSummary>("/api/v1/ops/executive"),
    refetchInterval: 30_000,
  });
}

export function useOpsServices() {
  return useQuery({
    queryKey: ["ops", "services"],
    queryFn: () => fetchJson<ServicesStatus>("/api/v1/ops/services"),
    refetchInterval: 30_000,
  });
}

export function useOpsAlerts() {
  return useQuery({
    queryKey: ["ops", "alerts"],
    queryFn: () => fetchJson<ZoneAlert[]>("/api/v1/ops/alerts?limit=20"),
    refetchInterval: 30_000,
  });
}

export function useOpsIngestion() {
  return useQuery({
    queryKey: ["ops", "ingestion"],
    queryFn: () => fetchJson<IngestionRun[]>("/api/v1/ops/ingestion?limit=10"),
    refetchInterval: 60_000,
  });
}

export function useModelInfo() {
  return useQuery({
    queryKey: ["ops", "model"],
    queryFn: () => fetchJson<ModelInfo>("/api/v1/model"),
    staleTime: 5 * 60_000,
  });
}

export function useRunIngestion() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (provider: string) =>
      postJson<IngestionRun>(`/api/v1/ops/ingest?provider=${encodeURIComponent(provider)}`),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: ["ops"] });
      void queryClient.invalidateQueries({ queryKey: ["zones"] });
      void queryClient.invalidateQueries({ queryKey: ["status"] });
    },
  });
}
