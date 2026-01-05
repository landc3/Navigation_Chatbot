param(
  [int]$BackendPort = 8000,
  [int]$FrontendPort = 3500
)

$ErrorActionPreference = "Stop"

Write-Host "== Production build & start ==" -ForegroundColor Cyan

if (!(Test-Path ".\.venv\Scripts\python.exe")) {
  Write-Host "❌ 未找到 .venv，请先创建并安装依赖：" -ForegroundColor Red
  Write-Host "   python -m venv .venv" -ForegroundColor Yellow
  Write-Host "   .\.venv\Scripts\pip install -r requirements.txt" -ForegroundColor Yellow
  exit 1
}

if ([string]::IsNullOrWhiteSpace($env:ALI_QWEN_API_KEY)) {
  Write-Host "❌ 缺少环境变量 ALI_QWEN_API_KEY（请在 .env 或系统环境变量中设置）" -ForegroundColor Red
  exit 1
}

Write-Host "🔧 启动后端 (uvicorn)..." -ForegroundColor Cyan
Start-Process -FilePath ".\.venv\Scripts\python.exe" -ArgumentList @(
  "-m","uvicorn","backend.app.main:app",
  "--host","0.0.0.0",
  "--port","$BackendPort"
) -NoNewWindow

Write-Host "🎨 构建并预览前端..." -ForegroundColor Cyan
Push-Location "frontend"
try {
  npm install | Out-Null
  npm run build | Out-Null
  npm run preview -- --host 0.0.0.0 --port $FrontendPort
} finally {
  Pop-Location
}




