import type { ReactNode } from "react";
import { useLocation } from "react-router-dom";

import { Footer } from "./Footer";
import { SkipLink } from "./SkipLink";
import { TopBar } from "./TopBar";

export function AppShell({ children }: { children: ReactNode }) {
  const { pathname } = useLocation();

  return (
    <div className="flex min-h-dvh flex-col bg-obsidian">
      <SkipLink />
      <TopBar />
      <main id="contenido" className="flex-1 pt-[59px]">
        {children}
      </main>
      {pathname !== "/mapa" ? <Footer /> : null}
    </div>
  );
}
