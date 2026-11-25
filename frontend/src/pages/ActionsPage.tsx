import { AlertTriangle, ClipboardList, RefreshCw } from "lucide-react";
import { useState, type FormEvent } from "react";
import { Link } from "react-router-dom";

import { PageLoader } from "../components/PageLoader";
import { useSession } from "../components/session";
import {
  useActionSummary,
  useActions,
  useCreateAction,
  useUpdateAction,
} from "../features/zones/useActions";
import type {
  ActionKind,
  ActionPriority,
  ActionStatus,
  PreventiveAction,
} from "../features/zones/types";
import { useZones } from "../features/zones/useZones";
import { actorLabel } from "../lib/actor";
import { formatNumber } from "../lib/format";
import { zoneLabel } from "../lib/names";

const STATUS_LABELS: Record<ActionStatus, string> = {
  pendiente: "Pendiente",
  en_ejecucion: "En ejecución",
  completada: "Completada",
  cancelada: "Cancelada",
};

const STATUS_CLASSES: Record<ActionStatus, string> = {
  pendiente: "border border-ember text-ember",
  en_ejecucion: "border border-surveyor text-surveyor",
  completada: "border border-iron text-ash",
  cancelada: "border border-iron text-ash",
};

const KIND_LABELS: Record<ActionKind, string> = {
  accion: "Acción preventiva",
  incidente: "Incidente",
};

const PRIORITY_LABELS: Record<ActionPriority, string> = {
  baja: "Baja",
  media: "Media",
  alta: "Alta",
};

const CATEGORY_LABELS: Record<string, string> = {
  vegetacion_seca: "Vegetación seca",
  microbasural: "Microbasural",
  quema: "Quema",
  acceso_bloqueado: "Acceso bloqueado",
  infraestructura: "Infraestructura",
  otro: "Otro",
};

const CATEGORIES = Object.keys(CATEGORY_LABELS);

const EMPTY_FORM = {
  zoneText: "",
  kind: "accion" as ActionKind,
  category: "vegetacion_seca",
  title: "",
  priority: "media" as ActionPriority,
  assigned_to: "",
  due_date: "",
  detail: "",
};

function StatusBadge({ status }: { status: ActionStatus }) {
  return <span className={`badge ${STATUS_CLASSES[status]}`}>{STATUS_LABELS[status]}</span>;
}

function ActionButtons({
  action,
  onChange,
  pending,
}: {
  action: PreventiveAction;
  onChange: (status: ActionStatus) => void;
  pending: boolean;
}) {
  if (action.status === "completada" || action.status === "cancelada") {
    return (
      <button
        type="button"
        className="btn btn-ghost px-3 py-2 text-[11px]"
        disabled={pending}
        onClick={() => onChange("pendiente")}
        aria-label={`Reabrir ${action.title}`}
      >
        Reabrir
      </button>
    );
  }

  return (
    <div className="flex flex-wrap gap-2">
      {action.status === "pendiente" ? (
        <button
          type="button"
          className="btn btn-ghost px-3 py-2 text-[11px]"
          disabled={pending}
          onClick={() => onChange("en_ejecucion")}
          aria-label={`Iniciar ${action.title}`}
        >
          Iniciar
        </button>
      ) : null}
      <button
        type="button"
        className="btn btn-primary px-3 py-2 text-[11px]"
        disabled={pending}
        onClick={() => onChange("completada")}
        aria-label={`Completar ${action.title}`}
      >
        Completar
      </button>
      <button
        type="button"
        className="btn btn-ghost px-3 py-2 text-[11px]"
        disabled={pending}
        onClick={() => onChange("cancelada")}
        aria-label={`Cancelar ${action.title}`}
      >
        Cancelar
      </button>
    </div>
  );
}

export default function ActionsPage() {
  const { canSimulate } = useSession();
  const [status, setStatus] = useState<ActionStatus | "todos">("todos");
  const [kind, setKind] = useState<ActionKind | "todos">("todos");
  const [form, setForm] = useState(EMPTY_FORM);
  const [message, setMessage] = useState<string | null>(null);

  const actions = useActions({ status, kind });
  const summary = useActionSummary();
  const zones = useZones();
  const createAction = useCreateAction();
  const updateAction = useUpdateAction();

  if (!canSimulate) {
    return (
      <div className="mx-auto flex min-h-[60dvh] max-w-[800px] flex-col justify-center px-5 py-16 md:px-8">
        <AlertTriangle size={28} strokeWidth={1.5} className="text-ember" aria-hidden="true" />
        <h1 className="mt-4 text-[34px] leading-tight tracking-[-0.03em]">
          Acciones reservadas para operadores.
        </h1>
        <p className="mt-3 max-w-lg text-bone-muted">
          Inicia sesión con una cuenta del grupo <span className="font-mono">operadores</span> para
          registrar acciones preventivas e incidentes.
        </p>
      </div>
    );
  }

  if (actions.isLoading) return <PageLoader />;

  if (actions.isError) {
    return (
      <div className="mx-auto flex min-h-[60dvh] max-w-[800px] flex-col justify-center px-5 py-16 md:px-8">
        <AlertTriangle size={28} strokeWidth={1.5} className="text-ember" aria-hidden="true" />
        <h1 className="mt-4 text-[34px] leading-tight tracking-[-0.03em]">
          No pudimos cargar las acciones.
        </h1>
        <p className="mt-3 text-bone-muted">Revisa la conexión con la API y vuelve a intentar.</p>
        <button
          type="button"
          className="btn btn-primary mt-6 w-fit"
          onClick={() => void actions.refetch()}
        >
          <RefreshCw size={16} strokeWidth={1.5} aria-hidden="true" /> Reintentar
        </button>
      </div>
    );
  }

  const rows = actions.data ?? [];
  const counts = summary.data;

  function handleCreate(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setMessage(null);
    const text = form.zoneText.trim().toLowerCase();
    const zone = (zones.data ?? []).find(
      (item) =>
        zoneLabel(item.name, item.display_name).toLowerCase() === text ||
        item.name.toLowerCase() === text,
    );
    if (!zone) {
      setMessage("Selecciona una zona de la lista de sugerencias.");
      return;
    }
    if (!form.title.trim()) {
      setMessage("Escribe un título para la acción.");
      return;
    }
    createAction.mutate(
      {
        zone_id: zone.id,
        kind: form.kind,
        category: form.category,
        title: form.title.trim(),
        detail: form.detail.trim() || null,
        priority: form.priority,
        assigned_to: form.assigned_to.trim() || null,
        due_date: form.due_date || null,
      },
      {
        onSuccess: () => {
          setForm((current) => ({
            ...EMPTY_FORM,
            kind: current.kind,
            priority: current.priority,
          }));
          setMessage(
            form.kind === "incidente"
              ? "Incidente registrado."
              : "Acción preventiva registrada.",
          );
        },
        onError: (error) =>
          setMessage(error instanceof Error ? error.message : "No pudimos registrar la acción."),
      },
    );
  }

  function handleTransition(action: PreventiveAction, next: ActionStatus) {
    setMessage(null);
    updateAction.mutate(
      { id: action.id, payload: { status: next } },
      {
        onSuccess: () => setMessage(`Acción #${action.id} actualizada.`),
        onError: (error) =>
          setMessage(error instanceof Error ? error.message : "No pudimos actualizar la acción."),
      },
    );
  }

  return (
    <div className="mx-auto max-w-[1200px] px-5 py-12 md:px-8 md:py-16">
      <p className="font-mono text-[12px] uppercase tracking-[0.14em] text-surveyor">
        Gestión preventiva
      </p>
      <div className="mt-3 flex flex-wrap items-end justify-between gap-5">
        <div>
          <h1 className="text-[40px] leading-none tracking-[-0.03em] md:text-[56px]">
            Acciones e incidentes
          </h1>
          <p className="mt-4 max-w-2xl text-bone-muted">
            Registra acciones preventivas, incidentes y su avance. Cada cambio conserva el
            responsable y la fecha de cierre. Esta vista está reservada al grupo operadores.
          </p>
        </div>
        <div className="flex flex-wrap gap-2">
          <Link className="btn btn-ghost" to="/prioridad">
            <ClipboardList size={16} strokeWidth={1.5} aria-hidden="true" /> Prioridad
          </Link>
          <button
            type="button"
            className="btn btn-ghost"
            onClick={() => {
              void actions.refetch();
              void summary.refetch();
            }}
          >
            <RefreshCw size={16} strokeWidth={1.5} aria-hidden="true" /> Actualizar
          </button>
        </div>
      </div>

      <section className="mt-10 grid gap-px bg-iron sm:grid-cols-2 lg:grid-cols-5">
        {[
          ["Total", counts?.total ?? rows.length, "Registros"],
          ["Pendientes", counts?.pendiente ?? 0, "Por iniciar"],
          ["En ejecución", counts?.en_ejecucion ?? 0, "En curso"],
          ["Vencidas", counts?.overdue ?? 0, "Fuera de plazo"],
          ["Incidentes abiertos", counts?.open_incidents ?? 0, "Pendientes o en curso"],
        ].map(([label, value, hint]) => (
          <div key={String(label)} className="bg-obsidian px-4 py-5">
            <p className="font-mono text-[10px] uppercase tracking-[0.1em] text-ash">{label}</p>
            <p className="mt-2 font-mono text-[24px] leading-none text-bone">{value}</p>
            <p className="mt-2 font-mono text-[10px] text-ash">{hint}</p>
          </div>
        ))}
      </section>

      <p className="mt-2 min-h-5 font-mono text-[11px] text-surveyor" aria-live="polite">
        {summary.isError ? "No pudimos cargar el resumen de acciones." : message}
      </p>

      <section className="mt-8 border border-iron p-5" aria-labelledby="tabla-acciones">
        <div className="flex flex-wrap items-end justify-between gap-4">
          <div className="flex items-center gap-2">
            <ClipboardList size={16} strokeWidth={1.5} className="text-surveyor" aria-hidden="true" />
            <h2 id="tabla-acciones" className="text-[22px] tracking-[-0.03em]">
              Registro de acciones
            </h2>
          </div>
          <div className="flex flex-wrap gap-3">
            <label className="flex min-w-[170px] flex-col gap-1">
              <span className="font-mono text-[10px] uppercase tracking-[0.1em] text-ash">
                Estado
              </span>
              <select
                className="input font-mono text-[12px] [color-scheme:dark]"
                value={status}
                onChange={(event) => setStatus(event.target.value as ActionStatus | "todos")}
              >
                <option value="todos">Todos</option>
                {Object.entries(STATUS_LABELS).map(([value, label]) => (
                  <option key={value} value={value}>
                    {label}
                  </option>
                ))}
              </select>
            </label>
            <label className="flex min-w-[170px] flex-col gap-1">
              <span className="font-mono text-[10px] uppercase tracking-[0.1em] text-ash">Tipo</span>
              <select
                className="input font-mono text-[12px] [color-scheme:dark]"
                value={kind}
                onChange={(event) => setKind(event.target.value as ActionKind | "todos")}
              >
                <option value="todos">Todos</option>
                {Object.entries(KIND_LABELS).map(([value, label]) => (
                  <option key={value} value={value}>
                    {label}
                  </option>
                ))}
              </select>
            </label>
          </div>
        </div>

        <div className="mt-4 overflow-x-auto">
          <table className="w-full min-w-[1040px] text-left font-mono text-[11px]">
            <caption className="sr-only">
              Acciones preventivas e incidentes por zona, con responsable, vencimiento y estado
            </caption>
            <thead className="text-ash">
              <tr>
                <th className="pb-2 font-normal">Zona</th>
                <th className="pb-2 font-normal">Tipo</th>
                <th className="pb-2 font-normal">Categoría</th>
                <th className="pb-2 font-normal">Título</th>
                <th className="pb-2 font-normal">Responsable</th>
                <th className="pb-2 font-normal">Vencimiento</th>
                <th className="pb-2 font-normal">Estado</th>
                <th className="pb-2 font-normal">Acciones</th>
              </tr>
            </thead>
            <tbody>
              {rows.map((action) => (
                <tr key={action.id} className="border-t border-iron">
                  <td className="py-3 pr-3">
                    <Link
                      to={`/mapa?zona=${action.zone_id}`}
                      className="text-bone hover:text-surveyor"
                    >
                      {zoneLabel(action.zone_name)}
                    </Link>
                    <p className="mt-1 text-[10px] text-ash">{action.comuna}</p>
                  </td>
                  <td className="py-3 pr-3 text-ash">{KIND_LABELS[action.kind]}</td>
                  <td className="py-3 pr-3 text-ash">
                    {CATEGORY_LABELS[action.category] ?? action.category}
                  </td>
                  <td className="max-w-[220px] py-3 pr-3">
                    <p className="truncate text-bone" title={action.title}>
                      {action.title}
                    </p>
                    <p className="mt-1 text-[10px] text-ash">
                      prioridad {PRIORITY_LABELS[action.priority]} · {actorLabel(action.created_by)}
                    </p>
                  </td>
                  <td className="py-3 pr-3 text-ash">{action.assigned_to ?? "Sin asignar"}</td>
                  <td
                    className={`whitespace-nowrap py-3 pr-3 ${
                      action.overdue ? "text-ember" : "text-ash"
                    }`}
                  >
                    {action.due_date ?? "Sin plazo"}
                    {action.overdue ? " · vencida" : ""}
                  </td>
                  <td className="py-3 pr-3">
                    <StatusBadge status={action.status} />
                  </td>
                  <td className="py-3">
                    <ActionButtons
                      action={action}
                      pending={updateAction.isPending}
                      onChange={(next) => handleTransition(action, next)}
                    />
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
          {rows.length === 0 ? (
            <p className="mt-4 border border-iron p-5 font-mono text-[11px] text-ash">
              No hay acciones para los filtros seleccionados.
            </p>
          ) : null}
        </div>
      </section>

      <section className="mt-8 border border-iron p-5" aria-labelledby="nueva-accion">
        <div className="flex items-center gap-2">
          <ClipboardList size={16} strokeWidth={1.5} className="text-surveyor" aria-hidden="true" />
          <h2 id="nueva-accion" className="text-[22px] tracking-[-0.03em]">
            Nueva acción o incidente
          </h2>
        </div>
        <form className="mt-5 grid gap-4 md:grid-cols-2" onSubmit={handleCreate}>
          <label className="flex flex-col gap-1">
            <span className="font-mono text-[10px] uppercase tracking-[0.1em] text-ash">
              Zona
            </span>
            <input
              className="input"
              list="zonas-acciones"
              placeholder="Busca por nombre de zona"
              required
              value={form.zoneText}
              onChange={(event) =>
                setForm((current) => ({ ...current, zoneText: event.target.value }))
              }
            />
            <datalist id="zonas-acciones">
              {(zones.data ?? []).map((zone) => (
                <option key={zone.id} value={zoneLabel(zone.name, zone.display_name)}>
                  {zone.comuna}
                </option>
              ))}
            </datalist>
          </label>
          <label className="flex flex-col gap-1">
            <span className="font-mono text-[10px] uppercase tracking-[0.1em] text-ash">Tipo</span>
            <select
              className="input font-mono text-[12px] [color-scheme:dark]"
              value={form.kind}
              onChange={(event) =>
                setForm((current) => ({ ...current, kind: event.target.value as ActionKind }))
              }
            >
              {Object.entries(KIND_LABELS).map(([value, label]) => (
                <option key={value} value={value}>
                  {label}
                </option>
              ))}
            </select>
          </label>
          <label className="flex flex-col gap-1">
            <span className="font-mono text-[10px] uppercase tracking-[0.1em] text-ash">
              Categoría
            </span>
            <select
              className="input font-mono text-[12px] [color-scheme:dark]"
              value={form.category}
              onChange={(event) =>
                setForm((current) => ({ ...current, category: event.target.value }))
              }
            >
              {CATEGORIES.map((category) => (
                <option key={category} value={category}>
                  {CATEGORY_LABELS[category]}
                </option>
              ))}
            </select>
          </label>
          <label className="flex flex-col gap-1">
            <span className="font-mono text-[10px] uppercase tracking-[0.1em] text-ash">
              Prioridad
            </span>
            <select
              className="input font-mono text-[12px] [color-scheme:dark]"
              value={form.priority}
              onChange={(event) =>
                setForm((current) => ({
                  ...current,
                  priority: event.target.value as ActionPriority,
                }))
              }
            >
              {Object.entries(PRIORITY_LABELS).map(([value, label]) => (
                <option key={value} value={value}>
                  {label}
                </option>
              ))}
            </select>
          </label>
          <label className="flex flex-col gap-1 md:col-span-2">
            <span className="font-mono text-[10px] uppercase tracking-[0.1em] text-ash">
              Título
            </span>
            <input
              className="input"
              maxLength={160}
              required
              placeholder="Ej. Despejar vegetación seca junto al acceso"
              value={form.title}
              onChange={(event) =>
                setForm((current) => ({ ...current, title: event.target.value }))
              }
            />
          </label>
          <label className="flex flex-col gap-1">
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
          <label className="flex flex-col gap-1">
            <span className="font-mono text-[10px] uppercase tracking-[0.1em] text-ash">
              Vencimiento
            </span>
            <input
              className="input font-mono text-[12px] [color-scheme:dark]"
              type="date"
              value={form.due_date}
              onChange={(event) =>
                setForm((current) => ({ ...current, due_date: event.target.value }))
              }
            />
          </label>
          <label className="flex flex-col gap-1 md:col-span-2">
            <span className="font-mono text-[10px] uppercase tracking-[0.1em] text-ash">
              Detalle
            </span>
            <textarea
              className="input min-h-24 resize-y py-2"
              maxLength={5000}
              placeholder="Contexto, acceso, coordinación o evidencia disponible"
              value={form.detail}
              onChange={(event) =>
                setForm((current) => ({ ...current, detail: event.target.value }))
              }
            />
          </label>
          <div className="md:col-span-2">
            <button
              type="submit"
              className="btn btn-primary"
              disabled={createAction.isPending || zones.isLoading}
            >
              {createAction.isPending ? "Registrando…" : "Registrar"}
            </button>
          </div>
        </form>
        <p className="mt-2 font-mono text-[10px] text-ash">
          {zones.isError
            ? "No pudimos cargar las zonas para el buscador."
            : `${formatNumber((zones.data ?? []).length, 0)} zonas disponibles en el buscador.`}
        </p>
      </section>
    </div>
  );
}
