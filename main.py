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

class VideoRequest(BaseModel):
    url: str

@app.get("/", response_class=HTMLResponse)
async def read_index():
    return FileResponse("index.html")

@app.post("/api/download")
async def download_video(req: VideoRequest):
    # Trích xuất URL chuẩn từ văn bản dán vào
    url_match = re.search(r'https?://[^\s]+', req.url)
    if not url_match:
        raise HTTPException(status_code=400, detail="Vui lòng dán liên kết hợp lệ từ RedNote/Xiaohongshu.")
    
    clean_url = url_match.group(0)

    # Giả lập Browser di động để RedNote không chặn
    headers = {
        "User-Agent": "Mozilla/5.0 (iPhone; CPU iPhone OS 16_6 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/16.6 Mobile/15E148 Safari/604.1",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8"
    }

    try:
        async with httpx.AsyncClient(follow_redirects=True, timeout=15.0) as client:
            response = await client.get(clean_url, headers=headers)
            html = response.text

            # Cách 1: Tìm cấu trúc dữ liệu JSON chính thức của bài viết
            json_match = re.search(r'window\.__INITIAL_STATE__\s*=\s*({.*?});</script>', html)
            if json_match:
                try:
                    json_str = json_match.group(1).replace("undefined", "null")
                    data = json.loads(json_str)
                    
                    note_data = data.get("note", {}).get("noteDetailMap", {})
                    if note_data:
                        first_key = list(note_data.keys())[0]
                        note = note_data[first_key].get("note", {})
                        
                        title = note.get("title") or note.get("desc") or "RedNote Video"
                        video = note.get("video", {})
                        media = video.get("media", {})
                        stream = media.get("stream", {})
                        
                        video_url = None
                        if "h264" in stream and stream["h264"]:
                            video_url = stream["h264"][0].get("masterUrl")
                        elif "h265" in stream and stream["h265"]:
                            video_url = stream["h265"][0].get("masterUrl")

                        if video_url:
                            return {"title": title[:60], "video_url": video_url}
                except Exception:
                    pass

            # Cách 2: Tìm quét trực tiếp đường dẫn CDN Video MP4 trong HTML bằng Regex
            patterns = [
                r'https://sns-video-bd\.xhscdn\.com/[^\s"]+',
                r'https://sns-video-qc\.xhscdn\.com/[^\s"]+',
                r'https://sns-video-[^\s"]+\.mp4'
            ]
            
            for pattern in patterns:
                video_url_match = re.search(pattern, html)
                if video_url_match:
                    found_url = video_url_match.group(0).replace("\\u002F", "/").replace("&amp;", "&")
                    return {
                        "title": "RedNote Video",
                        "video_url": found_url
                    }

            raise HTTPException(
                status_code=400, 
                detail="Không thể trích xuất video. Hãy chắc chắn đây là bài viết dạng Video (không phải bài viết ảnh)."
            )

    except HTTPException as e:
        raise e
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Lỗi hệ thống: {str(e)}")
