#!/usr/bin/env python3
"""
Base 모델 등록 및 서빙 예제

이 스크립트는 LLM Ops 플랫폼에 base 모델을 등록하고 서빙하는 전체 워크플로우를 보여줍니다.
"""

import requests
import json
import time
import sys
from typing import Optional, Dict, Any


class CatalogClient:
    """모델 카탈로그 API를 사용하기 위한 클라이언트 클래스"""
    
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
    
    def create_model(
        self,
        name: str,
        version: str,
        model_type: str,
        owner_team: str,
        metadata: Dict[str, Any],
        lineage_dataset_ids: Optional[list] = None,
        status: str = "draft",
        evaluation_summary: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        모델을 카탈로그에 등록합니다.
        
        Args:
            name: 모델 이름
            version: 모델 버전
            model_type: 모델 타입 (base, fine-tuned, external)
            owner_team: 소유 팀
            metadata: 모델 메타데이터 (dict)
            lineage_dataset_ids: 데이터셋 ID 목록 (선택)
            status: 모델 상태 (draft, under_review, approved, deprecated)
            evaluation_summary: 평가 요약 (선택)
        
        Returns:
            생성된 모델 정보
        """
        payload = {
            "name": name,
            "version": version,
            "type": model_type,
            "owner_team": owner_team,
            "metadata": metadata,
            "status": status
        }
        
        if lineage_dataset_ids:
            payload["lineage_dataset_ids"] = lineage_dataset_ids
        if evaluation_summary:
            payload["evaluation_summary"] = evaluation_summary
        
        response = requests.post(
            f"{self.base_url}/catalog/models",
            json=payload,
            headers=self.headers
        )
        response.raise_for_status()
        result = response.json()
        
        if result["status"] != "success":
            raise Exception(f"Model creation failed: {result['message']}")
        
        return result["data"]
    
    def get_model(self, model_id: str) -> Dict[str, Any]:
        """
        모델 정보를 조회합니다.
        
        Args:
            model_id: 모델 ID
        
        Returns:
            모델 정보
        """
        response = requests.get(
            f"{self.base_url}/catalog/models/{model_id}",
            headers=self.headers
        )
        response.raise_for_status()
        result = response.json()
        
        if result["status"] != "success":
            raise Exception(f"Failed to get model: {result['message']}")
        
        return result["data"]
    
    def update_model_status(self, model_id: str, status: str) -> Dict[str, Any]:
        """
        모델 상태를 업데이트합니다.
        
        Args:
            model_id: 모델 ID
            status: 새로운 상태 (draft, under_review, approved, deprecated)
        
        Returns:
            업데이트된 모델 정보
        """
        response = requests.patch(
            f"{self.base_url}/catalog/models/{model_id}/status",
            params={"status": status},
            headers=self.headers
        )
        response.raise_for_status()
        result = response.json()
        
        if result["status"] != "success":
            raise Exception(f"Status update failed: {result['message']}")
        
        return result["data"]
    
    def list_models(self) -> list[Dict[str, Any]]:
        """
        모든 모델 목록을 조회합니다.
        
        Returns:
            모델 목록
        """
        response = requests.get(
            f"{self.base_url}/catalog/models",
            headers=self.headers
        )
        response.raise_for_status()
        result = response.json()
        
        if result["status"] != "success":
            raise Exception(f"Failed to list models: {result['message']}")
        
        return result.get("data", [])


class ServingClient:
    """서빙 API를 사용하기 위한 클라이언트 클래스"""
    
    def __init__(self, base_url: str, user_id: str = "admin", user_roles: str = "admin"):
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
        autoscale_policy: Optional[Dict] = None
    ) -> Dict[str, Any]:
        """
        서빙 엔드포인트를 배포합니다.
        
        Args:
            model_id: 모델 카탈로그 엔트리 ID
            environment: 배포 환경 (dev/stg/prod)
            route: 인그레스 라우트 경로
            min_replicas: 최소 레플리카 수
            max_replicas: 최대 레플리카 수
            autoscale_policy: 오토스케일 정책
        
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


def example_register_base_model():
    """Base 모델 등록 예제"""
    base_url = "https://dev.llm-ops.local/llm-ops/v1"
    catalog_client = CatalogClient(base_url)
    
    print("=" * 60)
    print("Base 모델 등록 예제")
    print("=" * 60)
    
    # 1. Base 모델 등록
    print("\n1. Base 모델 등록 중...")
    model = catalog_client.create_model(
        name="gpt-4-base",
        version="1.0",
        model_type="base",
        owner_team="ml-platform",
        metadata={
            "architecture": "transformer",
            "parameters": "175B",
            "framework": "pytorch",
            "license": "proprietary",
            "description": "GPT-4 base model for general purpose tasks"
        },
        status="draft",
        evaluation_summary={
            "accuracy": 0.92,
            "latency_ms": 150
        }
    )
    print(f"  ✓ 모델 등록 완료: {model['id']}")
    print(f"    이름: {model['name']}")
    print(f"    버전: {model['version']}")
    print(f"    타입: {model['type']}")
    print(f"    상태: {model['status']}")
    
    # 2. 모델 상태를 approved로 변경
    print("\n2. 모델 상태를 approved로 변경 중...")
    approved_model = catalog_client.update_model_status(model['id'], "approved")
    print(f"  ✓ 모델 상태 업데이트 완료: {approved_model['status']}")
    
    return approved_model


def example_register_and_serve():
    """Base 모델 등록 및 서빙 전체 워크플로우 예제"""
    base_url = "https://dev.llm-ops.local/llm-ops/v1"
    catalog_client = CatalogClient(base_url)
    serving_client = ServingClient(base_url)
    
    print("=" * 60)
    print("Base 모델 등록 및 서빙 전체 워크플로우")
    print("=" * 60)
    
    try:
        # 1. Base 모델 등록
        print("\n[Step 1] Base 모델 등록...")
        model = catalog_client.create_model(
            name="my-base-model",
            version="1.0",
            model_type="base",
            owner_team="ml-platform",
            metadata={
                "architecture": "transformer",
                "parameters": "7B",
                "framework": "pytorch",
                "license": "apache-2.0",
                "description": "Custom base model for testing"
            },
            status="draft"
        )
        model_id = model['id']
        print(f"  ✓ 모델 등록 완료: {model_id}")
        
        # 2. 모델 승인
        print("\n[Step 2] 모델 승인...")
        approved_model = catalog_client.update_model_status(model_id, "approved")
        print(f"  ✓ 모델 승인 완료: {approved_model['status']}")
        
        # 3. 서빙 엔드포인트 배포
        print("\n[Step 3] 서빙 엔드포인트 배포...")
        endpoint = serving_client.deploy_endpoint(
            model_id=model_id,
            environment="dev",
            route="/llm-ops/v1/serve/my-base-model",
            min_replicas=1,
            max_replicas=3,
            autoscale_policy={"cpuUtilization": 70}
        )
        endpoint_id = endpoint['id']
        print(f"  ✓ 엔드포인트 배포 완료: {endpoint_id}")
        print(f"    라우트: {endpoint['route']}")
        print(f"    환경: {endpoint['environment']}")
        
        print("\n" + "=" * 60)
        print("✓ 전체 워크플로우 완료!")
        print("=" * 60)
        print(f"\n모델 ID: {model_id}")
        print(f"엔드포인트 ID: {endpoint_id}")
        print(f"서빙 라우트: {endpoint['route']}")
        
    except Exception as e:
        print(f"\n✗ 오류 발생: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


def example_from_json():
    """JSON 파일에서 모델 정보를 읽어서 등록하는 예제"""
    base_url = "https://dev.llm-ops.local/llm-ops/v1"
    catalog_client = CatalogClient(base_url)
    
    print("=" * 60)
    print("JSON 파일에서 모델 등록 예제")
    print("=" * 60)
    
    # JSON 파일 읽기
    try:
        with open("examples/model_register_example.json", "r") as f:
            model_data = json.load(f)
    except FileNotFoundError:
        print("  ✗ model_register_example.json 파일을 찾을 수 없습니다.")
        return
    
    print(f"\nJSON 파일에서 모델 정보 읽기 완료:")
    print(f"  이름: {model_data['name']}")
    print(f"  버전: {model_data['version']}")
    print(f"  타입: {model_data['type']}")
    
    # 모델 등록
    print("\n모델 등록 중...")
    model = catalog_client.create_model(
        name=model_data["name"],
        version=model_data["version"],
        model_type=model_data["type"],
        owner_team=model_data["owner_team"],
        metadata=model_data["metadata"],
        lineage_dataset_ids=model_data.get("lineage_dataset_ids", []),
        status=model_data.get("status", "draft"),
        evaluation_summary=model_data.get("evaluation_summary")
    )
    
    print(f"  ✓ 모델 등록 완료: {model['id']}")
    print(f"    상태: {model['status']}")


if __name__ == "__main__":
    import sys
    
    if len(sys.argv) > 1:
        example_name = sys.argv[1]
        if example_name == "register":
            example_register_base_model()
        elif example_name == "workflow":
            example_register_and_serve()
        elif example_name == "json":
            example_from_json()
        else:
            print(f"Unknown example: {example_name}")
            print("Available examples: register, workflow, json")
    else:
        print("Usage: python register_base_model.py <example_name>")
        print("\nAvailable examples:")
        print("  register - Register a base model")
        print("  workflow - Register and serve a base model (full workflow)")
        print("  json     - Register a model from JSON file")
        print("\nExample: python register_base_model.py workflow")

