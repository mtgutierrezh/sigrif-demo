import { Activity, AlertTriangle, Database, Gauge, RefreshCw, Server, Waves } from "lucide-react";
import { useState } from "react";

import { PageLoader } from "../components/PageLoader";
import { RiskBadge } from "../components/RiskBadge";
import { useSession } from "../components/session";
import {
  useModelInfo,
  useOpsAlerts,
  useOpsIngestion,
  useOpsOverview,
  useRunIngestion,
} from "../features/zones/useOps";
import { formatDateTime, formatNumber, formatScore } from "../lib/format";

function metricValue(metrics: Record<string, unknown>, key: string): number | null {
  const value = metrics[key];
  return typeof value === "number" ? value : null;
}

function sourceLabel(source: string | null | undefined): string {
  if (!source) return "Sin dato";
  return {
    dmc: "DMC",
    open_meteo: "Open-Meteo",
    synthetic: "Sintético (pruebas)",
    manual: "Manual",
    simulacion: "Simulación",
  }[source] ?? source;
}

export default function OperationsPage() {
  const { canSimulate } = useSession();
  const overview = useOpsOverview();
  const alerts = useOpsAlerts();
  const ingestion = useOpsIngestion();
  const model = useModelInfo();
  const runIngestion = useRunIngestion();
  const [provider, setProvider] = useState("auto");

  if (!canSimulate) {
    return (
      <div className="mx-auto flex min-h-[60dvh] max-w-[800px] flex-col justify-center px-5 py-16 md:px-8">
        <AlertTriangle size={28} strokeWidth={1.5} className="text-ember" aria-hidden="true" />
        <h1 className="mt-4 text-[34px] leading-tight tracking-[-0.03em]">
          Panel reservado para operadores.
        </h1>
        <p className="mt-3 max-w-lg text-bone-muted">
          Inicia sesión con una cuenta del grupo <span className="font-mono">operadores</span> para
          revisar la ingesta, el modelo, las alertas y las métricas operativas.
        </p>
      </div>
    );
  }

  if (overview.isLoading) return <PageLoader />;

  if (overview.isError || !overview.data) {
    return (
      <div className="mx-auto flex min-h-[60dvh] max-w-[800px] flex-col justify-center px-5 py-16 md:px-8">
        <AlertTriangle size={28} strokeWidth={1.5} className="text-ember" aria-hidden="true" />
        <h1 className="mt-4 text-[34px] leading-tight tracking-[-0.03em]">Panel no disponible.</h1>
        <p className="mt-3 text-bone-muted">Revisa la conexión con la API y vuelve a intentar.</p>
        <button type="button" className="btn btn-primary mt-6 w-fit" onClick={() => void overview.refetch()}>
          <RefreshCw size={16} strokeWidth={1.5} aria-hidden="true" /> Reintentar
        </button>
      </div>
    );
  }

  const data = overview.data;
  const freshness =
    data.freshness_minutes === null ? "Sin dato" : `${formatNumber(data.freshness_minutes, 0)} min`;
  const metrics = model.data?.metrics ?? {};
  const importance = model.data?.feature_importance ?? [];

  return (
    <div className="mx-auto max-w-[1200px] px-5 py-12 md:px-8 md:py-16">
      <p className="font-mono text-[12px] uppercase tracking-[0.14em] text-surveyor">Operaciones</p>
      <div className="mt-3 flex flex-wrap items-end justify-between gap-5">
        <div>
          <h1 className="text-[40px] leading-none tracking-[-0.03em] md:text-[56px]">
            Estado del sistema
          </h1>
          <p className="mt-4 max-w-2xl text-bone-muted">
            Ingesta, frescura de datos, alertas y salud del modelo. Esta vista está reservada al
            grupo operadores.
          </p>
        </div>
        <button type="button" className="btn btn-ghost" onClick={() => void overview.refetch()}>
          <RefreshCw size={16} strokeWidth={1.5} aria-hidden="true" /> Actualizar
        </button>
      </div>

      <section className="mt-10 grid gap-px bg-iron sm:grid-cols-2 lg:grid-cols-5">
        {[
          ["Zonas", String(data.zones), "Monitoreadas"],
          ["Frescura", freshness, data.stale ? "Datos desactualizados" : "Datos vigentes"],
          ["Alertas Alto", String(data.active_alerts), "Zonas en alerta"],
          ["Cola SQS", data.queue_depth === null ? "—" : String(data.queue_depth), "Mensajes"],
          ["p95 API", data.p95_ms === null ? "—" : `${formatNumber(data.p95_ms, 0)} ms`, "Últimos 500"],
        ].map(([label, value, hint]) => (
          <div key={label} className="bg-obsidian px-4 py-5">
            <p className="font-mono text-[10px] uppercase tracking-[0.1em] text-ash">{label}</p>
            <p className="mt-2 font-mono text-[24px] leading-none text-bone">{value}</p>
            <p className="mt-2 font-mono text-[10px] text-ash">{hint}</p>
          </div>
        ))}
      </section>

      <div className="mt-8 grid gap-6 lg:grid-cols-[1.1fr_0.9fr]">
        <section className="border border-iron p-5">
          <div className="flex items-center gap-2">
            <Database size={16} strokeWidth={1.5} className="text-surveyor" aria-hidden="true" />
            <h2 className="text-[22px] tracking-[-0.03em]">Datos e ingesta</h2>
          </div>
          <dl className="mt-5 grid gap-4 sm:grid-cols-2">
            <div>
              <dt className="font-mono text-[10px] uppercase tracking-[0.1em] text-ash">Última lectura</dt>
              <dd className="mt-1 font-mono text-[12px] text-bone">{formatDateTime(data.last_ingest)}</dd>
            </div>
            <div>
              <dt className="font-mono text-[10px] uppercase tracking-[0.1em] text-ash">Fuente</dt>
              <dd className="mt-1 font-mono text-[12px] text-bone">{sourceLabel(data.last_source)}</dd>
            </div>
            <div>
              <dt className="font-mono text-[10px] uppercase tracking-[0.1em] text-ash">Distribución</dt>
              <dd className="mt-1 font-mono text-[12px] text-bone">
                Bajo {data.risk_counts.Bajo ?? 0} · Medio {data.risk_counts.Medio ?? 0} · Alto{" "}
                {data.risk_counts.Alto ?? 0}
              </dd>
            </div>
            <div>
              <dt className="font-mono text-[10px] uppercase tracking-[0.1em] text-ash">Fuentes históricas</dt>
              <dd className="mt-1 font-mono text-[12px] text-bone">
                {Object.entries(data.sources)
                  .map(([source, count]) => `${sourceLabel(source)} ${count}`)
                  .join(" · ") || "Sin lecturas"}
              </dd>
            </div>
          </dl>
          <div className="mt-6 border-t border-iron pt-5">
            <label className="flex flex-col gap-1">
              <span className="font-mono text-[10px] uppercase tracking-[0.1em] text-ash">
                Ejecutar ingesta
              </span>
              <select
                className="input font-mono text-[12px] [color-scheme:dark]"
                value={provider}
                onChange={(event) => setProvider(event.target.value)}
              >
                <option className="bg-obsidian text-bone" value="auto">Automática (DMC + Open-Meteo)</option>
                <option className="bg-obsidian text-bone" value="dmc">DMC</option>
                <option className="bg-obsidian text-bone" value="open_meteo">Open-Meteo</option>
                <option className="bg-obsidian text-bone" value="synthetic">Sintética (pruebas)</option>
              </select>
            </label>
            <button
              type="button"
              className="btn btn-primary mt-3"
              disabled={runIngestion.isPending}
              onClick={() => runIngestion.mutate(provider)}
            >
              {runIngestion.isPending ? "Ejecutando…" : "Ejecutar ahora"}
            </button>
            <p className="mt-3 min-h-5 font-mono text-[11px] text-surveyor" aria-live="polite">
              {runIngestion.isError
                ? "No se pudo ejecutar la ingesta."
                : runIngestion.data
                  ? `${runIngestion.data.provider}: ${runIngestion.data.zones_ok}/${runIngestion.data.zones_total} zonas OK.`
                  : ""}
            </p>
          </div>
        </section>

        <section className="border border-iron p-5">
          <div className="flex items-center gap-2">
            <Server size={16} strokeWidth={1.5} className="text-surveyor" aria-hidden="true" />
            <h2 className="text-[22px] tracking-[-0.03em]">Modelo</h2>
          </div>
          <p className="mt-4 font-mono text-[13px] text-bone">{data.model_version}</p>
          <p className="mt-1 font-mono text-[10px] text-ash">
            {model.data?.trained_at ? `Entrenado ${formatDateTime(model.data.trained_at)}` : "Modelo activo"}
          </p>
          <div className="mt-4 grid grid-cols-2 gap-3">
            {[
              ["Accuracy", metricValue(metrics, "accuracy")],
              ["Macro F1", metricValue(metrics, "macro_f1")],
              ["ROC-AUC", metricValue(metrics, "roc_auc_ovr")],
              ["CV F1", metricValue(metrics, "cv_macro_f1_mean")],
            ].map(([label, value]) => (
              <div key={String(label)} className="border-t border-iron pt-3">
                <p className="font-mono text-[10px] uppercase tracking-[0.1em] text-ash">{label}</p>
                <p className="mt-1 font-mono text-[16px] text-bone">
                  {typeof value === "number" ? formatNumber(value, 3) : "—"}
                </p>
              </div>
            ))}
          </div>
          <div className="mt-5 border-t border-iron pt-4">
            <p className="font-mono text-[10px] uppercase tracking-[0.1em] text-ash">Importancia de variables</p>
            <div className="mt-3 space-y-2">
              {importance.slice(0, 6).map((item) => {
                const feature = String(item.feature ?? item.label ?? "—");
                const value = Number(item.importance ?? 0);
                return (
                  <div key={feature} className="grid grid-cols-[1fr_auto] gap-3 font-mono text-[11px]">
                    <div className="flex items-center gap-2">
                      <span className="text-bone">{feature}</span>
                      <span className="h-1 flex-1 bg-iron">
                        <span className="block h-full bg-surveyor" style={{ width: `${Math.min(100, value * 250)}%` }} />
                      </span>
                    </div>
                    <span className="text-ash">{formatNumber(value, 3)}</span>
                  </div>
                );
              })}
              {importance.length === 0 ? <p className="font-mono text-[11px] text-ash">Sin metadatos del modelo.</p> : null}
            </div>
          </div>
        </section>
      </div>

      <div className="mt-6 grid gap-6 lg:grid-cols-2">
        <section className="border border-iron p-5">
          <div className="flex items-center gap-2">
            <Waves size={16} strokeWidth={1.5} className="text-surveyor" aria-hidden="true" />
            <h2 className="text-[22px] tracking-[-0.03em]">Drift por variable</h2>
          </div>
          <div className="mt-4 overflow-x-auto">
            <table className="w-full text-left font-mono text-[11px]">
              <thead className="text-ash">
                <tr>
                  <th className="pb-2 font-normal">Variable</th>
                  <th className="pb-2 font-normal">PSI</th>
                  <th className="pb-2 font-normal">Estado</th>
                  <th className="pb-2 font-normal">Media actual</th>
                </tr>
              </thead>
              <tbody>
                {data.drift.map((item) => (
                  <tr key={item.feature} className="border-t border-iron">
                    <td className="py-2 text-bone">{item.feature}</td>
                    <td className="py-2 text-bone">{formatNumber(item.psi, 3)}</td>
                    <td className={`py-2 ${item.status === "deriva" ? "text-ember" : "text-surveyor"}`}>
                      {item.status}
                    </td>
                    <td className="py-2 text-ash">{formatNumber(item.current_mean, 2)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
            {data.drift.length === 0 ? <p className="mt-3 font-mono text-[11px] text-ash">Aún no hay suficientes lecturas.</p> : null}
          </div>
        </section>

        <section className="border border-iron p-5">
          <div className="flex items-center gap-2">
            <Gauge size={16} strokeWidth={1.5} className="text-surveyor" aria-hidden="true" />
            <h2 className="text-[22px] tracking-[-0.03em]">Últimas ingestas</h2>
          </div>
          <div className="mt-4 space-y-3">
            {(ingestion.data ?? []).slice(0, 5).map((run) => (
              <div key={run.id} className="border-t border-iron pt-3 font-mono text-[11px]">
                <div className="flex items-center justify-between gap-3">
                  <span className="text-bone">{sourceLabel(run.provider)}</span>
                  <span className={run.status === "ok" ? "text-surveyor" : "text-ember"}>{run.status}</span>
                </div>
                <p className="mt-1 text-ash">
                  {formatDateTime(run.started_at)} · {run.zones_ok}/{run.zones_total} zonas ·{" "}
                  {run.duration_ms === null ? "—" : `${formatNumber(run.duration_ms, 0)} ms`}
                </p>
              </div>
            ))}
            {(ingestion.data ?? []).length === 0 ? (
              <p className="font-mono text-[11px] text-ash">Sin ejecuciones registradas.</p>
            ) : null}
          </div>
        </section>
      </div>

      <section className="mt-6 border border-iron p-5">
        <div className="flex items-center gap-2">
          <Activity size={16} strokeWidth={1.5} className="text-ember" aria-hidden="true" />
          <h2 className="text-[22px] tracking-[-0.03em]">Zonas en alerta</h2>
        </div>
        <div className="mt-4 overflow-x-auto">
          <table className="w-full text-left font-mono text-[11px]">
            <thead className="text-ash">
              <tr>
                <th className="pb-2 font-normal">Zona</th>
                <th className="pb-2 font-normal">Comuna</th>
                <th className="pb-2 font-normal">Nivel</th>
                <th className="pb-2 font-normal">Score</th>
                <th className="pb-2 font-normal">Fuente</th>
                <th className="pb-2 font-normal">Actualizada</th>
              </tr>
            </thead>
            <tbody>
              {(alerts.data ?? []).map((zone) => (
                <tr key={zone.id} className="border-t border-iron">
                  <td className="py-2 text-bone">{zone.name}</td>
                  <td className="py-2 text-ash">{zone.comuna}</td>
                  <td className="py-2"><RiskBadge level={zone.risk_level} /></td>
                  <td className="py-2 text-bone">{formatScore(zone.risk_score)}</td>
                  <td className="py-2 text-ash">{sourceLabel(zone.last_source)}</td>
                  <td className="py-2 text-ash">{formatDateTime(zone.updated_at)}</td>
                </tr>
              ))}
            </tbody>
          </table>
          {(alerts.data ?? []).length === 0 ? (
            <p className="mt-3 font-mono text-[11px] text-ash">No hay zonas en nivel Alto.</p>
          ) : null}
        </div>
      </section>
    </div>
  );
}
