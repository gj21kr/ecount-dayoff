# 팀 휴가 대시보드

AI/SW팀 휴가를 월간·주간 캘린더와 목록으로 표시합니다. 회의·Outlook 수집은 비활성화되어 있습니다.

## 비공개 설정과 데이터

개인정보와 운영 설정은 모두 Git 및 Docker 빌드에서 제외된 `.credentials/`에 둡니다.
- `teams.json`: 팀원 명단과 이름 별칭. `examples/teams.json`은 가상 인물만 포함합니다.
- `data/`: 실제 휴가 저장본, 처리 이력 및 기존 캐시.
- `imports/`: 기본 PDF 입력 폴더. 외부 원본 폴더는 읽기 전용으로 연결할 수 있습니다.
- `artifacts/`: 실제 데이터가 보이는 스크린샷.
- `compose.private.yaml`: 사내 IP, 외부 폴더 경로 등 로컬 배포 설정.
- 기존 연결 비밀값과 실데이터 검증 기록도 이 폴더에만 보관합니다.

기본 설정에는 실제 명단이나 사내 IP가 없습니다. `.gitignore`는 암호화나 접근 제어가 아닙니다. 폴더 전체 ZIP 업로드에는 제외 규칙이 적용되지 않습니다.

## 시작

1. `.credentials/`를 만들고 `examples/teams.json`을 `.credentials/teams.json`으로 복사하여 실제 명단을 입력합니다.
2. `.credentials/imports/`에 PDF를 준비합니다.
3. `docker compose up -d --build`로 실행합니다. 기본 주소는 http://127.0.0.1:8787 입니다.
4. 사내 배포가 필요한 경우 비공개 Compose override를 작성하고 `.env.example`을 `.env`로 복사합니다. `.env`는 비공개 override 경로만 선택하며 실제 값은 `.credentials/`에 둡니다.

## 수집과 표시

PDF는 서버 시작·수동 갱신·매일 한국 시간 자정에 읽습니다. 근태일자가 휴가일입니다. 미명시 0.5일은 오전반차로 임시 표시하고 미명시 사실을 병기하며 원본은 유지합니다.
eCount 저장본은 `.credentials/data/ecount-snapshot.json`에서 읽습니다. 브라우저 로그인과 오전 8시 확인 예약은 로컬 자동화에 속하며 저장소를 복제한다고 설치되지 않습니다.
서비스에는 사용자 인증이 없습니다. 사내 배포 시 네트워크 접근 범위를 별도로 관리해야 합니다.

## 검증

`docker compose build` 후 `docker run --rm --network none ai-team-dashboard-dashboard python -m pytest -q tests`를 실행합니다. 테스트는 가상 인물과 합성 입력만 사용합니다.


