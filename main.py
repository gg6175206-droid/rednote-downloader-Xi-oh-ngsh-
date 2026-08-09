import re
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse, FileResponse
from pydantic import BaseModel
import httpx

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

class VideoRequest(BaseModel):
    url: str

@app.get("/", response_class=HTMLResponse)
async def read_index():
    return FileResponse("index.html")

@app.post("/api/download")
async def download_video(req: VideoRequest):
    url_match = re.search(r'https?://[^\s]+', req.url)
    if not url_match:
        raise HTTPException(status_code=400, detail="Vui lòng dán liên kết hợp lệ từ RedNote.")
    
    clean_url = url_match.group(0)

    headers = {
        "User-Agent": "Mozilla/5.0 (iPhone; CPU iPhone OS 16_6 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/16.6 Mobile/15E148 Safari/604.1",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8"
    }

    try:
        async with httpx.AsyncClient(follow_redirects=True, timeout=15.0) as client:
            res = await client.get(clean_url, headers=headers)
            target_url = str(res.url)
            html = res.text

            video_match = re.search(r'https?://sns-video-[^\s"\'<>]+', html)
            if video_match:
                vid_url = video_match.group(0).replace("\\u002F", "/").replace("&amp;", "&").split('"')[0]
                return {"status": "success", "video_url": vid_url, "target_url": target_url}

            return {"status": "redirect", "target_url": target_url}

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Lỗi: {str(e)}")
