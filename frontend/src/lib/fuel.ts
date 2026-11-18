export const FUEL_COLORS: Record<string, string> = {
  "Bosque nativo": "#1F7A3D",
  Plantación: "#8D5524",
  Matorral: "#C98A1B",
  Pradera: "#A7C957",
  Agrícola: "#C97C5D",
  Urbano: "#6C757D",
  "Sin dato": "#4B4B45",
};

export function fuelColor(value: string | null | undefined): string {
  return FUEL_COLORS[value ?? "Sin dato"] ?? FUEL_COLORS["Sin dato"];
}
