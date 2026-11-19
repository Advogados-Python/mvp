import type { Metadata } from "next";
import Link from "next/link";
import { Geist, Geist_Mono } from "next/font/google";
import { AuthProvider } from "@/components/auth-provider";
import { Logo } from "@/components/logo";
import { MenuUsuario } from "@/components/menu-usuario";
import { StatusApi } from "@/components/status-api";
import "./globals.css";

const geistSans = Geist({
  variable: "--font-geist-sans",
  subsets: ["latin"],
});

const geistMono = Geist_Mono({
  variable: "--font-geist-mono",
  subsets: ["latin"],
});

export const metadata: Metadata = {
  title: { default: "Leitor de Processos · Ribeiro e Souza", template: "%s · Ribeiro e Souza" },
  description: "Lê autos de processos em PDF e informa, com evidência, a fase do crédito e se a dívida já foi paga.",
};

export default function RootLayout({ children }: LayoutProps<"/">) {
  return (
    <html lang="pt-BR" className={`${geistSans.variable} ${geistMono.variable} h-full antialiased`}>
      <body className="flex min-h-full flex-col">
        <AuthProvider>
          <a
            href="#conteudo"
            className="sr-only focus:not-sr-only focus:fixed focus:left-4 focus:top-4 focus:z-50 focus:rounded-lg focus:bg-accent focus:px-4 focus:py-2 focus:text-sm focus:font-semibold focus:text-accent-foreground"
          >
            Pular para o conteúdo
          </a>
          <header className="vidro sticky top-0 z-20 border-x-0! border-t-0!">
            <div className="mx-auto flex w-full max-w-7xl items-center justify-between gap-3 px-4 py-3 sm:gap-4 sm:px-6">
              <Link href="/" className="flex min-w-0 items-center gap-3 rounded-lg">
                <Logo tamanho={36} />
                <span className="min-w-0 leading-tight">
                  <span className="block text-sm font-semibold">Ribeiro e Souza</span>
                  <span className="block text-xs text-muted">Leitor de Processos</span>
                </span>
              </Link>
              <div className="flex shrink-0 items-center gap-2 sm:gap-3">
                <StatusApi />
                <MenuUsuario />
              </div>
            </div>
          </header>
          <main id="conteudo" tabIndex={-1} className="mx-auto w-full max-w-7xl flex-1 px-4 py-6 focus:outline-none sm:px-6 sm:py-8">
            {children}
          </main>
        </AuthProvider>
      </body>
    </html>
  );
}
