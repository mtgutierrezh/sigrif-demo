import { Link } from "react-router-dom";

import { usePageMeta } from "../lib/usePageMeta";

const steps = [
  ["01", "Elige una zona", "Busca por comuna o sector, o selecciona una zona en el mapa."],
  ["02", "Lee el nivel", "El nivel es la clase con mayor probabilidad del modelo. El color acompaña, no reemplaza el texto."],
  ["03", "Revisa los factores", "Temperatura, humedad, viento, vegetación, incendios históricos y pendiente explican el resultado."],
  ["04", "Prueba un escenario", "Los operadores pueden cambiar las variables y comparar el riesgo antes y después."],
  ["05", "Gestiona la alerta", "Si el nivel es Alto, se crea una alerta para asignar responsable y dejar historial."],
];

export default function GuidePage() {
  usePageMeta(
    "Guía formativa",
    "Cómo leer el mapa, interpretar el riesgo y usar el simulador y las alertas de SIGRIF.",
  );

  return (
    <div className="mx-auto max-w-[1000px] px-5 py-14 md:px-8 md:py-20">
      <p className="font-mono text-[12px] uppercase tracking-[0.14em] text-surveyor">Guía formativa</p>
      <h1 className="mt-4 max-w-3xl text-[40px] leading-none tracking-[-0.03em] md:text-[58px]">
        Cómo usar SIGRIF.
      </h1>
      <p className="mt-6 max-w-2xl text-[17px] leading-relaxed text-bone-muted">
        Esta guía resume el flujo de consulta. El objetivo es que cualquier persona pueda entender
        qué significa el nivel de riesgo y qué hacer a continuación.
      </p>

      <section className="mt-12 border-t border-iron">
        {steps.map(([number, title, body]) => (
          <article key={number} className="grid gap-3 border-b border-iron py-6 md:grid-cols-[64px_260px_1fr]">
            <p className="font-mono text-[12px] text-surveyor">{number}</p>
            <h2 className="text-[21px] tracking-[-0.02em] text-bone">{title}</h2>
            <p className="text-[14px] leading-relaxed text-ash">{body}</p>
          </article>
        ))}
      </section>

      <section className="mt-12 grid gap-6 md:grid-cols-2">
        <article className="border border-iron p-6">
          <h2 className="text-[25px] tracking-[-0.03em] text-bone">Nivel y probabilidad</h2>
          <p className="mt-3 text-[14px] leading-relaxed text-bone-muted">
            El nivel no es una escala numérica. Es la clase con mayor probabilidad. La probabilidad
            de Alto y la severidad se muestran por separado para evitar confusiones.
          </p>
        </article>
        <article className="border border-iron p-6">
          <h2 className="text-[25px] tracking-[-0.03em] text-bone">Capas del mapa</h2>
          <p className="mt-3 text-[14px] leading-relaxed text-bone-muted">
            Riesgo muestra las zonas. Combustible y Prob. histórica muestran la malla H3. La malla
            necesita zoom 12 o superior y no representa riesgo operativo por celda.
          </p>
        </article>
      </section>

      <div className="mt-10 flex flex-wrap gap-3">
        <Link to="/mapa" className="btn btn-primary">
          Abrir mapa
        </Link>
        <Link to="/sobre" className="btn btn-ghost">
          Sobre SIGRIF
        </Link>
      </div>
    </div>
  );
}
