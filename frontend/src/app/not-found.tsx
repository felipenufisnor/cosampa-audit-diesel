import Link from "next/link";

import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";

export default function NotFound() {
  return (
    <div className="max-w-xl mx-auto pt-8">
      <Card>
        <CardContent className="space-y-3 text-center py-8">
          <p className="text-xs font-semibold uppercase tracking-wider text-zinc-500">
            Erro 404
          </p>
          <h2 className="text-2xl font-semibold text-zinc-900">
            Página não encontrada
          </h2>
          <p className="text-sm text-zinc-600">
            O endereço acessado não existe ou foi removido. Verifique o link ou
            volte ao painel principal.
          </p>
          <div className="pt-2 flex justify-center">
            <Link href="/">
              <Button>Voltar ao Dashboard</Button>
            </Link>
          </div>
        </CardContent>
      </Card>
    </div>
  );
}
