import logging
import uuid
from tasks import celery_app
from pathlib import Path
from fastapi import FastAPI
from celery.result import AsyncResult
from celery import Celery


# Настройка Celery
celery_app = Celery('tasks', broker='redis://localhost:6379/0', backend='redis://localhost:6379/0')

logging.basicConfig(level=logging.INFO)

app = FastAPI()

@app.post("/generate_pdf/")
async def generate_pdf_endpoint(url: str, temp_dir: str):
    task = celery_app.send_task('generate_pdf_task', args=[url, temp_dir])
    return {"task_id": task.id}

@app.get("/pdf_status/{task_id}")
async def get_pdf_status(task_id: str):
    result = AsyncResult(task_id, app=celery_app)
    if result.ready():
        return {"status": "completed", "result": result.get()}
    else:
        return {"status": "in_progress"}

if __name__ == '__main__':
    import uvicorn
    uvicorn.run(app, host="127.0.0.1", port=8000)
