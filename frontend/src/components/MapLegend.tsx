import { ChevronDown, ChevronUp } from "lucide-react";
import { useState } from "react";

import { RISK_LEVELS, riskColor } from "../lib/risk";
import { InfoTip } from "./InfoTip";

export function MapLegend() {
  const [open, setOpen] = useState(() => window.matchMedia("(min-width: 768px)").matches);

  return (
    <div className="absolute bottom-4 left-4 z-[1000] w-[190px] border border-iron bg-obsidian/90 p-3.5 backdrop-blur-sm">
      <button
        type="button"
        className="flex w-full items-center justify-between font-mono text-[12px] uppercase tracking-[0.08em] text-bone"
        onClick={() => setOpen((value) => !value)}
        aria-expanded={open}
        aria-controls="leyenda-riesgo"
      >
        <span className="flex items-center gap-2">
          Nivel de riesgo
          <InfoTip label="Cómo se interpreta el nivel de riesgo">
            El nivel es la clase con mayor probabilidad del modelo. El color no reemplaza el texto.
            La probabilidad de Alto y la severidad se muestran en el panel de la zona.
          </InfoTip>
        </span>
        {open ? <ChevronDown size={14} /> : <ChevronUp size={14} />}
      </button>
      {open ? (
        <ul id="leyenda-riesgo" className="mt-3 space-y-2">
          {RISK_LEVELS.map((level) => (
            <li key={level} className="flex items-center gap-2 font-mono text-[11px] text-bone">
              <span
                className="size-3.5 border"
                style={{ backgroundColor: riskColor(level), borderColor: riskColor(level) }}
                aria-hidden="true"
              />
              {level}
            </li>
          ))}
        </ul>
      ) : null}
    </div>
  );
}
