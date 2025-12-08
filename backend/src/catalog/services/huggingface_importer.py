"""Hugging Face model importer service."""
from __future__ import annotations

import logging
from typing import Optional
from uuid import UUID, uuid4

from sqlalchemy.orm import Session

from catalog import models as orm_models
from catalog.repositories import ModelCatalogRepository
from core.settings import get_settings
from integrations.registry.huggingface_adapter import HuggingFaceAdapter

logger = logging.getLogger(__name__)


class HuggingFaceImporter:
    """
    Service for importing models from Hugging Face Hub.

    기존에는 이 서비스가 Hugging Face Hub와 객체 스토리지에 직접 접근했지만,
    이제는 `HuggingFaceAdapter`(RegistryAdapter 구현체)를 통해 가져오기/업로드
    로직을 위임하여 레지스트리 통합 경로와 동일한 코드 경로를 사용한다.
    """

    def __init__(self, session: Session):
        self.session = session
        self.models = ModelCatalogRepository(session)
        self.settings = get_settings()

    def import_model(
        self,
        hf_model_id: str,
        name: Optional[str] = None,
        version: str = "1.0.0",
        model_type: str = "base",
        owner_team: str = "ml-platform",
        hf_token: Optional[str] = None,
        model_family: str = None,  # Required for training-serving-spec.md
    ) -> orm_models.ModelCatalogEntry:
        """
        Import a model from Hugging Face Hub.

        Steps:
        1. Validate catalog uniqueness
        2. Use HuggingFaceAdapter (RegistryAdapter) to download & upload model
        3. Create catalog entry with adapter metadata & storage URI
        4. Return catalog entry

        Args:
            hf_model_id: Hugging Face model ID (e.g., "microsoft/DialoGPT-small")
            name: Model name (defaults to last part of hf_model_id)
            version: Model version
            model_type: Model type (base, fine-tuned, external)
            owner_team: Owner team name
            hf_token: Hugging Face API token (for gated models)

        Returns:
            Created ModelCatalogEntry
        """
        # Generate model name if not provided
        if not name:
            name = hf_model_id.split("/")[-1].replace("-", "_").lower()

        # Check if model already exists to avoid unnecessary downloads
        existing = self.models.get_by_name_type_version(name, model_type, version)
        if existing:
            raise ValueError(
                f"Model with name '{name}', type '{model_type}', and version '{version}' already exists"
            )

        # Build adapter configuration from settings + optional explicit token
        hf_settings = self.settings
        token = hf_token
        if token is None and hf_settings.huggingface_hub_token is not None:
            token = hf_settings.huggingface_hub_token.get_secret_value()

        adapter_config = {
            # 항상 enabled 로 두어, 레지스트리 feature flag 와 무관하게
            # 기존 HuggingFace importer 기능이 동작하도록 한다.
            "enabled": True,
            "token": token,
            "cache_dir": hf_settings.huggingface_hub_cache_dir,
        }

        adapter = HuggingFaceAdapter(adapter_config)

        # Pre-generate catalog ID so adapter can use it for storage layout
        model_uuid = uuid4()
        logger.info(
            "Importing model from Hugging Face via adapter: hf_model_id=%s, "
            "catalog_id=%s, version=%s",
            hf_model_id,
            model_uuid,
            version,
        )

        result = adapter.import_model(
            registry_model_id=hf_model_id,
            model_catalog_id=model_uuid,
            version=version,
        )

        # Merge adapter metadata with importer-level metadata
        registry_metadata = result.get("registry_metadata") or {}
        metadata: dict = {
            **registry_metadata,
            "source": "huggingface",
            "huggingface_model_id": hf_model_id,
            "description": registry_metadata.get(
                "description",
                f"Model imported from Hugging Face: {hf_model_id}",
            ),
        }

        storage_uri = result.get("storage_uri")
        if not storage_uri:
            raise ValueError("HuggingFaceAdapter did not return a storage_uri")

        logger.info("Creating catalog entry for imported Hugging Face model: %s", name)
        entry = orm_models.ModelCatalogEntry(
            id=str(model_uuid),
            name=name,
            version=version,
            type=model_type,
            owner_team=owner_team,
            model_metadata=metadata,
            storage_uri=storage_uri,
            status="draft",
            model_family=model_family,  # Required for training-serving-spec.md
        )

        self.models.save(entry)
        self.session.commit()
        self.session.refresh(entry)

        logger.info("Successfully imported Hugging Face model into catalog: %s", entry.id)
        return entry

