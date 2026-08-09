from fastapi import FastAPI, HTTPException, Query
from fastapi.responses import StreamingResponse, FileResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import re, json, httpx

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

HEADERS = {
    "User-Agent": "Mozilla/5.0 (iPhone; CPU iPhone OS 16_6 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/16.6 Mobile/15E148 Safari/604.1",
}

class ParseRequest(BaseModel):
    url: str

def extract_url(text: str) -> str:
    url_match = re.search(r'https?://[^\s]+', text)
    if not url_match:
        raise ValueError("Không tìm thấy đường dẫn hợp lệ.")
    return url_match.group(0)

@app.get("/")
async def serve_frontend():
    return FileResponse("index.html")

@app.post("/api/parse")
async def parse_rednote(payload: ParseRequest):
    try:
        raw_url = extract_url(payload.url)
        async with httpx.AsyncClient(headers=HEADERS, follow_redirects=True, timeout=10.0) as client:
            response = await client.get(raw_url)
            html = response.text
            match = re.search(r'window\.__INITIAL_STATE__\s*=\s*(\{.*?\});?</script>', html, re.DOTALL)
            if not match:
                match = re.search(r'window\.__INITIAL_STATE__\s*=\s*(\{.*?\})</script>', html, re.DOTALL)
            if not match:
                raise HTTPException(status_code=400, detail="Không thể bóc tách dữ liệu bài viết.")
            data = json.loads(match.group(1))
            note_data = data.get("note", {}).get("note", {})
            if not note_data:
                note_data = data.get("note", {}).get("noteDetailMap", {})
                first_key = list(note_data.keys())[0] if note_data else None
                if first_key:
                    note_data = note_data[first_key].get("note", {})

            title = note_data.get("title") or note_data.get("desc", "rednote_video")
            title = re.sub(r'[\\/*?:"<>|]', "", title)[:50].strip()

            video_data = note_data.get("video", {})
            media_data = video_data.get("media", {}).get("stream", {})
            video_url = None
            if "h264" in media_data and len(media_data["h264"]) > 0:
                video_url = media_data["h264"][0].get("masterUrl")
            elif "h265" in media_data and len(media_data["h265"]) > 0:
                video_url = media_data["h265"][0].get("masterUrl")

            if not video_url:
                raise HTTPException(status_code=400, detail="Bài viết không chứa video.")

            return {"success": True, "title": title, "video_url": video_url}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/download")
async def download_proxy(url: str = Query(...), filename: str = Query("video")):
    client = httpx.AsyncClient(headers=HEADERS, timeout=30.0)
    req = client.build_request("GET", url)
    res = await client.send(req, stream=True)
    return StreamingResponse(
        res.aiter_raw(),
        media_type="video/mp4",
        headers={"Content-Disposition": f'attachment; filename="{filename}.mp4"'}
    )
