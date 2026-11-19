"use client";

import { useRouter, useSearchParams } from "next/navigation";
import { useEffect, useState, type FormEvent } from "react";
import { LoaderCircle } from "lucide-react";
import { useAuth } from "./auth-provider";
import { Logo } from "./logo";
import { Aviso } from "./ui";

export function FormLogin() {
  const { estado, entrar } = useAuth();
  const router = useRouter();
  const expirou = useSearchParams().get("expirou") === "1";
  const [email, setEmail] = useState("");
  const [senha, setSenha] = useState("");
  const [enviando, setEnviando] = useState(false);
  const [erro, setErro] = useState<string | null>(null);

  useEffect(() => {
    if (estado.status === "autenticado") router.replace("/");
  }, [estado.status, router]);

  async function enviar(evento: FormEvent) {
    evento.preventDefault();
    setEnviando(true);
    setErro(null);
    try {
      await entrar(email, senha);
      router.replace("/");
    } catch (falha) {
      setErro(falha instanceof Error ? falha.message : "Não foi possível entrar.");
      setEnviando(false);
    }
  }

  return (
    <div className="mx-auto w-full max-w-sm">
      <div className="mb-6 flex flex-col items-center gap-3 text-center">
        <Logo tamanho={56} className="rounded-xl" />
        <div>
          <h1 className="text-xl font-semibold tracking-tight">Entrar</h1>
          <p className="text-sm text-muted">Leitor de Processos · Ribeiro e Souza</p>
        </div>
      </div>

      <form onSubmit={enviar} className="vidro space-y-4 rounded-2xl p-6">
        {expirou && !erro && (
          <Aviso tom="info" titulo="Sua sessão terminou">
            Entre de novo para continuar.
          </Aviso>
        )}
        {erro && (
          <Aviso tom="danger" titulo="Não foi possível entrar">
            {erro}
          </Aviso>
        )}
        <label className="block">
          <span className="mb-1 block text-sm font-medium">E-mail</span>
          <input
            type="email"
            required
            autoComplete="username"
            value={email}
            onChange={(evento) => setEmail(evento.target.value)}
            className="w-full rounded-lg border border-border bg-background px-3 py-2 text-sm"
          />
        </label>
        <label className="block">
          <span className="mb-1 block text-sm font-medium">Senha</span>
          <input
            type="password"
            required
            autoComplete="current-password"
            value={senha}
            onChange={(evento) => setSenha(evento.target.value)}
            className="w-full rounded-lg border border-border bg-background px-3 py-2 text-sm"
          />
        </label>
        <button
          type="submit"
          disabled={enviando || !email || !senha}
          className="inline-flex w-full items-center justify-center gap-2 rounded-lg bg-accent px-4 py-2.5 text-sm font-semibold text-accent-foreground transition-opacity hover:opacity-90 disabled:cursor-not-allowed disabled:opacity-40"
        >
          {enviando && <LoaderCircle aria-hidden className="size-4 animate-spin" />}
          Entrar
        </button>
      </form>
    </div>
  );
}
