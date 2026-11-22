// Contrato com a API (backend/*/schemas.py). Mantenha os dois lados em sincronia.

export type DividaPaga = "SIM" | "PROVAVEL" | "NAO" | "SEM_INFORMACAO";

/** PENDENTE = na fila · ANALISANDO = lendo o PDF · CONCLUIDO · FALHOU (veja `erro`). */
export type StatusAnalise = "PENDENTE" | "ANALISANDO" | "CONCLUIDO" | "FALHOU";

export const emAndamento = (status: StatusAnalise) => status === "PENDENTE" || status === "ANALISANDO";

/**
 * Etapas que o backend informa enquanto analisa, na ordem real de execução (backend/pipeline.py: ETAPAS; uma por módulo do backend).
 * A etapa "recebido" não vem da API: é o status PENDENTE (o PDF chegou e espera a vez na fila).
 */
export const ETAPAS = ["LENDO_PDF", "IDENTIFICANDO", "BUSCANDO_TERMOS", "VALIDANDO", "FINALIZANDO"] as const;
export type EtapaAnalise = (typeof ETAPAS)[number];

/** Onde a análise está. `atual`/`total` (páginas) só existem nas etapas que andam página a página; nunca são estimados. */
export interface Progresso {
  /** Um código novo do backend que o front ainda não conhece é tratado como "andamento sem detalhe". */
  etapa: string;
  atual: number | null;
  total: number | null;
  /** status FALHOU: a análise parou nesta etapa. */
  falhou: boolean;
}

/** O que o fluxo de eventos (GET /api/processos/{id}/eventos) entrega: só status e progresso, nunca o resultado. */
export interface EstadoAnalise {
  status: StatusAnalise;
  progresso: Progresso | null;
}

export type EventoAnalise =
  | { tipo: "estado" | "fim"; estado: EstadoAnalise } // fim = CONCLUIDO/FALHOU: o resultado vem de GET /api/processos/{id}
  | { tipo: "removido" | "reconectar" };

export interface Usuario {
  id: number;
  email: string;
  nome: string;
  admin: boolean;
  ativo: boolean;
  criado_em: string;
}

export interface Token {
  access_token: string;
  token_type: "bearer";
  expira_em: string;
  usuario: Usuario;
}

export interface Parte {
  nome: string;
  papel: string;
}

export interface Evidencia {
  fase: string;
  termo: string;
  pagina: number;
  trecho: string;
  tipo_documento: string | null;
  /** Frase condicional/futura/negada: aparece, mas não decide a fase. */
  hipotetico: boolean;
  /** false = veio de peça da parte (petição, manifestação...), não do juízo. */
  origem_confiavel: boolean;
  /** Só evidências que "contam" (não hipotéticas e do juízo) decidem a fase. */
  conta: boolean;
}

interface ProcessoBase {
  id: string;
  arquivo: string;
  tamanho_bytes: number;
  criado_em: string;
  concluido_em: string | null;
  status: StatusAnalise;
  /** Motivo da falha (só quando status = FALHOU). */
  erro: string | null;
  /** ANALISANDO: a etapa atual. FALHOU: onde parou (some se o servidor reiniciou). Nos demais status: null. */
  progresso: Progresso | null;

  // Os campos abaixo só vêm preenchidos quando status = CONCLUIDO.
  total_paginas: number | null;
  paginas_sem_texto: number | null;
  numero_processo: string | null;
  tribunal: string | null;
  classe: string | null;
  orgao_julgador: string | null;
  valor_causa: string | null;
  valor_requisitado: string | null;
  data_emissao_pdf: string | null;
  partes: Parte[];
  advogados: string[];
  oabs: string[];
  juiz: string | null;
  fase: string | null;
  fase_descricao: string | null;
  divida_paga: DividaPaga | null;
  avisos: string[];
  evidencia_principal: Evidencia | null;
  total_evidencias: number;
  evidencias_que_contam: number;
}

/** Versão leve usada nas listas (sem as evidências). */
export type ResumoProcesso = ProcessoBase;

/** Resultado completo de um processo. */
export interface Processo extends ProcessoBase {
  evidencias: Evidencia[];
}

export interface Fase {
  codigo: string;
  rotulo: string;
  descricao: string;
  ordem: number;
}

export interface SignificadoDivida {
  valor: DividaPaga;
  significado: string;
  acao: string;
}

export interface Fases {
  fases: Fase[];
  divida_paga: SignificadoDivida[];
}

export interface FalhaEnvio {
  arquivo: string;
  erro: string;
}

/** Resposta do envio: `processos` foram aceitos (a análise segue em segundo plano); `falhas` foram recusados na hora. */
export interface RespostaEnvio {
  processos: ResumoProcesso[];
  falhas: FalhaEnvio[];
}
