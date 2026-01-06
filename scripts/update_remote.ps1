# 远程服务器代码更新脚本
# 适用于 Windows Server 2022
# 使用方法：在远程服务器的PowerShell中执行此脚本

Write-Host "========================================" -ForegroundColor Cyan
Write-Host "  导航聊天机器人 - 代码更新脚本" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan
Write-Host ""

# 检查是否在项目目录中
$projectPath = "C:\Navigation_Chatbot"
if (-not (Test-Path $projectPath)) {
    Write-Host "✗ 项目目录不存在: $projectPath" -ForegroundColor Red
    Write-Host "  请先运行部署脚本或手动克隆项目" -ForegroundColor Yellow
    exit 1
}

Set-Location $projectPath

# 步骤1: 检查Git是否安装
Write-Host "[1/4] 检查Git安装..." -ForegroundColor Green
try {
    $gitVersion = git --version
    Write-Host "✓ Git已安装: $gitVersion" -ForegroundColor Green
} catch {
    Write-Host "✗ Git未安装，请先安装Git for Windows" -ForegroundColor Red
    exit 1
}

# 步骤2: 检查Docker是否运行
Write-Host "[2/4] 检查Docker状态..." -ForegroundColor Green
try {
    docker info | Out-Null
    Write-Host "✓ Docker正在运行" -ForegroundColor Green
} catch {
    Write-Host "✗ Docker未运行，请启动Docker Desktop" -ForegroundColor Red
    exit 1
}

# 步骤3: 拉取最新代码
Write-Host "[3/4] 从GitHub拉取最新代码..." -ForegroundColor Green
Write-Host ""

try {
    # 检查是否有未提交的本地更改
    $status = git status --porcelain
    if ($status) {
        Write-Host "⚠ 警告: 检测到本地有未提交的更改" -ForegroundColor Yellow
        Write-Host "未提交的文件:" -ForegroundColor Yellow
        git status --short
        Write-Host ""
        Write-Host "服务器上的代码应该与GitHub保持一致" -ForegroundColor Cyan
        Write-Host "建议放弃本地更改，使用GitHub上的最新版本" -ForegroundColor Cyan
        Write-Host ""
        $choice = Read-Host "如何处理? (1=放弃本地更改/使用远程版本, 2=暂存本地更改, 3=取消) [默认:1]"
        
        if ($choice -eq "2" -or $choice -eq "2") {
            git stash
            Write-Host "✓ 已暂存本地更改" -ForegroundColor Green
        } elseif ($choice -eq "3" -or $choice -eq "3") {
            Write-Host "更新已取消" -ForegroundColor Yellow
            exit 0
        } else {
            # 默认：放弃本地更改
            Write-Host "放弃本地更改，使用远程版本..." -ForegroundColor Yellow
            git reset --hard HEAD
            Write-Host "✓ 已放弃本地更改" -ForegroundColor Green
        }
    }

    # 获取当前分支
    $currentBranch = git branch --show-current
    Write-Host "当前分支: $currentBranch" -ForegroundColor Gray
    Write-Host ""

    # 拉取最新代码
    Write-Host "正在拉取最新代码..." -ForegroundColor Yellow
    git fetch origin
    $pullResult = git pull origin $currentBranch
    
    if ($LASTEXITCODE -eq 0) {
        Write-Host "✓ 代码更新成功" -ForegroundColor Green
        
        # 显示最近的提交
        Write-Host ""
        Write-Host "最近的更新:" -ForegroundColor Yellow
        git log --oneline -5 --graph
        Write-Host ""
    } else {
        Write-Host "✗ 代码拉取失败" -ForegroundColor Red
        Write-Host "错误信息: $pullResult" -ForegroundColor Red
        exit 1
    }
} catch {
    Write-Host "✗ 更新代码时出错: $_" -ForegroundColor Red
    exit 1
}

# 步骤4: 重新构建并启动容器
Write-Host "[4/4] 重新构建并启动Docker容器..." -ForegroundColor Green
Write-Host ""

try {
    # 停止现有容器
    Write-Host "停止现有容器..." -ForegroundColor Yellow
    docker compose down 2>$null
    
    # 重新构建并启动
    Write-Host "构建新镜像（这可能需要几分钟）..." -ForegroundColor Yellow
    docker compose up --build -d
    
    if ($LASTEXITCODE -eq 0) {
        Write-Host ""
        Write-Host "等待容器启动..." -ForegroundColor Yellow
        Start-Sleep -Seconds 5
        
        # 检查容器状态
        $containers = docker ps --format "{{.Names}}"
        if ($containers -match "navigation_chatbot") {
            Write-Host ""
            Write-Host "========================================" -ForegroundColor Cyan
            Write-Host "  更新成功！" -ForegroundColor Green
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
        } else {
            Write-Host "⚠ 容器可能未正常启动，请检查日志:" -ForegroundColor Yellow
            Write-Host "  docker compose logs" -ForegroundColor Gray
        }
    } else {
        Write-Host "✗ 容器启动失败" -ForegroundColor Red
        Write-Host "请查看错误信息: docker compose logs" -ForegroundColor Yellow
        exit 1
    }
} catch {
    Write-Host "✗ 部署失败: $_" -ForegroundColor Red
    Write-Host "请检查错误信息并查看日志: docker compose logs" -ForegroundColor Yellow
    exit 1
}

Write-Host ""
Write-Host "更新完成！" -ForegroundColor Green

