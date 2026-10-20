import { useMutation, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";

import { useSession } from "../../components/session";
import { fetchJson, postJson } from "../../lib/api";
import type { Zone } from "./types";

interface SimulationResponse {
  zone_id: number;
  message: string;
}

export type SimulationStage = "idle" | "publishing" | "queued" | "processing" | "done" | "error";

const STEP_DELAY_MS = 1000;
const TIMEOUT_MS = 12000;
const sleep = (ms: number) => new Promise((resolve) => setTimeout(resolve, ms));

export function useSimulate() {
  const { token } = useSession();
  const queryClient = useQueryClient();
  const [stage, setStage] = useState<SimulationStage>("idle");

  const mutation = useMutation({
    mutationFn: async ({ zoneId, updatedAt }: { zoneId: number; updatedAt: string }) => {
      setStage("publishing");
      const response = await postJson<SimulationResponse>(
        `/api/v1/simulate?zone_id=${zoneId}`,
        token,
      );
      setStage("queued");
      const deadline = Date.now() + TIMEOUT_MS;
      while (Date.now() < deadline) {
        await sleep(STEP_DELAY_MS);
        setStage("processing");
        const zone = await fetchJson<Zone>(`/api/v1/zones/${zoneId}`, token);
        if (zone.updated_at !== updatedAt) {
          setStage("done");
          return { response, zone };
        }
      }
      throw new Error("La IA no actualizó el riesgo a tiempo.");
    },
    onSuccess: async () => {
      await Promise.all([
        queryClient.invalidateQueries({ queryKey: ["zones"] }),
        queryClient.invalidateQueries({ queryKey: ["zone"] }),
        queryClient.invalidateQueries({ queryKey: ["history"] }),
        queryClient.invalidateQueries({ queryKey: ["status"] }),
      ]);
    },
    onError: () => setStage("error"),
  });

  return { ...mutation, stage, resetStage: () => setStage("idle") };
}
