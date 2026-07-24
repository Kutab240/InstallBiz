import asyncio
import io
import zipfile
from datetime import datetime
from typing import Optional
from zoneinfo import ZoneInfo

import httpx
from fastapi import FastAPI
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

app = FastAPI()

API_BASE = "http://91.199.149.128:18001"
CANDIDATE_ID = "anatoly-python-001"
NSK = ZoneInfo("Asia/Novosibirsk")

downloaded_files: list[dict] = []
is_downloading = False
progress = {"status": "idle", "found": 0, "downloaded": 0, "start_time": None, "error": None}


async def api_request(client: httpx.AsyncClient, method: str, url: str, **kwargs):
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


async def download_all():
    global is_downloading, downloaded_files, progress

    is_downloading = True
    downloaded_files = []
    progress = {
        "status": "running",
        "found": 0,
        "downloaded": 0,
        "start_time": datetime.now(NSK).isoformat(),
        "error": None,
    }

    try:
        async with httpx.AsyncClient() as client:
            while True:
                resp = await api_request(client, "GET", "/api/files/names")
                names: list[str] = resp.json().get("file_names", [])

                if not names:
                    break

                progress["found"] += len(names)
                print(f"Got {len(names)} names, total: {progress['found']}")

                for i in range(0, len(names), 3):
                    batch = names[i : i + 3]

                    zip_resp = await api_request(
                        client, "POST", "/api/files/download", json={"file_names": batch}
                    )

                    downloaded_at = datetime.now(NSK).isoformat()
                    with zipfile.ZipFile(io.BytesIO(zip_resp.content)) as zf:
                        for name in zf.namelist():
                            content = zf.read(name).decode("utf-8").strip()
                            downloaded_files.append(
                                {"name": name, "content": content, "downloaded_at": downloaded_at}
                            )

                    await api_request(
                        client, "POST", "/api/files/downloaded", json={"file_names": batch}
                    )
                    progress["downloaded"] += len(batch)
                    print(f"Marked as downloaded: {progress['downloaded']} total")

                    await asyncio.sleep(2)

        progress["status"] = "done"
        print(f"Done. Total files: {len(downloaded_files)}")

    except Exception as e:
        progress["status"] = "error"
        progress["error"] = str(e)
        print(f"Error: {e}")
    finally:
        is_downloading = False


@app.post("/api/download")
async def start_download():
    if not is_downloading:
        asyncio.create_task(download_all())
    return {"ok": True}


@app.get("/api/progress")
async def get_progress():
    return {**progress, "total": len(downloaded_files)}


@app.get("/api/files")
async def get_files(page: int = 1, limit: int = 20):
    sorted_files = sorted(downloaded_files, key=lambda f: f["downloaded_at"])
    total = len(sorted_files)
    items = sorted_files[(page - 1) * limit : page * limit]
    return {
        "items": [{"name": f["name"], "downloaded_at": f["downloaded_at"]} for f in items],
        "total": total,
        "page": page,
        "limit": limit,
        "pages": max(1, -(-total // limit)),
    }


class CalcRequest(BaseModel):
    names: list[str]


@app.post("/api/calculate")
async def calculate(req: CalcRequest):
    selected = [f for f in downloaded_files if f["name"] in req.names]
    total_counts = {str(d): 0 for d in range(10)}
    file_counts: dict[str, dict] = {}

    for f in selected:
        counts = {str(d): 0 for d in range(10)}
        for ch in f["content"]:
            if ch.isdigit():
                counts[ch] += 1
                total_counts[ch] += 1
        file_counts[f["name"]] = counts

    return {"total": total_counts, "files": file_counts}


app.mount("/", StaticFiles(directory="static", html=True), name="static")
