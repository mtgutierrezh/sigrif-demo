import { ExternalLink } from "lucide-react";

const SOURCES = [
  { label: "IDE Chile", href: "https://www.ide.cl/" },
  { label: "CONAF", href: "https://www.conaf.cl/" },
  { label: "DMC", href: "https://www.meteochile.gob.cl/" },
  { label: "BCN SIIT", href: "https://www.bcn.cl/siit/" },
  { label: "INE", href: "https://www.ine.gob.cl/" },
  { label: "IDE Minagri", href: "https://ide.minagri.gob.cl/" },
];

export function Footer() {
  return (
    <footer className="border-t border-iron bg-obsidian px-5 pb-8 pt-14 md:px-8">
      <div className="mx-auto grid max-w-[1200px] gap-8 font-mono text-[12px] text-ash md:grid-cols-3">
        <div>
          <p className="mb-2 text-bone">Fuentes</p>
          <ul className="space-y-1">
            {SOURCES.map((source) => (
              <li key={source.label}>
                <a
                  href={source.href}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="inline-flex items-center gap-1 transition-colors hover:text-bone"
                >
                  {source.label}
                  <ExternalLink size={11} strokeWidth={1.5} aria-hidden="true" />
                </a>
              </li>
            ))}
          </ul>
        </div>
        <div>
          <p className="mb-2 text-bone">Aviso</p>
          <p>Datos sintéticos para demo. No reemplaza las alertas oficiales de CONAF ni SENAPRED.</p>
        </div>
        <div>
          <p className="mb-2 text-bone">Versión</p>
          <p>SIGRIF · v0.2.0 · {new Date().getFullYear()}</p>
        </div>
      </div>
    </footer>
  );
}
