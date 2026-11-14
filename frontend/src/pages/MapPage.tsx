import { AlertTriangle, RotateCcw } from "lucide-react";
import { useMemo } from "react";
import { useState } from "react";
import { useSearchParams } from "react-router-dom";

import { MapLegend } from "../components/MapLegend";
import { MapView } from "../components/MapView";
import { PageLoader } from "../components/PageLoader";
import { RiskSummary } from "../components/RiskSummary";
import { TelemetryStrip } from "../components/TelemetryStrip";
import { ZonePanel } from "../components/ZonePanel";
import { CELL_MIN_ZOOM, useCells, type MapViewport } from "../features/zones/useCells";
import type { Zone } from "../features/zones/types";
import { useHistory, useStatus, useZone, useZones } from "../features/zones/useZones";
import { useSimulate } from "../features/zones/useSimulate";
import { FUEL_COLORS } from "../lib/fuel";
import { zoneLabel } from "../lib/names";

export default function MapPage() {
  const [params, setParams] = useSearchParams();
  const [colorMode, setColorMode] = useState<"risk" | "fuel" | "fire">(
    params.get("capa") === "combustible" ? "fuel" : params.get("capa") === "fuego" ? "fire" : "risk",
  );
  const [showCells, setShowCells] = useState(true);
  const [viewport, setViewport] = useState<MapViewport | null>(null);
  const raw = params.get("zona");
  const selectedId = raw && !Number.isNaN(Number(raw)) ? Number(raw) : null;
  const cellsVisible = showCells && (viewport?.zoom ?? 0) >= CELL_MIN_ZOOM;

  const zonesQuery = useZones();
  const statusQuery = useStatus();
  const zoneQuery = useZone(selectedId);
  const historyQuery = useHistory(selectedId);
  const simulate = useSimulate();
  const cellsQuery = useCells(viewport?.bbox ?? null, cellsVisible);

  const selectedZone =
    zoneQuery.data ?? zonesQuery.data?.find((zone) => zone.id === selectedId) ?? null;

  const groupedZones = useMemo(() => {
    const groups = new Map<string, Zone[]>();
    for (const zone of zonesQuery.data ?? []) {
      const key = `${zone.provincia} · ${zone.comuna}`;
      const current = groups.get(key) ?? [];
      current.push(zone);
      groups.set(key, current);
    }
    return [...groups.entries()].sort(([a], [b]) => a.localeCompare(b, "es"));
  }, [zonesQuery.data]);

  const message =
    simulate.stage === "publishing"
      ? "Publicando lectura sintética…"
      : simulate.stage === "queued"
        ? "Lectura en cola SQS…"
        : simulate.stage === "processing"
          ? "La IA está procesando la lectura…"
          : simulate.stage === "done"
            ? "Riesgo actualizado."
            : simulate.stage === "error"
              ? "No pudimos actualizar el riesgo. Intenta nuevamente."
              : null;

  const cellStatus = !showCells
    ? "Malla H3 oculta"
    : (viewport?.zoom ?? 0) < CELL_MIN_ZOOM
      ? `Acércate a zoom ${CELL_MIN_ZOOM} para ver la malla`
      : cellsQuery.isLoading
        ? "Cargando malla H3…"
        : cellsQuery.isError
          ? "No se pudo cargar la malla H3"
          : `${(cellsQuery.data?.meta?.count ?? cellsQuery.data?.features.length ?? 0).toLocaleString("es-CL")} celdas res 8${
              cellsQuery.data?.meta?.truncated ? " · vista parcial" : ""
            }`;

  const selectZone = (zoneId: number) => {
    setParams({ zona: String(zoneId) }, { replace: true });
  };

  const closePanel = () => {
    setParams({}, { replace: true });
  };

  if (zonesQuery.isLoading) {
    return <PageLoader />;
  }

  if (zonesQuery.isError) {
    return (
      <div className="mx-auto flex min-h-[60dvh] max-w-[1200px] flex-col justify-center px-5 md:px-8">
        <AlertTriangle size={28} strokeWidth={1.5} className="text-ember" aria-hidden="true" />
        <h1 className="mt-4 text-[34px] leading-tight tracking-[-0.03em]">
          No pudimos cargar las zonas.
        </h1>
        <p className="mt-3 max-w-lg text-bone-muted">
          Revisa que la API esté disponible y vuelve a intentar.
        </p>
        <button type="button" className="btn btn-primary mt-6 w-fit" onClick={() => void zonesQuery.refetch()}>
          <RotateCcw size={16} strokeWidth={1.5} aria-hidden="true" />
          Reintentar
        </button>
      </div>
    );
  }

  return (
    <div>
      <div className="relative h-[calc(100dvh-59px)]">
        <MapView
          zones={zonesQuery.data ?? []}
          selectedId={selectedId}
          onSelect={selectZone}
          colorMode={colorMode}
          cells={cellsQuery.data ?? null}
          showCells={cellsVisible}
          onViewportChange={setViewport}
        />

        <div className="pointer-events-auto absolute left-4 top-4 z-[1000] w-[260px] rounded-[3.6px] border border-iron bg-obsidian/90 p-3 backdrop-blur-sm">
          <div className="mb-3 flex gap-2">
            <button
              type="button"
              className={`btn ${colorMode === "risk" ? "btn-primary" : "btn-ghost"} flex-1`}
              onClick={() => setColorMode("risk")}
            >
              Riesgo
            </button>
            <button
              type="button"
              className={`btn ${colorMode === "fuel" ? "btn-primary" : "btn-ghost"} flex-1`}
              onClick={() => setColorMode("fuel")}
            >
              Combustible
            </button>
            <button
              type="button"
              className={`btn ${colorMode === "fire" ? "btn-primary" : "btn-ghost"} flex-1`}
              onClick={() => setColorMode("fire")}
            >
              Prob. histórica
            </button>
          </div>
          {colorMode === "fuel" ? (
            <div className="mb-3 grid grid-cols-2 gap-1 font-mono text-[9px] text-ash">
              {Object.entries(FUEL_COLORS).map(([label, color]) => (
                <span key={label} className="inline-flex items-center gap-1">
                  <span className="size-2" style={{ backgroundColor: color }} />
                  {label}
                </span>
              ))}
            </div>
          ) : null}
          {colorMode === "fire" ? (
            <p className="mb-3 font-mono text-[9px] leading-relaxed text-ash">
              Probabilidad histórica experimental · no operativa. Bajo &lt; 0,278 · Medio 0,278–0,556 · Alto &gt; 0,556.
            </p>
          ) : null}
          <div className="mb-3 border-t border-iron pt-3">
            <label
              htmlFor="cells-toggle"
              className="flex items-center gap-2 font-mono text-[10px] uppercase tracking-[0.08em] text-bone"
            >
              <input
                id="cells-toggle"
                type="checkbox"
                checked={showCells}
                onChange={(event) => setShowCells(event.target.checked)}
                className="size-3 accent-[#ebfc72]"
              />
              Malla H3 res 8
            </label>
            <p className="mt-1 font-mono text-[9px] leading-relaxed text-ash">{cellStatus}</p>
          </div>
          <label
            htmlFor="zone-select"
            className="font-mono text-[10px] uppercase tracking-[0.1em] text-ash"
          >
            Comuna o sector
          </label>
          <select
            id="zone-select"
            className="input mt-1 w-full font-mono text-[12px] [color-scheme:dark]"
            value={selectedId ?? ""}
            onChange={(event) => {
              if (event.target.value) {
                selectZone(Number(event.target.value));
              }
            }}
          >
            <option className="bg-obsidian text-bone" value="">
              Selecciona…
            </option>
            {groupedZones.map(([label, group]) => (
              <optgroup key={label} label={label}>
                {(group ?? []).map((zone) => (
                  <option key={zone.id} className="bg-obsidian text-bone" value={zone.id}>
                    {zoneLabel(zone.name, zone.display_name)}
                  </option>
                ))}
              </optgroup>
            ))}
          </select>
        </div>

        <MapLegend />

        <ZonePanel
          zone={selectedZone}
          history={historyQuery.data ?? []}
          historyLoading={historyQuery.isLoading}
          simulating={simulate.isPending}
          simulateStage={simulate.stage}
          onClose={closePanel}
          onSimulate={() => {
            if (selectedZone) {
              simulate.mutate({
                zoneId: selectedZone.id,
                updatedAt: selectedZone.updated_at,
              });
            }
          }}
          message={message}
          telemetry={
            <div className="space-y-4">
              <RiskSummary />
              <TelemetryStrip status={statusQuery.data} compact />
            </div>
          }
        />
      </div>
    </div>
  );
}
