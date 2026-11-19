// Guarda o token de login no navegador (localStorage) e avisa quando a sessão expira.
//
// Escolha consciente: localStorage fica exposto a scripts da própria página (XSS). Em troca, o token
// viaja num cabeçalho (sem cookie, sem CSRF) e funciona com a API em outro endereço. O token expira
// em poucas horas e trocar a senha derruba todos os logins.

const CHAVE = "ribeiro.token";
let emMemoria: string | null = null; // se o localStorage estiver bloqueado, o login vale até recarregar a página

export function lerToken(): string | null {
  if (typeof window === "undefined") return null;
  try {
    return window.localStorage.getItem(CHAVE) ?? emMemoria;
  } catch {
    return emMemoria;
  }
}

export function gravarToken(token: string): void {
  emMemoria = token;
  try {
    window.localStorage.setItem(CHAVE, token);
  } catch {
    /* sem localStorage: fica só em memória */
  }
}

export function limparToken(): void {
  emMemoria = null;
  try {
    window.localStorage.removeItem(CHAVE);
  } catch {
    /* nada a limpar */
  }
}

// A API respondeu 401 a uma chamada que levava token: a sessão acabou (expirou, foi derrubada ou a conta foi desativada).
let ouvinte: (() => void) | null = null;

export function aoExpirar(funcao: () => void): () => void {
  ouvinte = funcao;
  return () => {
    if (ouvinte === funcao) ouvinte = null;
  };
}

export function avisarNaoAutorizado(): void {
  limparToken();
  ouvinte?.();
}
