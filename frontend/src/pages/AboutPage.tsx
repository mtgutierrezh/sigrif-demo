import { Link } from "react-router-dom";

import { usePageMeta } from "../lib/usePageMeta";

const sources = [
  ["IDE Chile y IDE Minagri", "Límites, uso de suelo y capas territoriales."],
  ["CONAF", "Catastro de vegetación, ocurrencia histórica y alertas oficiales."],
  ["DMC", "Temperatura, humedad y viento de la Red EMA."],
  ["INE", "Zonas censales y población de referencia."],
  ["OpenStreetMap", "Nombres referenciales y elementos de infraestructura."],
];

export default function AboutPage() {
  usePageMeta(
    "Sobre SIGRIF",
    "SIGRIF es un prototipo académico para explorar el riesgo de incendios forestales en la Región de Valparaíso.",
  );

  return (
    <div className="mx-auto max-w-[1000px] px-5 py-14 md:px-8 md:py-20">
      <p className="font-mono text-[12px] uppercase tracking-[0.14em] text-surveyor">Sobre SIGRIF</p>
      <h1 className="mt-4 max-w-3xl text-[40px] leading-none tracking-[-0.03em] md:text-[58px]">
        Riesgo territorial, explicado.
      </h1>
      <p className="mt-6 max-w-2xl text-[17px] leading-relaxed text-bone-muted">
        SIGRIF es un prototipo académico del Equipo 7 para la asignatura ITY1102. Organiza datos
        territoriales, meteorológicos y de combustible para apoyar la revisión preventiva del riesgo
        de incendios en la Región de Valparaíso.
      </p>

      <section className="mt-12 grid gap-6 md:grid-cols-2">
        <article className="border border-iron p-6">
          <h2 className="text-[26px] tracking-[-0.03em] text-bone">Qué hace</h2>
          <p className="mt-3 text-[15px] leading-relaxed text-bone-muted">
            Clasifica zonas en Bajo, Medio y Alto, explica los factores principales, genera
            recomendaciones preventivas y conserva un historial de evaluaciones y alertas.
          </p>
        </article>
        <article className="border border-iron p-6">
          <h2 className="text-[26px] tracking-[-0.03em] text-bone">Qué no hace</h2>
          <p className="mt-3 text-[15px] leading-relaxed text-bone-muted">
            No predice la fecha, hora o ubicación exacta de un incendio. No reemplaza a CONAF ni a
            SENAPRED. Es una herramienta de apoyo y no un sistema operativo de emergencia.
          </p>
        </article>
      </section>

      <section className="mt-12">
        <h2 className="text-[29px] tracking-[-0.03em] text-bone">Fuentes principales</h2>
        <div className="mt-5 border-t border-iron">
          {sources.map(([name, use]) => (
            <div key={name} className="grid gap-2 border-b border-iron py-4 md:grid-cols-[220px_1fr]">
              <p className="font-mono text-[12px] text-bone">{name}</p>
              <p className="text-[14px] leading-relaxed text-ash">{use}</p>
            </div>
          ))}
        </div>
      </section>

      <section className="mt-12 border-t border-iron pt-8">
        <h2 className="text-[29px] tracking-[-0.03em] text-bone">Equipo</h2>
        <p className="mt-3 text-[15px] leading-relaxed text-bone-muted">
          Matías Gutiérrez, David Larenas y Víctor Mena. Docente: Elizabeth Alina Chicata Castro.
          Proyecto académico de Ingeniería en Informática, Duoc UC.
        </p>
        <div className="mt-6 flex flex-wrap gap-3">
          <Link to="/guia" className="btn btn-primary">
            Ver guía formativa
          </Link>
          <Link to="/metodologia" className="btn btn-ghost">
            Revisar metodología
          </Link>
        </div>
      </section>
    </div>
  );
}
