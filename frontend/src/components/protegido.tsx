"use client";

import { useRouter } from "next/navigation";
import { useEffect, type ReactNode } from "react";
import { useAuth } from "./auth-provider";
import { Aviso, Esqueleto } from "./ui";

/** Só mostra o conteúdo para quem está logado; os demais vão para /login. */
export function Protegido({ children }: { children: ReactNode }) {
  const { estado, tentarDeNovo } = useAuth();
  const router = useRouter();

  useEffect(() => {
    if (estado.status === "anonimo") router.replace("/login");
  }, [estado.status, router]);

  if (estado.status === "autenticado") return <>{children}</>;

  if (estado.status === "indisponivel") {
    return (
      <div className="space-y-4">
        <Aviso tom="danger" titulo="Não foi possível verificar o seu login">
          {estado.mensagem}
        </Aviso>
        <button
          type="button"
          onClick={tentarDeNovo}
          className="rounded-lg border border-border bg-surface px-4 py-2 text-sm font-medium hover:border-accent"
        >
          Tentar de novo
        </button>
      </div>
    );
  }

  // carregando, ou anônimo a caminho do /login
  return (
    <div aria-busy="true" aria-label="Verificando login" className="space-y-4">
      <Esqueleto className="h-8 w-1/3" />
      <Esqueleto className="h-48" />
    </div>
  );
}
