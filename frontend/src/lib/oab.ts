// Número da OAB: a MESMA regra do backend (backend/userauths/schemas.py, normalizar_oab). Mudou lá, mude aqui.
// Confere só o formato e a UF; quem confere se a inscrição existe é o administrador, ao liberar a conta.

const UFS = new Set([
  "AC", "AL", "AP", "AM", "BA", "CE", "DF", "ES", "GO", "MA", "MT", "MS", "MG", "PA",
  "PB", "PR", "PE", "PI", "RJ", "RN", "RS", "RO", "RR", "SC", "SP", "SE", "TO",
]);

export type ResultadoOab = { ok: true; oab: string } | { ok: false; erro: string };

/** "123.456/sp", "SP 123456" e "sp-123456" viram "SP123456". Aceita a letra suplementar no fim do número (12345A/RJ). */
export function normalizarOab(texto: string): ResultadoOab {
  const limpo = texto.trim().toUpperCase().replace(/[.\-/\s]/g, "");
  const ufAntes = /^([A-Z]{2})(\d{1,6}[A-Z]?)$/.exec(limpo);
  const ufDepois = /^(\d{1,6}[A-Z]?)([A-Z]{2})$/.exec(limpo);
  let uf: string;
  let numero: string;
  if (ufAntes) [, uf, numero] = ufAntes;
  else if (ufDepois) [, numero, uf] = ufDepois;
  else return { ok: false, erro: "Formato inválido. Use UF + número (ex.: GO12345 ou 12345/GO)." };
  if (!UFS.has(uf)) return { ok: false, erro: `A sigla de estado '${uf}' não existe.` };
  return { ok: true, oab: `${uf}${numero}` };
}
