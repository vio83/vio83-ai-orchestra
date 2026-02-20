"""
╔══════════════════════════════════════════════════════════════════════╗
║           VIO 83 AI ORCHESTRA — Cloud Storage Abstraction           ║
║                                                                      ║
║  Adapters universali per storage locale e cloud:                     ║
║  • LocalStorage  — filesystem locale (default, zero config)          ║
║  • S3Storage     — Amazon S3 / MinIO / compatibili S3               ║
║  • GCSStorage    — Google Cloud Storage                              ║
║  • AzureStorage  — Azure Blob Storage                                ║
║  • DropboxStorage— Dropbox API v2                                    ║
║                                                                      ║
║  Pattern: Strategy + Factory                                         ║
║  Ogni adapter implementa StorageBackend (ABC)                        ║
║  Auto-detection delle librerie disponibili                           ║
╚══════════════════════════════════════════════════════════════════════╝
"""

from __future__ import annotations

import io
import json
import os
import shutil
import hashlib
import logging
import time
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import (
    Any, BinaryIO, Dict, Generator, List, Optional, Tuple, Union
)

logger = logging.getLogger("vio83.cloud_storage")

# ═══════════════════════════════════════════════════════
# Configurazione e Tipi
# ═══════════════════════════════════════════════════════

class StorageType(Enum):
    LOCAL = "local"
    S3 = "s3"
    GCS = "gcs"
    AZURE = "azure"
    DROPBOX = "dropbox"


@dataclass
class StorageConfig:
    """Configurazione universale per qualsiasi backend storage."""
    storage_type: StorageType = StorageType.LOCAL

    # Local
    local_base_path: str = ""

    # S3 / MinIO
    s3_bucket: str = ""
    s3_prefix: str = "vio83/"
    s3_region: str = "eu-south-1"
    s3_endpoint_url: str = ""  # per MinIO
    s3_access_key: str = ""
    s3_secret_key: str = ""

    # GCS
    gcs_bucket: str = ""
    gcs_prefix: str = "vio83/"
    gcs_credentials_path: str = ""

    # Azure
    azure_container: str = ""
    azure_prefix: str = "vio83/"
    azure_connection_string: str = ""

    # Dropbox
    dropbox_token: str = ""
    dropbox_prefix: str = "/vio83/"

    # Generale
    chunk_size: int = 8 * 1024 * 1024  # 8 MB per chunk upload/download
    max_retries: int = 3
    retry_delay: float = 1.0
    verify_checksum: bool = True

    @classmethod
    def from_env(cls) -> "StorageConfig":
        """Carica configurazione da variabili d'ambiente."""
        storage_type_str = os.environ.get("VIO83_STORAGE_TYPE", "local")
        try:
            st = StorageType(storage_type_str.lower())
        except ValueError:
            st = StorageType.LOCAL

        return cls(
            storage_type=st,
            local_base_path=os.environ.get("VIO83_LOCAL_PATH", ""),
            s3_bucket=os.environ.get("VIO83_S3_BUCKET", ""),
            s3_prefix=os.environ.get("VIO83_S3_PREFIX", "vio83/"),
            s3_region=os.environ.get("VIO83_S3_REGION", "eu-south-1"),
            s3_endpoint_url=os.environ.get("VIO83_S3_ENDPOINT", ""),
            s3_access_key=os.environ.get("AWS_ACCESS_KEY_ID", ""),
            s3_secret_key=os.environ.get("AWS_SECRET_ACCESS_KEY", ""),
            gcs_bucket=os.environ.get("VIO83_GCS_BUCKET", ""),
            gcs_prefix=os.environ.get("VIO83_GCS_PREFIX", "vio83/"),
            gcs_credentials_path=os.environ.get("GOOGLE_APPLICATION_CREDENTIALS", ""),
            azure_container=os.environ.get("VIO83_AZURE_CONTAINER", ""),
            azure_prefix=os.environ.get("VIO83_AZURE_PREFIX", "vio83/"),
            azure_connection_string=os.environ.get("AZURE_STORAGE_CONNECTION_STRING", ""),
            dropbox_token=os.environ.get("VIO83_DROPBOX_TOKEN", ""),
            dropbox_prefix=os.environ.get("VIO83_DROPBOX_PREFIX", "/vio83/"),
        )


@dataclass
class StorageObject:
    """Metadati di un oggetto nello storage."""
    key: str
    size: int = 0
    last_modified: float = 0.0
    etag: str = ""
    content_type: str = "application/octet-stream"
    metadata: Dict[str, str] = field(default_factory=dict)


# ═══════════════════════════════════════════════════════
# Interfaccia Astratta
# ═══════════════════════════════════════════════════════

class StorageBackend(ABC):
    """
    Interfaccia astratta per tutti i backend di storage.
    Ogni adapter DEVE implementare tutti i metodi.
    """

    def __init__(self, config: StorageConfig):
        self.config = config

    @abstractmethod
    def put(self, key: str, data: Union[bytes, BinaryIO], metadata: Optional[Dict[str, str]] = None) -> StorageObject:
        """Upload di un oggetto."""
        ...

    @abstractmethod
    def get(self, key: str) -> bytes:
        """Download completo di un oggetto."""
        ...

    @abstractmethod
    def get_stream(self, key: str) -> Generator[bytes, None, None]:
        """Download streaming (chunked)."""
        ...

    @abstractmethod
    def delete(self, key: str) -> bool:
        """Elimina un oggetto."""
        ...

    @abstractmethod
    def exists(self, key: str) -> bool:
        """Verifica esistenza."""
        ...

    @abstractmethod
    def list_objects(self, prefix: str = "", limit: int = 1000) -> List[StorageObject]:
        """Lista oggetti con prefisso."""
        ...

    @abstractmethod
    def head(self, key: str) -> Optional[StorageObject]:
        """Metadati senza download."""
        ...

    @abstractmethod
    def copy(self, src_key: str, dst_key: str) -> StorageObject:
        """Copia intra-storage."""
        ...

    def put_json(self, key: str, data: Any, metadata: Optional[Dict[str, str]] = None) -> StorageObject:
        """Convenience: upload JSON."""
        raw = json.dumps(data, ensure_ascii=False, default=str).encode("utf-8")
        meta = metadata or {}
        meta["content-type"] = "application/json"
        return self.put(key, raw, meta)

    def get_json(self, key: str) -> Any:
        """Convenience: download + parse JSON."""
        raw = self.get(key)
        return json.loads(raw.decode("utf-8"))

    def _compute_checksum(self, data: bytes) -> str:
        return hashlib.md5(data).hexdigest()

    def _retry(self, fn, *args, **kwargs):
        """Retry con backoff esponenziale."""
        last_err = None
        for attempt in range(self.config.max_retries):
            try:
                return fn(*args, **kwargs)
            except Exception as e:
                last_err = e
                delay = self.config.retry_delay * (2 ** attempt)
                logger.warning(f"Tentativo {attempt+1}/{self.config.max_retries} fallito: {e}. Retry in {delay}s")
                time.sleep(delay)
        raise last_err  # type: ignore


# ═══════════════════════════════════════════════════════
# 1. LOCAL STORAGE
# ═══════════════════════════════════════════════════════

class LocalStorage(StorageBackend):
    """Storage su filesystem locale. Zero dipendenze esterne."""

    def __init__(self, config: StorageConfig):
        super().__init__(config)
        base = config.local_base_path or os.path.join(
            os.path.expanduser("~"), ".vio83", "storage"
        )
        self.base_path = Path(base)
        self.base_path.mkdir(parents=True, exist_ok=True)
        logger.info(f"LocalStorage inizializzato: {self.base_path}")

    def _full_path(self, key: str) -> Path:
        safe_key = key.lstrip("/")
        return self.base_path / safe_key

    def put(self, key: str, data: Union[bytes, BinaryIO], metadata: Optional[Dict[str, str]] = None) -> StorageObject:
        path = self._full_path(key)
        path.parent.mkdir(parents=True, exist_ok=True)

        if isinstance(data, bytes):
            raw = data
        else:
            raw = data.read()

        path.write_bytes(raw)

        # Salva metadata se presente
        if metadata:
            meta_path = Path(str(path) + ".meta.json")
            meta_path.write_text(json.dumps(metadata, ensure_ascii=False))

        stat = path.stat()
        return StorageObject(
            key=key,
            size=stat.st_size,
            last_modified=stat.st_mtime,
            etag=self._compute_checksum(raw),
            metadata=metadata or {},
        )

    def get(self, key: str) -> bytes:
        path = self._full_path(key)
        if not path.exists():
            raise FileNotFoundError(f"Oggetto non trovato: {key}")
        return path.read_bytes()

    def get_stream(self, key: str) -> Generator[bytes, None, None]:
        path = self._full_path(key)
        if not path.exists():
            raise FileNotFoundError(f"Oggetto non trovato: {key}")
        with open(path, "rb") as f:
            while True:
                chunk = f.read(self.config.chunk_size)
                if not chunk:
                    break
                yield chunk

    def delete(self, key: str) -> bool:
        path = self._full_path(key)
        if path.exists():
            path.unlink()
            meta = Path(str(path) + ".meta.json")
            if meta.exists():
                meta.unlink()
            return True
        return False

    def exists(self, key: str) -> bool:
        return self._full_path(key).exists()

    def list_objects(self, prefix: str = "", limit: int = 1000) -> List[StorageObject]:
        search_path = self._full_path(prefix) if prefix else self.base_path
        results: List[StorageObject] = []

        if not search_path.exists():
            return results

        if search_path.is_file():
            stat = search_path.stat()
            results.append(StorageObject(key=prefix, size=stat.st_size, last_modified=stat.st_mtime))
            return results

        for item in sorted(search_path.rglob("*")):
            if item.is_file() and not item.name.endswith(".meta.json"):
                rel = str(item.relative_to(self.base_path))
                stat = item.stat()
                results.append(StorageObject(key=rel, size=stat.st_size, last_modified=stat.st_mtime))
                if len(results) >= limit:
                    break
        return results

    def head(self, key: str) -> Optional[StorageObject]:
        path = self._full_path(key)
        if not path.exists():
            return None
        stat = path.stat()
        metadata = {}
        meta_path = Path(str(path) + ".meta.json")
        if meta_path.exists():
            metadata = json.loads(meta_path.read_text())
        return StorageObject(key=key, size=stat.st_size, last_modified=stat.st_mtime, metadata=metadata)

    def copy(self, src_key: str, dst_key: str) -> StorageObject:
        src_path = self._full_path(src_key)
        dst_path = self._full_path(dst_key)
        dst_path.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(str(src_path), str(dst_path))
        stat = dst_path.stat()
        return StorageObject(key=dst_key, size=stat.st_size, last_modified=stat.st_mtime)

    def disk_usage(self) -> Dict[str, Any]:
        """Statistiche disco locale."""
        total_size = 0
        file_count = 0
        for f in self.base_path.rglob("*"):
            if f.is_file() and not f.name.endswith(".meta.json"):
                total_size += f.stat().st_size
                file_count += 1
        usage = shutil.disk_usage(str(self.base_path))
        return {
            "stored_files": file_count,
            "stored_bytes": total_size,
            "stored_gb": round(total_size / (1024**3), 2),
            "disk_total_gb": round(usage.total / (1024**3), 2),
            "disk_free_gb": round(usage.free / (1024**3), 2),
            "disk_used_pct": round((usage.used / usage.total) * 100, 1),
        }


# ═══════════════════════════════════════════════════════
# 2. S3 STORAGE (Amazon S3 / MinIO)
# ═══════════════════════════════════════════════════════

class S3Storage(StorageBackend):
    """
    Amazon S3 / MinIO / qualsiasi S3-compatibile.
    Richiede: pip install boto3
    """

    def __init__(self, config: StorageConfig):
        super().__init__(config)
        try:
            import boto3
            from botocore.config import Config as BotoConfig
        except ImportError:
            raise ImportError(
                "boto3 richiesto per S3Storage. Installa con: pip install boto3"
            )

        kwargs: Dict[str, Any] = {
            "region_name": config.s3_region,
            "config": BotoConfig(
                retries={"max_attempts": config.max_retries, "mode": "adaptive"},
                max_pool_connections=50,
            ),
        }
        if config.s3_endpoint_url:
            kwargs["endpoint_url"] = config.s3_endpoint_url
        if config.s3_access_key:
            kwargs["aws_access_key_id"] = config.s3_access_key
            kwargs["aws_secret_access_key"] = config.s3_secret_key

        self._client = boto3.client("s3", **kwargs)
        self._bucket = config.s3_bucket
        self._prefix = config.s3_prefix.rstrip("/") + "/"
        logger.info(f"S3Storage inizializzato: s3://{self._bucket}/{self._prefix}")

    def _full_key(self, key: str) -> str:
        return self._prefix + key.lstrip("/")

    def put(self, key: str, data: Union[bytes, BinaryIO], metadata: Optional[Dict[str, str]] = None) -> StorageObject:
        full_key = self._full_key(key)
        extra: Dict[str, Any] = {}
        if metadata:
            extra["Metadata"] = metadata

        if isinstance(data, bytes):
            self._client.put_object(Bucket=self._bucket, Key=full_key, Body=data, **extra)
            size = len(data)
            etag = self._compute_checksum(data)
        else:
            self._client.upload_fileobj(data, self._bucket, full_key, ExtraArgs=extra)
            size = 0
            etag = ""

        return StorageObject(key=key, size=size, etag=etag, metadata=metadata or {})

    def get(self, key: str) -> bytes:
        full_key = self._full_key(key)
        response = self._client.get_object(Bucket=self._bucket, Key=full_key)
        return response["Body"].read()

    def get_stream(self, key: str) -> Generator[bytes, None, None]:
        full_key = self._full_key(key)
        response = self._client.get_object(Bucket=self._bucket, Key=full_key)
        stream = response["Body"]
        while True:
            chunk = stream.read(self.config.chunk_size)
            if not chunk:
                break
            yield chunk

    def delete(self, key: str) -> bool:
        full_key = self._full_key(key)
        self._client.delete_object(Bucket=self._bucket, Key=full_key)
        return True

    def exists(self, key: str) -> bool:
        full_key = self._full_key(key)
        try:
            self._client.head_object(Bucket=self._bucket, Key=full_key)
            return True
        except Exception:
            return False

    def list_objects(self, prefix: str = "", limit: int = 1000) -> List[StorageObject]:
        full_prefix = self._full_key(prefix)
        results: List[StorageObject] = []
        paginator = self._client.get_paginator("list_objects_v2")

        for page in paginator.paginate(Bucket=self._bucket, Prefix=full_prefix, PaginationConfig={"MaxItems": limit}):
            for obj in page.get("Contents", []):
                rel_key = obj["Key"][len(self._prefix):]
                results.append(StorageObject(
                    key=rel_key,
                    size=obj["Size"],
                    last_modified=obj["LastModified"].timestamp(),
                    etag=obj.get("ETag", "").strip('"'),
                ))
        return results

    def head(self, key: str) -> Optional[StorageObject]:
        full_key = self._full_key(key)
        try:
            resp = self._client.head_object(Bucket=self._bucket, Key=full_key)
            return StorageObject(
                key=key,
                size=resp["ContentLength"],
                last_modified=resp["LastModified"].timestamp(),
                etag=resp.get("ETag", "").strip('"'),
                content_type=resp.get("ContentType", ""),
                metadata=resp.get("Metadata", {}),
            )
        except Exception:
            return None

    def copy(self, src_key: str, dst_key: str) -> StorageObject:
        src_full = self._full_key(src_key)
        dst_full = self._full_key(dst_key)
        self._client.copy_object(
            Bucket=self._bucket,
            CopySource={"Bucket": self._bucket, "Key": src_full},
            Key=dst_full,
        )
        head = self.head(dst_key)
        return head or StorageObject(key=dst_key)

    def multipart_upload(self, key: str, file_path: str, part_size: int = 50 * 1024 * 1024) -> StorageObject:
        """Upload multipart per file enormi (>5GB supportati)."""
        full_key = self._full_key(key)
        file_size = os.path.getsize(file_path)

        mpu = self._client.create_multipart_upload(Bucket=self._bucket, Key=full_key)
        upload_id = mpu["UploadId"]
        parts = []

        try:
            with open(file_path, "rb") as f:
                part_num = 1
                while True:
                    chunk = f.read(part_size)
                    if not chunk:
                        break
                    resp = self._client.upload_part(
                        Bucket=self._bucket, Key=full_key,
                        UploadId=upload_id, PartNumber=part_num, Body=chunk,
                    )
                    parts.append({"PartNumber": part_num, "ETag": resp["ETag"]})
                    logger.info(f"Parte {part_num} caricata ({len(chunk)} bytes)")
                    part_num += 1

            self._client.complete_multipart_upload(
                Bucket=self._bucket, Key=full_key, UploadId=upload_id,
                MultipartUpload={"Parts": parts},
            )
        except Exception as e:
            self._client.abort_multipart_upload(Bucket=self._bucket, Key=full_key, UploadId=upload_id)
            raise e

        return StorageObject(key=key, size=file_size)


# ═══════════════════════════════════════════════════════
# 3. GCS STORAGE (Google Cloud Storage)
# ═══════════════════════════════════════════════════════

class GCSStorage(StorageBackend):
    """
    Google Cloud Storage.
    Richiede: pip install google-cloud-storage
    """

    def __init__(self, config: StorageConfig):
        super().__init__(config)
        try:
            from google.cloud import storage as gcs
        except ImportError:
            raise ImportError(
                "google-cloud-storage richiesto per GCSStorage. "
                "Installa con: pip install google-cloud-storage"
            )

        if config.gcs_credentials_path:
            client = gcs.Client.from_service_account_json(config.gcs_credentials_path)
        else:
            client = gcs.Client()

        self._client = client
        self._bucket = client.bucket(config.gcs_bucket)
        self._prefix = config.gcs_prefix.rstrip("/") + "/"
        logger.info(f"GCSStorage inizializzato: gs://{config.gcs_bucket}/{self._prefix}")

    def _full_key(self, key: str) -> str:
        return self._prefix + key.lstrip("/")

    def put(self, key: str, data: Union[bytes, BinaryIO], metadata: Optional[Dict[str, str]] = None) -> StorageObject:
        blob = self._bucket.blob(self._full_key(key))
        if metadata:
            blob.metadata = metadata

        if isinstance(data, bytes):
            blob.upload_from_string(data)
            size = len(data)
        else:
            blob.upload_from_file(data)
            size = blob.size or 0

        return StorageObject(key=key, size=size, metadata=metadata or {})

    def get(self, key: str) -> bytes:
        blob = self._bucket.blob(self._full_key(key))
        return blob.download_as_bytes()

    def get_stream(self, key: str) -> Generator[bytes, None, None]:
        blob = self._bucket.blob(self._full_key(key))
        buf = io.BytesIO()
        blob.download_to_file(buf)
        buf.seek(0)
        while True:
            chunk = buf.read(self.config.chunk_size)
            if not chunk:
                break
            yield chunk

    def delete(self, key: str) -> bool:
        blob = self._bucket.blob(self._full_key(key))
        try:
            blob.delete()
            return True
        except Exception:
            return False

    def exists(self, key: str) -> bool:
        blob = self._bucket.blob(self._full_key(key))
        return blob.exists()

    def list_objects(self, prefix: str = "", limit: int = 1000) -> List[StorageObject]:
        full_prefix = self._full_key(prefix)
        results: List[StorageObject] = []
        for blob in self._bucket.list_blobs(prefix=full_prefix, max_results=limit):
            rel_key = blob.name[len(self._prefix):]
            results.append(StorageObject(
                key=rel_key,
                size=blob.size or 0,
                last_modified=blob.updated.timestamp() if blob.updated else 0,
                etag=blob.etag or "",
            ))
        return results

    def head(self, key: str) -> Optional[StorageObject]:
        blob = self._bucket.blob(self._full_key(key))
        if not blob.exists():
            return None
        blob.reload()
        return StorageObject(
            key=key,
            size=blob.size or 0,
            last_modified=blob.updated.timestamp() if blob.updated else 0,
            etag=blob.etag or "",
            content_type=blob.content_type or "",
            metadata=dict(blob.metadata or {}),
        )

    def copy(self, src_key: str, dst_key: str) -> StorageObject:
        src_blob = self._bucket.blob(self._full_key(src_key))
        self._bucket.copy_blob(src_blob, self._bucket, self._full_key(dst_key))
        return self.head(dst_key) or StorageObject(key=dst_key)


# ═══════════════════════════════════════════════════════
# 4. AZURE BLOB STORAGE
# ═══════════════════════════════════════════════════════

class AzureStorage(StorageBackend):
    """
    Azure Blob Storage.
    Richiede: pip install azure-storage-blob
    """

    def __init__(self, config: StorageConfig):
        super().__init__(config)
        try:
            from azure.storage.blob import BlobServiceClient
        except ImportError:
            raise ImportError(
                "azure-storage-blob richiesto per AzureStorage. "
                "Installa con: pip install azure-storage-blob"
            )

        self._service = BlobServiceClient.from_connection_string(config.azure_connection_string)
        self._container = self._service.get_container_client(config.azure_container)
        self._prefix = config.azure_prefix.rstrip("/") + "/"
        logger.info(f"AzureStorage inizializzato: {config.azure_container}/{self._prefix}")

    def _full_key(self, key: str) -> str:
        return self._prefix + key.lstrip("/")

    def put(self, key: str, data: Union[bytes, BinaryIO], metadata: Optional[Dict[str, str]] = None) -> StorageObject:
        blob_client = self._container.get_blob_client(self._full_key(key))
        if isinstance(data, bytes):
            blob_client.upload_blob(data, overwrite=True, metadata=metadata)
            size = len(data)
        else:
            blob_client.upload_blob(data, overwrite=True, metadata=metadata)
            size = 0
        return StorageObject(key=key, size=size, metadata=metadata or {})

    def get(self, key: str) -> bytes:
        blob_client = self._container.get_blob_client(self._full_key(key))
        return blob_client.download_blob().readall()

    def get_stream(self, key: str) -> Generator[bytes, None, None]:
        blob_client = self._container.get_blob_client(self._full_key(key))
        stream = blob_client.download_blob()
        for chunk in stream.chunks():
            yield chunk

    def delete(self, key: str) -> bool:
        blob_client = self._container.get_blob_client(self._full_key(key))
        try:
            blob_client.delete_blob()
            return True
        except Exception:
            return False

    def exists(self, key: str) -> bool:
        blob_client = self._container.get_blob_client(self._full_key(key))
        try:
            blob_client.get_blob_properties()
            return True
        except Exception:
            return False

    def list_objects(self, prefix: str = "", limit: int = 1000) -> List[StorageObject]:
        full_prefix = self._full_key(prefix)
        results: List[StorageObject] = []
        for blob in self._container.list_blobs(name_starts_with=full_prefix):
            rel_key = blob.name[len(self._prefix):]
            results.append(StorageObject(
                key=rel_key,
                size=blob.size or 0,
                last_modified=blob.last_modified.timestamp() if blob.last_modified else 0,
                etag=blob.etag or "",
            ))
            if len(results) >= limit:
                break
        return results

    def head(self, key: str) -> Optional[StorageObject]:
        blob_client = self._container.get_blob_client(self._full_key(key))
        try:
            props = blob_client.get_blob_properties()
            return StorageObject(
                key=key,
                size=props.size or 0,
                last_modified=props.last_modified.timestamp() if props.last_modified else 0,
                etag=props.etag or "",
                content_type=props.content_settings.content_type if props.content_settings else "",
                metadata=dict(props.metadata or {}),
            )
        except Exception:
            return None

    def copy(self, src_key: str, dst_key: str) -> StorageObject:
        src_blob = self._container.get_blob_client(self._full_key(src_key))
        dst_blob = self._container.get_blob_client(self._full_key(dst_key))
        dst_blob.start_copy_from_url(src_blob.url)
        return self.head(dst_key) or StorageObject(key=dst_key)


# ═══════════════════════════════════════════════════════
# 5. DROPBOX STORAGE
# ═══════════════════════════════════════════════════════

class DropboxStorage(StorageBackend):
    """
    Dropbox API v2.
    Richiede: pip install dropbox
    """

    def __init__(self, config: StorageConfig):
        super().__init__(config)
        try:
            import dropbox as dbx_mod
        except ImportError:
            raise ImportError(
                "dropbox richiesto per DropboxStorage. Installa con: pip install dropbox"
            )

        self._dbx = dbx_mod.Dropbox(config.dropbox_token)
        self._prefix = config.dropbox_prefix.rstrip("/") + "/"
        logger.info(f"DropboxStorage inizializzato: {self._prefix}")

    def _full_path(self, key: str) -> str:
        return self._prefix + key.lstrip("/")

    def put(self, key: str, data: Union[bytes, BinaryIO], metadata: Optional[Dict[str, str]] = None) -> StorageObject:
        import dropbox
        path = self._full_path(key)
        if isinstance(data, bytes):
            raw = data
        else:
            raw = data.read()

        if len(raw) <= 150 * 1024 * 1024:
            result = self._dbx.files_upload(raw, path, mode=dropbox.files.WriteMode.overwrite)
        else:
            # Sessione upload per file grandi
            session = self._dbx.files_upload_session_start(raw[:self.config.chunk_size])
            cursor = dropbox.files.UploadSessionCursor(session_id=session.session_id, offset=self.config.chunk_size)
            commit = dropbox.files.CommitInfo(path=path, mode=dropbox.files.WriteMode.overwrite)

            offset = self.config.chunk_size
            while offset < len(raw):
                end = min(offset + self.config.chunk_size, len(raw))
                if end < len(raw):
                    self._dbx.files_upload_session_append_v2(raw[offset:end], cursor)
                    cursor.offset = end
                else:
                    result = self._dbx.files_upload_session_finish(raw[offset:end], cursor, commit)
                offset = end

        return StorageObject(key=key, size=len(raw))

    def get(self, key: str) -> bytes:
        path = self._full_path(key)
        _, response = self._dbx.files_download(path)
        return response.content

    def get_stream(self, key: str) -> Generator[bytes, None, None]:
        data = self.get(key)
        offset = 0
        while offset < len(data):
            yield data[offset:offset + self.config.chunk_size]
            offset += self.config.chunk_size

    def delete(self, key: str) -> bool:
        path = self._full_path(key)
        try:
            self._dbx.files_delete_v2(path)
            return True
        except Exception:
            return False

    def exists(self, key: str) -> bool:
        path = self._full_path(key)
        try:
            self._dbx.files_get_metadata(path)
            return True
        except Exception:
            return False

    def list_objects(self, prefix: str = "", limit: int = 1000) -> List[StorageObject]:
        import dropbox
        path = self._full_path(prefix).rstrip("/")
        if not path:
            path = ""
        results: List[StorageObject] = []
        try:
            resp = self._dbx.files_list_folder(path, limit=min(limit, 2000))
            for entry in resp.entries:
                if isinstance(entry, dropbox.files.FileMetadata):
                    rel_key = entry.path_display[len(self._prefix):]
                    results.append(StorageObject(
                        key=rel_key,
                        size=entry.size,
                        last_modified=entry.server_modified.timestamp() if entry.server_modified else 0,
                    ))
            while resp.has_more and len(results) < limit:
                resp = self._dbx.files_list_folder_continue(resp.cursor)
                for entry in resp.entries:
                    if isinstance(entry, dropbox.files.FileMetadata):
                        rel_key = entry.path_display[len(self._prefix):]
                        results.append(StorageObject(key=rel_key, size=entry.size))
        except Exception:
            pass
        return results[:limit]

    def head(self, key: str) -> Optional[StorageObject]:
        import dropbox
        path = self._full_path(key)
        try:
            meta = self._dbx.files_get_metadata(path)
            if isinstance(meta, dropbox.files.FileMetadata):
                return StorageObject(
                    key=key,
                    size=meta.size,
                    last_modified=meta.server_modified.timestamp() if meta.server_modified else 0,
                )
            return StorageObject(key=key)
        except Exception:
            return None

    def copy(self, src_key: str, dst_key: str) -> StorageObject:
        src_path = self._full_path(src_key)
        dst_path = self._full_path(dst_key)
        self._dbx.files_copy_v2(src_path, dst_path)
        return self.head(dst_key) or StorageObject(key=dst_key)


# ═══════════════════════════════════════════════════════
# FACTORY + SINGLETON
# ═══════════════════════════════════════════════════════

_STORAGE_MAP = {
    StorageType.LOCAL: LocalStorage,
    StorageType.S3: S3Storage,
    StorageType.GCS: GCSStorage,
    StorageType.AZURE: AzureStorage,
    StorageType.DROPBOX: DropboxStorage,
}

_instance: Optional[StorageBackend] = None


def get_storage(config: Optional[StorageConfig] = None) -> StorageBackend:
    """
    Factory + Singleton per ottenere il backend di storage.

    Uso:
        # Default (da env vars)
        storage = get_storage()

        # Esplicito
        storage = get_storage(StorageConfig(storage_type=StorageType.S3, s3_bucket="my-bucket"))
    """
    global _instance
    if _instance is None:
        if config is None:
            config = StorageConfig.from_env()
        backend_cls = _STORAGE_MAP.get(config.storage_type)
        if backend_cls is None:
            raise ValueError(f"Storage type non supportato: {config.storage_type}")
        _instance = backend_cls(config)
    return _instance


def reset_storage() -> None:
    """Reset singleton (per testing)."""
    global _instance
    _instance = None


# ═══════════════════════════════════════════════════════
# TIERED STORAGE (hot/warm/cold)
# ═══════════════════════════════════════════════════════

class TieredStorage:
    """
    Storage a 3 livelli: hot (locale SSD), warm (S3/GCS), cold (Glacier/Archive).
    Automatizza il tiering basato su frequenza di accesso.
    """

    def __init__(
        self,
        hot: StorageBackend,
        warm: Optional[StorageBackend] = None,
        cold: Optional[StorageBackend] = None,
        hot_max_gb: float = 50.0,
    ):
        self.hot = hot
        self.warm = warm
        self.cold = cold
        self.hot_max_bytes = int(hot_max_gb * 1024**3)
        self._access_log: Dict[str, int] = {}  # key -> access count

    def get(self, key: str) -> bytes:
        """Cerca nel tier più veloce, poi scende."""
        self._access_log[key] = self._access_log.get(key, 0) + 1

        # Hot (locale)
        if self.hot.exists(key):
            return self.hot.get(key)

        # Warm (cloud standard)
        if self.warm and self.warm.exists(key):
            data = self.warm.get(key)
            # Promuovi a hot se accesso frequente
            if self._access_log.get(key, 0) >= 3:
                self.hot.put(key, data)
            return data

        # Cold (archivio)
        if self.cold and self.cold.exists(key):
            data = self.cold.get(key)
            # Promuovi a warm
            if self.warm:
                self.warm.put(key, data)
            return data

        raise FileNotFoundError(f"Oggetto non trovato in nessun tier: {key}")

    def put(self, key: str, data: Union[bytes, BinaryIO], tier: str = "hot") -> StorageObject:
        """Inserisci nel tier specificato."""
        if tier == "hot":
            return self.hot.put(key, data)
        elif tier == "warm" and self.warm:
            return self.warm.put(key, data)
        elif tier == "cold" and self.cold:
            return self.cold.put(key, data)
        return self.hot.put(key, data)

    def evict_cold(self, max_age_days: int = 90) -> int:
        """Sposta da hot a warm gli oggetti meno usati."""
        if not self.warm:
            return 0

        objects = self.hot.list_objects(limit=10000)
        evicted = 0
        cutoff = time.time() - (max_age_days * 86400)

        for obj in objects:
            if obj.last_modified < cutoff and self._access_log.get(obj.key, 0) < 3:
                data = self.hot.get(obj.key)
                self.warm.put(obj.key, data)
                self.hot.delete(obj.key)
                evicted += 1
                logger.info(f"Evicted to warm: {obj.key}")

        return evicted

    def stats(self) -> Dict[str, Any]:
        hot_objects = self.hot.list_objects(limit=100000)
        hot_size = sum(o.size for o in hot_objects)
        result = {
            "hot": {"count": len(hot_objects), "size_gb": round(hot_size / 1024**3, 2)},
        }
        if self.warm:
            warm_objects = self.warm.list_objects(limit=100000)
            warm_size = sum(o.size for o in warm_objects)
            result["warm"] = {"count": len(warm_objects), "size_gb": round(warm_size / 1024**3, 2)}
        if self.cold:
            cold_objects = self.cold.list_objects(limit=100000)
            cold_size = sum(o.size for o in cold_objects)
            result["cold"] = {"count": len(cold_objects), "size_gb": round(cold_size / 1024**3, 2)}
        return result
