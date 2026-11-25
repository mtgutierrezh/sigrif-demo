import { AlertTriangle, Columns3 } from "lucide-react";
import { useMemo, useState } from "react";
import { Link } from "react-router-dom";

import { PageLoader } from "../components/PageLoader";
import { RiskBadge } from "../components/RiskBadge";
import { useSession } from "../components/session";
import { useZoneEvaluations } from "../features/zones/useEvaluations";
import { usePriority } from "../features/zones/usePriority";
import type { EvaluationSummary, Zone } from "../features/zones/types";
import { useZones } from "../features/zones/useZones";
import { formatDateTime, formatNumber } from "../lib/format";
import { zoneLabel } from "../lib/names";
import { riskColor } from "../lib/risk";

function Sparkline({ zone, points }: { zone: Zone; points: EvaluationSummary[] }) {
  const ordered = [...points].reverse();
  const scores = ordered
    .map((item) => item.risk_score)
    .filter((value): value is number => typeof value === "number");
  if (scores.length < 2) {
    return (
      <p className="mt-3 font-mono text-[10px] text-ash">
        Historial insuficiente para dibujar la serie.
      </p>
    );
  }
  const width = 240;
  const height = 68;
  const top = 8;
  const bottom = 54;
  const coords = scores
    .map((score, index) => {
      const x = scores.length === 1 ? 0 : (index / (scores.length - 1)) * width;
      const y = bottom - Math.min(1, Math.max(0, score)) * (bottom - top);
      return `${x.toFixed(1)},${y.toFixed(1)}`;
    })
    .join(" ");

  return (
    <svg
      viewBox={`0 0 ${width} ${height}`}
      className="mt-3 h-20 w-full"
      role="img"
      aria-label={`Historial reciente de ${zoneLabel(zone.name, zone.display_name)}: ${scores.length} evaluaciones`}
    >
      <line x1="0" y1={bottom} x2={width} y2={bottom} stroke="#404040" strokeWidth="1" />
      <line x1="0" y1={top} x2={width} y2={top} stroke="#404040" strokeWidth="0.5" />
      <polyline
        points={coords}
        fill="none"
        stroke={riskColor(zone.risk_level)}
        strokeWidth="2"
        strokeLinejoin="round"
        strokeLinecap="round"
      />
    </svg>
  );
}

function ZoneSelect({
  index,
  value,
  zones,
  selected,
  onChange,
}: {
  index: number;
  value: number | null;
  zones: Zone[];
  selected: Array<number | null>;
  onChange: (value: number | null) => void;
}) {
  const label = index === 0 ? "Zona A" : index === 1 ? "Zona B" : "Zona C (opcional)";
  return (
    <label className="flex flex-col gap-1">
      <span className="font-mono text-[10px] uppercase tracking-[0.1em] text-ash">{label}</span>
      <select
        className="input font-mono text-[12px] [color-scheme:dark]"
        value={value ?? ""}
        onChange={(event) => onChange(event.target.value ? Number(event.target.value) : null)}
      >
        <option value="">{index === 2 ? "Sin tercera zona" : "Selecciona una zona"}</option>
        {zones.map((zone) => (
          <option
            key={zone.id}
            value={zone.id}
            disabled={selected.includes(zone.id) && zone.id !== value}
          >
            {zoneLabel(zone.name, zone.display_name)} · {zone.comuna}
          </option>
        ))}
      </select>
    </label>
  );
}

export default function ComparePage() {
  const { canSimulate } = useSession();
  const zonesQuery = useZones();
  const priority = usePriority(1000);
  const [selectedIds, setSelectedIds] = useState<Array<number | null>>([null, null, null]);

  const historyA = useZoneEvaluations(selectedIds[0], 12);
  const historyB = useZoneEvaluations(selectedIds[1], 12);
  const historyC = useZoneEvaluations(selectedIds[2], 12);

  const zoneById = useMemo(
    () => new Map((zonesQuery.data ?? []).map((zone) => [zone.id, zone])),
    [zonesQuery.data],
  );
  const priorityById = useMemo(
    () => new Map((priority.data?.items ?? []).map((item) => [item.zone_id, item])),
    [priority.data],
  );

  if (!canSimulate) {
    return (
      <div className="mx-auto flex min-h-[60dvh] max-w-[800px] flex-col justify-center px-5 py-16 md:px-8">
        <AlertTriangle size={28} strokeWidth={1.5} className="text-ember" aria-hidden="true" />
        <h1 className="mt-4 text-[34px] leading-tight tracking-[-0.03em]">
          Comparador reservado para operadores.
        </h1>
        <p className="mt-3 max-w-lg text-bone-muted">
          Inicia sesión con una cuenta del grupo <span className="font-mono">operadores</span> para
          comparar zonas y revisar su historial reciente.
        </p>
      </div>
    );
  }

  if (zonesQuery.isLoading) return <PageLoader />;

  if (zonesQuery.isError) {
    return (
      <div className="mx-auto flex min-h-[60dvh] max-w-[800px] flex-col justify-center px-5 py-16 md:px-8">
        <AlertTriangle size={28} strokeWidth={1.5} className="text-ember" aria-hidden="true" />
        <h1 className="mt-4 text-[34px] leading-tight tracking-[-0.03em]">
          No pudimos cargar las zonas.
        </h1>
        <p className="mt-3 text-bone-muted">Revisa la conexión con la API y vuelve a intentar.</p>
        <button
          type="button"
          className="btn btn-primary mt-6 w-fit"
          onClick={() => void zonesQuery.refetch()}
        >
          Reintentar
        </button>
      </div>
    );
  }

  const zones = zonesQuery.data ?? [];
  const selected = selectedIds
    .map((id) => (id === null ? null : zoneById.get(id) ?? null))
    .filter((zone): zone is Zone => zone !== null);
  const histories = [historyA.data ?? [], historyB.data ?? [], historyC.data ?? []];
  const historyByZoneId = new Map<number, EvaluationSummary[]>();
  selectedIds.forEach((id, index) => {
    if (id !== null) {
      historyByZoneId.set(id, histories[index] ?? []);
    }
  });

  function setAt(index: number, value: number | null) {
    setSelectedIds((current) => {
      const next = [...current];
      next[index] = value;
      return next;
    });
  }

  return (
    <div className="mx-auto max-w-[1200px] px-5 py-12 md:px-8 md:py-16">
      <p className="font-mono text-[12px] uppercase tracking-[0.14em] text-surveyor">
        Lectura comparada
      </p>
      <div className="mt-3">
        <h1 className="text-[40px] leading-none tracking-[-0.03em] md:text-[56px]">
          Comparar zonas
        </h1>
        <p className="mt-4 max-w-2xl text-bone-muted">
          Selecciona dos o tres zonas para contrastar el nivel del modelo, sus variables, la
          población disponible y las evaluaciones recientes.
        </p>
      </div>

      <div className="mt-10 grid gap-5 md:grid-cols-3">
        {[0, 1, 2].map((index) => (
          <ZoneSelect
            key={index}
            index={index}
            value={selectedIds[index] ?? null}
            zones={zones}
            selected={selectedIds}
            onChange={(value) => setAt(index, value)}
          />
        ))}
      </div>

      <p className="mt-4 font-mono text-[11px] text-ash" role="status" aria-live="polite">
        {selected.length < 2
          ? "Selecciona al menos dos zonas para comparar."
          : `${selected.length} zonas seleccionadas.`}
        {priority.isError ? " No pudimos cargar la población desde prioridad." : ""}
      </p>

      {selected.length < 2 ? (
        <div className="mt-8 border border-iron p-8">
          <p className="text-[22px] tracking-[-0.02em] text-bone">Comparación incompleta</p>
          <p className="mt-2 font-mono text-[12px] text-ash">
            Usa los selectores para elegir dos o tres zonas del territorio monitoreado.
          </p>
        </div>
      ) : (
        <>
          <section className="mt-8 border border-iron p-5" aria-labelledby="tabla-comparacion">
            <div className="flex items-center gap-2">
              <Columns3 size={16} strokeWidth={1.5} className="text-surveyor" aria-hidden="true" />
              <h2 id="tabla-comparacion" className="text-[22px] tracking-[-0.03em]">
                Variables y riesgo
              </h2>
            </div>
            <div className="mt-4 overflow-x-auto">
              <table className="w-full min-w-[720px] text-left font-mono text-[11px]">
                <caption className="sr-only">
                  Comparación de nivel de riesgo, probabilidad, vegetación, incendios, pendiente,
                  combustible y población entre las zonas seleccionadas
                </caption>
                <thead className="text-ash">
                  <tr>
                    <th className="pb-2 font-normal">Métrica</th>
                    {selected.map((zone) => (
                      <th key={zone.id} className="pb-2 font-normal">
                        {zoneLabel(zone.name, zone.display_name)}
                        <span className="block text-[10px] text-ash">{zone.comuna}</span>
                      </th>
                    ))}
                  </tr>
                </thead>
                <tbody>
                  <tr className="border-t border-iron">
                    <th scope="row" className="py-3 pr-3 font-normal text-ash">
                      Nivel
                    </th>
                    {selected.map((zone) => (
                      <td key={zone.id} className="py-3 pr-3">
                        <RiskBadge level={zone.risk_level} />
                      </td>
                    ))}
                  </tr>
                  <tr className="border-t border-iron">
                    <th scope="row" className="py-3 pr-3 font-normal text-ash">
                      P(Alto)
                    </th>
                    {selected.map((zone) => (
                      <td key={zone.id} className="py-3 pr-3 text-bone">
                        {formatNumber(zone.risk_score * 100, 0)} %
                      </td>
                    ))}
                  </tr>
                  <tr className="border-t border-iron">
                    <th scope="row" className="py-3 pr-3 font-normal text-ash">
                      Vegetación
                    </th>
                    {selected.map((zone) => (
                      <td key={zone.id} className="py-3 pr-3 text-bone">
                        {formatNumber(zone.vegetation * 100, 0)} %
                      </td>
                    ))}
                  </tr>
                  <tr className="border-t border-iron">
                    <th scope="row" className="py-3 pr-3 font-normal text-ash">
                      Incendios históricos
                    </th>
                    {selected.map((zone) => (
                      <td key={zone.id} className="py-3 pr-3 text-bone">
                        {formatNumber(zone.historical_fires, 0)}
                      </td>
                    ))}
                  </tr>
                  <tr className="border-t border-iron">
                    <th scope="row" className="py-3 pr-3 font-normal text-ash">
                      Pendiente
                    </th>
                    {selected.map((zone) => (
                      <td key={zone.id} className="py-3 pr-3 text-bone">
                        {formatNumber(zone.slope, 1)} °
                      </td>
                    ))}
                  </tr>
                  <tr className="border-t border-iron">
                    <th scope="row" className="py-3 pr-3 font-normal text-ash">
                      Combustible dominante
                    </th>
                    {selected.map((zone) => (
                      <td key={zone.id} className="py-3 pr-3 text-bone">
                        {zone.dominant_fuel}
                      </td>
                    ))}
                  </tr>
                  <tr className="border-t border-iron">
                    <th scope="row" className="py-3 pr-3 font-normal text-ash">
                      Población
                    </th>
                    {selected.map((zone) => {
                      const item = priorityById.get(zone.id);
                      return (
                        <td key={zone.id} className="py-3 pr-3 text-bone">
                          {item?.population_available && item.population !== null
                            ? formatNumber(item.population, 0)
                            : "Sin dato"}
                        </td>
                      );
                    })}
                  </tr>
                  <tr className="border-t border-iron">
                    <th scope="row" className="py-3 pr-3 font-normal text-ash">
                      Mapa
                    </th>
                    {selected.map((zone) => (
                      <td key={zone.id} className="py-3 pr-3">
                        <Link
                          to={`/mapa?zona=${zone.id}`}
                          className="text-surveyor hover:text-bone"
                        >
                          Abrir zona
                        </Link>
                      </td>
                    ))}
                  </tr>
                </tbody>
              </table>
            </div>
          </section>

          <section className="mt-8" aria-labelledby="historial-comparado">
            <h2 id="historial-comparado" className="text-[22px] tracking-[-0.03em]">
              Historial reciente
            </h2>
            <p className="mt-2 font-mono text-[11px] text-ash">
              Últimas evaluaciones registradas por zona; la línea sigue P(Alto) entre 0 y 1.
            </p>
            <div className="mt-4 grid gap-4 md:grid-cols-3">
              {selected.map((zone) => {
                const points = historyByZoneId.get(zone.id) ?? [];
                return (
                  <article key={zone.id} className="border border-iron p-4">
                    <div className="flex items-start justify-between gap-3">
                      <div>
                        <h3 className="text-[18px] tracking-[-0.02em] text-bone">
                          {zoneLabel(zone.name, zone.display_name)}
                        </h3>
                        <p className="mt-1 font-mono text-[10px] text-ash">{zone.comuna}</p>
                      </div>
                      <RiskBadge level={zone.risk_level} />
                    </div>
                    <Sparkline zone={zone} points={points} />
                    <p className="mt-2 font-mono text-[10px] text-ash">
                      {points.length > 0
                        ? `${points.length} evaluaciones · última ${formatDateTime(points[0].created_at)}`
                        : "Sin evaluaciones registradas."}
                    </p>
                  </article>
                );
              })}
            </div>
          </section>
        </>
      )}
    </div>
  );
}
