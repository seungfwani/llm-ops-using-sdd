#!/usr/bin/env python3
"""
Hugging Face 모델 다운로드 및 등록 예제

이 스크립트는 Hugging Face에서 모델을 다운로드하고 LLM Ops 플랫폼에 등록하는 예제입니다.

주의: 실제 모델 파일은 매우 클 수 있으므로(수 GB ~ 수십 GB), 
프로덕션 환경에서는 별도의 워크플로우로 다운로드 및 업로드를 수행하는 것을 권장합니다.
"""

import os
import sys
import requests
from pathlib import Path
from typing import Optional, Dict, Any

# Hugging Face 라이브러리 사용 (선택사항)
try:
    from huggingface_hub import snapshot_download, hf_hub_download
    HF_AVAILABLE = True
except ImportError:
    HF_AVAILABLE = False
    print("⚠️  huggingface_hub이 설치되지 않았습니다.")
    print("   pip install huggingface_hub 로 설치하거나, 수동으로 모델을 다운로드하세요.")


class HuggingFaceModelDownloader:
    """Hugging Face 모델 다운로드 유틸리티"""
    
    def __init__(self, cache_dir: Optional[str] = None):
        """
        Args:
            cache_dir: 모델 다운로드 캐시 디렉토리 (기본값: ~/.cache/huggingface)
        """
        self.cache_dir = cache_dir or os.path.expanduser("~/.cache/huggingface")
        Path(self.cache_dir).mkdir(parents=True, exist_ok=True)
    
    def download_model(
        self,
        model_id: str,
        local_dir: Optional[str] = None,
        token: Optional[str] = None
    ) -> str:
        """
        Hugging Face에서 모델을 다운로드합니다.
        
        Args:
            model_id: Hugging Face 모델 ID (예: "meta-llama/Llama-2-7b-chat-hf")
            local_dir: 다운로드할 로컬 디렉토리 (None이면 캐시 디렉토리 사용)
            token: Hugging Face API 토큰 (gated 모델의 경우 필요)
        
        Returns:
            다운로드된 모델의 로컬 경로
        """
        if not HF_AVAILABLE:
            raise ImportError(
                "huggingface_hub이 필요합니다. "
                "pip install huggingface_hub 로 설치하세요."
            )
        
        print(f"📥 Hugging Face에서 모델 다운로드 중: {model_id}")
        
        try:
            if local_dir:
                download_path = snapshot_download(
                    repo_id=model_id,
                    local_dir=local_dir,
                    token=token,
                    local_dir_use_symlinks=False
                )
            else:
                download_path = snapshot_download(
                    repo_id=model_id,
                    cache_dir=self.cache_dir,
                    token=token
                )
            
            print(f"✓ 모델 다운로드 완료: {download_path}")
            return download_path
        
        except Exception as e:
            print(f"✗ 모델 다운로드 실패: {e}")
            raise
    
    def get_model_info(self, model_id: str) -> Dict[str, Any]:
        """
        Hugging Face 모델 정보를 조회합니다.
        
        Args:
            model_id: Hugging Face 모델 ID
        
        Returns:
            모델 정보 딕셔너리
        """
        try:
            from huggingface_hub import model_info
            info = model_info(model_id)
            
            return {
                "model_id": model_id,
                "author": info.author if hasattr(info, 'author') else None,
                "tags": info.tags if hasattr(info, 'tags') else [],
                "model_type": getattr(info, 'model_type', None),
                "library_name": getattr(info, 'library_name', None),
                "pipeline_tag": getattr(info, 'pipeline_tag', None),
            }
        except Exception as e:
            print(f"⚠️  모델 정보 조회 실패: {e}")
            return {"model_id": model_id}


class CatalogClient:
    """모델 카탈로그 API 클라이언트"""
    
    def __init__(self, base_url: str, user_id: str = "admin", user_roles: str = "admin"):
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
        storage_uri: Optional[str] = None,
        status: str = "draft"
    ) -> Dict[str, Any]:
        """모델을 카탈로그에 등록합니다."""
        payload = {
            "name": name,
            "version": version,
            "type": model_type,
            "owner_team": owner_team,
            "metadata": metadata,
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
    
    def upload_model_files(self, model_id: str, model_dir: str) -> Dict[str, Any]:
        """
        모델 디렉토리의 파일들을 업로드합니다.
        
        주의: 실제 구현에서는 대용량 파일을 스트리밍 업로드하거나
        별도의 워크플로우를 사용해야 합니다.
        """
        import requests
        from pathlib import Path
        
        model_path = Path(model_dir)
        files_to_upload = []
        
        # 주요 모델 파일들 찾기
        important_files = [
            "config.json",
            "tokenizer.json",
            "tokenizer_config.json",
            "model.safetensors",
            "pytorch_model.bin",
            "model.bin",
        ]
        
        for file_pattern in important_files:
            for file_path in model_path.rglob(file_pattern):
                files_to_upload.append(file_path)
        
        # 모든 .json, .bin, .safetensors 파일도 포함
        for ext in [".json", ".bin", ".safetensors", ".txt"]:
            for file_path in model_path.rglob(f"*{ext}"):
                if file_path not in files_to_upload:
                    files_to_upload.append(file_path)
        
        print(f"\n📤 {len(files_to_upload)}개 파일 업로드 준비 중...")
        
        # 실제 업로드는 API를 통해 수행
        # 여기서는 예제로 파일 목록만 출력
        uploaded_files = []
        for file_path in files_to_upload[:10]:  # 예제: 처음 10개만
            relative_path = file_path.relative_to(model_path)
            file_size = file_path.stat().st_size / (1024 * 1024)  # MB
            print(f"  - {relative_path} ({file_size:.2f} MB)")
            uploaded_files.append({
                "path": str(relative_path),
                "size_mb": file_size
            })
        
        if len(files_to_upload) > 10:
            print(f"  ... 외 {len(files_to_upload) - 10}개 파일")
        
        print("\n⚠️  실제 파일 업로드는 API를 통해 수행해야 합니다:")
        print(f"   POST {self.base_url}/catalog/models/{model_id}/upload")
        print("   (multipart/form-data)")
        
        return {
            "model_id": model_id,
            "files_prepared": len(files_to_upload),
            "sample_files": uploaded_files
        }


def example_download_and_register():
    """Hugging Face 모델 다운로드 및 등록 예제"""
    base_url = "https://dev.llm-ops.local/llm-ops/v1"
    
    # Hugging Face 모델 ID
    hf_model_id = "microsoft/DialoGPT-small"  # 작은 모델로 예제 (실제 사용 시 더 큰 모델 가능)
    
    print("=" * 60)
    print("Hugging Face 모델 다운로드 및 등록 예제")
    print("=" * 60)
    
    if not HF_AVAILABLE:
        print("\n⚠️  huggingface_hub이 설치되지 않았습니다.")
        print("   다음 명령으로 설치하세요: pip install huggingface_hub")
        print("\n   또는 수동으로 모델을 다운로드한 후 등록할 수 있습니다.")
        return
    
    try:
        # 1. 모델 정보 조회
        print(f"\n[Step 1] Hugging Face 모델 정보 조회: {hf_model_id}")
        downloader = HuggingFaceModelDownloader()
        model_info = downloader.get_model_info(hf_model_id)
        print(f"  ✓ 모델 정보: {model_info}")
        
        # 2. 모델 다운로드
        print(f"\n[Step 2] 모델 다운로드 중...")
        download_dir = f"/tmp/hf_models/{hf_model_id.replace('/', '_')}"
        model_path = downloader.download_model(
            model_id=hf_model_id,
            local_dir=download_dir
        )
        print(f"  ✓ 다운로드 완료: {model_path}")
        
        # 3. 모델 등록
        print(f"\n[Step 3] 모델 카탈로그에 등록 중...")
        catalog_client = CatalogClient(base_url)
        
        # 모델 이름 생성 (Hugging Face ID에서)
        model_name = hf_model_id.split("/")[-1].replace("-", "_")
        
        model = catalog_client.create_model(
            name=model_name,
            version="1.0",
            model_type="base",
            owner_team="ml-platform",
            metadata={
                "source": "huggingface",
                "huggingface_model_id": hf_model_id,
                "architecture": model_info.get("model_type", "unknown"),
                "framework": "pytorch",
                "license": "unknown",
                "description": f"Model downloaded from Hugging Face: {hf_model_id}",
                "download_path": model_path
            },
            storage_uri=f"s3://models/{model_name}/1.0/",
            status="draft"
        )
        print(f"  ✓ 모델 등록 완료: {model['id']}")
        
        # 4. 모델 파일 업로드 (예제 - 실제로는 별도 워크플로우 필요)
        print(f"\n[Step 4] 모델 파일 업로드 준비...")
        upload_info = catalog_client.upload_model_files(model['id'], model_path)
        print(f"  ✓ {upload_info['files_prepared']}개 파일 준비 완료")
        
        print("\n" + "=" * 60)
        print("✓ 모델 등록 프로세스 완료!")
        print("=" * 60)
        print(f"\n다음 단계:")
        print(f"1. 모델 파일을 S3/객체 스토리지에 업로드")
        print(f"2. 모델 상태를 'approved'로 변경")
        print(f"3. 서빙 엔드포인트 배포")
        
    except Exception as e:
        print(f"\n✗ 오류 발생: {e}")
        import traceback
        traceback.print_exc()


def example_register_with_storage_uri():
    """이미 다운로드된 모델을 storage_uri로 등록하는 예제"""
    base_url = "https://dev.llm-ops.local/llm-ops/v1"
    catalog_client = CatalogClient(base_url)
    
    print("=" * 60)
    print("Hugging Face 모델 (storage_uri로 등록)")
    print("=" * 60)
    
    # 이미 S3에 업로드된 모델을 등록하는 경우
    hf_model_id = "meta-llama/Llama-2-7b-chat-hf"
    model_name = "llama_2_7b_chat"
    
    print(f"\n모델 등록 중: {model_name}")
    
    model = catalog_client.create_model(
        name=model_name,
        version="1.0",
        model_type="base",
        owner_team="ml-platform",
        metadata={
            "source": "huggingface",
            "huggingface_model_id": hf_model_id,
            "architecture": "llama",
            "parameters": "7B",
            "framework": "pytorch",
            "license": "llama2",
            "description": f"Llama 2 7B Chat model from Hugging Face"
        },
        storage_uri="s3://models/llama_2_7b_chat/1.0/",  # 이미 업로드된 모델 경로
        status="draft"
    )
    
    print(f"✓ 모델 등록 완료: {model['id']}")
    print(f"  Storage URI: {model.get('storage_uri', 'N/A')}")


if __name__ == "__main__":
    import sys
    
    if len(sys.argv) > 1:
        example_name = sys.argv[1]
        if example_name == "download":
            example_download_and_register()
        elif example_name == "register":
            example_register_with_storage_uri()
        else:
            print(f"Unknown example: {example_name}")
            print("Available examples: download, register")
    else:
        print("Usage: python download_and_register_hf_model.py <example_name>")
        print("\nAvailable examples:")
        print("  download - Download model from Hugging Face and register")
        print("  register - Register model with existing storage_uri")
        print("\nExample: python download_and_register_hf_model.py download")
        print("\nNote: Install huggingface_hub first:")
        print("  pip install huggingface_hub")

