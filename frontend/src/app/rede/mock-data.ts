/**
 * Dados sinteticos do grafo de relacionamentos (preview).
 *
 * Posicoes (x, y) curadas a mao para que o grafo conte uma historia: tres
 * "clusters suspeitos" pre-rotulados ficam em regioes destacaveis por
 * cor de fundo. NAO ha algoritmo de layout em runtime - estatico.
 *
 * Coordenadas no espaco SVG 1200x720.
 */

export type TipoNo = "obra" | "veiculo" | "fornecedor" | "operador";

export interface NoGrafo {
  id: string;
  tipo: TipoNo;
  rotulo: string;
  detalhe?: string;
  x: number;
  y: number;
  destaque?: "alta" | "media" | null;
  cluster?: string;
}

export interface ArestaGrafo {
  de: string;
  para: string;
  relacao: string;
  destacada?: boolean;
}

export interface ClusterSuspeito {
  id: string;
  titulo: string;
  descricao: string;
  severidade: "alta" | "media";
  bbox: { x: number; y: number; w: number; h: number };
  ids: string[];
}

// --- Nos -------------------------------------------------------------------

export const NOS: NoGrafo[] = [
  // Obras (4)
  { id: "obra-arco", tipo: "obra", rotulo: "Arco JP", detalhe: "obra-piloto (POC)", x: 220, y: 130 },
  { id: "obra-pelotas", tipo: "obra", rotulo: "Pelotas Sul", detalhe: "rodovia federal", x: 980, y: 140 },
  { id: "obra-rec-norte", tipo: "obra", rotulo: "Recife Norte", detalhe: "solar fotovoltaica", x: 220, y: 600, cluster: "cluster-multiplas-obras" },
  { id: "obra-fortal", tipo: "obra", rotulo: "Fortaleza Oeste", detalhe: "saneamento", x: 980, y: 600 },

  // Fornecedores (3)
  { id: "forn-A", tipo: "fornecedor", rotulo: "Posto BR Diesel A", x: 600, y: 90, cluster: "cluster-fornecedor" },
  { id: "forn-B", tipo: "fornecedor", rotulo: "Posto Norte Combust.", x: 100, y: 360 },
  { id: "forn-C", tipo: "fornecedor", rotulo: "Comboio Express", x: 1100, y: 360 },

  // Operadores (5)
  { id: "op-1", tipo: "operador", rotulo: "Operador 207", detalhe: "Renato A.", x: 420, y: 350, cluster: "cluster-operador" },
  { id: "op-2", tipo: "operador", rotulo: "Operador 089", detalhe: "Lucas T.", x: 760, y: 350 },
  { id: "op-3", tipo: "operador", rotulo: "Operador 311", detalhe: "Marcos P.", x: 600, y: 470 },
  { id: "op-4", tipo: "operador", rotulo: "Operador 015", detalhe: "Pedro M.", x: 920, y: 250 },
  { id: "op-5", tipo: "operador", rotulo: "Operador 144", detalhe: "Andre B.", x: 280, y: 250 },

  // Veiculos (15)
  // Cluster A: veiculo em 2 obras no mesmo dia
  { id: "veh-04T639", tipo: "veiculo", rotulo: "04T639", detalhe: "desmobilizado", x: 220, y: 380, destaque: "alta", cluster: "cluster-multiplas-obras" },

  // Cluster B: operador em multiplas NFs com alerta
  { id: "veh-OSB8826", tipo: "veiculo", rotulo: "OSB8826", detalhe: "outlier +329%", x: 420, y: 200, destaque: "alta", cluster: "cluster-operador" },
  { id: "veh-31T801", tipo: "veiculo", rotulo: "31T801", detalhe: "outlier +119%", x: 540, y: 290, destaque: "media", cluster: "cluster-operador" },
  { id: "veh-QFT5F93", tipo: "veiculo", rotulo: "QFT5F93", detalhe: "outlier +121%", x: 360, y: 300, destaque: "media", cluster: "cluster-operador" },

  // Cluster C: fornecedor com inconsistencias recorrentes
  { id: "veh-KJP6427", tipo: "veiculo", rotulo: "KJP6427", detalhe: "inconsistências x4", x: 520, y: 180, destaque: "media", cluster: "cluster-fornecedor" },
  { id: "veh-OIP6397", tipo: "veiculo", rotulo: "OIP6397", detalhe: "inconsistências x3", x: 680, y: 180, destaque: "media", cluster: "cluster-fornecedor" },
  { id: "veh-NNK8I04", tipo: "veiculo", rotulo: "NNK8I04", detalhe: "inconsistências x3", x: 720, y: 60, destaque: "media", cluster: "cluster-fornecedor" },

  // Veiculos sem destaque (ruido de fundo)
  { id: "veh-SBM1B12", tipo: "veiculo", rotulo: "SBM1B12", detalhe: "cadastrado", x: 880, y: 460, destaque: null },
  { id: "veh-KIN2G72", tipo: "veiculo", rotulo: "KIN2G72", detalhe: "cadastrado", x: 1020, y: 480, destaque: null },
  { id: "veh-JMG1J00", tipo: "veiculo", rotulo: "JMG1J00", detalhe: "cadastrado", x: 1080, y: 240, destaque: null },
  { id: "veh-PVN3R88", tipo: "veiculo", rotulo: "PVN3R88", detalhe: "cadastrado", x: 380, y: 540, destaque: null },
  { id: "veh-TGY9Z01", tipo: "veiculo", rotulo: "TGY9Z01", detalhe: "cadastrado", x: 580, y: 590, destaque: null },
  { id: "veh-LRC4M77", tipo: "veiculo", rotulo: "LRC4M77", detalhe: "cadastrado", x: 800, y: 530, destaque: null },
  { id: "veh-DXS2F19", tipo: "veiculo", rotulo: "DXS2F19", detalhe: "cadastrado", x: 130, y: 470, destaque: null },
  { id: "veh-WHB6Q22", tipo: "veiculo", rotulo: "WHB6Q22", detalhe: "cadastrado", x: 1100, y: 540, destaque: null },
];

// --- Arestas ---------------------------------------------------------------

export const ARESTAS: ArestaGrafo[] = [
  // Cluster A: veiculo 04T639 conecta 2 obras (suspeito)
  { de: "veh-04T639", para: "obra-arco", relacao: "abasteceu", destacada: true },
  { de: "veh-04T639", para: "obra-rec-norte", relacao: "abasteceu", destacada: true },
  { de: "veh-04T639", para: "op-5", relacao: "operado por" },

  // Cluster B: operador 207 ligado a 3 veiculos com outlier
  { de: "veh-OSB8826", para: "op-1", relacao: "operado por", destacada: true },
  { de: "veh-31T801", para: "op-1", relacao: "operado por", destacada: true },
  { de: "veh-QFT5F93", para: "op-1", relacao: "operado por", destacada: true },
  { de: "veh-OSB8826", para: "obra-arco", relacao: "abasteceu" },
  { de: "veh-31T801", para: "obra-arco", relacao: "abasteceu" },
  { de: "veh-QFT5F93", para: "obra-arco", relacao: "abasteceu" },

  // Cluster C: fornecedor A com varias inconsistencias
  { de: "veh-KJP6427", para: "forn-A", relacao: "fornecido por", destacada: true },
  { de: "veh-OIP6397", para: "forn-A", relacao: "fornecido por", destacada: true },
  { de: "veh-NNK8I04", para: "forn-A", relacao: "fornecido por", destacada: true },
  { de: "veh-KJP6427", para: "obra-arco", relacao: "abasteceu" },
  { de: "veh-OIP6397", para: "obra-arco", relacao: "abasteceu" },
  { de: "veh-NNK8I04", para: "obra-pelotas", relacao: "abasteceu" },

  // Conexoes normais (ruido de fundo)
  { de: "veh-SBM1B12", para: "obra-fortal", relacao: "abasteceu" },
  { de: "veh-SBM1B12", para: "op-2", relacao: "operado por" },
  { de: "veh-KIN2G72", para: "obra-fortal", relacao: "abasteceu" },
  { de: "veh-KIN2G72", para: "op-2", relacao: "operado por" },
  { de: "veh-JMG1J00", para: "obra-pelotas", relacao: "abasteceu" },
  { de: "veh-JMG1J00", para: "op-4", relacao: "operado por" },
  { de: "veh-PVN3R88", para: "obra-rec-norte", relacao: "abasteceu" },
  { de: "veh-PVN3R88", para: "op-3", relacao: "operado por" },
  { de: "veh-TGY9Z01", para: "obra-rec-norte", relacao: "abasteceu" },
  { de: "veh-TGY9Z01", para: "op-3", relacao: "operado por" },
  { de: "veh-LRC4M77", para: "obra-fortal", relacao: "abasteceu" },
  { de: "veh-LRC4M77", para: "op-2", relacao: "operado por" },
  { de: "veh-DXS2F19", para: "obra-rec-norte", relacao: "abasteceu" },
  { de: "veh-DXS2F19", para: "forn-B", relacao: "fornecido por" },
  { de: "veh-WHB6Q22", para: "obra-fortal", relacao: "abasteceu" },
  { de: "veh-WHB6Q22", para: "forn-C", relacao: "fornecido por" },

  // Fornecedores tambem ligados a obras
  { de: "forn-A", para: "obra-arco", relacao: "atende" },
  { de: "forn-A", para: "obra-pelotas", relacao: "atende" },
  { de: "forn-B", para: "obra-rec-norte", relacao: "atende" },
  { de: "forn-C", para: "obra-fortal", relacao: "atende" },
];

// --- Clusters --------------------------------------------------------------

export const CLUSTERS: ClusterSuspeito[] = [
  {
    id: "cluster-multiplas-obras",
    titulo: "Veículo em 2 obras",
    descricao:
      "04T639 aparece em Arco JP e Recife Norte no mesmo período, após data de desmobilização.",
    severidade: "alta",
    bbox: { x: 80, y: 340, w: 280, h: 290 },
    ids: ["veh-04T639", "obra-arco", "obra-rec-norte", "op-5"],
  },
  {
    id: "cluster-operador",
    titulo: "Operador comum a 3 outliers",
    descricao:
      "Operador 207 (Renato A.) registrou 3 veículos com aumento de consumo >100%.",
    severidade: "alta",
    bbox: { x: 320, y: 160, w: 290, h: 230 },
    ids: ["op-1", "veh-OSB8826", "veh-31T801", "veh-QFT5F93"],
  },
  {
    id: "cluster-fornecedor",
    titulo: "Fornecedor com inconsistências",
    descricao:
      "Posto BR Diesel A concentra 10 abastecimentos com flag Infleet nos últimos 30 dias.",
    severidade: "media",
    bbox: { x: 470, y: 30, w: 290, h: 200 },
    ids: ["forn-A", "veh-KJP6427", "veh-OIP6397", "veh-NNK8I04"],
  },
];

export const TIPOS_NO: { id: TipoNo; label: string }[] = [
  { id: "obra", label: "Obras" },
  { id: "veiculo", label: "Veículos" },
  { id: "fornecedor", label: "Fornecedores" },
  { id: "operador", label: "Operadores" },
];
