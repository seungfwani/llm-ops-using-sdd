from __future__ import annotations

import boto3
from botocore.config import Config

from core.settings import get_settings

_client = None


def get_object_store_client():
    global _client
    if _client is None:
        settings = get_settings()
        _client = boto3.client(
            "s3",
            endpoint_url=str(settings.object_store_endpoint),
            aws_access_key_id=settings.object_store_access_key,
            aws_secret_access_key=settings.object_store_secret_key.get_secret_value(),
            use_ssl=settings.object_store_secure,
            config=Config(signature_version="s3v4"),
        )
    return _client

