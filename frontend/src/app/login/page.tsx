import type { Metadata } from "next";
import { Suspense } from "react";
import { FormLogin } from "@/components/form-login";

export const metadata: Metadata = { title: "Entrar" };

export default function PaginaLogin() {
  // useSearchParams (o aviso "sessão terminou") exige um <Suspense> com o Cache Components.
  return (
    <div className="py-8">
      <Suspense fallback={null}>
        <FormLogin />
      </Suspense>
    </div>
  );
}
