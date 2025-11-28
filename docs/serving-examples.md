# 서빙된 모델 사용 예제

이 문서는 LLM Ops 플랫폼에서 서빙된 모델을 사용하는 다양한 예제를 제공합니다.

## 목차
1. [서빙 엔드포인트 배포](#1-서빙-엔드포인트-배포)
2. [엔드포인트 조회 및 상태 확인](#2-엔드포인트-조회-및-상태-확인)
3. [서빙된 모델 추론 호출](#3-서빙된-모델-추론-호출)
4. [Health Check](#4-health-check)
5. [프롬프트 A/B 테스트](#5-프롬프트-ab-테스트)
6. [롤백](#6-롤백)

---

## 1. 서빙 엔드포인트 배포

서빙 엔드포인트를 배포하는 방법입니다.

### 1.1 API를 통한 배포

```bash
curl -X POST https://dev.llm-ops.local/llm-ops/v1/serving/endpoints \
  -H "Content-Type: application/json" \
  -H "X-User-Id: admin" \
  -H "X-User-Roles: admin" \
  -d '{
    "modelId": "<approved-model-id>",
    "environment": "dev",
    "route": "/llm-ops/v1/serve/chat-model",
    "minReplicas": 1,
    "maxReplicas": 3,
    "autoscalePolicy": {"cpuUtilization": 70}
  }'
```

**응답 예시:**
```json
{
  "status": "success",
  "message": "Serving endpoint deployed successfully",
  "data": {
    "id": "550e8400-e29b-41d4-a716-446655440000",
    "modelId": "123e4567-e89b-12d3-a456-426614174000",
    "environment": "dev",
    "route": "/llm-ops/v1/serve/chat-model",
    "status": "healthy",
    "minReplicas": 1,
    "maxReplicas": 3,
    "createdAt": "2025-01-15T10:30:00Z"
  }
}
```

### 1.2 Python 클라이언트 예제

```python
import requests

BASE_URL = "https://dev.llm-ops.local/llm-ops/v1"
HEADERS = {
    "Content-Type": "application/json",
    "X-User-Id": "admin",
    "X-User-Roles": "admin"
}

# 서빙 엔드포인트 배포
deploy_request = {
    "modelId": "123e4567-e89b-12d3-a456-426614174000",
    "environment": "dev",
    "route": "/llm-ops/v1/serve/chat-model",
    "minReplicas": 1,
    "maxReplicas": 3,
    "autoscalePolicy": {"cpuUtilization": 70}
}

response = requests.post(
    f"{BASE_URL}/serving/endpoints",
    json=deploy_request,
    headers=HEADERS
)

result = response.json()
if result["status"] == "success":
    endpoint_id = result["data"]["id"]
    route = result["data"]["route"]
    print(f"Endpoint deployed: {endpoint_id} at {route}")
else:
    print(f"Deployment failed: {result['message']}")
```

### 1.3 JavaScript/TypeScript 클라이언트 예제

```typescript
import axios from 'axios';

const API_BASE = 'https://dev.llm-ops.local/llm-ops/v1';
const headers = {
  'Content-Type': 'application/json',
  'X-User-Id': 'admin',
  'X-User-Roles': 'admin'
};

// 서빙 엔드포인트 배포
async function deployEndpoint(modelId: string, route: string) {
  try {
    const response = await axios.post(
      `${API_BASE}/serving/endpoints`,
      {
        modelId,
        environment: 'dev',
        route,
        minReplicas: 1,
        maxReplicas: 3,
        autoscalePolicy: { cpuUtilization: 70 }
      },
      { headers }
    );
    
    if (response.data.status === 'success') {
      console.log('Endpoint deployed:', response.data.data);
      return response.data.data;
    } else {
      throw new Error(response.data.message);
    }
  } catch (error) {
    console.error('Deployment failed:', error);
    throw error;
  }
}

// 사용 예제
deployEndpoint('123e4567-e89b-12d3-a456-426614174000', '/llm-ops/v1/serve/chat-model');
```

---

## 2. 엔드포인트 조회 및 상태 확인

### 2.1 모든 엔드포인트 조회

```bash
curl https://dev.llm-ops.local/llm-ops/v1/serving/endpoints \
  -H "X-User-Id: admin" \
  -H "X-User-Roles: admin"
```

### 2.2 환경별 필터링

```bash
# dev 환경의 엔드포인트만 조회
curl "https://dev.llm-ops.local/llm-ops/v1/serving/endpoints?environment=dev" \
  -H "X-User-Id: admin" \
  -H "X-User-Roles: admin"
```

### 2.3 모델 및 상태별 필터링

```bash
# 특정 모델의 healthy 상태 엔드포인트 조회
curl "https://dev.llm-ops.local/llm-ops/v1/serving/endpoints?modelId=<model-id>&status=healthy" \
  -H "X-User-Id: admin" \
  -H "X-User-Roles: admin"
```

### 2.4 특정 엔드포인트 상세 정보 조회

```bash
curl https://dev.llm-ops.local/llm-ops/v1/serving/endpoints/<endpoint-id> \
  -H "X-User-Id: admin" \
  -H "X-User-Roles: admin"
```

**응답 예시:**
```json
{
  "status": "success",
  "message": "",
  "data": {
    "id": "550e8400-e29b-41d4-a716-446655440000",
    "modelId": "123e4567-e89b-12d3-a456-426614174000",
    "environment": "dev",
    "route": "/llm-ops/v1/serve/chat-model",
    "status": "healthy",
    "minReplicas": 1,
    "maxReplicas": 3,
    "createdAt": "2025-01-15T10:30:00Z"
  }
}
```

---

## 3. 서빙된 모델 추론 호출

배포된 모델에 추론 요청을 보내는 예제입니다.

### 3.1 Chat Completion 호출 (예상 API)

> **참고**: 실제 추론 API (`/inference/{model_name}` 또는 `/llm-ops/v1/serve/{model-name}/chat`)는 PRD에 명시되어 있으나 현재 구현되어 있지 않습니다. 아래는 예상되는 사용 방법입니다.

#### cURL 예제

```bash
# Chat completion 요청
curl -X POST https://dev.llm-ops.local/llm-ops/v1/serve/chat-model/chat \
  -H "Content-Type: application/json" \
  -H "X-User-Id: user123" \
  -H "X-User-Roles: researcher" \
  -d '{
    "messages": [
      {"role": "system", "content": "You are a helpful assistant."},
      {"role": "user", "content": "안녕하세요! LLM Ops 플랫폼에 대해 설명해주세요."}
    ],
    "temperature": 0.7,
    "max_tokens": 500
  }'
```

#### Python 예제

```python
import requests

BASE_URL = "https://dev.llm-ops.local/llm-ops/v1"
HEADERS = {
    "Content-Type": "application/json",
    "X-User-Id": "user123",
    "X-User-Roles": "researcher"
}

# Chat completion 요청
def call_chat_model(model_route: str, messages: list, temperature: float = 0.7, max_tokens: int = 500):
    response = requests.post(
        f"{BASE_URL}/serve/{model_route}/chat",
        json={
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens
        },
        headers=HEADERS
    )
    
    if response.status_code == 200:
        result = response.json()
        if result.get("status") == "success":
            return result["data"]["choices"][0]["message"]["content"]
        else:
            raise Exception(f"API error: {result.get('message')}")
    else:
        response.raise_for_status()

# 사용 예제
messages = [
    {"role": "system", "content": "You are a helpful assistant."},
    {"role": "user", "content": "안녕하세요! LLM Ops 플랫폼에 대해 설명해주세요."}
]

response_text = call_chat_model("chat-model", messages)
print(response_text)
```

#### JavaScript/TypeScript 예제

```typescript
import axios from 'axios';

const API_BASE = 'https://dev.llm-ops.local/llm-ops/v1';

interface ChatMessage {
  role: 'system' | 'user' | 'assistant';
  content: string;
}

interface ChatRequest {
  messages: ChatMessage[];
  temperature?: number;
  max_tokens?: number;
}

async function callChatModel(
  modelRoute: string,
  request: ChatRequest
): Promise<string> {
  try {
    const response = await axios.post(
      `${API_BASE}/serve/${modelRoute}/chat`,
      request,
      {
        headers: {
          'Content-Type': 'application/json',
          'X-User-Id': 'user123',
          'X-User-Roles': 'researcher'
        }
      }
    );
    
    if (response.data.status === 'success') {
      return response.data.data.choices[0].message.content;
    } else {
      throw new Error(response.data.message);
    }
  } catch (error) {
    console.error('Chat request failed:', error);
    throw error;
  }
}

// 사용 예제
const messages: ChatMessage[] = [
  { role: 'system', content: 'You are a helpful assistant.' },
  { role: 'user', content: '안녕하세요! LLM Ops 플랫폼에 대해 설명해주세요.' }
];

callChatModel('chat-model', {
  messages,
  temperature: 0.7,
  max_tokens: 500
}).then(response => {
  console.log('Response:', response);
}).catch(error => {
  console.error('Error:', error);
});
```

### 3.2 Text Completion 호출 (예상 API)

```bash
# Text completion 요청
curl -X POST https://dev.llm-ops.local/llm-ops/v1/serve/text-model/completion \
  -H "Content-Type: application/json" \
  -H "X-User-Id: user123" \
  -H "X-User-Roles: researcher" \
  -d '{
    "prompt": "LLM Ops 플랫폼은",
    "temperature": 0.7,
    "max_tokens": 200,
    "stop": ["\n\n"]
  }'
```

### 3.3 Embedding 호출 (예상 API)

```bash
# Embedding 요청
curl -X POST https://dev.llm-ops.local/llm-ops/v1/serve/embedding-model/embeddings \
  -H "Content-Type: application/json" \
  -H "X-User-Id: user123" \
  -H "X-User-Roles: researcher" \
  -d '{
    "input": "This is a text to embed",
    "model": "embedding-model-v1"
  }'
```

---

## 4. Health Check

엔드포인트의 헬스 체크를 확인하는 예제입니다.

```bash
# Health check
curl https://dev.llm-ops.local/llm-ops/v1/serve/chat-model/health
```

**응답 예시:**
```json
{
  "status": "healthy",
  "timestamp": "2025-01-15T10:30:00Z",
  "model": {
    "name": "chat-model",
    "version": "v1.0.0"
  }
}
```

**Python 예제:**
```python
import requests

def check_endpoint_health(model_route: str):
    response = requests.get(f"https://dev.llm-ops.local/llm-ops/v1/serve/{model_route}/health")
    return response.json()

# 사용 예제
health = check_endpoint_health("chat-model")
print(f"Status: {health['status']}")
```

---

## 5. 프롬프트 A/B 테스트

프롬프트 A/B 테스트를 설정하고 사용하는 예제입니다.

### 5.1 프롬프트 A/B 실험 생성

```bash
curl -X POST https://dev.llm-ops.local/llm-ops/v1/prompts/experiments \
  -H "Content-Type: application/json" \
  -H "X-User-Id: admin" \
  -H "X-User-Roles: admin" \
  -d '{
    "templateAId": "<template-a-id>",
    "templateBId": "<template-b-id>",
    "allocation": 50,
    "metric": "latency_ms"
  }'
```

### 5.2 실험 상태 확인

```bash
curl https://dev.llm-ops.local/llm-ops/v1/prompts/experiments/{experiment-id} \
  -H "X-User-Id: admin" \
  -H "X-User-Roles: admin"
```

### 5.3 실험 종료 및 승자 선정

```bash
curl -X POST https://dev.llm-ops.local/llm-ops/v1/prompts/experiments/{experiment-id}/conclude \
  -H "Content-Type: application/json" \
  -H "X-User-Id: admin" \
  -H "X-User-Roles: admin" \
  -d '{
    "winnerTemplateId": "<template-id>",
    "notes": "Template A가 더 낮은 지연시간을 보여주어 선택되었습니다."
  }'
```

---

## 6. 롤백

서빙 엔드포인트를 이전 버전으로 롤백하는 예제입니다.

### 6.1 API를 통한 롤백

```bash
curl -X POST https://dev.llm-ops.local/llm-ops/v1/serving/endpoints/<endpoint-id>/rollback \
  -H "X-User-Id: admin" \
  -H "X-User-Roles: admin"
```

**응답 예시:**
```json
{
  "status": "success",
  "message": "Endpoint rolled back successfully",
  "data": {
    "id": "550e8400-e29b-41d4-a716-446655440000",
    "modelId": "123e4567-e89b-12d3-a456-426614174000",
    "environment": "dev",
    "route": "/llm-ops/v1/serve/chat-model",
    "status": "rollback",
    "minReplicas": 1,
    "maxReplicas": 3,
    "createdAt": "2025-01-15T10:30:00Z"
  }
}
```

### 6.2 스크립트를 통한 롤백

```bash
# 롤백 스크립트 사용
./infra/scripts/serving_rollback.sh <endpoint-id> [namespace]
```

### 6.3 Python 클라이언트 예제

```python
import requests

def rollback_endpoint(endpoint_id: str):
    response = requests.post(
        f"https://dev.llm-ops.local/llm-ops/v1/serving/endpoints/{endpoint_id}/rollback",
        headers={
            "X-User-Id": "admin",
            "X-User-Roles": "admin"
        }
    )
    
    result = response.json()
    if result["status"] == "success":
        print(f"Endpoint {endpoint_id} rolled back successfully")
        return result["data"]
    else:
        raise Exception(f"Rollback failed: {result['message']}")

# 사용 예제
try:
    endpoint = rollback_endpoint("550e8400-e29b-41d4-a716-446655440000")
    print(f"Rollback status: {endpoint['status']}")
except Exception as e:
    print(f"Error: {e}")
```

---

## 7. Kubernetes 검증

서빙 엔드포인트가 Kubernetes에 제대로 배포되었는지 확인하는 예제입니다.

```bash
# Deployment 확인
kubectl get deployment serving-<endpoint-id> -n default

# HPA (Horizontal Pod Autoscaler) 확인
kubectl get hpa serving-<endpoint-id>-hpa -n default

# Ingress 확인
kubectl get ingress serving-<endpoint-id>-ingress -n default

# Pod 상태 확인
kubectl get pods -l app=serving-<endpoint-id> -n default

# Pod 로그 확인
kubectl logs -l app=serving-<endpoint-id> -n default --tail=100
```

---

## 8. 전체 워크플로우 예제

서빙 엔드포인트를 배포하고 사용하는 전체 워크플로우 예제입니다.

```python
import requests
import time

BASE_URL = "https://dev.llm-ops.local/llm-ops/v1"
HEADERS = {
    "Content-Type": "application/json",
    "X-User-Id": "admin",
    "X-User-Roles": "admin"
}

# 1. 서빙 엔드포인트 배포
print("1. Deploying endpoint...")
deploy_response = requests.post(
    f"{BASE_URL}/serving/endpoints",
    json={
        "modelId": "123e4567-e89b-12d3-a456-426614174000",
        "environment": "dev",
        "route": "/llm-ops/v1/serve/chat-model",
        "minReplicas": 1,
        "maxReplicas": 3
    },
    headers=HEADERS
)
deploy_result = deploy_response.json()
if deploy_result["status"] != "success":
    print(f"Deployment failed: {deploy_result['message']}")
    exit(1)

endpoint_id = deploy_result["data"]["id"]
route = deploy_result["data"]["route"]
print(f"Endpoint deployed: {endpoint_id} at {route}")

# 2. 엔드포인트가 healthy 상태가 될 때까지 대기
print("2. Waiting for endpoint to be healthy...")
max_retries = 30
for i in range(max_retries):
    status_response = requests.get(
        f"{BASE_URL}/serving/endpoints/{endpoint_id}",
        headers=HEADERS
    )
    status_result = status_response.json()
    if status_result["status"] == "success" and status_result["data"]["status"] == "healthy":
        print("Endpoint is healthy!")
        break
    time.sleep(2)
else:
    print("Timeout waiting for endpoint to be healthy")
    exit(1)

# 3. Health check
print("3. Checking endpoint health...")
health_response = requests.get(f"{BASE_URL}/serve/chat-model/health")
health_result = health_response.json()
print(f"Health status: {health_result['status']}")

# 4. 모델 추론 호출 (예상 API)
print("4. Calling model for inference...")
# 실제 추론 API가 구현되면 아래 코드를 사용할 수 있습니다:
"""
inference_response = requests.post(
    f"{BASE_URL}/serve/chat-model/chat",
    json={
        "messages": [
            {"role": "system", "content": "You are a helpful assistant."},
            {"role": "user", "content": "Hello!"}
        ],
        "temperature": 0.7,
        "max_tokens": 100
    },
    headers={
        "Content-Type": "application/json",
        "X-User-Id": "user123",
        "X-User-Roles": "researcher"
    }
)
print(f"Inference response: {inference_response.json()}")
"""

print("Workflow completed successfully!")
```

---

## 참고 사항

1. **인증**: 모든 API 요청에는 `X-User-Id`와 `X-User-Roles` 헤더가 필요합니다.
2. **환경**: `dev`, `stg`, `prod` 환경에 따라 BASE_URL이 달라집니다.
3. **에러 처리**: 모든 API 응답은 `{status, message, data}` 형식의 envelope을 사용합니다.
4. **추론 API**: 실제 추론 API (`/inference/{model_name}` 또는 `/serve/{model-name}/chat`)는 현재 구현되어 있지 않으며, PRD에 명시되어 있습니다.
5. **모델 상태**: 추론 요청을 보내기 전에 모델이 `approved` 상태인지 확인해야 합니다.

---

## 다음 단계

- 실제 추론 API 구현 후 이 문서가 업데이트될 예정입니다.
- 더 많은 예제와 사용 사례는 [Quickstart 가이드](../specs/001-document-llm-ops/quickstart.md)를 참조하세요.
