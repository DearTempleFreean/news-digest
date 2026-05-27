# 📰 글로벌 뉴스 다이제스트

매일 오전 7시 KST, 26개 언론사 뉴스를 자동으로 이메일 발송. 완전 무료.

## 설치 방법

### 1. Gmail 앱 비밀번호 발급
1. myaccount.google.com → 보안 → 2단계 인증 활성화
2. 검색창에 "앱 비밀번호" → 16자리 발급

### 2. GitHub Secrets 등록
Settings → Secrets and variables → Actions → New repository secret

| 이름 | 값 |
|------|----|
| GMAIL_ADDRESS | 발신 Gmail 주소 |
| GMAIL_APP_PASSWORD | 앱 비밀번호 16자리 (공백 없이) |
| RECIPIENT_EMAILS | 수신 이메일 (콤마로 여러 개 가능) |

### 3. 테스트 실행
Actions 탭 → Daily Global News Digest → Run workflow
