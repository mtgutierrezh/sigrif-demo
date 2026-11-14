export function zoneLabel(name: string, displayName?: string | null): string {
  if (displayName?.trim()) {
    return displayName;
  }
  return name;
}
