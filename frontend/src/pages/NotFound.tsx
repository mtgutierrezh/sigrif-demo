import { Link } from "react-router-dom";

export default function NotFound() {
  return (
    <div className="mx-auto flex min-h-[60dvh] max-w-[1200px] flex-col justify-center px-5 md:px-8">
      <p className="font-mono text-[12px] uppercase tracking-[0.14em] text-surveyor">Error 404</p>
      <h1 className="mt-4 text-[40px] leading-none tracking-[-0.03em] md:text-[58px]">
        Esta zona no existe.
      </h1>
      <p className="mt-4 max-w-lg text-bone-muted">
        La página que buscas no está disponible. Vuelve al mapa para consultar una zona.
      </p>
      <Link to="/mapa" className="btn btn-primary mt-8 w-fit">
        Volver al mapa
      </Link>
    </div>
  );
}
