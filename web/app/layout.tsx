import type { Metadata } from "next";
import "./globals.css";
import Disclaimer from "@/components/Disclaimer";
import { path } from "@/lib/paths";

export const metadata: Metadata = {
  title: "인도네시아 법령 검색",
  description: "인도네시아 정부 부처(JDIH) 법령을 한국어로 검색합니다.",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="ko">
      <body>
        <header className="border-b bg-white">
          <div className="mx-auto max-w-5xl px-6 py-4">
            <a href={path("/")} className="text-lg font-semibold">
              인도네시아 법령 검색
            </a>
          </div>
        </header>
        <main className="mx-auto max-w-5xl px-6 py-8">{children}</main>
        <Disclaimer />
      </body>
    </html>
  );
}
