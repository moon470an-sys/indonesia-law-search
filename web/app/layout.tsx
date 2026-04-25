import type { Metadata } from "next";
import "./globals.css";
import Disclaimer from "@/components/Disclaimer";
import SiteHeader from "@/components/SiteHeader";

export const metadata: Metadata = {
  title: "인도네시아 법령정보센터",
  description:
    "인도네시아 정부 공식 법령(peraturan.go.id) 정보를 한국어로 검색하는 비공식 정보 사이트입니다.",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="ko">
      <body>
        <SiteHeader />
        <main className="mx-auto max-w-6xl px-6 py-6">{children}</main>
        <Disclaimer />
      </body>
    </html>
  );
}
