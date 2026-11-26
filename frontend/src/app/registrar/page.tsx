import type { Metadata } from "next";
import { FormRegistro } from "@/components/form-registro";

export const metadata: Metadata = { title: "Registre-se" };

export default function PaginaRegistro() {
  return (
    <div className="py-8">
      <FormRegistro />
    </div>
  );
}
