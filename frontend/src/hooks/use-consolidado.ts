import { useQuery } from "@tanstack/react-query";

import { api } from "@/lib/api";

export function useConsolidado() {
  return useQuery({
    queryKey: ["consolidado"],
    queryFn: () => api.consolidado(),
    staleTime: 30_000,
  });
}
