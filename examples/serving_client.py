"""
서빙된 모델을 사용하는 Python 클라이언트 예제

이 스크립트는 LLM Ops 플랫폼의 서빙 API를 사용하는 다양한 예제를 제공합니다.
"""
import requests
import json
import time
from typing import Optional, Dict, List, Any


class ServingClient:
    """서빙 API를 사용하기 위한 클라이언트 클래스"""
    
    def __init__(self, base_url: str, user_id: str = "admin", user_roles: str = "admin"):
        """
        Args:
            base_url: API 기본 URL (예: "https://dev.llm-ops.local/llm-ops/v1")
            user_id: 사용자 ID
            user_roles: 사용자 역할 (쉼표로 구분)
        """
        self.base_url = base_url.rstrip('/')
        self.headers = {
            "Content-Type": "application/json",
            "X-User-Id": user_id,
            "X-User-Roles": user_roles
        }
    
    def deploy_endpoint(
        self,
        model_id: str,
        environment: str,
        route: str,
        min_replicas: int = 1,
        max_replicas: int = 3,
        autoscale_policy: Optional[Dict] = None,
        prompt_policy_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        서빙 엔드포인트를 배포합니다.
        
        Args:
            model_id: 모델 카탈로그 엔트리 ID
            environment: 배포 환경 (dev/stg/prod)
            route: 인그레스 라우트 경로 (예: "/llm-ops/v1/serve/model-name")
            min_replicas: 최소 레플리카 수
            max_replicas: 최대 레플리카 수
            autoscale_policy: 오토스케일 정책
            prompt_policy_id: 프롬프트 정책 ID (선택)
        
        Returns:
            배포된 엔드포인트 정보
        """
        payload = {
            "modelId": model_id,
            "environment": environment,
            "route": route,
            "minReplicas": min_replicas,
            "maxReplicas": max_replicas
        }
        
        if autoscale_policy:
            payload["autoscalePolicy"] = autoscale_policy
        if prompt_policy_id:
            payload["promptPolicyId"] = prompt_policy_id
        
        response = requests.post(
            f"{self.base_url}/serving/endpoints",
            json=payload,
            headers=self.headers
        )
        response.raise_for_status()
        result = response.json()
        
        if result["status"] != "success":
            raise Exception(f"Deployment failed: {result['message']}")
        
        return result["data"]
    
    def list_endpoints(
        self,
        environment: Optional[str] = None,
        model_id: Optional[str] = None,
        status: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """
        서빙 엔드포인트 목록을 조회합니다.
        
        Args:
            environment: 환경 필터 (dev/stg/prod)
            model_id: 모델 ID 필터
            status: 상태 필터 (deploying/healthy/degraded/failed)
        
        Returns:
            엔드포인트 목록
        """
        params = {}
        if environment:
            params["environment"] = environment
        if model_id:
            params["modelId"] = model_id
        if status:
            params["status"] = status
        
        response = requests.get(
            f"{self.base_url}/serving/endpoints",
            params=params,
            headers=self.headers
        )
        response.raise_for_status()
        result = response.json()
        
        if result["status"] != "success":
            raise Exception(f"Failed to list endpoints: {result['message']}")
        
        return result.get("data", [])
    
    def get_endpoint(self, endpoint_id: str) -> Dict[str, Any]:
        """
        특정 엔드포인트의 상세 정보를 조회합니다.
        
        Args:
            endpoint_id: 엔드포인트 ID
        
        Returns:
            엔드포인트 정보
        """
        response = requests.get(
            f"{self.base_url}/serving/endpoints/{endpoint_id}",
            headers=self.headers
        )
        response.raise_for_status()
        result = response.json()
        
        if result["status"] != "success":
            raise Exception(f"Failed to get endpoint: {result['message']}")
        
        return result["data"]
    
    def wait_for_healthy(
        self,
        endpoint_id: str,
        max_wait_seconds: int = 120,
        check_interval_seconds: int = 2
    ) -> bool:
        """
        엔드포인트가 healthy 상태가 될 때까지 대기합니다.
        
        Args:
            endpoint_id: 엔드포인트 ID
            max_wait_seconds: 최대 대기 시간 (초)
            check_interval_seconds: 체크 간격 (초)
        
        Returns:
            healthy 상태에 도달하면 True, 타임아웃이면 False
        """
        max_retries = max_wait_seconds // check_interval_seconds
        
        for i in range(max_retries):
            try:
                endpoint = self.get_endpoint(endpoint_id)
                if endpoint["status"] == "healthy":
                    return True
                print(f"Waiting for endpoint to be healthy... (status: {endpoint['status']})")
            except Exception as e:
                print(f"Error checking endpoint status: {e}")
            
            time.sleep(check_interval_seconds)
        
        return False
    
    def check_health(self, model_route: str) -> Dict[str, Any]:
        """
        엔드포인트의 헬스 체크를 수행합니다.
        
        Args:
            model_route: 모델 라우트 (예: "chat-model")
        
        Returns:
            헬스 체크 결과
        """
        response = requests.get(
            f"{self.base_url}/serve/{model_route}/health",
            headers=self.headers
        )
        response.raise_for_status()
        return response.json()
    
    def rollback_endpoint(self, endpoint_id: str) -> Dict[str, Any]:
        """
        서빙 엔드포인트를 이전 버전으로 롤백합니다.
        
        Args:
            endpoint_id: 엔드포인트 ID
        
        Returns:
            롤백된 엔드포인트 정보
        """
        response = requests.post(
            f"{self.base_url}/serving/endpoints/{endpoint_id}/rollback",
            headers=self.headers
        )
        response.raise_for_status()
        result = response.json()
        
        if result["status"] != "success":
            raise Exception(f"Rollback failed: {result['message']}")
        
        return result["data"]
    
    def call_chat_model(
        self,
        model_route: str,
        messages: List[Dict[str, str]],
        temperature: float = 0.7,
        max_tokens: int = 500,
        user_id: Optional[str] = None
    ) -> str:
        """
        Chat 모델에 추론 요청을 보냅니다.
        
        참고: 이 API는 현재 구현되어 있지 않으며, 실제 구현 후 사용할 수 있습니다.
        
        Args:
            model_route: 모델 라우트 (예: "chat-model")
            messages: 메시지 목록
            temperature: 생성 온도
            max_tokens: 최대 토큰 수
            user_id: 사용자 ID (선택)
        
        Returns:
            모델의 응답 텍스트
        """
        # 실제 추론 API가 구현되면 아래 주석을 해제하고 사용하세요
        """
        headers = self.headers.copy()
        if user_id:
            headers["X-User-Id"] = user_id
        
        response = requests.post(
            f"{self.base_url}/serve/{model_route}/chat",
            json={
                "messages": messages,
                "temperature": temperature,
                "max_tokens": max_tokens
            },
            headers=headers
        )
        response.raise_for_status()
        result = response.json()
        
        if result["status"] != "success":
            raise Exception(f"Inference failed: {result['message']}")
        
        return result["data"]["choices"][0]["message"]["content"]
        """
        raise NotImplementedError(
            "Chat inference API is not yet implemented. "
            "This method will be available after the inference endpoint is implemented."
        )


def example_deploy_and_check():
    """엔드포인트 배포 및 상태 확인 예제"""
    client = ServingClient("https://dev.llm-ops.local/llm-ops/v1")
    
    # 1. 엔드포인트 배포
    print("Deploying endpoint...")
    endpoint = client.deploy_endpoint(
        model_id="123e4567-e89b-12d3-a456-426614174000",
        environment="dev",
        route="/llm-ops/v1/serve/chat-model",
        min_replicas=1,
        max_replicas=3
    )
    print(f"Endpoint deployed: {endpoint['id']}")
    print(f"Route: {endpoint['route']}")
    
    # 2. Healthy 상태 대기
    print("\nWaiting for endpoint to be healthy...")
    if client.wait_for_healthy(endpoint["id"]):
        print("Endpoint is now healthy!")
    else:
        print("Timeout waiting for endpoint to be healthy")
        return
    
    # 3. 엔드포인트 정보 조회
    print("\nGetting endpoint details...")
    endpoint_details = client.get_endpoint(endpoint["id"])
    print(json.dumps(endpoint_details, indent=2, default=str))
    
    # 4. Health check
    print("\nPerforming health check...")
    health = client.check_health("chat-model")
    print(json.dumps(health, indent=2, default=str))


def example_list_endpoints():
    """엔드포인트 목록 조회 예제"""
    client = ServingClient("https://dev.llm-ops.local/llm-ops/v1")
    
    # 모든 엔드포인트 조회
    print("Listing all endpoints...")
    all_endpoints = client.list_endpoints()
    print(f"Found {len(all_endpoints)} endpoints")
    for ep in all_endpoints:
        print(f"  - {ep['id']}: {ep['route']} ({ep['status']})")
    
    # dev 환경의 healthy 엔드포인트만 조회
    print("\nListing healthy endpoints in dev environment...")
    dev_endpoints = client.list_endpoints(environment="dev", status="healthy")
    print(f"Found {len(dev_endpoints)} healthy endpoints in dev")
    for ep in dev_endpoints:
        print(f"  - {ep['id']}: {ep['route']}")


def example_rollback():
    """롤백 예제"""
    client = ServingClient("https://dev.llm-ops.local/llm-ops/v1")
    
    endpoint_id = "550e8400-e29b-41d4-a716-446655440000"
    
    print(f"Rolling back endpoint {endpoint_id}...")
    try:
        rolled_back = client.rollback_endpoint(endpoint_id)
        print(f"Rollback successful! New status: {rolled_back['status']}")
    except Exception as e:
        print(f"Rollback failed: {e}")


def example_full_workflow():
    """전체 워크플로우 예제"""
    client = ServingClient("https://dev.llm-ops.local/llm-ops/v1")
    
    model_id = "123e4567-e89b-12d3-a456-426614174000"
    route = "/llm-ops/v1/serve/my-chat-model"
    
    try:
        # 1. 배포
        print("Step 1: Deploying endpoint...")
        endpoint = client.deploy_endpoint(
            model_id=model_id,
            environment="dev",
            route=route,
            min_replicas=1,
            max_replicas=3
        )
        endpoint_id = endpoint["id"]
        print(f"  ✓ Endpoint deployed: {endpoint_id}")
        
        # 2. Healthy 상태 대기
        print("\nStep 2: Waiting for endpoint to be healthy...")
        if not client.wait_for_healthy(endpoint_id, max_wait_seconds=120):
            print("  ✗ Timeout waiting for healthy status")
            return
        print("  ✓ Endpoint is healthy")
        
        # 3. Health check
        print("\nStep 3: Performing health check...")
        health = client.check_health("my-chat-model")
        print(f"  ✓ Health status: {health.get('status', 'unknown')}")
        
        # 4. 추론 호출 (구현 후 사용 가능)
        print("\nStep 4: Calling model for inference...")
        print("  ℹ Inference API is not yet implemented")
        # messages = [
        #     {"role": "system", "content": "You are a helpful assistant."},
        #     {"role": "user", "content": "Hello!"}
        # ]
        # response = client.call_chat_model("my-chat-model", messages)
        # print(f"  ✓ Model response: {response}")
        
        print("\n✓ Full workflow completed successfully!")
        
    except Exception as e:
        print(f"\n✗ Workflow failed: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    import sys
    
    if len(sys.argv) > 1:
        example_name = sys.argv[1]
        if example_name == "deploy":
            example_deploy_and_check()
        elif example_name == "list":
            example_list_endpoints()
        elif example_name == "rollback":
            example_rollback()
        elif example_name == "workflow":
            example_full_workflow()
        else:
            print(f"Unknown example: {example_name}")
            print("Available examples: deploy, list, rollback, workflow")
    else:
        print("Usage: python serving_client.py <example_name>")
        print("Available examples:")
        print("  deploy   - Deploy endpoint and check status")
        print("  list     - List endpoints")
        print("  rollback - Rollback an endpoint")
        print("  workflow - Run full workflow example")
        print("\nExample: python serving_client.py workflow")
