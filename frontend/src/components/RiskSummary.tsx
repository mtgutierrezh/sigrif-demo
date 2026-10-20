import { useRiskSurface } from "../features/zones/useRiskSurface";
import { riskColor } from "../lib/risk";

export function RiskSummary() {
  const { data, isLoading } = useRiskSurface();
  const classes = data?.features.map((feature) => feature.properties) ?? [];
  const total = classes.reduce((sum, item) => sum + item.area_ha, 0);

  if (isLoading) {
    return <p className="font-mono text-[11px] text-ash">Cargando superficie…</p>;
  }

  if (!classes.length) {
    return null;
  }

  return (
    <section aria-label="Resumen de riesgo" className="space-y-3">
      <div className="grid grid-cols-3 gap-2">
        {classes.map((item) => (
          <div key={item.risk_level} className="border border-iron p-2">
            <p className="font-mono text-[10px] uppercase tracking-[0.1em] text-ash">
              {item.risk_level}
            </p>
            <p className="mt-1 font-mono text-[14px] text-bone">
              {Math.round(item.area_ha).toLocaleString("es-CL")} ha
            </p>
          </div>
        ))}
        <div className="border border-iron p-2">
          <p className="font-mono text-[10px] uppercase tracking-[0.1em] text-ash">Total</p>
          <p className="mt-1 font-mono text-[14px] text-bone">
            {Math.round(total).toLocaleString("es-CL")} ha
          </p>
        </div>
      </div>

      <div className="space-y-2">
        {classes.map((item) => {
          const percent = total ? (item.area_ha / total) * 100 : 0;
          return (
            <div key={item.risk_level}>
              <div className="flex justify-between font-mono text-[10px] text-ash">
                <span>{item.risk_level}</span>
                <span>{percent.toFixed(1)}%</span>
              </div>
              <div className="mt-1 h-1.5 bg-iron">
                <div
                  className="h-full"
                  style={{
                    width: `${percent}%`,
                    backgroundColor: riskColor(
                      item.risk_level as Parameters<typeof riskColor>[0],
                    ),
                  }}
                />
              </div>
            </div>
          );
        })}
      </div>

      <p className="font-mono text-[10px] leading-relaxed text-ash">
        Superficie forestal CONAF · riesgo potencial
      </p>
    </section>
  );
}
