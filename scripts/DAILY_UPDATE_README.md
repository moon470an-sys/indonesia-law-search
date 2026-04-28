# 매일 09:00 KST 자동 업데이트 + 이메일 알림

## 한 번만 설정 (최초 1회)

### 1. SMTP 설정 (이메일 발송용)

가장 쉬운 방법: **Gmail 앱 비밀번호** (계정 `moon470an@gmail.com` 가정)

1. https://myaccount.google.com/security 에서 **2단계 인증** 활성화
2. https://myaccount.google.com/apppasswords 에서 **앱 비밀번호** 생성 (16자리, 공백 무시)
3. PowerShell(관리자)에서 환경 변수 영구 등록:
   ```powershell
   [Environment]::SetEnvironmentVariable("JDIH_SMTP_HOST", "smtp.gmail.com", "User")
   [Environment]::SetEnvironmentVariable("JDIH_SMTP_PORT", "587", "User")
   [Environment]::SetEnvironmentVariable("JDIH_SMTP_USER", "moon470an@gmail.com", "User")
   [Environment]::SetEnvironmentVariable("JDIH_SMTP_PASSWORD", "abcd efgh ijkl mnop", "User")
   [Environment]::SetEnvironmentVariable("JDIH_EMAIL_FROM", "moon470an@gmail.com", "User")
   [Environment]::SetEnvironmentVariable("JDIH_EMAIL_TO", "yoonseok.moon@sticorp.co.kr", "User")
   ```

대안: `@sticorp.co.kr` 메일이 Office 365라면
```powershell
[Environment]::SetEnvironmentVariable("JDIH_SMTP_HOST", "smtp.office365.com", "User")
[Environment]::SetEnvironmentVariable("JDIH_SMTP_PORT", "587", "User")
[Environment]::SetEnvironmentVariable("JDIH_SMTP_USER", "yoonseok.moon@sticorp.co.kr", "User")
[Environment]::SetEnvironmentVariable("JDIH_SMTP_PASSWORD", "<MS365 비밀번호 또는 앱 비밀번호>", "User")
```

### 2. Windows Task Scheduler 등록

PowerShell에서:
```powershell
cd "C:\Users\yoonseok.moon\OneDrive - (주) ST International\Projects\인도네시아 법령"
powershell -ExecutionPolicy Bypass -File scripts\install_daily_task.ps1
```

### 3. 즉시 테스트 (선택)
```powershell
Start-ScheduledTask -TaskName "JDIH-Daily-Update"
# 1~5분 후 결과 확인
Get-Content "data\pending\last_daily_log.txt"
```

이메일이 도착하면 정상. 안 오면 `data\pending\last_daily_log.txt` 의 `[email]` 라인에서 원인 확인.

---

## 동작 흐름

매일 09:00 KST:
1. `git pull --rebase` — 최신 DB 상태 sync
2. `python -m crawler.update_all` — 등록된 부처 크롤러 실행 → `data/pending/chunks/*.json` 생성
3. `python -m crawler.build_db` — `data/laws.db` 재생성
4. `git add` + `git commit` + `git push` — 변경 사항 publish
5. SMTP로 yoonseok.moon@sticorp.co.kr 에 결과 메일 전송

이메일 본문 예시:
```
Subject: [JDIH 일일 크롤] 2026-04-29 09:00 KST — +12 건

## 인도네시아 법령 일일 업데이트
실행 시각: 2026-04-29 09:00 KST
신규 미번역: 12 건

### 부처별 결과
  - EsdmScraper (esdm): new=8, chunks=1
  - DephubScraper (dephub): new=4, chunks=1

### 다음 단계
신규 행이 있다면 Claude Code 채팅에서 /translate-pending 으로 번역하세요.

---
### 실행 로그
git pull (exit 0)
...
crawler.update_all (exit 0)
...
git push (exit 0)
```

## 번역은 자동화되지 않음

CLAUDE.md 절대원칙에 따라 번역은 외부 API 호출 없이 Claude Code 채팅 안에서만 처리합니다. 일일 크롤은 신규 항목을 감지해 chunk 파일로 저장하고 메일로 알리지만, 실제 번역은 사용자가 채팅을 열어 `/translate-pending` 슬래시 커맨드를 실행해야 합니다.

## 트러블슈팅

| 증상 | 확인 |
|---|---|
| Task가 실행 안 됨 | `Get-ScheduledTaskInfo -TaskName JDIH-Daily-Update` → LastTaskResult 확인 |
| 크롤은 됐는데 메일 미수신 | `data\pending\last_daily_log.txt` 의 `[email]` 라인 |
| 크롤 자체 실패 | 같은 파일의 "crawler.update_all" 섹션 출력 |
| Gmail "less secure app" 거부 | 앱 비밀번호 사용 (일반 비밀번호 X) |
| 회사 프록시 차단 | SMTP 호스트/포트 회사 정책 확인 |
| 일부 .go.id 사이트 접속 불가 | 한국 통신망 차단 — 해당 부처는 자동 skip, 다른 부처는 진행 |

## 일시 정지 / 변경

```powershell
# 비활성화 (다시 활성화하려면 Enable-ScheduledTask)
Disable-ScheduledTask -TaskName "JDIH-Daily-Update"

# 시간 변경 (예: 07:00 KST)
$trigger = New-ScheduledTaskTrigger -Daily -At 07:00
Set-ScheduledTask -TaskName "JDIH-Daily-Update" -Trigger $trigger

# 완전 제거
Unregister-ScheduledTask -TaskName "JDIH-Daily-Update" -Confirm:$false
```
