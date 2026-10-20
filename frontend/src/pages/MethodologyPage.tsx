import { RiskBadge } from "../components/RiskBadge";
import { RISK_LEVELS, riskRange } from "../lib/risk";

const variables = [
  ["Temperatura", "°C", "Calor disponible para la ignición."],
  ["Humedad relativa", "%", "Contenido de vapor en el aire."],
  ["Viento", "km/h", "Velocidad que propaga el fuego."],
  ["Vegetación", "0–1", "Cobertura y continuidad del combustible."],
  ["Pendiente", "°", "Inclinación que acelera la propagación."],
];

export default function MethodologyPage() {
  return (
    <div className="mx-auto max-w-[1200px] px-5 py-14 md:px-8 md:py-20">
      <p className="font-mono text-[12px] uppercase tracking-[0.14em] text-surveyor">Metodología</p>
      <h1 className="mt-4 max-w-3xl text-[40px] leading-[0.95] tracking-[-0.03em] md:text-[58px]">
        Cómo se calcula el riesgo.
      </h1>
      <p className="mt-6 max-w-2xl text-bone-muted">
        Usamos un modelo Random Forest de cinco variables para clasificar cada zona en Bajo, Medio o
        Alto. El resultado se acompaña de su score y de la fecha de la última lectura.
      </p>

      <section className="mt-14 grid gap-10 md:grid-cols-2">
        <div>
          <h2 className="text-[29px] leading-tight tracking-[-0.03em]">Variables</h2>
          <div className="mt-5 border-t border-iron">
            {variables.map(([name, unit, description]) => (
              <div key={name} className="grid grid-cols-[1fr_auto] gap-4 border-b border-iron py-4">
                <div>
                  <p className="font-mono text-[13px] text-bone">{name}</p>
                  <p className="mt-1 text-[14px] leading-relaxed text-ash">{description}</p>
                </div>
                <span className="font-mono text-[13px] text-surveyor">{unit}</span>
              </div>
            ))}
          </div>
        </div>

        <div>
          <h2 className="text-[29px] leading-tight tracking-[-0.03em]">Escala de riesgo</h2>
          <div className="mt-5 space-y-4">
            {RISK_LEVELS.map((level) => (
              <div key={level} className="flex items-center justify-between border-b border-iron pb-3">
                <RiskBadge level={level} />
                <span className="font-mono text-[12px] text-ash">{riskRange(level)}</span>
              </div>
            ))}
          </div>
          <p className="mt-5 text-[14px] leading-relaxed text-ash">
            El nivel siempre se muestra con texto y score; el color es un apoyo, nunca la única
            señal. Las bandas son de interfaz: el nivel final lo define el modelo y se muestra tal
            como llega.
          </p>
        </div>
      </section>

      <section className="mt-14 grid gap-10 border-t border-iron pt-10 md:grid-cols-2">
        <div>
          <h2 className="text-[29px] leading-tight tracking-[-0.03em]">Fuentes y límites</h2>
          <p className="mt-4 text-bone-muted">
            Las fuentes previstas son IDE Chile, CONAF, DMC y BCN SIIT. La demo usa datos sintéticos
            para mostrar el flujo completo; no reemplaza las alertas oficiales de CONAF ni SENAPRED.
          </p>
        </div>
        <div>
          <h2 className="text-[29px] leading-tight tracking-[-0.03em]">Privacidad</h2>
          <p className="mt-4 text-bone-muted">
            No almacenamos datos personales. Solo se usan variables territoriales y ambientales,
            alineadas con la Ley 19.628. Los accesos se registran sin identificadores personales.
          </p>
        </div>
      </section>
    </div>
  );
}
