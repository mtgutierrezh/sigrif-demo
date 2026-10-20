import type { ReactNode } from "react";

import { Footer } from "./Footer";
import { SkipLink } from "./SkipLink";
import { TopBar } from "./TopBar";

export function AppShell({ children }: { children: ReactNode }) {
  return (
    <div className="flex min-h-dvh flex-col bg-obsidian">
      <SkipLink />
      <TopBar />
      <main id="contenido" className="flex-1 pt-[59px]">
        {children}
      </main>
      <Footer />
    </div>
  );
}
