import { NFsTable } from "@/components/dashboard/nfs-table";
import { PadroesDetectados } from "@/components/dashboard/padroes-detectados";
import { StatsCards } from "@/components/dashboard/stats-cards";

export default function DashboardPage() {
  return (
    <div className="mx-auto max-w-[1500px] space-y-7">
      <header>
        <p className="text-sm font-semibold uppercase tracking-[0.12em] text-brand-primary-dark">
          Painel executivo
        </p>
        <h2 className="mt-1 text-[26px] font-bold tracking-tight text-zinc-950">
          Visão geral
        </h2>
        <p className="mt-1 text-[16px] text-zinc-500">
          Indicadores agregados das NFs recebidas e do consumo de diesel da obra.
        </p>
      </header>
      <PadroesDetectados />
      <StatsCards />
      <NFsTable />
    </div>
  );
}
