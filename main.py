import re
import json
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

class MediaRequest(BaseModel):
    url: str

@app.get("/", response_class=HTMLResponse)
async def read_index():
    return FileResponse("index.html")

@app.post("/api/download")
async def download_media(req: MediaRequest):
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

            # 1. Trích xuất URL Video
            video_match = re.search(r'https?://sns-video-[^\s"\'<>]+', html)
            if video_match:
                vid_url = video_match.group(0).replace("\\u002F", "/").replace("&amp;", "&").split('"')[0]
                return {"type": "video", "video_url": vid_url, "target_url": target_url}

            # 2. Trích xuất danh sách Ảnh
            images = []
            json_match = re.search(r'window\.__INITIAL_STATE__\s*=\s*({.*?});</script>', html)
            if json_match:
                try:
                    json_str = json_match.group(1).replace("undefined", "null")
                    data = json.loads(json_str)
                    note_data = data.get("note", {}).get("noteDetailMap", {})
                    if note_data:
                        first_key = list(note_data.keys())[0]
                        note = note_data[first_key].get("note", {})
                        image_list = note.get("imageList", [])
                        for img in image_list:
                            img_url = img.get("urlDefault") or img.get("urlPre")
                            if img_url:
                                if not img_url.startswith("http"):
                                    img_url = "https:" + img_url
                                images.append(img_url)
                except Exception:
                    pass

            if images:
                return {"type": "image", "images": images, "target_url": target_url}

            return {"type": "redirect", "target_url": target_url}

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Lỗi hệ thống: {str(e)}")
