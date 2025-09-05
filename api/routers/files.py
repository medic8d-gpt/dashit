from fastapi import APIRouter, UploadFile, File, HTTPException
from fastapi.responses import FileResponse
import os

UPLOAD_DIR = os.path.join(os.path.dirname(__file__), "../uploaded_files")
MAX_FILE_SIZE = 100 * 1024 * 1024  # 100 MB

router = APIRouter()


@router.post("/upload")
async def upload_file(file: UploadFile = File(...)):
    contents = await file.read()
    if len(contents) > MAX_FILE_SIZE:
        raise HTTPException(status_code=413, detail="File too large (max 100 MB)")
    file_path = os.path.join(UPLOAD_DIR, file.filename)
    with open(file_path, "wb") as f:
        f.write(contents)
    return {"filename": file.filename, "size": len(contents)}


@router.get("/download/{filename}")
def download_file(filename: str):
    file_path = os.path.join(UPLOAD_DIR, filename)
    if not os.path.isfile(file_path):
        raise HTTPException(status_code=404, detail="File not found")
    return FileResponse(file_path, filename=filename)
