import { useQuery } from "@tanstack/react-query";

import { fetchJson } from "../../lib/api";
import type { PriorityRanking } from "./types";

export function usePriority(limit = 20) {
  return useQuery({
    queryKey: ["ops", "priority", limit],
    queryFn: () => fetchJson<PriorityRanking>(`/api/v1/ops/priority?limit=${limit}`),
    refetchInterval: 60_000,
  });
}
