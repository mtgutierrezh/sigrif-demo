import { X } from "lucide-react";
import type { ReactNode } from "react";

import type { SimulationStage } from "../features/zones/useSimulate";
import type { HistoryPoint, Zone } from "../features/zones/types";
import { formatDateTime, formatScore } from "../lib/format";
import { RiskBadge } from "./RiskBadge";
import { RiskHistory } from "./RiskHistory";
import { VariableList } from "./VariableList";
import { useSession } from "./session";

interface ZonePanelProps {
  zone: Zone | null;
  history: HistoryPoint[];
  historyLoading: boolean;
  simulating: boolean;
  simulateStage: SimulationStage;
  onClose: () => void;
  onSimulate: () => void;
  message: string | null;
  telemetry?: ReactNode;
}

export function ZonePanel({
  zone,
  history,
  historyLoading,
  simulating,
  simulateStage,
  onClose,
  onSimulate,
  message,
  telemetry,
}: ZonePanelProps) {
  const { canSimulate } = useSession();
  const steps = [
    { key: "publishing", label: "Publicada en SNS" },
    { key: "queued", label: "En cola SQS" },
    { key: "processing", label: "Procesada por la IA" },
  ] as const;
  const activeStep =
    simulateStage === "publishing"
      ? 0
      : simulateStage === "queued"
        ? 1
        : simulateStage === "processing"
          ? 2
          : simulateStage === "done"
            ? 3
            : -1;

  return (
    <aside
      className="fixed inset-x-0 bottom-0 z-[1100] h-[60dvh] overflow-y-auto border-t border-iron bg-obsidian p-5 md:absolute md:inset-y-0 md:left-auto md:right-0 md:h-full md:w-[380px] md:border-l md:border-t-0 md:p-6"
      aria-label="Detalle de la zona"
    >
      <div className="flex items-start justify-between gap-4">
        <div>
          <p className="font-mono text-[11px] uppercase tracking-[0.12em] text-ash">
            {zone ? zone.comuna : "Sin selección"}
          </p>
          <h2 className="mt-2 text-[29px] leading-tight tracking-[-0.03em] text-bone">
            {zone ? zone.name : "Selecciona una zona"}
          </h2>
        </div>
        <button
          type="button"
          onClick={onClose}
          className="inline-flex size-11 items-center justify-center text-ash hover:text-bone"
          aria-label="Cerrar panel"
        >
          <X size={18} strokeWidth={1.5} />
        </button>
      </div>

      {zone ? (
        <>
          <div className="mt-6 flex items-center gap-3">
            <RiskBadge level={zone.risk_level} />
            <span className="font-mono text-[12px] text-ash">score de riesgo</span>
          </div>
          <p className="mt-2 font-mono text-[65px] font-light leading-none text-bone">
            {formatScore(zone.risk_score)}
          </p>
          <p className="mt-3 font-mono text-[12px] text-ash">
            Actualizado {formatDateTime(zone.updated_at)}
          </p>

          <div className="mt-6">
            <p className="font-mono text-[11px] uppercase tracking-[0.1em] text-ash">
              Variables de la última lectura
            </p>
            <VariableList reading={zone.latest_reading} />
          </div>

          <p className="mt-4 font-mono text-[11px] text-ash">
            Fuente: datos sintéticos · demo SIGRIF
          </p>

          {canSimulate ? (
            <button
              type="button"
              className="btn btn-primary mt-5 w-full"
              onClick={onSimulate}
              disabled={simulating}
            >
              {simulating ? "Publicando…" : "Simular lectura"}
            </button>
          ) : (
            <p className="mt-5 border border-iron p-3 font-mono text-[11px] text-ash">
              La simulación requiere el grupo operadores.
            </p>
          )}

          <p className="mt-3 min-h-5 font-mono text-[11px] text-surveyor" aria-live="polite">
            {message}
          </p>

          {activeStep >= 0 ? (
            <ol className="mt-3 space-y-2 font-mono text-[11px]" aria-label="Progreso de la simulación">
              {steps.map((step, index) => {
                const done = activeStep > index;
                const active = activeStep === index;
                return (
                  <li
                    key={step.key}
                    className={done ? "text-surveyor" : active ? "text-bone" : "text-ash"}
                  >
                    <span
                      className={`mr-2 inline-block size-2 rounded-full ${
                        done || active ? "bg-surveyor" : "bg-iron"
                      }`}
                      aria-hidden="true"
                    />
                    {step.label}
                  </li>
                );
              })}
            </ol>
          ) : null}

          <RiskHistory points={history} loading={historyLoading} />
        </>
      ) : (
        <div className="mt-8 border-t border-iron pt-6">
          <p className="text-bone-muted">
            Haz clic en un polígono del mapa o elige una zona en la tabla para ver su riesgo, sus
            variables y su historial.
          </p>
        </div>
      )}

      {telemetry ? <div className="mt-6 border-t border-iron pt-4">{telemetry}</div> : null}
    </aside>
  );
}
