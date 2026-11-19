"use client";

import { useCallback, useEffect, useState } from "react";
import { api } from "./api";
import { emAndamento, type ResumoProcesso } from "./tipos";

const INTERVALO_MS = 2000; // enquanto houver análise em andamento
const ESPERA_MAXIMA_APOS_FALHA_MS = 15_000;

/** Mantém o objeto antigo quando nada mudou nele: a lista inteira só renderiza de novo se algo de fato mudou. */
function reaproveitar(antigos: ResumoProcesso[] | null, novos: ResumoProcesso[]): ResumoProcesso[] {
  if (!antigos) return novos;
  const porId = new Map(antigos.map((processo) => [processo.id, processo]));
  let igual = antigos.length === novos.length;
  const resultado = novos.map((novo, indice) => {
    const velho = porId.get(novo.id);
    const mantido = velho && JSON.stringify(velho) === JSON.stringify(novo) ? velho : novo;
    if (mantido !== antigos[indice]) igual = false;
    return mantido;
  });
  return igual ? antigos : resultado;
}

/**
 * A lista de processos. Enquanto algum estiver na fila ou sendo analisado, consulta a API a cada 2 s e atualiza só o
 * que mudou (sem voltar ao "carregando"). Não consulta com a aba escondida (e consulta na hora ao voltar). Se a API
 * falhar, mantém a lista que já tinha, avisa e tenta de novo com espera crescente: a falha de uma consulta não encerra
 * o acompanhamento. `versao` muda quando um envio termina: é o sinal para buscar já.
 */
export function useListaProcessos(versao: number) {
  const [processos, setProcessos] = useState<ResumoProcesso[] | null>(null);
  const [erro, setErro] = useState<string | null>(null);
  const [rodada, setRodada] = useState(0);

  useEffect(() => {
    let ativo = true;
    let temporizador: ReturnType<typeof setTimeout> | undefined;
    let falhasSeguidas = 0;

    const agendar = (ms: number) => {
      clearTimeout(temporizador);
      temporizador = setTimeout(buscar, ms);
    };

    function buscar() {
      if (document.hidden) return; // aba escondida: o `visibilitychange` retoma
      api
        .listar()
        .then((dados) => {
          if (!ativo) return;
          falhasSeguidas = 0;
          setProcessos((antigos) => reaproveitar(antigos, dados));
          setErro(null);
          if (dados.some((processo) => emAndamento(processo.status))) agendar(INTERVALO_MS);
        })
        .catch((falha: Error) => {
          if (!ativo) return;
          falhasSeguidas += 1;
          setErro(falha.message);
          agendar(Math.min(INTERVALO_MS * 2 ** falhasSeguidas, ESPERA_MAXIMA_APOS_FALHA_MS));
        });
    }

    const aoMudarVisibilidade = () => {
      if (!document.hidden) buscar();
    };
    document.addEventListener("visibilitychange", aoMudarVisibilidade);
    buscar();
    return () => {
      ativo = false;
      clearTimeout(temporizador);
      document.removeEventListener("visibilitychange", aoMudarVisibilidade);
    };
  }, [versao, rodada]);

  const recarregar = useCallback(() => setRodada((atual) => atual + 1), []);
  const remover = useCallback(
    (id: string) => setProcessos((atuais) => atuais?.filter((processo) => processo.id !== id) ?? null),
    [],
  );

  return { processos, erro, recarregar, remover, definirErro: setErro };
}
