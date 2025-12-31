"""
FastAPI主应用
"""
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
import sys
from pathlib import Path

# 添加项目根目录到路径
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

from config import config
from backend.app.api import chat, health

# 创建FastAPI应用
app = FastAPI(
    title="智能车辆电路图资料导航 Chatbot",
    description="基于大语言模型的车辆电路图检索对话机器人",
    version="1.0.0"
)

# 配置CORS
# 构建允许的源列表，过滤掉 None 值
allowed_origins = [
    "http://localhost:3500",  # 前端主端口
    "http://localhost:3100",  # 备用端口
    "http://localhost:3000",  # 备用端口
    "http://localhost:3001",  # 备用端口
    "http://localhost:5173",
    "http://127.0.0.1:3500",  # 前端主端口
    "http://127.0.0.1:3100",  # 备用端口
    "http://127.0.0.1:3000",  # 备用端口
    "http://127.0.0.1:3001",  # 备用端口
    "http://127.0.0.1:5173",
]
if config.FRONTEND_URL:
    allowed_origins.append(config.FRONTEND_URL)

app.add_middleware(
    CORSMiddleware,
    allow_origins=allowed_origins,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
    allow_headers=["*"],
    expose_headers=["*"],
)

# 注册路由
app.include_router(health.router, prefix="/api", tags=["健康检查"])
app.include_router(chat.router, prefix="/api", tags=["聊天"])


@app.exception_handler(Exception)
async def global_exception_handler(request, exc):
    """全局异常处理"""
    return JSONResponse(
        status_code=500,
        content={"error": "服务器内部错误", "detail": str(exc)}
    )


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "backend.app.main:app",
        host=config.BACKEND_HOST,
        port=config.BACKEND_PORT,
        reload=True
    )

