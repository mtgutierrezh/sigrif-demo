import { describe, expect, it } from "vitest";

import { actorLabel } from "./actor";

describe("actorLabel", () => {
  it("traduce la ingesta automática", () => {
    expect(actorLabel("ingest")).toBe("Ingesta automática");
  });

  it("oculta identificadores de Cognito", () => {
    expect(actorLabel("914b85a0-70e1-70c5-5909-465a2b5c9c14")).toBe("Operador");
  });

  it("mantiene nombres legibles", () => {
    expect(actorLabel("operador@demo.sigrif.cl")).toBe("operador@demo.sigrif.cl");
    expect(actorLabel(null)).toBe("local");
  });
});
