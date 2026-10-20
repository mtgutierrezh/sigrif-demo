import { Link } from "react-router-dom";

import type { Zone } from "../features/zones/types";
import { formatDateTime, formatScore } from "../lib/format";
import { RiskBadge } from "./RiskBadge";

export function ZoneTable({ zones }: { zones: Zone[] }) {
  return (
    <>
      <div className="hidden md:block">
        <table className="w-full table-fixed border-collapse text-left">
          <caption className="sr-only">Zonas monitoreadas y su nivel de riesgo</caption>
          <colgroup>
            <col className="w-[26%]" />
            <col className="w-[18%]" />
            <col className="w-[12%]" />
            <col className="w-[12%]" />
            <col className="w-[32%]" />
          </colgroup>
          <thead>
            <tr className="border-b border-iron">
              {[
                { label: "Zona", className: "py-3" },
                { label: "Comuna", className: "py-3" },
                { label: "Nivel", className: "py-3" },
                { label: "Score", className: "py-3 pr-6 text-right" },
                { label: "Actualizado", className: "py-3 pl-6" },
              ].map((header) => (
                <th
                  key={header.label}
                  scope="col"
                  className={`${header.className} font-mono text-[11px] font-normal uppercase tracking-[0.1em] text-ash`}
                >
                  {header.label}
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
                <td className="truncate py-3 font-mono text-[12px] text-ash">{zone.comuna}</td>
                <td className="py-3">
                  <RiskBadge level={zone.risk_level} />
                </td>
                <td className="whitespace-nowrap py-3 pr-6 text-right font-mono text-[13px] tabular-nums text-bone">
                  {formatScore(zone.risk_score)}
                </td>
                <td className="whitespace-nowrap py-3 pl-6 font-mono text-[11px] text-ash">
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
