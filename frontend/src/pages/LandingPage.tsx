import { ArrowRight, BookOpen, Clock, Layers, Map } from "lucide-react";
import { Link } from "react-router-dom";

import { RiskBadge } from "../components/RiskBadge";
import { useStatus } from "../features/zones/useZones";
import { formatDateTime, formatNumber } from "../lib/format";
import { RISK_LEVELS, riskRange } from "../lib/risk";

export default function LandingPage() {
  const status = useStatus();

  return (
    <div>
      <section className="hero-image relative flex min-h-[calc(100dvh-59px)] items-end">
        <div className="absolute inset-0 bg-gradient-to-t from-obsidian via-obsidian/55 to-obsidian/10" />
        <div className="relative mx-auto w-full max-w-[1200px] px-5 pb-16 md:px-8 md:pb-24">
          <p className="font-mono text-[12px] uppercase tracking-[0.16em] text-surveyor">
            Valparaíso · Riesgo de incendios
          </p>
          <h1 className="mt-5 max-w-4xl text-[44px] font-normal leading-[0.9] tracking-[-0.03em] text-bone md:text-[72px]">
            El riesgo de incendio, cerro por cerro.
          </h1>
          <p className="mt-6 max-w-xl text-[18px] leading-[1.62] text-bone-muted">
            Consulta el nivel de riesgo de cada zona, revisa las variables que lo explican y sigue
            su evolución en el tiempo.
          </p>
          <div className="mt-8 flex flex-wrap gap-3">
            <Link to="/mapa" className="btn btn-primary">
              <Map size={16} strokeWidth={1.5} aria-hidden="true" />
              Explorar mapa
            </Link>
            <Link to="/metodologia" className="btn btn-ghost">
              <BookOpen size={16} strokeWidth={1.5} aria-hidden="true" />
              Ver metodología
            </Link>
          </div>
          <div className="mt-10 flex flex-wrap gap-x-8 gap-y-2 font-mono text-[12px] text-ash">
            <span className="inline-flex items-center gap-2">
              <Clock size={14} strokeWidth={1.5} aria-hidden="true" />
              Actualizado {formatDateTime(status.data?.last_ingest)}
            </span>
            <span className="inline-flex items-center gap-2">
              <Layers size={14} strokeWidth={1.5} aria-hidden="true" />
              {status.data?.zones ?? "—"} zonas monitoreadas
            </span>
            <span>-33,0470 / -71,6120</span>
          </div>
        </div>
      </section>

      <section className="mx-auto max-w-[1200px] px-5 py-16 md:px-8 md:py-24">
        <div className="grid gap-10 md:grid-cols-[1.2fr_1fr]">
          <div>
            <p className="font-mono text-[12px] uppercase tracking-[0.14em] text-surveyor">
              Lectura rápida
            </p>
            <h2 className="mt-4 max-w-xl text-[34px] leading-[1.05] tracking-[-0.03em] text-bone md:text-[48px]">
              Tres preguntas, una superficie.
            </h2>
            <p className="mt-5 max-w-xl text-bone-muted">
              El mapa responde qué zona estás mirando, cuál es su nivel de riesgo y qué variable lo
              explica. Cada cifra muestra su unidad, su fuente y su marca temporal.
            </p>
          </div>
          <div className="grid gap-4">
            {RISK_LEVELS.map((level) => (
              <div
                key={level}
                className="flex items-center justify-between border-b border-iron pb-3"
              >
                <RiskBadge level={level} />
                <span className="font-mono text-[12px] text-ash">{riskRange(level)}</span>
              </div>
            ))}
          </div>
        </div>

        <div className="mt-14 grid gap-6 md:grid-cols-3">
          {[
            ["01", "Selecciona una zona", "Haz clic en el mapa o búscala por comuna y sector."],
            ["02", "Lee el riesgo", "Nivel, score y timestamp en una sola vista."],
            ["03", "Sigue la evolución", "Historial de lecturas y variables que explican el cambio."],
          ].map(([number, title, body]) => (
            <article key={number} className="border-t border-iron pt-4">
              <p className="font-mono text-[12px] text-surveyor">{number}</p>
              <h3 className="mt-3 text-[22px] leading-tight tracking-[-0.03em] text-bone">{title}</h3>
              <p className="mt-2 text-[15px] leading-[1.6] text-ash">{body}</p>
            </article>
          ))}
        </div>

        <div className="telemetry mt-16 grid-cols-2 md:grid-cols-4">
          {[
            ["Zonas", status.data?.zones ?? "—"],
            ["Última ingesta", formatDateTime(status.data?.last_ingest)],
            ["Modelo", status.data?.model_version ?? "—"],
            ["p95 API", status.data?.p95_ms ? `${formatNumber(status.data.p95_ms, 0)} ms` : "—"],
          ].map(([label, value]) => (
            <div key={label} className="border-r border-iron px-4 py-4 last:border-r-0">
              <p className="font-mono text-[11px] uppercase tracking-[0.1em] text-ash">{label}</p>
              <p className="mt-1 font-mono text-[13px] text-bone">{value}</p>
            </div>
          ))}
        </div>

        <Link
          to="/mapa"
          className="mt-12 inline-flex items-center gap-2 font-mono text-[13px] uppercase tracking-[0.08em] text-surveyor hover:text-bone"
        >
          Abrir el mapa completo
          <ArrowRight size={16} strokeWidth={1.5} aria-hidden="true" />
        </Link>
      </section>
    </div>
  );
}
