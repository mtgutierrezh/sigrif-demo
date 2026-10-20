import { LogIn, LogOut, Menu, X } from "lucide-react";
import { useEffect, useState } from "react";
import { Link, NavLink, useLocation } from "react-router-dom";

import { isAuthEnabled } from "../lib/auth";
import { useSession } from "./session";

const links = [
  { to: "/mapa", label: "Mapa" },
  { to: "/zonas", label: "Zonas" },
  { to: "/metodologia", label: "Metodología" },
];

export function TopBar() {
  const [open, setOpen] = useState(false);
  const session = useSession();
  const location = useLocation();

  useEffect(() => {
    setOpen(false);
  }, [location.pathname]);

  const authenticated = session.status === "authenticated";

  return (
    <header className="fixed inset-x-0 top-0 z-50 border-b border-iron/40 bg-obsidian/85 backdrop-blur-md">
      <div className="mx-auto flex h-[59px] max-w-[1200px] items-center justify-between px-5 md:px-8">
        <Link
          to="/"
          className="flex items-center"
          aria-label="SIGRIF, ir al inicio"
        >
          <img src="/brand/logotype.svg" alt="SIGRIF" className="h-5 w-auto md:h-6" />
        </Link>

        <nav className="hidden items-center gap-7 md:flex" aria-label="Navegación principal">
          {links.map((link) => (
            <NavLink
              key={link.to}
              to={link.to}
              className={({ isActive }) =>
                `font-mono text-[13px] uppercase tracking-[0.08em] transition-colors ${
                  isActive ? "text-surveyor" : "text-bone hover:text-surveyor"
                }`
              }
            >
              {link.label}
            </NavLink>
          ))}
        </nav>

        <div className="hidden items-center gap-5 md:flex">
          {isAuthEnabled ? (
            authenticated ? (
              <button
                type="button"
                onClick={session.signOut}
                className="inline-flex items-center gap-1.5 font-mono uppercase tracking-[0.04em] text-bone hover:text-surveyor"
                style={{ fontSize: "11px", lineHeight: 1.2, height: "24px", padding: "0 8px" }}
              >
                <LogOut size={12} strokeWidth={1.5} aria-hidden="true" />
                Salir
              </button>
            ) : (
              <button
                type="button"
                onClick={session.signIn}
                style={{ fontSize: "11px", lineHeight: 1.2, height: "24px", padding: "0 8px" }}
                className="inline-flex items-center gap-1.5 font-mono uppercase tracking-[0.04em] text-bone hover:text-surveyor"
              >
                <LogIn size={12} strokeWidth={1.5} aria-hidden="true" />
                Ingresar
              </button>
            )
          ) : null}
        </div>

        <button
          type="button"
          className="inline-flex size-11 items-center justify-center text-bone md:hidden"
          onClick={() => setOpen((value) => !value)}
          aria-expanded={open}
          aria-controls="menu-movil"
          aria-label={open ? "Cerrar menú" : "Abrir menú"}
        >
          {open ? <X size={20} strokeWidth={1.5} /> : <Menu size={20} strokeWidth={1.5} />}
        </button>
      </div>

      {open ? (
        <div id="menu-movil" className="border-t border-iron bg-obsidian px-5 py-4 md:hidden">
          <nav className="flex flex-col gap-4" aria-label="Navegación móvil">
            {links.map((link) => (
              <NavLink
                key={link.to}
                to={link.to}
                className={({ isActive }) =>
                  `font-mono text-[13px] uppercase tracking-[0.08em] ${
                    isActive ? "text-surveyor" : "text-bone"
                  }`
                }
              >
                {link.label}
              </NavLink>
            ))}
          </nav>
        </div>
      ) : null}
    </header>
  );
}
