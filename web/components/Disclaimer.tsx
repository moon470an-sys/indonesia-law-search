export default function Disclaimer() {
  return (
    <footer className="mt-20 border-t border-slate-200 bg-white">
      <div className="mx-auto max-w-7xl space-y-2 px-6 py-8 text-sm text-slate-500">
        <p>
          <strong className="font-semibold text-slate-700">면책</strong>
          {" · "}
          본 한국어 번역은 참고용이며, 법적 효력은 인니어 원문에만 있습니다.
        </p>
        <p className="text-xs leading-relaxed text-slate-400">
          The Korean translations on this site are provided for reference only.
          Legal effect resides solely with the original Indonesian text.
        </p>
        <p className="text-xs leading-relaxed text-slate-500">
          <strong className="font-semibold text-slate-600">원문 접속 안내</strong>
          {" · "}
          peraturan.go.id 일부 도메인은 한국 통신망에서 직접 접속이 차단될 수 있습니다.
          상세 페이지의 <em>원문 자료</em> 섹션에서 Wayback Machine / Google 번역 프록시 등 우회 링크를 제공합니다.
        </p>
      </div>
    </footer>
  );
}
