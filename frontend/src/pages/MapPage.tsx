import { AlertTriangle, RotateCcw } from "lucide-react";
import { useSearchParams } from "react-router-dom";

import { MapLegend } from "../components/MapLegend";
import { MapView } from "../components/MapView";
import { PageLoader } from "../components/PageLoader";
import { TelemetryStrip } from "../components/TelemetryStrip";
import { ZonePanel } from "../components/ZonePanel";
import { useHistory, useStatus, useZone, useZones } from "../features/zones/useZones";
import { useSimulate } from "../features/zones/useSimulate";

export default function MapPage() {
  const [params, setParams] = useSearchParams();
  const raw = params.get("zona");
  const selectedId = raw && !Number.isNaN(Number(raw)) ? Number(raw) : null;

  const zonesQuery = useZones();
  const statusQuery = useStatus();
  const zoneQuery = useZone(selectedId);
  const historyQuery = useHistory(selectedId);
  const simulate = useSimulate();

  const selectedZone =
    zoneQuery.data ?? zonesQuery.data?.find((zone) => zone.id === selectedId) ?? null;

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
        <MapView zones={zonesQuery.data ?? []} selectedId={selectedId} onSelect={selectZone} />

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
          telemetry={<TelemetryStrip status={statusQuery.data} />}
        />
      </div>
    </div>
  );
}
