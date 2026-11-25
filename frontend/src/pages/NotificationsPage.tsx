import { AlertTriangle, Bell, CheckCheck, RefreshCw } from "lucide-react";
import { useState } from "react";
import { Link } from "react-router-dom";

import { PageLoader } from "../components/PageLoader";
import { RiskBadge } from "../components/RiskBadge";
import { useSession } from "../components/session";
import {
  useMarkAllNotificationsRead,
  useMarkNotificationRead,
  useNotificationSummary,
  useNotifications,
} from "../features/zones/useNotifications";
import { actorLabel } from "../lib/actor";
import { formatDateTime } from "../lib/format";
import { zoneLabel } from "../lib/names";

const EVENT_LABELS: Record<string, string> = {
  cambio_nivel: "Cambio de nivel",
  alerta_alto: "Alerta Alto",
};

export default function NotificationsPage() {
  const { canSimulate } = useSession();
  const [unreadOnly, setUnreadOnly] = useState(false);
  const [message, setMessage] = useState<string | null>(null);
  const notifications = useNotifications(unreadOnly);
  const summary = useNotificationSummary();
  const markRead = useMarkNotificationRead();
  const markAll = useMarkAllNotificationsRead();

  if (!canSimulate) {
    return (
      <div className="mx-auto flex min-h-[60dvh] max-w-[800px] flex-col justify-center px-5 py-16 md:px-8">
        <AlertTriangle size={28} strokeWidth={1.5} className="text-ember" aria-hidden="true" />
        <h1 className="mt-4 text-[34px] leading-tight tracking-[-0.03em]">
          Notificaciones reservadas para operadores.
        </h1>
        <p className="mt-3 max-w-lg text-bone-muted">
          Inicia sesión con una cuenta del grupo <span className="font-mono">operadores</span> para
          revisar los cambios de nivel y las alertas del sistema.
        </p>
      </div>
    );
  }

  if (notifications.isLoading) return <PageLoader />;

  if (notifications.isError) {
    return (
      <div className="mx-auto flex min-h-[60dvh] max-w-[800px] flex-col justify-center px-5 py-16 md:px-8">
        <AlertTriangle size={28} strokeWidth={1.5} className="text-ember" aria-hidden="true" />
        <h1 className="mt-4 text-[34px] leading-tight tracking-[-0.03em]">
          No pudimos cargar las notificaciones.
        </h1>
        <p className="mt-3 text-bone-muted">Revisa la conexión con la API y vuelve a intentar.</p>
        <button
          type="button"
          className="btn btn-primary mt-6 w-fit"
          onClick={() => void notifications.refetch()}
        >
          <RefreshCw size={16} strokeWidth={1.5} aria-hidden="true" /> Reintentar
        </button>
      </div>
    );
  }

  const rows = notifications.data ?? [];
  const unread = summary.data?.unread ?? rows.filter((item) => item.read_at === null).length;

  function handleMarkAll() {
    setMessage(null);
    markAll.mutate(undefined, {
      onSuccess: () => setMessage("Todas las notificaciones quedaron marcadas como leídas."),
      onError: (error) =>
        setMessage(error instanceof Error ? error.message : "No pudimos marcar las notificaciones."),
    });
  }

  function handleMarkRead(id: number) {
    setMessage(null);
    markRead.mutate(id, {
      onSuccess: () => setMessage("Notificación marcada como leída."),
      onError: (error) =>
        setMessage(error instanceof Error ? error.message : "No pudimos marcar la notificación."),
    });
  }

  return (
    <div className="mx-auto max-w-[1000px] px-5 py-12 md:px-8 md:py-16">
      <p className="font-mono text-[12px] uppercase tracking-[0.14em] text-surveyor">Avisos</p>
      <div className="mt-3 flex flex-wrap items-end justify-between gap-5">
        <div>
          <h1 className="text-[40px] leading-none tracking-[-0.03em] md:text-[56px]">
            Centro de notificaciones
          </h1>
          <p className="mt-4 max-w-2xl text-bone-muted">
            Cambios de nivel Bajo, Medio y Alto, y aperturas de alertas. Cada aviso enlaza a su
            zona o alerta y puede marcarse como leído.
          </p>
        </div>
        <div className="flex flex-wrap items-center gap-2">
          <button
            type="button"
            className="btn btn-ghost"
            onClick={() => void notifications.refetch()}
            aria-label="Actualizar las notificaciones"
          >
            <RefreshCw size={16} strokeWidth={1.5} aria-hidden="true" /> Actualizar
          </button>
          <button
            type="button"
            className="btn btn-primary"
            onClick={handleMarkAll}
            disabled={markAll.isPending || unread === 0}
            aria-label="Marcar todas las notificaciones como leídas"
          >
            <CheckCheck size={16} strokeWidth={1.5} aria-hidden="true" />
            {markAll.isPending ? "Marcando…" : "Marcar todas"}
          </button>
        </div>
      </div>

      <div className="mt-8 flex flex-wrap items-center justify-between gap-3 border-y border-iron py-3">
        <p className="font-mono text-[11px] text-bone" role="status" aria-live="polite">
          {unread} sin leer · {summary.data?.total ?? rows.length} notificaciones
        </p>
        <label className="flex items-center gap-2 font-mono text-[11px] text-bone">
          <input
            type="checkbox"
            checked={unreadOnly}
            onChange={(event) => setUnreadOnly(event.target.checked)}
            className="size-4 accent-[#ebfc72]"
          />
          Mostrar solo no leídas
        </label>
      </div>

      <p className="mt-2 min-h-5 font-mono text-[11px] text-surveyor" role="status" aria-live="polite">
        {message}
      </p>

      <ul className="mt-2 space-y-3">
        {rows.map((notification) => {
          const unreadItem = notification.read_at === null;
          return (
            <li
              key={notification.id}
              className="border border-iron p-4 transition-colors hover:border-bone/40"
            >
              <div className="flex flex-wrap items-start justify-between gap-3">
                <div className="flex flex-wrap items-center gap-2">
                  <Bell
                    size={14}
                    strokeWidth={1.5}
                    className={unreadItem ? "text-surveyor" : "text-ash"}
                    aria-hidden="true"
                  />
                  <span className="font-mono text-[10px] uppercase tracking-[0.1em] text-surveyor">
                    {EVENT_LABELS[notification.event_type] ?? notification.event_type}
                  </span>
                  <span
                    className={`font-mono text-[10px] uppercase tracking-[0.08em] ${
                      unreadItem ? "text-bone" : "text-ash"
                    }`}
                  >
                    {unreadItem ? "No leída" : "Leída"}
                  </span>
                </div>
                <div className="flex items-center gap-3">
                  <time className="font-mono text-[10px] text-ash" dateTime={notification.created_at}>
                    {formatDateTime(notification.created_at)}
                  </time>
                  {unreadItem ? (
                    <button
                      type="button"
                      className="font-mono text-[10px] uppercase tracking-[0.08em] text-bone underline decoration-iron underline-offset-4 hover:text-surveyor"
                      onClick={() => handleMarkRead(notification.id)}
                      disabled={markRead.isPending}
                      aria-label={`Marcar como leída: ${notification.title}`}
                    >
                      Marcar leída
                    </button>
                  ) : null}
                </div>
              </div>

              <h2 className="mt-3 text-[22px] leading-tight tracking-[-0.03em] text-bone">
                {notification.title}
              </h2>
              {notification.detail ? (
                <p className="mt-2 text-[15px] text-bone-muted">{notification.detail}</p>
              ) : null}

              <div className="mt-3 flex flex-wrap items-center gap-3">
                {notification.level_from ? (
                  <RiskBadge level={notification.level_from} />
                ) : null}
                {notification.level_from && notification.level_to ? (
                  <span className="font-mono text-[11px] text-ash" aria-label="Nivel anterior y nuevo">
                    →
                  </span>
                ) : null}
                {notification.level_to ? <RiskBadge level={notification.level_to} /> : null}
                <Link
                  to={`/mapa?zona=${notification.zone_id}`}
                  className="font-mono text-[11px] text-bone underline decoration-iron underline-offset-4 hover:text-surveyor"
                >
                  {zoneLabel(notification.zone_name)} · {notification.comuna}
                </Link>
                {notification.alert_id !== null ? (
                  <Link
                    to={`/alertas?alerta=${notification.alert_id}`}
                    className="font-mono text-[11px] text-surveyor underline decoration-iron underline-offset-4"
                  >
                    Ver alerta #{notification.alert_id}
                  </Link>
                ) : null}
                <span className="font-mono text-[10px] text-ash">
                  {notification.event_type === "cambio_nivel"
                    ? `Evaluación #${notification.evaluation_id ?? "—"}`
                    : `Registrada por ${actorLabel(notification.actor)}`}
                </span>
              </div>
            </li>
          );
        })}
      </ul>

      {rows.length === 0 ? (
        <p className="mt-4 border border-iron p-6 font-mono text-[12px] text-ash">
          {unreadOnly
            ? "No hay notificaciones sin leer."
            : "Aún no hay notificaciones registradas. Los cambios de nivel y las alertas aparecerán aquí."}
        </p>
      ) : null}
    </div>
  );
}
