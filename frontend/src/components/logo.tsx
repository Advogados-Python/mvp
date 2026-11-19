import Image from "next/image";

/**
 * O logo do escritório (public/logo.jpeg: balança preta sobre fundo branco, 1254 × 1254). Aparece como um selo quadrado
 * arredondado, sem recolorir a imagem. Decorativo (alt vazio): o nome "Ribeiro e Souza" vem sempre escrito ao lado.
 */
export function Logo({ tamanho = 36, className = "" }: { tamanho?: number; className?: string }) {
  return (
    <Image
      src="/logo.jpeg"
      alt=""
      width={tamanho}
      height={tamanho}
      priority
      style={{ width: tamanho, height: tamanho }}
      className={`shrink-0 rounded-lg bg-white object-cover ring-1 ring-white/25 ${className}`}
    />
  );
}
