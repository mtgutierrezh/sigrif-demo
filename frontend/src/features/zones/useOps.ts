import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { fetchJson, postJson } from "../../lib/api";
import type { IngestionRun, ModelInfo, OpsOverview, ZoneAlert } from "./types";

export function useOpsOverview() {
  return useQuery({
    queryKey: ["ops", "overview"],
    queryFn: () => fetchJson<OpsOverview>("/api/v1/ops/overview"),
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
