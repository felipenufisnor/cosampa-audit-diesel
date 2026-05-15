import type { Metadata } from "next";
import { Inter } from "next/font/google";
import { Toaster } from "sonner";

import { AppShell } from "@/components/layout/app-shell";
import { ReactQueryProvider } from "@/components/providers";
import "./globals.css";

const inter = Inter({
  variable: "--font-inter",
  subsets: ["latin"],
  display: "swap",
});

export const metadata: Metadata = {
  title: "CONTROLE TÉCNICO DE DIESEL - ARCO METROPOLITANO JP",
  description:
    "Auditoria automatizada de notas fiscais de diesel para o consórcio CLC/Rocha/Cosampa.",
};

export default function RootLayout({
  children,
}: Readonly<{ children: React.ReactNode }>) {
  return (
    <html lang="pt-BR" className={`${inter.variable} h-full antialiased`}>
      <body className="min-h-full bg-app-bg text-zinc-900">
        <ReactQueryProvider>
          <AppShell>{children}</AppShell>
          {/* Sonner padronizado: top-right, 4s, dismiss manual habilitado.
              richColors aplica verde/vermelho/cinza nas variantes do toast. */}
          <Toaster
            richColors
            closeButton
            position="top-right"
            duration={4000}
            toastOptions={{ style: { fontSize: "0.85rem" } }}
          />
        </ReactQueryProvider>
      </body>
    </html>
  );
}
