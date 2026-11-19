"use client";

import { LogOut } from "lucide-react";
import { useAuth } from "./auth-provider";

/** Nome de quem está logado e o botão de sair (só aparece com sessão). */
export function MenuUsuario() {
  const { estado, sair } = useAuth();
  if (estado.status !== "autenticado") return null;

  return (
    <span className="flex items-center gap-2">
      <span className="hidden max-w-40 truncate text-sm text-muted sm:inline" title={estado.usuario.email}>
        {estado.usuario.nome}
      </span>
      <button
        type="button"
        onClick={sair}
        className="inline-flex items-center gap-1.5 rounded-lg border border-border bg-surface px-3 py-1.5 text-xs font-medium text-muted transition-colors hover:border-accent hover:text-foreground"
      >
        <LogOut aria-hidden className="size-3.5" />
        Sair
      </button>
    </span>
  );
}
