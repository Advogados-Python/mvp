"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useEffect, useRef, useState, type FormEvent, type ReactNode } from "react";
import { LoaderCircle } from "lucide-react";
import { normalizarOab } from "@/lib/oab";
import { useAuth } from "./auth-provider";
import { Logo } from "./logo";
import { Aviso } from "./ui";

// Mesmos limites do backend (backend/userauths/schemas.py).
const SENHA_MINIMA = 10;
const SENHA_MAXIMA = 128;

type Campo = "nome" | "email" | "senha" | "confirmacao" | "oab";
type Valores = Record<Campo, string>;
type Erros = Partial<Record<Campo, string>>;

const VAZIO: Valores = { nome: "", email: "", senha: "", confirmacao: "", oab: "" };

function validar(valores: Valores): Erros {
  const erros: Erros = {};
  if (!valores.nome.trim()) erros.nome = "Informe o seu nome completo.";
  if (!valores.email.trim()) erros.email = "Informe o seu e-mail.";
  else if (!/^[^@\s]+@[^@\s]+\.[^@\s]+$/.test(valores.email.trim())) erros.email = "E-mail inválido.";
  if (valores.senha.length < SENHA_MINIMA) erros.senha = `A senha precisa ter pelo menos ${SENHA_MINIMA} caracteres.`;
  else if (valores.senha.length > SENHA_MAXIMA) erros.senha = `A senha pode ter no máximo ${SENHA_MAXIMA} caracteres.`;
  if (!valores.confirmacao) erros.confirmacao = "Repita a senha.";
  else if (valores.confirmacao !== valores.senha) erros.confirmacao = "As senhas não conferem.";
  const oab = normalizarOab(valores.oab);
  if (!valores.oab.trim()) erros.oab = "Informe o número da OAB.";
  else if (!oab.ok) erros.oab = oab.erro;
  return erros;
}

export function FormRegistro() {
  const { estado, registrar } = useAuth();
  const router = useRouter();
  const [valores, setValores] = useState<Valores>(VAZIO);
  const [erros, setErros] = useState<Erros>({});
  const [enviando, setEnviando] = useState(false);
  const [erroGeral, setErroGeral] = useState<string | null>(null);
  const formulario = useRef<HTMLFormElement>(null);

  useEffect(() => {
    if (estado.status === "autenticado") router.replace("/");
  }, [estado.status, router]);

  function mudar(campo: Campo, valor: string) {
    setValores((atuais) => ({ ...atuais, [campo]: valor }));
    // o erro do campo some assim que a pessoa corrige; os outros só são conferidos de novo no envio
    if (erros[campo]) setErros((atuais) => ({ ...atuais, [campo]: undefined }));
  }

  /** Ao sair do campo, mostra a OAB já no formato que será gravado (123.456/sp -> SP123456). */
  function padronizarOab() {
    const oab = normalizarOab(valores.oab);
    if (oab.ok && oab.oab !== valores.oab) setValores((atuais) => ({ ...atuais, oab: oab.oab }));
  }

  async function enviar(evento: FormEvent) {
    evento.preventDefault();
    setErroGeral(null);
    const encontrados = validar(valores);
    setErros(encontrados);
    const primeiro = (Object.keys(VAZIO) as Campo[]).find((campo) => encontrados[campo]);
    if (primeiro) {
      formulario.current?.querySelector<HTMLInputElement>(`[name="${primeiro}"]`)?.focus();
      return;
    }

    setEnviando(true);
    try {
      const oab = normalizarOab(valores.oab);
      await registrar({
        nome: valores.nome.trim(),
        email: valores.email.trim(),
        senha: valores.senha,
        oab: oab.ok ? oab.oab : valores.oab,
      });
      router.replace("/"); // a conta nasce ativa: entra direto
    } catch (falha) {
      setErroGeral(falha instanceof Error ? falha.message : "Não foi possível concluir o cadastro.");
      setEnviando(false);
    }
  }

  return (
    <div className="mx-auto w-full max-w-sm">
      <div className="mb-6 flex flex-col items-center gap-3 text-center">
        <Logo tamanho={56} className="rounded-xl" />
        <div>
          <h1 className="text-xl font-semibold tracking-tight">Registre-se</h1>
          <p className="text-sm text-muted">Leitor de Processos · Ribeiro e Souza</p>
        </div>
      </div>

      <form ref={formulario} onSubmit={enviar} noValidate className="vidro space-y-4 rounded-2xl p-6">
        {erroGeral && (
          <Aviso tom="danger" titulo="Não foi possível concluir o cadastro">
            {erroGeral}
          </Aviso>
        )}
        <CampoTexto
          campo="nome"
          rotulo="Nome completo"
          autoComplete="name"
          valor={valores.nome}
          erro={erros.nome}
          aoMudar={mudar}
        />
        <CampoTexto
          campo="email"
          rotulo="E-mail"
          tipo="email"
          autoComplete="email"
          valor={valores.email}
          erro={erros.email}
          aoMudar={mudar}
        />
        <CampoTexto
          campo="senha"
          rotulo="Senha"
          tipo="password"
          autoComplete="new-password"
          dica={`Mínimo de ${SENHA_MINIMA} caracteres.`}
          valor={valores.senha}
          erro={erros.senha}
          aoMudar={mudar}
        />
        <CampoTexto
          campo="confirmacao"
          rotulo="Confirmação de senha"
          tipo="password"
          autoComplete="new-password"
          valor={valores.confirmacao}
          erro={erros.confirmacao}
          aoMudar={mudar}
        />
        <CampoTexto
          campo="oab"
          rotulo="OAB"
          autoComplete="off"
          dica="UF + número, ex.: GO12345 ou 12345/GO."
          valor={valores.oab}
          erro={erros.oab}
          aoMudar={mudar}
          aoSair={padronizarOab}
        />
        <button
          type="submit"
          disabled={enviando}
          className="inline-flex w-full items-center justify-center gap-2 rounded-lg bg-accent px-4 py-2.5 text-sm font-semibold text-accent-foreground transition-opacity hover:opacity-90 disabled:cursor-not-allowed disabled:opacity-40"
        >
          {enviando && <LoaderCircle aria-hidden className="size-4 animate-spin" />}
          Criar conta
        </button>
        <p className="text-center text-sm text-muted">
          Já tem conta?{" "}
          <Link href="/login" className="font-medium text-accent underline-offset-4 hover:underline">
            Entrar
          </Link>
        </p>
      </form>
    </div>
  );
}

function CampoTexto({
  campo,
  rotulo,
  tipo = "text",
  autoComplete,
  dica,
  valor,
  erro,
  aoMudar,
  aoSair,
}: {
  campo: Campo;
  rotulo: string;
  tipo?: "text" | "email" | "password";
  autoComplete: string;
  dica?: ReactNode;
  valor: string;
  erro?: string;
  aoMudar: (campo: Campo, valor: string) => void;
  aoSair?: () => void;
}) {
  const idDica = `${campo}-dica`;
  const idErro = `${campo}-erro`;
  const descricao = erro ? idErro : dica ? idDica : undefined; // com erro, a dica sai da tela e dá lugar a ele
  // <label htmlFor> separado (e não envolvendo tudo): a dica e o erro não entram no NOME do campo, só na descrição.
  return (
    <div>
      <label htmlFor={campo} className="mb-1 block text-sm font-medium">
        {rotulo}
      </label>
      <input
        id={campo}
        name={campo}
        type={tipo}
        required
        autoComplete={autoComplete}
        value={valor}
        onChange={(evento) => aoMudar(campo, evento.target.value)}
        onBlur={aoSair}
        aria-invalid={erro ? true : undefined}
        aria-describedby={descricao}
        className={`w-full rounded-lg border bg-background px-3 py-2 text-sm ${erro ? "border-danger" : "border-border"}`}
      />
      {erro && (
        <p id={idErro} className="mt-1 text-xs text-danger">
          {erro}
        </p>
      )}
      {dica && !erro && (
        <p id={idDica} className="mt-1 text-xs text-muted">
          {dica}
        </p>
      )}
    </div>
  );
}
