#!/usr/bin/env python3
"""
LLM Ops Platform 전체 워크플로우 예제

데이터셋 등록부터 모델 서빙 및 채팅 테스트까지의 전체 과정을 보여주는 예제입니다.

워크플로우:
1. 데이터셋 등록 및 업로드
2. Base 모델 등록 (또는 Hugging Face 모델)
3. 학습 작업 제출 (선택사항)
4. 모델 승인
5. 서빙 엔드포인트 배포 (DeploymentSpec 포함)
6. 채팅 테스트

사용 방법:
    python examples/complete_workflow_example.py

환경 변수:
    LLM_OPS_API_BASE_URL: API 기본 URL (기본값: http://localhost:8000/llm-ops/v1)
    LLM_OPS_USER_ID: 사용자 ID (기본값: admin)
    LLM_OPS_USER_ROLES: 사용자 역할 (기본값: admin,llm-ops-user)
                        주의: llm-ops-user 역할이 포함되어야 합니다 (governance 미들웨어 요구사항)
    USE_GPU: GPU 사용 여부 (기본값: false, 로컬 개발 환경에서는 CPU 사용)
             GPU를 사용하려면: export USE_GPU=true
"""

import os
import sys
import time
import requests
import json
from pathlib import Path
from typing import Optional, Dict, List, Any

# 예제 데이터셋 경로
EXAMPLE_DATASET_PATH = Path(__file__).parent / "datasets" / "customer-support-sample.csv"


class CatalogClient:
    """카탈로그 API 클라이언트"""
    
    def __init__(self, base_url: str, user_id: str = "admin", user_roles: str = "admin"):
        self.base_url = base_url.rstrip('/')
        self.headers = {
            "Content-Type": "application/json",
            "X-User-Id": user_id,
            "X-User-Roles": user_roles
        }
    
    def list_datasets(self) -> List[Dict[str, Any]]:
        """데이터셋 목록 조회"""
        response = requests.get(
            f"{self.base_url}/catalog/datasets",
            headers=self.headers
        )
        response.raise_for_status()
        result = response.json()
        if result["status"] != "success":
            raise Exception(f"Dataset list failed: {result['message']}")
        return result.get("data", [])
    
    def get_dataset_by_name_version(self, name: str, version: str) -> Optional[Dict[str, Any]]:
        """이름과 버전으로 데이터셋 조회"""
        datasets = self.list_datasets()
        for dataset in datasets:
            if dataset.get("name") == name and dataset.get("version") == version:
                return dataset
        return None
    
    def create_dataset(
        self,
        name: str,
        version: str,
        owner_team: str = "ml-platform",
        dataset_type: str = "sft_pair",
        storage_uri: Optional[str] = None,
        reuse_existing: bool = True
    ) -> Dict[str, Any]:
        """데이터셋 생성 (기존 데이터셋이 있으면 재사용 가능)"""
        # 기존 데이터셋 확인
        if reuse_existing:
            existing = self.get_dataset_by_name_version(name, version)
            if existing:
                print(f"  ℹ️  기존 데이터셋 발견: {existing['id']} (재사용)")
                return existing
        
        # storage_uri가 제공되지 않으면 자동 생성
        if storage_uri is None:
            storage_uri = f"s3://datasets/{name}/{version}/"
        
        payload = {
            "name": name,
            "version": version,
            "owner_team": owner_team,  # API는 snake_case 사용
            "type": dataset_type,
            "storage_uri": storage_uri  # API는 snake_case 사용
        }
        response = requests.post(
            f"{self.base_url}/catalog/datasets",
            json=payload,
            headers=self.headers
        )
        response.raise_for_status()
        result = response.json()
        if result["status"] != "success":
            raise Exception(f"Dataset creation failed: {result['message']}")
        return result["data"]
    
    def upload_dataset(self, dataset_id: str, file_path: Path) -> Dict[str, Any]:
        """데이터셋 파일 업로드"""
        with open(file_path, 'rb') as f:
            files = {'files': (file_path.name, f, 'text/csv')}
            headers = {k: v for k, v in self.headers.items() if k != "Content-Type"}
            response = requests.post(
                f"{self.base_url}/catalog/datasets/{dataset_id}/upload",
                files=files,
                headers=headers
            )
        response.raise_for_status()
        result = response.json()
        if result["status"] != "success":
            raise Exception(f"Dataset upload failed: {result['message']}")
        return result["data"]
    
    def list_models(self) -> List[Dict[str, Any]]:
        """모델 목록 조회"""
        response = requests.get(
            f"{self.base_url}/catalog/models",
            headers=self.headers
        )
        response.raise_for_status()
        result = response.json()
        if result["status"] != "success":
            raise Exception(f"Model list failed: {result['message']}")
        return result.get("data", [])
    
    def get_model_by_name_version(self, name: str, version: str) -> Optional[Dict[str, Any]]:
        """이름과 버전으로 모델 조회"""
        models = self.list_models()
        for model in models:
            if model.get("name") == name and model.get("version") == version:
                return model
        return None
    
    def create_model(
        self,
        name: str,
        version: str,
        model_type: str,
        model_family: str,
        owner_team: str = "ml-platform",
        metadata: Optional[Dict] = None,
        storage_uri: Optional[str] = None,
        status: str = "draft",
        reuse_existing: bool = True
    ) -> Dict[str, Any]:
        """모델 등록 (기존 모델이 있으면 재사용 가능)"""
        # 기존 모델 확인
        if reuse_existing:
            existing = self.get_model_by_name_version(name, version)
            if existing:
                print(f"  ℹ️  기존 모델 발견: {existing['id']} (재사용)")
                return existing
        
        payload = {
            "name": name,
            "version": version,
            "type": model_type,
            "model_family": model_family,
            "owner_team": owner_team,
            "metadata": metadata or {},
            "status": status
        }
        if storage_uri:
            payload["storage_uri"] = storage_uri
        
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
    
    def update_model_status(self, model_id: str, status: str) -> Dict[str, Any]:
        """모델 상태 업데이트"""
        response = requests.patch(
            f"{self.base_url}/catalog/models/{model_id}/status",
            params={"status": status},
            headers=self.headers
        )
        response.raise_for_status()
        result = response.json()
        if result["status"] != "success":
            raise Exception(f"Model status update failed: {result['message']}")
        return result["data"]
    
    def get_model(self, model_id: str) -> Dict[str, Any]:
        """모델 조회"""
        response = requests.get(
            f"{self.base_url}/catalog/models/{model_id}",
            headers=self.headers
        )
        response.raise_for_status()
        result = response.json()
        if result["status"] != "success":
            raise Exception(f"Model retrieval failed: {result['message']}")
        return result["data"]
    
    def update_dataset_status(self, dataset_id: str, status: str) -> Dict[str, Any]:
        """데이터셋 상태 업데이트"""
        response = requests.patch(
            f"{self.base_url}/catalog/datasets/{dataset_id}/status",
            params={"status": status},
            headers=self.headers
        )
        response.raise_for_status()
        result = response.json()
        if result["status"] != "success":
            raise Exception(f"Dataset status update failed: {result['message']}")
        return result["data"]
    
    def upload_model_files(self, model_id: str, file_paths: List[Path]) -> Dict[str, Any]:
        """모델 파일 업로드"""
        files = []
        file_handles = []
        
        try:
            for file_path in file_paths:
                if file_path.exists():
                    f = open(file_path, 'rb')
                    file_handles.append(f)
                    files.append(('files', (file_path.name, f, 'application/octet-stream')))
            
            if not files:
                raise Exception("No valid files to upload")
            
            headers = {k: v for k, v in self.headers.items() if k != "Content-Type"}
            response = requests.post(
                f"{self.base_url}/catalog/models/{model_id}/upload",
                files=files,
                headers=headers
            )
            
            response.raise_for_status()
            result = response.json()
            if result["status"] != "success":
                raise Exception(f"Model file upload failed: {result['message']}")
            return result["data"]
        finally:
            # 파일 핸들 닫기
            for f in file_handles:
                try:
                    f.close()
                except Exception:
                    pass


class TrainingClient:
    """학습 API 클라이언트"""
    
    def __init__(self, base_url: str, user_id: str = "admin", user_roles: str = "admin"):
        self.base_url = base_url.rstrip('/')
        self.headers = {
            "Content-Type": "application/json",
            "X-User-Id": user_id,
            "X-User-Roles": user_roles
        }
    
    def submit_job(
        self,
        model_id: Optional[str],
        dataset_id: str,
        job_type: str,
        use_gpu: bool = False,
        resource_profile: Optional[Dict] = None,
        train_job_spec: Optional[Dict] = None
    ) -> Dict[str, Any]:
        """학습 작업 제출"""
        if resource_profile is None:
            if use_gpu:
                resource_profile = {
                    "gpuCount": 1,
                    "gpuType": "nvidia-tesla-v100",
                    "maxDuration": 60
                }
            else:
                resource_profile = {
                    "cpuCores": 4,
                    "memory": "8Gi",
                    "maxDuration": 60
                }
        
        payload = {
            "datasetId": dataset_id,
            "jobType": job_type,
            "useGpu": use_gpu,
            "resourceProfile": resource_profile
        }
        
        if model_id:
            payload["modelId"] = model_id
        
        if train_job_spec:
            payload["trainJobSpec"] = train_job_spec
        
        response = requests.post(
            f"{self.base_url}/training/jobs",
            json=payload,
            headers=self.headers
        )
        response.raise_for_status()
        result = response.json()
        if result["status"] != "success":
            raise Exception(f"Training job submission failed: {result['message']}")
        return result["data"]
    
    def get_job(self, job_id: str) -> Dict[str, Any]:
        """학습 작업 조회"""
        response = requests.get(
            f"{self.base_url}/training/jobs/{job_id}",
            headers=self.headers
        )
        response.raise_for_status()
        result = response.json()
        if result["status"] != "success":
            raise Exception(f"Training job retrieval failed: {result['message']}")
        return result["data"]


class ServingClient:
    """서빙 API 클라이언트"""
    
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
        deployment_spec: Optional[Dict] = None,
        use_gpu: bool = False
    ) -> Dict[str, Any]:
        """서빙 엔드포인트 배포"""
        payload = {
            "modelId": model_id,
            "environment": environment,
            "route": route,
            "minReplicas": min_replicas,
            "maxReplicas": max_replicas,
            "useGpu": use_gpu
        }
        
        if deployment_spec:
            payload["deploymentSpec"] = deployment_spec
        
        response = requests.post(
            f"{self.base_url}/serving/endpoints",
            json=payload,
            headers=self.headers
        )
        response.raise_for_status()
        result = response.json()
        if result["status"] != "success":
            raise Exception(f"Endpoint deployment failed: {result['message']}")
        return result["data"]
    
    def list_endpoints(
        self,
        environment: Optional[str] = None,
        model_id: Optional[str] = None,
        status: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """엔드포인트 목록 조회"""
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
            raise Exception(f"Endpoint list failed: {result['message']}")
        return result.get("data", [])
    
    def get_endpoint(self, endpoint_id: str) -> Dict[str, Any]:
        """엔드포인트 조회"""
        response = requests.get(
            f"{self.base_url}/serving/endpoints/{endpoint_id}",
            headers=self.headers
        )
        response.raise_for_status()
        result = response.json()
        if result["status"] != "success":
            raise Exception(f"Endpoint retrieval failed: {result['message']}")
        return result["data"]
    
    def delete_endpoint(self, endpoint_id: str) -> Dict[str, Any]:
        """엔드포인트 삭제"""
        response = requests.delete(
            f"{self.base_url}/serving/endpoints/{endpoint_id}",
            headers=self.headers
        )
        response.raise_for_status()
        result = response.json()
        if result["status"] != "success":
            raise Exception(f"Endpoint deletion failed: {result['message']}")
        return result.get("data", {})
    
    def get_endpoint_by_route(self, route: str, environment: str) -> Optional[Dict[str, Any]]:
        """Route와 environment로 엔드포인트 조회"""
        endpoints = self.list_endpoints(environment=environment)
        for endpoint in endpoints:
            if endpoint.get("route") == route:
                return endpoint
        return None
    
    def wait_for_healthy(self, endpoint_id: str, timeout: int = 300) -> bool:
        """엔드포인트가 healthy 상태가 될 때까지 대기"""
        start_time = time.time()
        while time.time() - start_time < timeout:
            endpoint = self.get_endpoint(endpoint_id)
            status = endpoint.get("status")
            print(f"  엔드포인트 상태: {status}")
            if status == "healthy":
                return True
            elif status == "failed":
                raise Exception("Endpoint deployment failed")
            time.sleep(5)
        raise Exception(f"Endpoint did not become healthy within {timeout} seconds")
    
    def chat_completion(
        self,
        route_name: str,
        messages: List[Dict[str, str]],
        temperature: float = 0.7,
        max_tokens: int = 500
    ) -> Dict[str, Any]:
        """채팅 완성 API 호출"""
        payload = {
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens
        }
        response = requests.post(
            f"{self.base_url}/serve/{route_name}/chat",
            json=payload,
            headers=self.headers
        )
        response.raise_for_status()
        result = response.json()
        return result


def print_section(title: str):
    """섹션 제목 출력"""
    print("\n" + "=" * 60)
    print(f"  {title}")
    print("=" * 60)


def complete_workflow_example():
    """전체 워크플로우 예제 실행"""
    base_url = os.getenv("LLM_OPS_API_BASE_URL", "http://localhost:8000/llm-ops/v1")
    user_id = os.getenv("LLM_OPS_USER_ID", "admin")
    # 기본 역할에 llm-ops-user를 포함 (governance 미들웨어 요구사항)
    user_roles = os.getenv("LLM_OPS_USER_ROLES", "admin,llm-ops-user")
    
    print_section("LLM Ops Platform 전체 워크플로우 예제")
    print(f"\nAPI URL: {base_url}")
    print(f"User ID: {user_id}")
    print(f"User Roles: {user_roles}")
    
    # CPU/GPU 모드 확인
    use_gpu_env = os.getenv("USE_GPU", "false").lower() == "true"
    print(f"리소스 모드: {'GPU' if use_gpu_env else 'CPU (로컬 개발 모드)'}")
    if not use_gpu_env:
        print(f"  💡 GPU를 사용하려면: export USE_GPU=true")
    
    catalog_client = CatalogClient(base_url, user_id, user_roles)
    training_client = TrainingClient(base_url, user_id, user_roles)
    serving_client = ServingClient(base_url, user_id, user_roles)
    
    try:
        # Step 1: 데이터셋 등록 및 업로드
        print_section("Step 1: 데이터셋 등록 및 업로드")
        dataset = catalog_client.create_dataset(
            name="customer-support-dataset",
            version="v1.0",
            owner_team="ml-platform",
            dataset_type="sft_pair"  # SFT fine-tuning용 데이터셋 타입
        )
        dataset_id = dataset["id"]
        print(f"  ✓ 데이터셋 생성 완료: {dataset_id}")
        
        if EXAMPLE_DATASET_PATH.exists():
            upload_result = catalog_client.upload_dataset(dataset_id, EXAMPLE_DATASET_PATH)
            print(f"  ✓ 데이터셋 파일 업로드 완료: {upload_result.get('files_uploaded', 0)}개 파일")
        else:
            print(f"  ⚠️  예제 데이터셋 파일을 찾을 수 없습니다: {EXAMPLE_DATASET_PATH}")
            print(f"     데이터셋 파일을 수동으로 업로드하세요.")
        
        # Step 1.5: 데이터셋 승인 (학습 작업을 위해 필요)
        print_section("Step 1.5: 데이터셋 승인")
        try:
            approved_dataset = catalog_client.update_dataset_status(dataset_id, "approved")
            print(f"  ✓ 데이터셋 승인 완료: {approved_dataset.get('status', 'approved')}")
        except Exception as e:
            print(f"  ⚠️  데이터셋 승인 실패: {e}")
            print(f"     학습 작업을 건너뛰거나 수동으로 승인하세요.")
        
        # Step 2: Base 모델 등록
        print_section("Step 2: Base 모델 등록")
        model = catalog_client.create_model(
            name="example-base-model",
            version="1.0",
            model_type="base",
            model_family="llama",
            owner_team="ml-platform",
            metadata={
                "architecture": "transformer",
                "parameters": "7B",
                "framework": "pytorch",
                "description": "Example base model for workflow demonstration"
            },
            storage_uri="s3://models/example-base-model/1.0/",
            status="draft"
        )
        model_id = model["id"]
        print(f"  ✓ 모델 등록 완료: {model_id}")
        
        # Step 2.5: 모델 파일 업로드 (storage_uri가 없을 경우)
        # 참고: 실제 모델 파일이 없으면 이 단계를 건너뛰고, 
        # 서빙 시 storage_uri가 없으면 외부 모델로 처리하거나 경고를 출력합니다.
        if not model.get("storage_uri"):
            print(f"  ⚠️  모델에 storage_uri가 없습니다.")
            print(f"     모델 파일을 업로드하거나 외부 모델로 설정하세요.")
            print(f"     예: catalog_client.upload_model_files(model_id, [Path('model.bin')])")
        else:
            print(f"  ✓ 모델 storage_uri: {model.get('storage_uri')}")
        
        # Step 3: 모델 승인
        print_section("Step 3: 모델 승인")
        approved_model = catalog_client.update_model_status(model_id, "approved")
        print(f"  ✓ 모델 승인 완료: {approved_model['status']}")
        
        # Step 4: 학습 작업 제출 (선택사항)
        print_section("Step 4: 학습 작업 제출 (선택사항)")
        print("  학습 작업을 제출하시겠습니까? (y/n): ", end="")
        submit_training = input().strip().lower() == 'y'
        
        training_job_id = None
        if submit_training:
            try:
                # CPU-only 학습 (개발/테스트용)
                train_job_spec = {
                    "model_ref": f"{model['name']}-{model['version']}",
                    "model_family": "llama",
                    "job_type": "SFT",
                    "dataset_ref": f"{dataset['name']}-{dataset['version']}",
                    "dataset_type": "instruction",
                    "resources": {
                        "gpus": 0  # CPU-only
                    },
                    "hyperparameters": {
                        "learning_rate": 2e-5,
                        "batch_size": 4,
                        "num_epochs": 1
                    },
                    "use_gpu": False
                }
                
                training_job = training_client.submit_job(
                    model_id=model_id,
                    dataset_id=dataset_id,
                    job_type="finetune",
                    use_gpu=False,
                    train_job_spec=train_job_spec
                )
                training_job_id = training_job["id"]
                print(f"  ✓ 학습 작업 제출 완료: {training_job_id}")
                print(f"     상태: {training_job['status']}")
                print(f"     참고: 학습 작업은 백그라운드에서 실행됩니다.")
            except Exception as e:
                print(f"  ⚠️  학습 작업 제출 실패: {e}")
                print(f"     계속 진행합니다...")
        else:
            print("  학습 작업 제출을 건너뜁니다.")
        
        # Step 5: 서빙 엔드포인트 배포
        print_section("Step 5: 서빙 엔드포인트 배포")
        
        # 모델 정보 다시 조회하여 storage_uri 확인
        model_info = catalog_client.get_model(model_id)
        if not model_info.get("storage_uri"):
            print(f"  ⚠️  경고: 모델에 storage_uri가 없습니다.")
            print(f"     서빙 배포가 실패할 수 있습니다.")
            print(f"     모델 파일을 업로드하거나 외부 모델로 설정하세요.")
            print(f"     계속 진행합니다...")
        
        # DeploymentSpec 생성
        # 로컬 개발 환경을 위해 기본적으로 CPU 사용 (USE_GPU 환경 변수로 GPU 활성화 가능)
        use_gpu = os.getenv("USE_GPU", "false").lower() == "true"
        
        deployment_spec = {
            "model_ref": f"{model['name']}-{model['version']}",
            "model_family": "llama",
            "job_type": "SFT",
            "serve_target": "GENERATION",
            "resources": {
                "gpus": 1 if use_gpu else 0,
            },
            "runtime": {
                "max_concurrent_requests": 256,
                "max_input_tokens": 4096,
                "max_output_tokens": 1024
            },
            "use_gpu": use_gpu
        }
        
        # CPU 모드일 때는 GPU 메모리 설정 제거
        if use_gpu:
            deployment_spec["resources"]["gpu_memory_gb"] = 80
        route = "/llm-ops/v1/serve/example-model"
        environment = "dev"
        
        # 기존 엔드포인트 확인
        existing_endpoint = serving_client.get_endpoint_by_route(route, environment)
        if existing_endpoint:
            print(f"  ℹ️  기존 엔드포인트 발견: {existing_endpoint['id']}")
            print(f"     Route: {route}")
            print(f"     상태: {existing_endpoint.get('status', 'unknown')}")
            
            # 기존 엔드포인트 재사용 또는 삭제 후 재배포
            reuse = input("  기존 엔드포인트를 재사용하시겠습니까? (y/n, 기본값: y): ").strip().lower()
            if reuse == 'n':
                print(f"  기존 엔드포인트 삭제 중...")
                serving_client.delete_endpoint(existing_endpoint['id'])
                print(f"  ✓ 기존 엔드포인트 삭제 완료")
                
                # 새 엔드포인트 배포
                endpoint = serving_client.deploy_endpoint(
                    model_id=model_id,
                    environment=environment,
                    route=route,
                    min_replicas=1,
                    max_replicas=3,
                    deployment_spec=deployment_spec,
                    use_gpu=use_gpu
                )
            else:
                # 기존 엔드포인트 재사용
                endpoint = existing_endpoint
                print(f"  ✓ 기존 엔드포인트 재사용: {endpoint['id']}")
        else:
            # 새 엔드포인트 배포
            endpoint = serving_client.deploy_endpoint(
                model_id=model_id,
                environment=environment,
                route=route,
                min_replicas=1,
                max_replicas=3,
                deployment_spec=deployment_spec,
                use_gpu=use_gpu
            )
        endpoint_id = endpoint["id"]
        print(f"  ✓ 서빙 엔드포인트 배포 완료: {endpoint_id}")
        print(f"     Route: {route}")
        print(f"     리소스: {'GPU' if use_gpu else 'CPU (로컬 개발 모드)'}")
        print(f"     상태: {endpoint['status']}")
        
        # Step 6: 엔드포인트가 healthy 상태가 될 때까지 대기
        print_section("Step 6: 엔드포인트 배포 대기")
        print("  엔드포인트가 healthy 상태가 될 때까지 대기 중...")
        try:
            serving_client.wait_for_healthy(endpoint_id, timeout=300)
            print("  ✓ 엔드포인트가 healthy 상태입니다!")
        except Exception as e:
            print(f"  ⚠️  엔드포인트 대기 중 오류: {e}")
            print(f"     수동으로 상태를 확인하세요.")
        
        # Step 7: 채팅 테스트
        print_section("Step 7: 채팅 테스트")
        route_name = route.split("/")[-1]  # "example-model"
        
        messages = [
            {"role": "system", "content": "You are a helpful assistant."},
            {"role": "user", "content": "Hello! Can you help me?"}
        ]
        
        print(f"  채팅 요청 전송 중...")
        print(f"  메시지: {messages[-1]['content']}")
        
        try:
            response = serving_client.chat_completion(
                route_name=route_name,
                messages=messages,
                temperature=0.7,
                max_tokens=100
            )
            
            if response.get("status") == "success" and response.get("data"):
                choice = response["data"]["choices"][0]
                assistant_message = choice["message"]["content"]
                print(f"  ✓ 응답 수신 완료!")
                print(f"  응답: {assistant_message}")
                
                if response["data"].get("usage"):
                    usage = response["data"]["usage"]
                    print(f"  토큰 사용량:")
                    print(f"    - Prompt: {usage.get('prompt_tokens', 0)}")
                    print(f"    - Completion: {usage.get('completion_tokens', 0)}")
                    print(f"    - Total: {usage.get('total_tokens', 0)}")
            else:
                print(f"  ⚠️  채팅 응답 실패: {response.get('message', 'Unknown error')}")
        except Exception as e:
            print(f"  ⚠️  채팅 테스트 실패: {e}")
            print(f"     엔드포인트가 아직 준비되지 않았거나 모델이 배포되지 않았을 수 있습니다.")
        
        # 요약
        print_section("워크플로우 완료 요약")
        print(f"  데이터셋 ID: {dataset_id}")
        print(f"  모델 ID: {model_id}")
        if training_job_id:
            print(f"  학습 작업 ID: {training_job_id}")
        print(f"  서빙 엔드포인트 ID: {endpoint_id}")
        print(f"  서빙 Route: {route}")
        print(f"\n  다음 단계:")
        print(f"    1. UI에서 엔드포인트 상태 확인: /serving/endpoints/{endpoint_id}")
        print(f"    2. 채팅 테스트: /serving/chat/{endpoint_id}")
        print(f"    3. API로 채팅: POST {base_url}/serve/{route_name}/chat")
        
    except Exception as e:
        print(f"\n✗ 오류 발생: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    complete_workflow_example()

