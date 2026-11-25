const UUID = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i;

export function actorLabel(actor: string | null | undefined): string {
  if (!actor) return "local";
  if (UUID.test(actor)) return "Operador";
  if (actor === "ingest") return "Ingesta automática";
  return actor;
}
