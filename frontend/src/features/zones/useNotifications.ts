import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { fetchJson, patchJson } from "../../lib/api";
import type { NotificationEvent, NotificationSummary } from "./types";

export function useNotifications(unreadOnly = false) {
  return useQuery({
    queryKey: ["notifications", unreadOnly ? "unread" : "all"],
    queryFn: () =>
      fetchJson<NotificationEvent[]>(
        `/api/v1/notifications?limit=100${unreadOnly ? "&unread_only=true" : ""}`,
      ),
    refetchInterval: 30_000,
  });
}

export function useNotificationSummary() {
  return useQuery({
    queryKey: ["notifications", "summary"],
    queryFn: () => fetchJson<NotificationSummary>("/api/v1/notifications/summary"),
    refetchInterval: 30_000,
  });
}

export function useMarkNotificationRead() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (id: number) =>
      patchJson<NotificationEvent>(`/api/v1/notifications/${id}/read`, undefined),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: ["notifications"] });
    },
  });
}

export function useMarkAllNotificationsRead() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: () =>
      patchJson<NotificationSummary>("/api/v1/notifications/read-all", undefined),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: ["notifications"] });
    },
  });
}
