import { Link } from "react-router-dom";

import type { Zone } from "../features/zones/types";
import { formatDateTime, formatScore } from "../lib/format";
import { RiskBadge } from "./RiskBadge";

export function ZoneTable({ zones }: { zones: Zone[] }) {
  return (
    <>
      <div className="hidden md:block">
        <table className="w-full border-collapse text-left">
          <caption className="sr-only">Zonas monitoreadas y su nivel de riesgo</caption>
          <thead>
            <tr className="border-b border-iron">
              {["Zona", "Comuna", "Nivel", "Score", "Actualizado"].map((header) => (
                <th
                  key={header}
                  scope="col"
                  className="py-3 font-mono text-[11px] font-normal uppercase tracking-[0.1em] text-ash"
                >
                  {header}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {zones.map((zone) => (
              <tr key={zone.id} className="border-b border-iron">
                <td className="py-3">
                  <Link
                    to={`/mapa?zona=${zone.id}`}
                    className="text-[16px] tracking-[-0.02em] text-bone hover:text-surveyor"
                  >
                    {zone.name}
                  </Link>
                </td>
                <td className="py-3 font-mono text-[12px] text-ash">{zone.comuna}</td>
                <td className="py-3">
                  <RiskBadge level={zone.risk_level} />
                </td>
                <td className="py-3 text-right font-mono text-[13px] text-bone">
                  {formatScore(zone.risk_score)}
                </td>
                <td className="py-3 font-mono text-[11px] text-ash">
                  {formatDateTime(zone.updated_at)}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      <ul className="space-y-3 md:hidden">
        {zones.map((zone) => (
          <li key={zone.id}>
            <Link
              to={`/mapa?zona=${zone.id}`}
              className="block border border-iron p-4 transition-colors hover:border-bone"
            >
              <div className="flex items-start justify-between gap-4">
                <div>
                  <p className="text-[18px] tracking-[-0.02em] text-bone">{zone.name}</p>
                  <p className="mt-1 font-mono text-[11px] text-ash">{zone.comuna}</p>
                </div>
                <RiskBadge level={zone.risk_level} />
              </div>
              <div className="mt-4 flex items-center justify-between font-mono text-[11px] text-ash">
                <span>score {formatScore(zone.risk_score)}</span>
                <span>{formatDateTime(zone.updated_at)}</span>
              </div>
            </Link>
          </li>
        ))}
      </ul>
    </>
  );
}
