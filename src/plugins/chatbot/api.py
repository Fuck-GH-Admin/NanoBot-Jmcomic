from nonebot import get_driver

driver = get_driver()
app = driver.server_app

from .services import book_srv

@app.post("/api/jm/download")
async def jm_download(ids: list[str]):
    results = await book_srv.process_download(ids)
    return {
        "results": [
            {
                "id": r.album_id,
                "title": r.title,
                "success": r.success,
                "file": str(r.file_path) if r.file_path else None,
                "series_ids": r.series_ids,
                "error": r.error_msg or None,
            }
            for r in results
        ]
    }


@app.get("/api/jm/status")
async def jm_status():
    return {"ready": book_srv._check_env(), "temp_dir": str(book_srv.temp_dir)}
