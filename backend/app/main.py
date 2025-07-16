from typing import Optional  # <--- 1. 在这里导入 Optional

import numpy as np
from fastapi import FastAPI, File, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from app.optimizer import EdgeOptimizer, auto_canny
from app.utils import base64_to_np, np_to_base64

app = FastAPI()

# ... (CORS 中间件配置保持不变)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

optimizer_cache = {}


# --- Pydantic Models (已修复) ---
class ProcessRequest(BaseModel):
    session_id: str
    # 2. 将 | None 替换为 Optional[...]
    main_body_mask_b64: Optional[str] = None
    detail_mask_b64: Optional[str] = None
    budget_ratio: Optional[float] = None


class CannyRequest(BaseModel):
    session_id: str
    canny_low: int
    canny_high: int


class UploadResponse(BaseModel):
    session_id: str
    original_image_b64: str
    initial_edges_b64: str
    canny_low: int
    canny_high: int
    image_width: int
    image_height: int


class ProcessResponse(BaseModel):
    sketch_b64: str


class CannyResponse(BaseModel):
    edges_b64: str


class AutoTuneResponse(BaseModel):
    canny_low: int
    canny_high: int


# --- API Endpoints (保持不变) ---
@app.post("/upload", response_model=UploadResponse)
async def upload_image(file: UploadFile = File(...)):
    session_id = file.filename or "default"
    image_bytes = await file.read()
    try:
        temp_optimizer = EdgeOptimizer(image_bytes)
        low, high = auto_canny(temp_optimizer.gray)
        optimizer = EdgeOptimizer(image_bytes, canny_low=low, canny_high=high)
        optimizer_cache[session_id] = optimizer

        return UploadResponse(
            session_id=session_id,
            original_image_b64=np_to_base64(optimizer.original_image, ".jpeg"),
            initial_edges_b64=np_to_base64(optimizer.edges),
            canny_low=low,
            canny_high=high,
            image_width=optimizer.width,
            image_height=optimizer.height,
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error processing image: {e}")


@app.post("/update-canny", response_model=CannyResponse)
async def update_canny(request: CannyRequest):
    if request.session_id not in optimizer_cache:
        raise HTTPException(status_code=404, detail="Session not found.")

    optimizer = optimizer_cache[request.session_id]
    optimizer.update_canny_parameters(request.canny_low, request.canny_high)

    return CannyResponse(edges_b64=np_to_base64(optimizer.edges))


@app.post("/process", response_model=ProcessResponse)
async def process_image(request: ProcessRequest):
    optimizer = optimizer_cache.get(request.session_id)
    if not optimizer:
        raise HTTPException(status_code=404, detail="Session not found.")

    if request.budget_ratio is not None:
        optimizer.budget_ratio = request.budget_ratio
        optimizer.update_canny_edges()

    main_mask = (
        base64_to_np(request.main_body_mask_b64) > 0
        if request.main_body_mask_b64
        else None
    )
    detail_mask = (
        base64_to_np(request.detail_mask_b64) > 0 if request.detail_mask_b64 else None
    )

    # 调用修改后的优化函数
    # optimized_sketch = optimizer.optimize_edges(
    #     main_body_mask=main_mask, detail_mask=detail_mask
    # )
    optimized_sketch = optimizer.optimize_edges_energy(
        main_body_mask=main_mask, detail_mask=detail_mask
    )

    return ProcessResponse(sketch_b64=np_to_base64(optimized_sketch))


@app.post("/autotune-canny", response_model=AutoTuneResponse)
async def autotune(request: ProcessRequest):  # 复用 ProcessRequest 来接收蒙版
    optimizer = optimizer_cache.get(request.session_id)
    if not optimizer:
        raise HTTPException(status_code=404, detail="Session not found.")

    # 检查是否提供了主体蒙版
    main_mask = (
        base64_to_np(request.main_body_mask_b64) > 0
        if request.main_body_mask_b64
        else None
    )

    # 调用新的 auto_canny
    low, high = auto_canny(optimizer.gray, mask=main_mask)
    optimizer.update_canny_parameters(low, high)

    return AutoTuneResponse(canny_low=low, canny_high=high)
