export const FUEL_COLORS: Record<string, string> = {
  "Bosque nativo": "#2f7d4f",
  Plantación: "#8a6a2f",
  Matorral: "#b58b2a",
  Pradera: "#c8c35a",
  Agrícola: "#a98753",
  Urbano: "#8b8b86",
  "Sin dato": "#4b4b45",
};

export function fuelColor(value: string | null | undefined): string {
  return FUEL_COLORS[value ?? "Sin dato"] ?? FUEL_COLORS["Sin dato"];
}
