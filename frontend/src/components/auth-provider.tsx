"use client";

import { createContext, useCallback, useContext, useEffect, useMemo, useState, type ReactNode } from "react";
import { ErroApi, api } from "@/lib/api";
import { aoExpirar, gravarToken, limparToken, lerToken } from "@/lib/sessao";
import type { Usuario } from "@/lib/tipos";

type Estado =
  | { status: "carregando" }
  | { status: "anonimo" }
  | { status: "indisponivel"; mensagem: string } // a API não respondeu: NÃO desloga, o token continua valendo
  | { status: "autenticado"; usuario: Usuario };

interface ContextoAuth {
  estado: Estado;
  entrar: (email: string, senha: string) => Promise<void>;
  sair: () => void;
  tentarDeNovo: () => void;
}

const Contexto = createContext<ContextoAuth | null>(null);

export function useAuth(): ContextoAuth {
  const contexto = useContext(Contexto);
  if (!contexto) throw new Error("useAuth precisa estar dentro de <AuthProvider>");
  return contexto;
}

// Navegação COMPLETA (e não router.push): zera a memória da página. Com o Cache Components as telas
// anteriores ficam "escondidas" em memória; sem isto, o próximo login nesta máquina veria por um instante
// a lista de processos de quem saiu.
const irParaLogin = (expirou: boolean) => window.location.assign(expirou ? "/login?expirou=1" : "/login");

export function AuthProvider({ children }: { children: ReactNode }) {
  const [estado, setEstado] = useState<Estado>({ status: "carregando" });
  const [tentativa, setTentativa] = useState(0);

  useEffect(() => aoExpirar(() => irParaLogin(true)), []);

  useEffect(() => {
    let ativo = true;
    const token = lerToken();
    (token ? api.eu() : Promise.reject(new ErroApi("sem sessão", 401)))
      .then((usuario) => ativo && setEstado({ status: "autenticado", usuario }))
      .catch((falha: ErroApi) => {
        if (!ativo) return;
        if (falha.status === 401) {
          limparToken();
          setEstado({ status: "anonimo" });
        } else {
          setEstado({ status: "indisponivel", mensagem: falha.message });
        }
      });
    return () => {
      ativo = false;
    };
  }, [tentativa]);

  const entrar = useCallback(async (email: string, senha: string) => {
    const resposta = await api.login(email, senha);
    gravarToken(resposta.access_token);
    setEstado({ status: "autenticado", usuario: resposta.usuario });
  }, []);

  const sair = useCallback(() => {
    limparToken();
    irParaLogin(false);
  }, []);

  const tentarDeNovo = useCallback(() => {
    setEstado({ status: "carregando" });
    setTentativa((atual) => atual + 1);
  }, []);

  const valor = useMemo(() => ({ estado, entrar, sair, tentarDeNovo }), [estado, entrar, sair, tentarDeNovo]);
  return <Contexto.Provider value={valor}>{children}</Contexto.Provider>;
}
