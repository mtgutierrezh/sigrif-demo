export function PageLoader() {
  return (
    <div className="flex min-h-[60dvh] items-center justify-center" role="status" aria-live="polite">
      <div className="w-48">
        <img
          src="/brand/isotype.svg"
          alt=""
          aria-hidden="true"
          className="mx-auto mb-5 h-10 w-10 opacity-80"
        />
        <div className="loading-line" />
        <p className="mt-4 text-center font-mono text-[13px] text-ash">Cargando SIGRIF…</p>
      </div>
    </div>
  );
}
