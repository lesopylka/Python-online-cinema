"""
Клиент для работы с объектным хранилищем (S3/MinIO).
"""

import logging
import boto3
from botocore.client import Config
from botocore.exceptions import ClientError
from typing import Optional, Dict, Any, BinaryIO, List
from datetime import datetime, timedelta
from uuid import UUID
import io

from src.config.settings import settings

logger = logging.getLogger(__name__)


class StorageClient:
    """
    Клиент для работы с S3-совместимым хранилищем.
    
    Attributes:
        client: boto3 S3 client
        bucket_media: Бакет для медиа файлов
        bucket_thumbnails: Бакет для миниатюр
        endpoint_url: URL хранилища
    """
    
    def __init__(self):
        self.endpoint_url = f"http://{settings.S3_ENDPOINT}"
        self.bucket_media = settings.S3_BUCKET_MEDIA
        self.bucket_thumbnails = settings.S3_BUCKET_THUMBNAILS
        
        try:
            self.client = boto3.client(
                's3',
                endpoint_url=self.endpoint_url,
                aws_access_key_id=settings.S3_ACCESS_KEY,
                aws_secret_access_key=settings.S3_SECRET_KEY,
                config=Config(signature_version='s3v4'),
                verify=False
            )
            
            # Создаем бакеты если не существуют
            self._create_bucket_if_not_exists(self.bucket_media)
            self._create_bucket_if_not_exists(self.bucket_thumbnails)
            
            logger.info(f"Connected to storage at {self.endpoint_url}")
            
        except Exception as e:
            logger.error(f"Failed to connect to storage: {e}")
            raise
    
    def _create_bucket_if_not_exists(self, bucket_name: str):
        """Создание бакета если не существует."""
        try:
            self.client.head_bucket(Bucket=bucket_name)
            logger.debug(f"Bucket {bucket_name} already exists")
        except ClientError as e:
            if e.response['Error']['Code'] == '404':
                try:
                    self.client.create_bucket(Bucket=bucket_name)
                    logger.info(f"Bucket {bucket_name} created")
                except Exception as create_error:
                    logger.error(f"Failed to create bucket {bucket_name}: {create_error}")
            else:
                logger.error(f"Error checking bucket {bucket_name}: {e}")
    
    def generate_presigned_url(
        self,
        bucket: str,
        key: str,
        expiration: int = 3600,
        method: str = 'get_object'
    ) -> Optional[str]:
        """
        Генерация предварительно подписанного URL.
        
        Args:
            bucket: Название бакета
            key: Ключ объекта
            expiration: Время жизни в секундах
            method: HTTP метод
            
        Returns:
            Предварительно подписанный URL или None
        """
        try:
            url = self.client.generate_presigned_url(
                ClientMethod=method,
                Params={'Bucket': bucket, 'Key': key},
                ExpiresIn=expiration
            )
            return url
        except ClientError as e:
            logger.error(f"Failed to generate presigned URL for {bucket}/{key}: {e}")
            return None
    
    def upload_file(
        self,
        bucket: str,
        key: str,
        file_path: str,
        metadata: Optional[Dict[str, str]] = None
    ) -> bool:
        """
        Загрузка файла в хранилище.
        
        Args:
            bucket: Название бакета
            key: Ключ объекта
            file_path: Путь к файлу
            metadata: Метаданные
            
        Returns:
            True если успешно, False если ошибка
        """
        try:
            extra_args = {}
            if metadata:
                extra_args['Metadata'] = metadata
            
            self.client.upload_file(
                file_path,
                bucket,
                key,
                ExtraArgs=extra_args
            )
            
            logger.debug(f"File uploaded: {bucket}/{key}")
            return True
            
        except ClientError as e:
            logger.error(f"Failed to upload file {bucket}/{key}: {e}")
            return False
    
    def upload_fileobj(
        self,
        bucket: str,
        key: str,
        file_obj: BinaryIO,
        content_type: Optional[str] = None,
        metadata: Optional[Dict[str, str]] = None
    ) -> bool:
        """
        Загрузка файла из объекта.
        
        Args:
            bucket: Название бакета
            key: Ключ объекта
            file_obj: Объект файла
            content_type: Content-Type
            metadata: Метаданные
            
        Returns:
            True если успешно, False если ошибка
        """
        try:
            extra_args = {}
            if content_type:
                extra_args['ContentType'] = content_type
            if metadata:
                extra_args['Metadata'] = metadata
            
            self.client.upload_fileobj(
                file_obj,
                bucket,
                key,
                ExtraArgs=extra_args
            )
            
            logger.debug(f"File uploaded from object: {bucket}/{key}")
            return True
            
        except ClientError as e:
            logger.error(f"Failed to upload file object {bucket}/{key}: {e}")
            return False
    
    def download_file(
        self,
        bucket: str,
        key: str,
        file_path: str
    ) -> bool:
        """
        Скачивание файла из хранилища.
        
        Args:
            bucket: Название бакета
            key: Ключ объекта
            file_path: Путь для сохранения
            
        Returns:
            True если успешно, False если ошибка
        """
        try:
            self.client.download_file(bucket, key, file_path)
            logger.debug(f"File downloaded: {bucket}/{key}")
            return True
            
        except ClientError as e:
            logger.error(f"Failed to download file {bucket}/{key}: {e}")
            return False
    
    def download_fileobj(
        self,
        bucket: str,
        key: str
    ) -> Optional[bytes]:
        """
        Скачивание файла как объекта.
        
        Args:
            bucket: Название бакета
            key: Ключ объекта
            
        Returns:
            Данные файла или None
        """
        try:
            buffer = io.BytesIO()
            self.client.download_fileobj(bucket, key, buffer)
            buffer.seek(0)
            return buffer.read()
            
        except ClientError as e:
            logger.error(f"Failed to download file object {bucket}/{key}: {e}")
            return None
    
    def delete_file(self, bucket: str, key: str) -> bool:
        """
        Удаление файла из хранилища.
        
        Args:
            bucket: Название бакета
            key: Ключ объекта
            
        Returns:
            True если успешно, False если ошибка
        """
        try:
            self.client.delete_object(Bucket=bucket, Key=key)
            logger.debug(f"File deleted: {bucket}/{key}")
            return True
            
        except ClientError as e:
            logger.error(f"Failed to delete file {bucket}/{key}: {e}")
            return False
    
    def list_files(
        self,
        bucket: str,
        prefix: Optional[str] = None,
        max_keys: int = 1000
    ) -> List[Dict[str, Any]]:
        """
        Список файлов в бакете.
        
        Args:
            bucket: Название бакета
            prefix: Префикс для фильтрации
            max_keys: Максимальное количество
            
        Returns:
            Список файлов
        """
        try:
            params = {'Bucket': bucket, 'MaxKeys': max_keys}
            if prefix:
                params['Prefix'] = prefix
            
            response = self.client.list_objects_v2(**params)
            
            files = []
            if 'Contents' in response:
                for obj in response['Contents']:
                    files.append({
                        'key': obj['Key'],
                        'size': obj['Size'],
                        'last_modified': obj['LastModified'],
                        'etag': obj['ETag']
                    })
            
            return files
            
        except ClientError as e:
            logger.error(f"Failed to list files in bucket {bucket}: {e}")
            return []
    
    def get_file_info(
        self,
        bucket: str,
        key: str
    ) -> Optional[Dict[str, Any]]:
        """
        Получение информации о файле.
        
        Args:
            bucket: Название бакета
            key: Ключ объекта
            
        Returns:
            Информация о файле или None
        """
        try:
            response = self.client.head_object(Bucket=bucket, Key=key)
            
            return {
                'key': key,
                'size': response['ContentLength'],
                'content_type': response.get('ContentType'),
                'last_modified': response['LastModified'],
                'etag': response['ETag'],
                'metadata': response.get('Metadata', {})
            }
            
        except ClientError as e:
            logger.error(f"Failed to get file info for {bucket}/{key}: {e}")
            return None
    
    def create_multipart_upload(
        self,
        bucket: str,
        key: str,
        content_type: Optional[str] = None,
        metadata: Optional[Dict[str, str]] = None
    ) -> Optional[str]:
        """
        Создание multipart загрузки.
        
        Args:
            bucket: Название бакета
            key: Ключ объекта
            content_type: Content-Type
            metadata: Метаданные
            
        Returns:
            Upload ID или None
        """
        try:
            extra_args = {}
            if content_type:
                extra_args['ContentType'] = content_type
            if metadata:
                extra_args['Metadata'] = metadata
            
            response = self.client.create_multipart_upload(
                Bucket=bucket,
                Key=key,
                **extra_args
            )
            
            logger.debug(f"Multipart upload created: {response['UploadId']}")
            return response['UploadId']
            
        except ClientError as e:
            logger.error(f"Failed to create multipart upload for {bucket}/{key}: {e}")
            return None
    
    def complete_multipart_upload(
        self,
        bucket: str,
        key: str,
        upload_id: str,
        parts: List[Dict[str, Any]]
    ) -> bool:
        """
        Завершение multipart загрузки.
        
        Args:
            bucket: Название бакета
            key: Ключ объекта
            upload_id: ID загрузки
            parts: Список частей
            
        Returns:
            True если успешно, False если ошибка
        """
        try:
            self.client.complete_multipart_upload(
                Bucket=bucket,
                Key=key,
                UploadId=upload_id,
                MultipartUpload={'Parts': parts}
            )
            
            logger.debug(f"Multipart upload completed: {upload_id}")
            return True
            
        except ClientError as e:
            logger.error(f"Failed to complete multipart upload {upload_id}: {e}")
            return False
    
    def abort_multipart_upload(
        self,
        bucket: str,
        key: str,
        upload_id: str
    ) -> bool:
        """
        Отмена multipart загрузки.
        
        Args:
            bucket: Название бакета
            key: Ключ объекта
            upload_id: ID загрузки
            
        Returns:
            True если успешно, False если ошибка
        """
        try:
            self.client.abort_multipart_upload(
                Bucket=bucket,
                Key=key,
                UploadId=upload_id
            )
            
            logger.debug(f"Multipart upload aborted: {upload_id}")
            return True
            
        except ClientError as e:
            logger.error(f"Failed to abort multipart upload {upload_id}: {e}")
            return False
    
    def get_bucket_stats(self, bucket: str) -> Optional[Dict[str, Any]]:
        """
        Получение статистики бакета.
        
        Args:
            bucket: Название бакета
            
        Returns:
            Статистика или None
        """
        try:
            # Получаем список всех объектов
            total_size = 0
            total_files = 0
            
            paginator = self.client.get_paginator('list_objects_v2')
            for page in paginator.paginate(Bucket=bucket):
                if 'Contents' in page:
                    for obj in page['Contents']:
                        total_size += obj['Size']
                        total_files += 1
            
            return {
                'bucket': bucket,
                'total_files': total_files,
                'total_size_bytes': total_size,
                'total_size_mb': total_size / (1024 * 1024)
            }
            
        except ClientError as e:
            logger.error(f"Failed to get bucket stats for {bucket}: {e}")
            return None


# Глобальный инстанс клиента
storage_client = StorageClient()