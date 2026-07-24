import asyncio

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from models import CalcRequest, CalcResult, DownloadProgress, FileInfo, FilesPage
from services.calculator import CalculatorService
from services.downloader import DownloadService

app = FastAPI(
    title="File Downloader Service",
    description="""
Сервис для скачивания каталога текстовых файлов через внешний API и анализа их содержимого.

## Возможности

- **Скачивание** — постепенно скачивает весь каталог файлов через API с обработкой rate-limit
- **Прогресс** — отслеживание статуса скачивания в реальном времени
- **Файлы** — постраничный список скачанных файлов с временем загрузки
- **Расчёты** — подсчёт вхождений цифр 0–9 в выбранных файлах
""",
    version="1.0.0",
)

downloader = DownloadService()
calculator = CalculatorService()


@app.post("/api/download", tags=["Скачивание"])
async def start_download():
    """
    Запускает процесс скачивания всего каталога файлов через внешний API.

    Процесс выполняется асинхронно в фоне. Если скачивание уже идёт — повторный
    запрос игнорируется. Прогресс доступен через `/api/progress`.
    """
    if not downloader.is_running:
        asyncio.create_task(downloader.run())
    return {"ok": True}


@app.get("/api/progress", response_model=DownloadProgress, tags=["Скачивание"])
async def get_progress():
    """
    Возвращает текущий статус скачивания.

    - `status`: idle | running | done | error
    - `found`: сколько имён файлов получено от API
    - `downloaded`: сколько файлов скачано и отмечено
    - `total`: сколько файлов сохранено в памяти
    - `start_time`: время старта по НСК (UTC+7)
    """
    return downloader.get_progress()


@app.get("/api/files", response_model=FilesPage, tags=["Файлы"])
async def get_files(page: int = 1, limit: int = 20):
    """
    Возвращает постраничный список скачанных файлов, отсортированный по времени загрузки.

    - `page`: номер страницы (начиная с 1)
    - `limit`: количество файлов на странице
    """
    items, total = downloader.get_files(page, limit)
    return FilesPage(
        items=[FileInfo(name=f.name, downloaded_at=f.downloaded_at) for f in items],
        total=total,
        page=page,
        limit=limit,
        pages=max(1, -(-total // limit)),
    )


@app.post("/api/calculate", response_model=CalcResult, tags=["Расчёты"])
async def calculate(req: CalcRequest):
    """
    Считает статистику вхождений цифр 0–9 для выбранных файлов.

    Возвращает:
    - `total`: общее количество каждой цифры по всем выбранным файлам
    - `files`: количество каждой цифры отдельно для каждого файла
    """
    return calculator.calculate(downloader.files, req.names)


app.mount("/", StaticFiles(directory="static", html=True), name="static")
