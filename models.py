from datetime import datetime
from typing import Optional
from pydantic import BaseModel


class DownloadedFile(BaseModel):
    name: str
    content: str
    downloaded_at: datetime


class FileInfo(BaseModel):
    name: str
    downloaded_at: datetime


class FilesPage(BaseModel):
    items: list[FileInfo]
    total: int
    page: int
    limit: int
    pages: int


class DownloadProgress(BaseModel):
    status: str
    found: int
    downloaded: int
    start_time: Optional[str]
    error: Optional[str]
    total: int


class CalcRequest(BaseModel):
    names: list[str]


class CalcResult(BaseModel):
    total: dict[str, int]
    files: dict[str, dict[str, int]]
