export function Footer() {
  return (
    <footer className="border-t border-iron bg-obsidian px-5 pb-8 pt-14 md:px-8">
      <div className="mx-auto grid max-w-[1200px] gap-8 font-mono text-[12px] text-ash md:grid-cols-3">
        <div>
          <p className="mb-2 text-bone">Fuentes</p>
          <p>IDE Chile · CONAF · DMC · BCN SIIT</p>
        </div>
        <div>
          <p className="mb-2 text-bone">Aviso</p>
          <p>Datos sintéticos para demo. No reemplaza las alertas oficiales de CONAF ni SENAPRED.</p>
        </div>
        <div>
          <p className="mb-2 text-bone">Versión</p>
          <p>SIGRIF · v0.1.2 · {new Date().getFullYear()}</p>
        </div>
      </div>
    </footer>
  );
}
