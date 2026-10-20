import { AlertTriangle, RotateCcw } from "lucide-react";
import { useMemo, useState } from "react";
import { Link } from "react-router-dom";

import { PageLoader } from "../components/PageLoader";
import { SearchBox } from "../components/SearchBox";
import { TelemetryStrip } from "../components/TelemetryStrip";
import { ZoneTable } from "../components/ZoneTable";
import { useStatus, useZones } from "../features/zones/useZones";
import type { Zone } from "../features/zones/types";
import { useDebouncedValue } from "../lib/useDebouncedValue";
import { riskRank } from "../lib/risk";

type SortKey = "risk" | "score" | "name";

function sortZones(zones: Zone[], key: SortKey): Zone[] {
  return [...zones].sort((a, b) => {
    if (key === "name") {
      return a.name.localeCompare(b.name, "es");
    }
    if (key === "score") {
      return b.risk_score - a.risk_score;
    }
    return riskRank(b.risk_level) - riskRank(a.risk_level) || b.risk_score - a.risk_score;
  });
}

export default function ZonesPage() {
  const zonesQuery = useZones();
  const statusQuery = useStatus();
  const [search, setSearch] = useState("");
  const [sort, setSort] = useState<SortKey>("risk");
  const debounced = useDebouncedValue(search);

  const visible = useMemo(() => {
    const term = debounced.trim().toLowerCase();
    const filtered = (zonesQuery.data ?? []).filter(
      (zone) =>
        term.length === 0 ||
        zone.name.toLowerCase().includes(term) ||
        zone.comuna.toLowerCase().includes(term),
    );
    return sortZones(filtered, sort);
  }, [debounced, sort, zonesQuery.data]);

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
        <button
          type="button"
          className="btn btn-primary mt-6 w-fit"
          onClick={() => void zonesQuery.refetch()}
        >
          <RotateCcw size={16} strokeWidth={1.5} aria-hidden="true" />
          Reintentar
        </button>
      </div>
    );
  }

  return (
    <div className="mx-auto max-w-[1200px] px-5 py-12 md:px-8 md:py-16">
      <div className="flex flex-wrap items-end justify-between gap-6">
        <div>
          <p className="font-mono text-[12px] uppercase tracking-[0.14em] text-surveyor">
            Zonas monitoreadas
          </p>
          <h1 className="mt-3 text-[40px] leading-none tracking-[-0.03em] md:text-[58px]">
            Tabla de zonas
          </h1>
          <p className="mt-4 max-w-xl text-bone-muted">
            Compara el nivel y el score de cada zona. Abre una fila para ver el detalle, las
            variables y el historial.
          </p>
        </div>
        <Link to="/mapa" className="btn btn-ghost">
          Ver mapa
        </Link>
      </div>

      <div className="mt-10 grid gap-5 md:grid-cols-[1fr_220px]">
        <SearchBox value={search} onChange={setSearch} />
        <label className="flex flex-col gap-1">
          <span className="font-mono text-[10px] uppercase tracking-[0.1em] text-ash">Ordenar por</span>
          <select
            className="input font-mono text-[12px] [color-scheme:dark]"
            value={sort}
            onChange={(event) => setSort(event.target.value as SortKey)}
          >
            <option className="bg-obsidian text-bone" value="risk">
              Riesgo
            </option>
            <option className="bg-obsidian text-bone" value="score">
              Score
            </option>
            <option className="bg-obsidian text-bone" value="name">
              Nombre
            </option>
          </select>
        </label>
      </div>

      <div className="mt-8">
        {visible.length > 0 ? (
          <ZoneTable zones={visible} />
        ) : (
          <div className="border border-iron p-8">
            <p className="text-[22px] tracking-[-0.02em] text-bone">Sin resultados</p>
            <p className="mt-2 font-mono text-[12px] text-ash">
              No encontramos zonas para “{debounced}”. Prueba con otra comuna o nombre.
            </p>
          </div>
        )}
      </div>

      <div className="mt-12">
        <TelemetryStrip status={statusQuery.data} />
      </div>
    </div>
  );
}
