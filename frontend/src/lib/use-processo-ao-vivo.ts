"use client";

import { useCallback, useEffect, useState } from "react";
import { ErroApi, acompanharAnalise, api } from "./api";
import { emAndamento, type EstadoAnalise, type Processo } from "./tipos";

const INTERVALO_POLLING_MS = 2000;
const JANELA_POLLING_INICIAL_MS = 6000; // depois de uma falha do SSE: quanto tempo fica só no polling antes de tentar o SSE de novo
const JANELA_POLLING_MAXIMA_MS = 60_000; // a janela dobra a cada falha seguida, até este teto

/** conectando = abrindo o fluxo · ao-vivo = recebendo eventos (SSE) · polling = SSE indisponível, consultando a API a cada 2 s. */
export type Conexao = "conectando" | "ao-vivo" | "polling";

type Leitura = { dados: Processo } | { falha: ErroApi };

function dormir(ms: number, sinal: AbortSignal): Promise<void> {
  return new Promise((resolver) => {
    const temporizador = setTimeout(resolver, ms);
    sinal.addEventListener(
      "abort",
      () => {
        clearTimeout(temporizador);
        resolver();
      },
      { once: true },
    );
  });
}

/**
 * Um processo, atualizado enquanto a análise roda.
 *
 * Fonte da verdade: GET /api/processos/{id} (resultado, status, avisos). Por cima dele, enquanto está na fila ou
 * sendo analisado, abre o fluxo SSE (/eventos), que só traz status + etapa. Quando o fluxo anuncia o fim, busca o
 * resultado completo no GET. Se o SSE não conectar ou cair, cai para o polling de 2 s e tenta o SSE de novo com
 * espera crescente; falhas de rede no meio do caminho não interrompem nada (a tela mantém o último resultado e segue
 * tentando). Reanálise: `recarregar()` recomeça o ciclo (o fluxo anterior é abortado).
 */
export function useProcessoAoVivo(id: string) {
  const [processo, setProcesso] = useState<Processo | null>(null);
  const [erro, setErro] = useState<ErroApi | null>(null);
  const [estado, setEstado] = useState<EstadoAnalise | null>(null);
  const [conexao, setConexao] = useState<Conexao>("conectando");
  const [rodada, setRodada] = useState(0);

  useEffect(() => {
    const controle = new AbortController();
    const { signal: sinal } = controle;

    // Busca o processo completo. null = a tela saiu (efeito cancelado).
    async function carregar(): Promise<Leitura | null> {
      try {
        const dados = await api.obter(id);
        if (sinal.aborted) return null;
        setProcesso(dados);
        setErro(null);
        setEstado({ status: dados.status, progresso: dados.progresso });
        return { dados };
      } catch (falha) {
        if (sinal.aborted) return null;
        setErro(falha as ErroApi);
        return { falha: falha as ErroApi };
      }
    }

    // Só o polling, até a janela acabar ou o processo terminar. Devolve true se não há mais o que acompanhar.
    async function consultarPor(janelaMs: number): Promise<boolean> {
      setConexao("polling");
      const fim = Date.now() + janelaMs;
      while (!sinal.aborted && Date.now() < fim) {
        await dormir(INTERVALO_POLLING_MS, sinal);
        if (sinal.aborted) return true;
        const leitura = await carregar();
        if (leitura === null) return true;
        if ("falha" in leitura ? leitura.falha.status === 404 : !emAndamento(leitura.dados.status)) return true;
      }
      return false;
    }

    async function ciclo() {
      let falhasSeguidas = 0;
      for (;;) {
        const leitura = await carregar();
        if (leitura === null) return;
        if ("falha" in leitura) {
          if (leitura.falha.status === 404 || leitura.falha.status === 401) return; // apagado, ou sessão expirada (o login cuida)
          await dormir(INTERVALO_POLLING_MS, sinal); // sem conexão com a API: segue tentando
          if (sinal.aborted) return;
          continue;
        }
        if (!emAndamento(leitura.dados.status)) return; // terminou: o resultado já está na tela

        setConexao("conectando");
        let recebeuEvento = false;
        let anunciouFim = false;
        const abertoEm = Date.now();
        try {
          await acompanharAnalise(
            id,
            (evento) => {
              recebeuEvento = true;
              setConexao("ao-vivo");
              if (evento.tipo === "estado" || evento.tipo === "fim") setEstado(evento.estado);
              if (evento.tipo === "fim" || evento.tipo === "removido") anunciouFim = true;
            },
            sinal,
          );
        } catch (falha) {
          if (sinal.aborted || (falha as ErroApi).status === 401) return;
          if ((falha as ErroApi).status === 404) {
            await carregar(); // o processo sumiu: a tela mostra "não encontrado"
            return;
          }
          recebeuEvento = false; // não conectou ou caiu no meio: polling por uma janela, depois tenta o SSE de novo
        }
        if (sinal.aborted) return;

        if (recebeuEvento) {
          falhasSeguidas = 0; // o fluxo funcionou e foi encerrado (fim, removido ou limite de duração): volta ao topo
          // (e o `carregar` do topo traz o resultado, ou o 404, e decide se abre o fluxo de novo)
          if (!anunciouFim && Date.now() - abertoEm < 1000) await dormir(INTERVALO_POLLING_MS, sinal); // proxy que corta o fluxo na hora: sem laço apertado
          continue;
        }
        falhasSeguidas += 1;
        const janela = Math.min(JANELA_POLLING_INICIAL_MS * 2 ** (falhasSeguidas - 1), JANELA_POLLING_MAXIMA_MS);
        if (await consultarPor(janela)) return;
      }
    }

    void ciclo();
    return () => controle.abort();
  }, [id, rodada]);

  const recarregar = useCallback(() => setRodada((atual) => atual + 1), []);

  return {
    // se o id mudou, não mostra o processo anterior enquanto o novo carrega
    processo: processo?.id === id ? processo : null,
    erro,
    estado,
    conexao,
    recarregar,
    definirErro: setErro,
  };
}
