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

## 테스트

```bash
npm test
```

