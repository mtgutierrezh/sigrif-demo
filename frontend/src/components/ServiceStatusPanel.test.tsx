import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import type { ServicesStatus } from "../features/zones/types";
import { ServiceStatusPanel } from "./ServiceStatusPanel";

const DATA: ServicesStatus = {
  checked_at: "2026-11-25T12:00:00Z",
  status: "degraded",
  services: [
    { key: "api", label: "API", status: "ok", detail: "FastAPI en línea" },
    { key: "ia", label: "IA", status: "ok", detail: "Modelo disponible" },
    { key: "postgis", label: "PostGIS", status: "ok", detail: "PostGIS 3.4" },
    { key: "sqs", label: "SQS", status: "degraded", detail: "No se pudo leer la cola" },
    { key: "ingesta", label: "Ingesta", status: "ok", detail: "dmc: 563/563" },
    { key: "frescura", label: "Frescura", status: "degraded", detail: "60 min" },
  ],
  queue_depth: null,
  last_ingest: "2026-11-25T11:00:00Z",
  freshness_minutes: 60,
  stale: true,
};

describe("ServiceStatusPanel", () => {
  it("muestra el estado con texto además del color", () => {
    render(
      <ServiceStatusPanel data={DATA} loading={false} error={false} onRetry={() => undefined} />,
    );

    expect(screen.getByText("Estado general: Degradado", { exact: false })).toBeInTheDocument();
    expect(screen.getAllByText("Operativo")).toHaveLength(4);
    expect(screen.getAllByText("Degradado")).toHaveLength(2);
    expect(screen.getByText("No se pudo leer la cola")).toBeInTheDocument();
  });

  it("anuncia el error de consulta", () => {
    render(
      <ServiceStatusPanel data={undefined} loading={false} error onRetry={() => undefined} />,
    );

    expect(
      screen.getByText("No pudimos consultar el estado de los servicios."),
    ).toBeInTheDocument();
  });
});
