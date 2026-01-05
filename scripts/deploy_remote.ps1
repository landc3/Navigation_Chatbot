# 远程服务器快速部署脚本
# 适用于 Windows Server 2022
# 使用方法：在远程服务器的PowerShell中执行此脚本

Write-Host "========================================" -ForegroundColor Cyan
Write-Host "  导航聊天机器人 - 远程部署脚本" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan
Write-Host ""

# 检查是否以管理员身份运行
$isAdmin = ([Security.Principal.WindowsPrincipal] [Security.Principal.WindowsIdentity]::GetCurrent()).IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)
if (-not $isAdmin) {
    Write-Host "警告: 建议以管理员身份运行此脚本以配置防火墙规则" -ForegroundColor Yellow
}

# 步骤1: 检查Git是否安装
Write-Host "[1/6] 检查Git安装..." -ForegroundColor Green
try {
    $gitVersion = git --version
    Write-Host "✓ Git已安装: $gitVersion" -ForegroundColor Green
} catch {
    Write-Host "✗ Git未安装，请先安装Git for Windows" -ForegroundColor Red
    Write-Host "  下载地址: https://git-scm.com/download/win" -ForegroundColor Yellow
    exit 1
}

# 步骤2: 检查Docker是否安装
Write-Host "[2/6] 检查Docker安装..." -ForegroundColor Green
try {
    $dockerVersion = docker --version
    Write-Host "✓ Docker已安装: $dockerVersion" -ForegroundColor Green
    
    # 检查Docker是否运行
    try {
        docker info | Out-Null
        Write-Host "✓ Docker正在运行" -ForegroundColor Green
    } catch {
        Write-Host "✗ Docker未运行，请启动Docker Desktop" -ForegroundColor Red
        exit 1
    }
} catch {
    Write-Host "✗ Docker未安装，请先安装Docker Desktop" -ForegroundColor Red
    Write-Host "  下载地址: https://www.docker.com/products/docker-desktop/" -ForegroundColor Yellow
    exit 1
}

# 步骤3: 克隆或更新项目
Write-Host "[3/6] 准备项目代码..." -ForegroundColor Green
$projectPath = "C:\Navigation_Chatbot"
$githubUrl = "https://github.com/landc3/Navigation_Chatbot.git"

if (Test-Path $projectPath) {
    Write-Host "项目目录已存在，更新代码..." -ForegroundColor Yellow
    Set-Location $projectPath
    git pull
} else {
    Write-Host "克隆项目到 $projectPath ..." -ForegroundColor Yellow
    Set-Location C:\
    git clone $githubUrl
    if (-not (Test-Path $projectPath)) {
        Write-Host "✗ 克隆失败，请检查网络连接和GitHub仓库地址" -ForegroundColor Red
        exit 1
    }
    Write-Host "✓ 项目克隆成功" -ForegroundColor Green
}

Set-Location $projectPath

# 步骤4: 配置环境变量
Write-Host "[4/6] 配置环境变量..." -ForegroundColor Green
$envFile = Join-Path $projectPath ".env"
$envExample = Join-Path $projectPath "env.example"

if (-not (Test-Path $envFile)) {
    if (Test-Path $envExample) {
        Copy-Item $envExample $envFile
        Write-Host "✓ 已创建.env文件" -ForegroundColor Green
    } else {
        Write-Host "✗ 找不到env.example文件" -ForegroundColor Red
        exit 1
    }
}

# 检查API密钥是否已配置
$envContent = Get-Content $envFile -Raw
if ($envContent -notmatch "ALI_QWEN_API_KEY=sk-") {
    Write-Host "⚠ 警告: .env文件中的API密钥可能未配置" -ForegroundColor Yellow
    Write-Host "  请编辑 $envFile 并设置你的ALI_QWEN_API_KEY" -ForegroundColor Yellow
    Write-Host ""
    $continue = Read-Host "是否现在编辑.env文件? (y/n)"
    if ($continue -eq "y" -or $continue -eq "Y") {
        notepad $envFile
        Write-Host "请确保已保存.env文件，然后按任意键继续..." -ForegroundColor Yellow
        $null = $Host.UI.RawUI.ReadKey("NoEcho,IncludeKeyDown")
    }
} else {
    Write-Host "✓ 环境变量已配置" -ForegroundColor Green
}

# 步骤5: 配置Windows防火墙（需要管理员权限）
Write-Host "[5/6] 配置Windows防火墙..." -ForegroundColor Green
if ($isAdmin) {
    try {
        # 检查规则是否已存在
        $rule80 = Get-NetFirewallRule -DisplayName "Navigation_Chatbot_HTTP_80" -ErrorAction SilentlyContinue
        $rule8000 = Get-NetFirewallRule -DisplayName "Navigation_Chatbot_API_8000" -ErrorAction SilentlyContinue
        
        if (-not $rule80) {
            New-NetFirewallRule -DisplayName "Navigation_Chatbot_HTTP_80" -Direction Inbound -LocalPort 80 -Protocol TCP -Action Allow | Out-Null
            Write-Host "✓ 已添加防火墙规则: 端口80" -ForegroundColor Green
        } else {
            Write-Host "✓ 防火墙规则已存在: 端口80" -ForegroundColor Green
        }
        
        if (-not $rule8000) {
            New-NetFirewallRule -DisplayName "Navigation_Chatbot_API_8000" -Direction Inbound -LocalPort 8000 -Protocol TCP -Action Allow | Out-Null
            Write-Host "✓ 已添加防火墙规则: 端口8000" -ForegroundColor Green
        } else {
            Write-Host "✓ 防火墙规则已存在: 端口8000" -ForegroundColor Green
        }
    } catch {
        Write-Host "⚠ 无法配置防火墙规则: $_" -ForegroundColor Yellow
        Write-Host "  请手动在Windows防火墙中添加端口80和8000的入站规则" -ForegroundColor Yellow
    }
} else {
    Write-Host "⚠ 未以管理员身份运行，跳过防火墙配置" -ForegroundColor Yellow
    Write-Host "  请手动在Windows防火墙中添加端口80和8000的入站规则" -ForegroundColor Yellow
}

# 步骤6: 启动Docker容器
Write-Host "[6/6] 启动Docker容器..." -ForegroundColor Green
Write-Host "构建和启动容器（这可能需要几分钟）..." -ForegroundColor Yellow

try {
    # 停止现有容器（如果存在）
    docker compose down 2>$null
    
    # 构建并启动
    docker compose up --build -d
    
    Write-Host ""
    Write-Host "等待容器启动..." -ForegroundColor Yellow
    Start-Sleep -Seconds 5
    
    # 检查容器状态
    $containers = docker ps --format "{{.Names}}"
    if ($containers -match "navigation_chatbot") {
        Write-Host ""
        Write-Host "========================================" -ForegroundColor Cyan
        Write-Host "  部署成功！" -ForegroundColor Green
        Write-Host "========================================" -ForegroundColor Cyan
        Write-Host ""
        Write-Host "容器状态:" -ForegroundColor Yellow
        docker ps --filter "name=navigation_chatbot" --format "table {{.Names}}\t{{.Status}}\t{{.Ports}}"
        Write-Host ""
        Write-Host "访问地址:" -ForegroundColor Yellow
        Write-Host "  前端应用: http://101.37.89.207" -ForegroundColor Cyan
        Write-Host "  后端API:  http://101.37.89.207:8000" -ForegroundColor Cyan
        Write-Host "  API文档:  http://101.37.89.207:8000/docs" -ForegroundColor Cyan
        Write-Host ""
        Write-Host "查看日志: docker compose logs -f" -ForegroundColor Gray
        Write-Host "停止服务: docker compose down" -ForegroundColor Gray
    } else {
        Write-Host "⚠ 容器可能未正常启动，请检查日志:" -ForegroundColor Yellow
        Write-Host "  docker compose logs" -ForegroundColor Gray
    }
} catch {
    Write-Host "✗ 启动失败: $_" -ForegroundColor Red
    Write-Host "请检查错误信息并查看日志: docker compose logs" -ForegroundColor Yellow
    exit 1
}

Write-Host ""
Write-Host "部署完成！" -ForegroundColor Green


