import { useMutation, useQueryClient } from "@tanstack/react-query";

import { useSession } from "../../components/session";
import { postJson } from "../../lib/api";
import type { Evaluation, RiskFeatures } from "./types";

interface EvaluateInput {
  zoneId: number;
  features: RiskFeatures;
}

export function useEvaluate() {
  const { token } = useSession();
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: ({ zoneId, features }: EvaluateInput) =>
      postJson<Evaluation>(`/api/v1/zones/${zoneId}/evaluate`, token, features),
    onSuccess: async () => {
      await Promise.all([
        queryClient.invalidateQueries({ queryKey: ["zones"] }),
        queryClient.invalidateQueries({ queryKey: ["zone"] }),
        queryClient.invalidateQueries({ queryKey: ["history"] }),
        queryClient.invalidateQueries({ queryKey: ["status"] }),
      ]);
    },
  });
}
