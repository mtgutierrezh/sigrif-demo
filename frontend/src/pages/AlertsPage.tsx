import { AlertTriangle, Bell, RefreshCw } from "lucide-react";
import { useEffect, useState, type FormEvent } from "react";

import { PageLoader } from "../components/PageLoader";
import { RiskBadge } from "../components/RiskBadge";
import { useSession } from "../components/session";
import {
  useAlert,
  useAlertSummary,
  useAlerts,
  useCreateAlertEvent,
  useUpdateAlert,
} from "../features/zones/useAlerts";
import type { AlertStatus } from "../features/zones/types";
import { formatDateTime, formatScore } from "../lib/format";
import { zoneLabel } from "../lib/names";

const STATUS_LABELS: Record<AlertStatus, string> = {
  nueva: "Nueva",
  en_revision: "En revisión",
  cerrada: "Cerrada",
};

const STATUS_CLASSES: Record<AlertStatus, string> = {
  nueva: "border border-ember text-ember",
  en_revision: "border border-surveyor text-surveyor",
  cerrada: "border border-iron text-ash",
};

const EVENT_LABELS: Record<string, string> = {
  creada: "Alerta creada",
  reclasificada: "Reclasificada",
  estado: "Cambio de estado",
  asignacion: "Asignación",
  comentario: "Comentario",
  llamada: "Llamada",
  visita: "Visita",
  nota: "Nota",
  evento: "Evento",
};

function StatusBadge({ status }: { status: AlertStatus }) {
  return <span className={`badge ${STATUS_CLASSES[status]}`}>{STATUS_LABELS[status]}</span>;
}

export default function AlertsPage() {
  const { canSimulate } = useSession();
  const [status, setStatus] = useState<AlertStatus | "todas">("todas");
  const [selectedId, setSelectedId] = useState<number | null>(null);
  const [form, setForm] = useState<{
    status: AlertStatus;
    assigned_to: string;
    comment: string;
  }>({ status: "nueva", assigned_to: "", comment: "" });
  const [eventType, setEventType] = useState("comentario");
  const [eventDetail, setEventDetail] = useState("");
  const [message, setMessage] = useState<string | null>(null);
  const [eventMessage, setEventMessage] = useState<string | null>(null);

  const alerts = useAlerts(status);
  const summary = useAlertSummary();
  const detail = useAlert(selectedId);
  const updateAlert = useUpdateAlert();
  const createEvent = useCreateAlertEvent();

  useEffect(() => {
    if (!detail.data) return;
    setForm({
      status: detail.data.status,
      assigned_to: detail.data.assigned_to ?? "",
      comment: detail.data.comment ?? "",
    });
  }, [detail.data]);

  useEffect(() => {
    setEventDetail("");
    setMessage(null);
    setEventMessage(null);
  }, [selectedId]);

  if (!canSimulate) {
    return (
      <div className="mx-auto flex min-h-[60dvh] max-w-[800px] flex-col justify-center px-5 py-16 md:px-8">
        <AlertTriangle size={28} strokeWidth={1.5} className="text-ember" aria-hidden="true" />
        <h1 className="mt-4 text-[34px] leading-tight tracking-[-0.03em]">
          Centro de alertas reservado para operadores.
        </h1>
        <p className="mt-3 max-w-lg text-bone-muted">
          Inicia sesión con una cuenta del grupo <span className="font-mono">operadores</span> para
          revisar, asignar y cerrar alertas operativas.
        </p>
      </div>
    );
  }

  if (alerts.isLoading) return <PageLoader />;

  if (alerts.isError) {
    return (
      <div className="mx-auto flex min-h-[60dvh] max-w-[800px] flex-col justify-center px-5 py-16 md:px-8">
        <AlertTriangle size={28} strokeWidth={1.5} className="text-ember" aria-hidden="true" />
        <h1 className="mt-4 text-[34px] leading-tight tracking-[-0.03em]">
          No pudimos cargar las alertas.
        </h1>
        <p className="mt-3 text-bone-muted">Revisa la conexión con la API y vuelve a intentar.</p>
        <button
          type="button"
          className="btn btn-primary mt-6 w-fit"
          onClick={() => void alerts.refetch()}
        >
          <RefreshCw size={16} strokeWidth={1.5} aria-hidden="true" /> Reintentar
        </button>
      </div>
    );
  }

  const rows = alerts.data ?? [];
  const counts = summary.data;
  const active = detail.data ?? null;

  function handleUpdate(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!active) return;
    setMessage(null);
    updateAlert.mutate(
      {
        id: active.id,
        payload: {
          status: form.status,
          assigned_to: form.assigned_to.trim(),
          comment: form.comment.trim(),
        },
      },
      {
        onSuccess: () => setMessage("Alerta actualizada."),
        onError: (error) =>
          setMessage(error instanceof Error ? error.message : "No pudimos actualizar la alerta."),
      },
    );
  }

  function handleEvent(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!active || !eventDetail.trim()) return;
    setEventMessage(null);
    createEvent.mutate(
      {
        id: active.id,
        payload: { event_type: eventType, detail: eventDetail.trim() },
      },
      {
        onSuccess: () => {
          setEventDetail("");
          setEventMessage("Evento registrado.");
        },
        onError: (error) =>
          setEventMessage(error instanceof Error ? error.message : "No pudimos registrar el evento."),
      },
    );
  }

  return (
    <div className="mx-auto max-w-[1200px] px-5 py-12 md:px-8 md:py-16">
      <p className="font-mono text-[12px] uppercase tracking-[0.14em] text-surveyor">
        Centro de alertas
      </p>
      <div className="mt-3 flex flex-wrap items-end justify-between gap-5">
        <div>
          <h1 className="text-[40px] leading-none tracking-[-0.03em] md:text-[56px]">
            Gestión operativa
          </h1>
          <p className="mt-4 max-w-2xl text-bone-muted">
            Revisa las alertas abiertas por zona, asigna responsables y deja registro de cada
            cambio. Esta vista está reservada al grupo operadores.
          </p>
        </div>
        <button
          type="button"
          className="btn btn-ghost"
          onClick={() => {
            void alerts.refetch();
            void summary.refetch();
          }}
        >
          <RefreshCw size={16} strokeWidth={1.5} aria-hidden="true" /> Actualizar
        </button>
      </div>

      <section className="mt-10 grid gap-px bg-iron sm:grid-cols-2 lg:grid-cols-4">
        {[
          ["Total", counts?.total ?? rows.length, "Alertas registradas"],
          ["Nuevas", counts?.nueva ?? 0, "Sin revisar"],
          ["En revisión", counts?.en_revision ?? 0, "Con responsable"],
          ["Cerradas", counts?.cerrada ?? 0, "Con historial"],
        ].map(([label, value, hint]) => (
          <div key={String(label)} className="bg-obsidian px-4 py-5">
            <p className="font-mono text-[10px] uppercase tracking-[0.1em] text-ash">{label}</p>
            <p className="mt-2 font-mono text-[24px] leading-none text-bone">{value}</p>
            <p className="mt-2 font-mono text-[10px] text-ash">{hint}</p>
          </div>
        ))}
      </section>

      <div className="mt-8 grid gap-6 lg:grid-cols-[1.15fr_0.85fr]">
        <section className="border border-iron p-5">
          <div className="flex flex-wrap items-end justify-between gap-4">
            <div className="flex items-center gap-2">
              <Bell size={16} strokeWidth={1.5} className="text-ember" aria-hidden="true" />
              <h2 className="text-[22px] tracking-[-0.03em]">Alertas</h2>
            </div>
            <label className="flex min-w-[190px] flex-col gap-1">
              <span className="font-mono text-[10px] uppercase tracking-[0.1em] text-ash">
                Filtrar por estado
              </span>
              <select
                className="input font-mono text-[12px] [color-scheme:dark]"
                value={status}
                onChange={(event) => {
                  setStatus(event.target.value as AlertStatus | "todas");
                  setSelectedId(null);
                }}
              >
                <option value="todas">Todas</option>
                <option value="nueva">Nuevas</option>
                <option value="en_revision">En revisión</option>
                <option value="cerrada">Cerradas</option>
              </select>
            </label>
          </div>

          <div className="mt-4 overflow-x-auto">
            <table className="w-full text-left font-mono text-[11px]">
              <thead className="text-ash">
                <tr>
                  <th className="pb-2 font-normal">Zona</th>
                  <th className="pb-2 font-normal">Comuna</th>
                  <th className="pb-2 font-normal">Nivel</th>
                  <th className="pb-2 font-normal">Score</th>
                  <th className="pb-2 font-normal">Estado</th>
                  <th className="pb-2 font-normal">Responsable</th>
                  <th className="pb-2 font-normal">Creada</th>
                </tr>
              </thead>
              <tbody>
                {rows.map((alert) => (
                  <tr
                    key={alert.id}
                    className={`border-t border-iron ${
                      selectedId === alert.id ? "bg-iron/20" : ""
                    }`}
                  >
                    <td className="py-2">
                      <button
                        type="button"
                        className="text-left text-bone hover:text-surveyor"
                        onClick={() => setSelectedId(alert.id)}
                      >
                        {zoneLabel(alert.zone_name)}
                      </button>
                    </td>
                    <td className="py-2 text-ash">{alert.comuna}</td>
                    <td className="py-2">
                      <RiskBadge level={alert.risk_level ?? "Sin dato"} />
                    </td>
                    <td className="py-2 text-bone">{formatScore(alert.risk_score)}</td>
                    <td className="py-2">
                      <StatusBadge status={alert.status} />
                    </td>
                    <td className="py-2 text-ash">{alert.assigned_to ?? "Sin asignar"}</td>
                    <td className="py-2 text-ash">{formatDateTime(alert.created_at)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
            {rows.length === 0 ? (
              <p className="mt-4 border border-iron p-5 font-mono text-[11px] text-ash">
                No hay alertas para el estado seleccionado.
              </p>
            ) : null}
          </div>
        </section>

        <aside className="border border-iron p-5" aria-label="Detalle de la alerta">
          {selectedId === null ? (
            <p className="font-mono text-[12px] text-ash">
              Selecciona una alerta para ver su historial y gestionar su estado.
            </p>
          ) : detail.isLoading ? (
            <p className="font-mono text-[12px] text-ash">Cargando alerta…</p>
          ) : detail.isError || !active ? (
            <p className="font-mono text-[12px] text-ember">No pudimos cargar esta alerta.</p>
          ) : (
            <>
              <div className="flex items-start justify-between gap-3">
                <div>
                  <p className="font-mono text-[11px] uppercase tracking-[0.12em] text-ash">
                    {active.comuna}
                  </p>
                  <h2 className="mt-2 text-[26px] leading-tight tracking-[-0.03em] text-bone">
                    {zoneLabel(active.zone_name)}
                  </h2>
                </div>
                <StatusBadge status={active.status} />
              </div>

              <div className="mt-4 flex flex-wrap items-center gap-3">
                <RiskBadge level={active.risk_level ?? "Sin dato"} />
                <span className="font-mono text-[12px] text-ash">score</span>
                <span className="font-mono text-[20px] text-bone">
                  {formatScore(active.risk_score)}
                </span>
              </div>
              <p className="mt-2 font-mono text-[11px] text-ash">
                Creada {formatDateTime(active.created_at)}
                {active.evaluation
                  ? ` · Evaluación #${active.evaluation.id} (${active.evaluation.model_version})`
                  : ""}
              </p>
              <p className="mt-1 font-mono text-[11px] text-ash">
                Responsable: {active.assigned_to ?? "sin asignar"}
              </p>

              <div className="mt-5 border-t border-iron pt-4">
                <p className="font-mono text-[10px] uppercase tracking-[0.1em] text-ash">
                  Historial
                </p>
                <ol className="mt-3 space-y-3">
                  {active.events.map((event) => (
                    <li key={event.id} className="border-l border-iron pl-3">
                      <div className="flex flex-wrap items-center justify-between gap-2 font-mono text-[10px]">
                        <span className="text-surveyor">
                          {EVENT_LABELS[event.event_type] ?? event.event_type}
                        </span>
                        <span className="text-ash">{formatDateTime(event.created_at)}</span>
                      </div>
                      {event.detail ? (
                        <p className="mt-1 text-[13px] text-bone-muted">{event.detail}</p>
                      ) : null}
                      <p className="mt-1 font-mono text-[10px] text-ash">{event.actor}</p>
                    </li>
                  ))}
                  {active.events.length === 0 ? (
                    <li className="font-mono text-[11px] text-ash">Sin eventos registrados.</li>
                  ) : null}
                </ol>
              </div>

              <form className="mt-5 border-t border-iron pt-4" onSubmit={handleUpdate}>
                <p className="font-mono text-[10px] uppercase tracking-[0.1em] text-ash">
                  Gestionar alerta
                </p>
                <label className="mt-3 flex flex-col gap-1">
                  <span className="font-mono text-[10px] uppercase tracking-[0.1em] text-ash">
                    Estado
                  </span>
                  <select
                    className="input font-mono text-[12px] [color-scheme:dark]"
                    value={form.status}
                    onChange={(event) =>
                      setForm((current) => ({
                        ...current,
                        status: event.target.value as AlertStatus,
                      }))
                    }
                  >
                    <option value="nueva">Nueva</option>
                    <option value="en_revision">En revisión</option>
                    <option value="cerrada">Cerrada</option>
                  </select>
                </label>
                <label className="mt-3 flex flex-col gap-1">
                  <span className="font-mono text-[10px] uppercase tracking-[0.1em] text-ash">
                    Responsable
                  </span>
                  <input
                    className="input"
                    maxLength={120}
                    placeholder="Nombre o turno"
                    value={form.assigned_to}
                    onChange={(event) =>
                      setForm((current) => ({ ...current, assigned_to: event.target.value }))
                    }
                  />
                </label>
                <label className="mt-3 flex flex-col gap-1">
                  <span className="font-mono text-[10px] uppercase tracking-[0.1em] text-ash">
                    Comentario
                  </span>
                  <textarea
                    className="input min-h-20 resize-y py-2"
                    maxLength={5000}
                    placeholder="Observaciones de la alerta"
                    value={form.comment}
                    onChange={(event) =>
                      setForm((current) => ({ ...current, comment: event.target.value }))
                    }
                  />
                </label>
                <button
                  type="submit"
                  className="btn btn-primary mt-3 w-full"
                  disabled={updateAlert.isPending}
                >
                  {updateAlert.isPending ? "Guardando…" : "Guardar cambios"}
                </button>
                <p
                  className="mt-2 min-h-5 font-mono text-[11px] text-surveyor"
                  aria-live="polite"
                >
                  {message}
                </p>
              </form>

              <form className="mt-4 border-t border-iron pt-4" onSubmit={handleEvent}>
                <p className="font-mono text-[10px] uppercase tracking-[0.1em] text-ash">
                  Registrar evento
                </p>
                <label className="mt-3 flex flex-col gap-1">
                  <span className="font-mono text-[10px] uppercase tracking-[0.1em] text-ash">
                    Tipo
                  </span>
                  <select
                    className="input font-mono text-[12px] [color-scheme:dark]"
                    value={eventType}
                    onChange={(event) => setEventType(event.target.value)}
                  >
                    <option value="comentario">Comentario</option>
                    <option value="llamada">Llamada</option>
                    <option value="visita">Visita</option>
                    <option value="nota">Nota</option>
                  </select>
                </label>
                <label className="mt-3 flex flex-col gap-1">
                  <span className="font-mono text-[10px] uppercase tracking-[0.1em] text-ash">
                    Detalle
                  </span>
                  <textarea
                    className="input min-h-20 resize-y py-2"
                    maxLength={5000}
                    required
                    placeholder="¿Qué ocurrió con esta alerta?"
                    value={eventDetail}
                    onChange={(event) => setEventDetail(event.target.value)}
                  />
                </label>
                <button
                  type="submit"
                  className="btn btn-ghost mt-3 w-full"
                  disabled={createEvent.isPending || !eventDetail.trim()}
                >
                  {createEvent.isPending ? "Registrando…" : "Registrar evento"}
                </button>
                <p
                  className="mt-2 min-h-5 font-mono text-[11px] text-surveyor"
                  aria-live="polite"
                >
                  {eventMessage}
                </p>
              </form>
            </>
          )}
        </aside>
      </div>
    </div>
  );
}
