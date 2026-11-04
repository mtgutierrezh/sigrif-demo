import type { Reading } from "../features/zones/types";
import { formatNumber } from "../lib/format";

const fields: Array<[keyof Reading, string, string, number]> = [
  ["temperature", "Temperatura", "°C", 1],
  ["humidity", "Humedad", "%", 1],
  ["wind_speed", "Viento", "km/h", 1],
  ["vegetation", "Vegetación", "0–1", 3],
  ["historical_fires", "Incendios históricos", "eventos", 0],
  ["slope", "Pendiente", "°", 1],
];

export function VariableList({ reading }: { reading: Reading | null }) {
  return (
    <dl className="border-t border-iron">
      {fields.map(([key, label, unit, digits]) => {
        const raw = reading?.[key];
        const value = typeof raw === "number" ? formatNumber(raw, digits) : "—";
        return (
          <div key={key} className="flex items-center justify-between border-b border-iron py-2.5">
            <dt className="font-mono text-[12px] text-ash">{label}</dt>
            <dd className="font-mono text-[13px] text-bone">
              {value} <span className="text-ash">{unit}</span>
            </dd>
          </div>
        );
      })}
    </dl>
  );
}
