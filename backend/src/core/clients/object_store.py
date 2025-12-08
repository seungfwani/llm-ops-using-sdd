from __future__ import annotations

import boto3
import urllib3
import logging
from botocore.config import Config

from core.settings import get_settings

# Disable urllib3 header parsing warnings for MinIO compatibility
# MinIO sometimes returns headers that urllib3 considers non-standard
urllib3.disable_warnings(urllib3.exceptions.HeaderParsingError)

# Suppress urllib3 connection pool warnings
logging.getLogger("urllib3.connectionpool").setLevel(logging.ERROR)
logging.getLogger("urllib3.connection").setLevel(logging.ERROR)

_client = None


def get_object_store_client():
    global _client
    if _client is None:
        settings = get_settings()
        # Configure boto3 to be more lenient with MinIO responses
        config = Config(
            signature_version="s3v4",
            # Disable strict header validation for MinIO compatibility
            parameter_validation=False,
        )
        _client = boto3.client(
            "s3",
            endpoint_url=str(settings.object_store_endpoint),
            aws_access_key_id=settings.object_store_access_key,
            aws_secret_access_key=settings.object_store_secret_key.get_secret_value(),
            use_ssl=settings.object_store_secure,
            config=config,
        )
    return _client

