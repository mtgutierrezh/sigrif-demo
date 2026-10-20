import { useMutation, useQueryClient } from "@tanstack/react-query";

import { useSession } from "../../components/session";
import { postJson } from "../../lib/api";

interface SimulationResponse {
  zone_id: number;
  message: string;
}

export function useSimulate() {
  const { token } = useSession();
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: () => postJson<SimulationResponse>("/api/v1/simulate", token),
    onSuccess: async () => {
      await new Promise((resolve) => setTimeout(resolve, 2500));
      await Promise.all([
        queryClient.invalidateQueries({ queryKey: ["zones"] }),
        queryClient.invalidateQueries({ queryKey: ["zone"] }),
        queryClient.invalidateQueries({ queryKey: ["history"] }),
        queryClient.invalidateQueries({ queryKey: ["status"] }),
      ]);
    },
  });
}
