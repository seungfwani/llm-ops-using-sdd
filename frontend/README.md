# LLM Ops Platform Frontend

Vue 3 + TypeScript + Vite 기반 프론트엔드 애플리케이션입니다.

## 개발 환경 설정

### 1. 의존성 설치

```bash
cd frontend
npm install
```

### 2. 환경 변수 설정 (선택사항)

`.env` 파일을 생성하거나 `.env.example`을 참고하세요:

```bash
# 개발 환경에서는 프록시를 사용하므로 기본값으로 충분합니다
VITE_API_BASE_URL=/llm-ops/v1
```

### 3. 개발 서버 실행

```bash
npm run dev
```

프론트엔드는 `http://localhost:3000`에서 실행됩니다.

## Backend 연결

### 프록시 설정

`vite.config.ts`에 프록시가 설정되어 있어, 개발 환경에서는 자동으로 backend(`http://localhost:8000`)로 요청이 전달됩니다.

### 인증 헤더

모든 API 요청에는 다음 헤더가 자동으로 추가됩니다:
- `X-User-Id`: 사용자 ID (기본값: "test-user")
- `X-User-Roles`: 사용자 역할 (기본값: "llm-ops-user")

이 값들은 `localStorage`에서 가져오며, 필요시 수정할 수 있습니다.

### API 클라이언트

모든 API 클라이언트는 `src/services/apiClient.ts`를 통해 공통 axios 인스턴스를 사용합니다:
- `catalogClient`: 모델 카탈로그 API
- `trainingClient`: 트레이닝 작업 API
- `servingClient`: 서빙 엔드포인트 API
- `governanceClient`: 거버넌스 및 감사 로그 API

## 실행 순서

1. **Backend 서버 실행** (다른 터미널):
   ```bash
   cd backend
   source .venv/bin/activate
   python -m src.api.app
   ```

2. **Frontend 서버 실행**:
   ```bash
   cd frontend
   npm run dev
   ```

3. 브라우저에서 `http://localhost:3000` 접속

## 빌드

```bash
npm run build
```

빌드된 파일은 `dist/` 디렉토리에 생성됩니다.

## UI 일관성 가이드 (Phase 9)

다음 규칙은 **리스트 / 상세 / 생성(Submit/Deploy) 페이지** 전반의 버튼, 헤더, 라벨을 통일하기 위한 기준입니다.

- **페이지 헤더 (공통)**
  - 최상단에는 항상 `<h1>` 제목을 사용합니다. (예: `Model Catalog`, `Dataset Catalog`, `Training Jobs`, `Serving Endpoints`, `Workflow Pipelines`, `Governance Policies`)
  - 리스트 페이지의 헤더 오른쪽에는 `Refresh` Secondary 버튼과 `New XXX` Primary 버튼을 이 순서로 배치합니다.

- **상세 페이지 헤더**
  - 제목은 단수 명사로 (`Model Detail`, `Dataset Detail`, `Job Detail`, `Endpoint Detail`, `Pipeline Detail`, `Policy List` 등) 통일합니다.
  - 헤더 오른쪽에는 주요 액션(예: `Edit`, `Deploy`, `Chat`, `Compare`, `Restore`)을 Primary/Secondary 버튼으로 배치하고, 필요 시 `← Back to List` 링크를 가장 오른쪽에 둡니다.

- **버튼 스타일**
  - **Primary (`.btn-primary`)**: 생성/주요 액션에 사용 (`New Model`, `New Dataset`, `New Job`, `New Endpoint`, `New Pipeline`, `New Policy`, `Deploy`, `Submit` 등).
  - **Secondary (`.btn-secondary`)**: 보조 액션/갱신/버전 작업에 사용 (`Refresh`, `Compare Versions`, `Restore`, `Download`, `Test` 등).
  - **링크 버튼 (`.btn-link`)**: 행 단위 액션 링크 (`View`, `Chat`, `Details` 등)에 사용합니다.
  - 삭제/취소 계열은 붉은 계열 버튼(`.btn-delete`, `.btn-cancel-small` 등)을 사용하고, 문구는 단순하게 `Delete`, `Cancel` 로 유지합니다.

- **Back 링크**
  - 상세/제출 페이지 상단에는 필요 시 “목록으로 돌아가기” 링크를 `← Back to List` 형태로 배치합니다.
  - Router 경로는 상단 탭/사이드바와 자연스럽게 매핑되도록 유지합니다.

- **라벨/케이싱**
  - 버튼 텍스트는 Title Case 또는 간단한 명령형 (`New Job`, `New Dataset`, `Refresh`, `Deploy`, `Submit`) 으로 통일합니다.
  - 상태/타입 배지는 소문자 값을 그대로 보여주되, CSS 클래스(`status-xxx`, `type-xxx`)를 이용해 색상만 구분합니다.

- **필터/테이블**
  - 필터 영역은 헤더 아래에 `filters` 컨테이너로 배치하고, label+input 조합을 세로 정렬합니다.
  - 테이블의 헤더는 기능 이름과 일관된 용어를 사용하고, `Actions` 컬럼은 항상 마지막에 둡니다.

새로운 페이지를 추가할 때는 위 규칙을 참고해 헤더/버튼/필터/테이블 구조를 맞춰 주세요.

## 테스트

```bash
npm test
```

