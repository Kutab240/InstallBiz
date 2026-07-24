import asyncio
import io
import zipfile
from datetime import datetime
from zoneinfo import ZoneInfo

import httpx

from models import DownloadedFile, DownloadProgress

API_BASE = "http://91.199.149.128:18001"
CANDIDATE_ID = "anatoly-python-001"
NSK = ZoneInfo("Asia/Novosibirsk")
BATCH_SIZE = 3
PAUSE_BETWEEN_BATCHES = 2.0


class DownloadService:
    def __init__(self):
        self.files: list[DownloadedFile] = []
        self.is_running = False
        self.progress = DownloadProgress(
            status="idle", found=0, downloaded=0, start_time=None, error=None, total=0
        )

    async def _request(self, client: httpx.AsyncClient, method: str, url: str, **kwargs):
        while True:
            response = await client.request(
                method,
                API_BASE + url,
                headers={"X-Candidate-Id": CANDIDATE_ID},
                timeout=15.0,
                **kwargs,
            )
            if response.status_code in (429, 403):
                retry_after = int(response.headers.get("retry-after", "10"))
                print(f"Rate limited ({response.status_code}), waiting {retry_after}s...")
                await asyncio.sleep(retry_after + 1)
                continue
            response.raise_for_status()
            return response

    async def _fetch_names(self, client: httpx.AsyncClient) -> list[str]:
        resp = await self._request(client, "GET", "/api/files/names")
        return resp.json().get("file_names", [])

    async def _download_batch(self, client: httpx.AsyncClient, batch: list[str]) -> list[DownloadedFile]:
        resp = await self._request(client, "POST", "/api/files/download", json={"file_names": batch})
        downloaded_at = datetime.now(NSK)
        result = []
        with zipfile.ZipFile(io.BytesIO(resp.content)) as zf:
            for name in zf.namelist():
                content = zf.read(name).decode("utf-8").strip()
                result.append(DownloadedFile(name=name, content=content, downloaded_at=downloaded_at))
        return result

    async def _mark_downloaded(self, client: httpx.AsyncClient, batch: list[str]):
        await self._request(client, "POST", "/api/files/downloaded", json={"file_names": batch})

    async def run(self):
        self.is_running = True
        self.files = []
        self.progress = DownloadProgress(
            status="running",
            found=0,
            downloaded=0,
            start_time=datetime.now(NSK).isoformat(),
            error=None,
            total=0,
        )

        try:
            async with httpx.AsyncClient() as client:
                while True:
                    names = await self._fetch_names(client)
                    if not names:
                        break

                    self.progress.found += len(names)
                    print(f"Got {len(names)} names, total found: {self.progress.found}")

                    for i in range(0, len(names), BATCH_SIZE):
                        batch = names[i : i + BATCH_SIZE]
                        downloaded = await self._download_batch(client, batch)
                        self.files.extend(downloaded)
                        await self._mark_downloaded(client, batch)
                        self.progress.downloaded += len(batch)
                        self.progress.total = len(self.files)
                        print(f"Downloaded and marked: {self.progress.downloaded} files")
                        await asyncio.sleep(PAUSE_BETWEEN_BATCHES)

            self.progress.status = "done"
            print(f"Done. Total files: {len(self.files)}")

        except Exception as e:
            self.progress.status = "error"
            self.progress.error = str(e)
            print(f"Error: {e}")
        finally:
            self.is_running = False

    def get_progress(self) -> DownloadProgress:
        self.progress.total = len(self.files)
        return self.progress

    def get_files(self, page: int, limit: int):
        sorted_files = sorted(self.files, key=lambda f: f.downloaded_at)
        total = len(sorted_files)
        items = sorted_files[(page - 1) * limit : page * limit]
        return items, total
