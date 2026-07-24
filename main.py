import asyncio

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from models import CalcRequest, CalcResult, DownloadProgress, FileInfo, FilesPage
from services.calculator import CalculatorService
from services.downloader import DownloadService

app = FastAPI(title="File Downloader Service")

downloader = DownloadService()
calculator = CalculatorService()


@app.post("/api/download")
async def start_download():
    if not downloader.is_running:
        asyncio.create_task(downloader.run())
    return {"ok": True}


@app.get("/api/progress", response_model=DownloadProgress)
async def get_progress():
    return downloader.get_progress()


@app.get("/api/files", response_model=FilesPage)
async def get_files(page: int = 1, limit: int = 20):
    items, total = downloader.get_files(page, limit)
    return FilesPage(
        items=[FileInfo(name=f.name, downloaded_at=f.downloaded_at) for f in items],
        total=total,
        page=page,
        limit=limit,
        pages=max(1, -(-total // limit)),
    )


@app.post("/api/calculate", response_model=CalcResult)
async def calculate(req: CalcRequest):
    return calculator.calculate(downloader.files, req.names)


app.mount("/", StaticFiles(directory="static", html=True), name="static")
