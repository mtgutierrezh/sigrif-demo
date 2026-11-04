import { useState } from "react";

import { useEvaluate } from "../features/zones/useEvaluate";
import type { Evaluation, RiskFeatures, Zone } from "../features/zones/types";
import { formatDateTime, formatNumber, formatScore } from "../lib/format";
import { RiskBadge } from "./RiskBadge";

const FIELDS: Array<{
  key: keyof RiskFeatures;
  label: string;
  unit: string;
  min: number;
  max: number;
  step: number;
}> = [
  { key: "temperature", label: "Temperatura", unit: "°C", min: -10, max: 50, step: 0.1 },
  { key: "humidity", label: "Humedad", unit: "%", min: 0, max: 100, step: 1 },
  { key: "wind_speed", label: "Viento", unit: "km/h", min: 0, max: 150, step: 1 },
  { key: "vegetation", label: "Vegetación", unit: "0–1", min: 0, max: 1, step: 0.01 },
  { key: "historical_fires", label: "Incendios históricos", unit: "eventos", min: 0, max: 30, step: 1 },
  { key: "slope", label: "Pendiente", unit: "°", min: 0, max: 60, step: 1 },
];

const DEFAULTS: RiskFeatures = {
  temperature: 28,
  humidity: 35,
  wind_speed: 25,
  vegetation: 0.5,
  historical_fires: 3,
  slope: 15,
};

function initialFeatures(zone: Zone): RiskFeatures {
  const reading = zone.latest_reading;
  if (!reading) {
    return DEFAULTS;
  }
  return {
    temperature: reading.temperature,
    humidity: reading.humidity,
    wind_speed: reading.wind_speed,
    vegetation: reading.vegetation,
    historical_fires: reading.historical_fires,
    slope: reading.slope,
  };
}

function factorDecimals(feature: string): number {
  if (feature === "vegetation") {
    return 2;
  }
  return feature === "historical_fires" ? 0 : 1;
}

function Evidence({ evaluation }: { evaluation: Evaluation }) {
  return (
    <div className="mt-4 space-y-4 border-t border-iron pt-4">
      <div className="flex items-center gap-3">
        <RiskBadge level={evaluation.risk_level} />
        <span className="font-mono text-[28px] leading-none text-bone">
          {formatScore(evaluation.risk_score)}
        </span>
        <span className="font-mono text-[10px] text-ash">score de riesgo</span>
      </div>
      <p className="font-mono text-[10px] text-ash">
        {evaluation.model_version} · {formatDateTime(evaluation.evaluated_at)}
      </p>

      <div>
        <p className="font-mono text-[10px] uppercase tracking-[0.1em] text-ash">
          Factores que explican la estimación
        </p>
        <ul className="mt-2 space-y-1.5">
          {evaluation.factors.map((factor) => (
            <li
              key={factor.feature}
              className="flex items-baseline justify-between gap-3 border-b border-iron pb-1.5"
            >
              <span className="text-[12px] text-bone-muted">
                {factor.label}{" "}
                <span className="font-mono text-[10px] text-ash">
                  {formatNumber(factor.value, factorDecimals(factor.feature))} {factor.unit}
                </span>
              </span>
              <span
                className={`font-mono text-[10px] ${
                  factor.direction === "aumenta" ? "text-ember" : "text-surveyor"
                }`}
              >
                {factor.impact >= 0 ? "+" : ""}
                {formatNumber(factor.impact * 100, 0)} pts
              </span>
            </li>
          ))}
        </ul>
        <p className="mt-1.5 font-mono text-[9px] leading-relaxed text-ash">
          Puntos de probabilidad que aporta cada variable respecto de un valor de bajo riesgo.
        </p>
      </div>

      {evaluation.scenario ? (
        <div className="border border-iron p-3">
          <p className="font-mono text-[10px] uppercase tracking-[0.1em] text-ash">
            Escenario de gestión
          </p>
          <p className="mt-1 text-[12px] text-bone-muted">{evaluation.scenario.description}</p>
          <div className="mt-2 flex items-center gap-3">
            <RiskBadge level={evaluation.scenario.risk_level} />
            <span className="font-mono text-[14px] text-bone">
              {formatScore(evaluation.scenario.risk_score)}
            </span>
            <span className="font-mono text-[10px] text-surveyor">
              {evaluation.scenario.delta >= 0 ? "+" : ""}
              {formatNumber(evaluation.scenario.delta * 100, 0)} pts
            </span>
          </div>
        </div>
      ) : null}

      <div>
        <p className="font-mono text-[10px] uppercase tracking-[0.1em] text-ash">
          Prescripción operativa
        </p>
        <ol className="mt-2 space-y-2">
          {evaluation.prescription.map((action, index) => (
            <li key={action.code} className="border border-iron p-2.5">
              <div className="flex items-start gap-2">
                <span className="mt-0.5 font-mono text-[10px] text-surveyor">
                  {String(index + 1).padStart(2, "0")}
                </span>
                <div>
                  <p className="text-[12px] leading-snug text-bone">{action.title}</p>
                  <p className="mt-1 text-[11px] leading-snug text-bone-muted">
                    {action.description}
                  </p>
                  <p className="mt-1 font-mono text-[9px] uppercase tracking-[0.06em] text-ash">
                    {action.priority} · {action.horizon}
                  </p>
                </div>
              </div>
            </li>
          ))}
        </ol>
      </div>
    </div>
  );
}

export function RiskEvaluator({ zone }: { zone: Zone }) {
  const [form, setForm] = useState<RiskFeatures>(() => initialFeatures(zone));
  const evaluate = useEvaluate();

  const update = (key: keyof RiskFeatures, value: number) => {
    setForm((current) => ({ ...current, [key]: value }));
  };

  return (
    <details className="mt-5 border border-iron">
      <summary className="cursor-pointer select-none px-3 py-2.5 font-mono text-[11px] uppercase tracking-[0.08em] text-bone">
        Evaluar escenario y prescripción
      </summary>
      <form
        className="border-t border-iron p-3"
        onSubmit={(event) => {
          event.preventDefault();
          evaluate.mutate({ zoneId: zone.id, features: form });
        }}
      >
        <p className="text-[11px] leading-snug text-bone-muted">
          Ajusta las variables y obtén una estimación explicada con acciones operativas. La
          evaluación queda registrada en el historial de la zona.
        </p>
        <div className="mt-3 grid grid-cols-2 gap-2">
          {FIELDS.map((field) => (
            <label key={field.key} className="flex flex-col gap-1">
              <span className="font-mono text-[9px] uppercase tracking-[0.06em] text-ash">
                {field.label} <span className="normal-case">({field.unit})</span>
              </span>
              <input
                className="input px-2 py-1.5 font-mono text-[12px]"
                type="number"
                min={field.min}
                max={field.max}
                step={field.step}
                value={form[field.key]}
                onChange={(event) => update(field.key, Number(event.target.value))}
                required
              />
            </label>
          ))}
        </div>
        <button
          type="submit"
          className="btn btn-primary mt-3 w-full"
          disabled={evaluate.isPending}
        >
          {evaluate.isPending ? "Evaluando…" : "Evaluar riesgo"}
        </button>

        {evaluate.isError ? (
          <p className="mt-3 border border-ember/40 p-2 font-mono text-[10px] text-ember" role="alert">
            {evaluate.error instanceof Error
              ? evaluate.error.message
              : "No pudimos completar la evaluación."}
          </p>
        ) : null}

        {evaluate.data ? <Evidence evaluation={evaluate.data} /> : null}
      </form>
    </details>
  );
}
