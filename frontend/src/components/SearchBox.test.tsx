import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { useState } from "react";
import { describe, expect, it } from "vitest";

import { SearchBox } from "./SearchBox";

function ControlledSearch() {
  const [value, setValue] = useState("");
  return <SearchBox value={value} onChange={setValue} />;
}

describe("SearchBox", () => {
  it("updates the query as the user types", async () => {
    const user = userEvent.setup();
    render(<ControlledSearch />);

    const input = screen.getByRole("searchbox", { name: "Buscar zona" });
    await user.type(input, "quil");

    expect(input).toHaveValue("quil");
  });

  it("accepts a custom label and placeholder", () => {
    render(<SearchBox value="" onChange={() => undefined} label="Filtrar" placeholder="Comuna" />);

    expect(screen.getByRole("searchbox", { name: "Filtrar" })).toHaveAttribute(
      "placeholder",
      "Comuna",
    );
  });
});
