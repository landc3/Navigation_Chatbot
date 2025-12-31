#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
项目启动脚本
自动启动前后端服务并打开浏览器
使用方法: python run.py
"""

import os
import sys
import time
import socket
import subprocess
import threading
import webbrowser
import urllib.request
import urllib.error
from pathlib import Path
from typing import Optional

# 颜色输出（Windows 10+ 支持）
class Colors:
    """终端颜色"""
    CYAN = '\033[96m'
    GREEN = '\033[92m'
    YELLOW = '\033[93m'
    RED = '\033[91m'
    WHITE = '\033[97m'
    GRAY = '\033[90m'
    RESET = '\033[0m'
    
    @staticmethod
    def print(text: str, color: str = ''):
        """打印带颜色的文本"""
        if sys.platform == 'win32':
            # Windows 需要启用 ANSI 转义序列
            try:
                import ctypes
                kernel32 = ctypes.windll.kernel32
                kernel32.SetConsoleMode(kernel32.GetStdHandle(-11), 7)
            except:
                pass
        print(f"{color}{text}{Colors.RESET}")


def check_port(port: int) -> bool:
    """检查端口是否被占用"""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        try:
            s.bind(('localhost', port))
            return False  # 端口可用
        except OSError:
            return True  # 端口被占用


def get_port_process(port: int) -> Optional[int]:
    """获取占用端口的进程ID（Windows）"""
    if sys.platform == 'win32':
        try:
            result = subprocess.run(
                ['netstat', '-ano'],
                capture_output=True,
                text=True,
                encoding='gbk' if sys.platform == 'win32' else 'utf-8'
            )
            for line in result.stdout.split('\n'):
                if f':{port}' in line and 'LISTENING' in line:
                    parts = line.split()
                    if len(parts) > 4:
                        return int(parts[-1])
        except:
            pass
    return None


def get_process_name(pid: int) -> Optional[str]:
    """获取进程名称（Windows）"""
    if sys.platform == 'win32':
        try:
            result = subprocess.run(
                ['tasklist', '/FI', f'PID eq {pid}', '/FO', 'CSV', '/NH'],
                capture_output=True,
                text=True,
                encoding='gbk' if sys.platform == 'win32' else 'utf-8'
            )
            for line in result.stdout.split('\n'):
                if line.strip() and f'{pid}' in line:
                    parts = line.split('","')
                    if len(parts) > 0:
                        # 移除引号
                        process_name = parts[0].strip('"')
                        return process_name
        except:
            pass
    return None


def kill_process(pid: int) -> bool:
    """终止进程（Windows）"""
    if sys.platform == 'win32':
        try:
            result = subprocess.run(
                ['taskkill', '/F', '/PID', str(pid)],
                capture_output=True,
                text=True,
                encoding='gbk' if sys.platform == 'win32' else 'utf-8'
            )
            return result.returncode == 0
        except:
            return False
    return False


def check_venv() -> bool:
    """检查虚拟环境"""
    venv_path = Path('.venv')
    if not venv_path.exists():
        Colors.print("❌ 错误: 未找到虚拟环境 .venv", Colors.RED)
        Colors.print("请先运行: python -m venv .venv", Colors.YELLOW)
        return False
    return True


def check_backend_deps() -> bool:
    """检查后端依赖"""
    try:
        import fastapi
        import uvicorn
        return True
    except ImportError:
        return False


def check_frontend_deps() -> bool:
    """检查前端依赖"""
    node_modules = Path('frontend/node_modules')
    return node_modules.exists()


def install_backend_deps():
    """安装后端依赖"""
    Colors.print("📥 安装后端依赖...", Colors.YELLOW)
    subprocess.run([sys.executable, '-m', 'pip', 'install', '-r', 'requirements.txt'], check=True)


def install_frontend_deps():
    """安装前端依赖"""
    Colors.print("📥 安装前端依赖...", Colors.YELLOW)
    frontend_dir = Path('frontend')
    if sys.platform == 'win32':
        subprocess.run(['npm', 'install'], cwd=frontend_dir, shell=True, check=True)
    else:
        subprocess.run(['npm', 'install'], cwd=frontend_dir, check=True)


def wait_for_server(url: str, timeout: int = 30) -> bool:
    """等待服务器启动"""
    start_time = time.time()
    while time.time() - start_time < timeout:
        try:
            urllib.request.urlopen(url, timeout=2)
            return True
        except (urllib.error.URLError, socket.timeout):
            time.sleep(0.5)
    return False


def start_backend():
    """启动后端服务"""
    Colors.print("🔧 启动后端服务 (端口 8000)...", Colors.CYAN)
    
    # 使用当前 Python 解释器启动 uvicorn
    cmd = [
        sys.executable,
        '-m', 'uvicorn',
        'backend.app.main:app',
        '--host', '0.0.0.0',
        '--port', '8000',
        '--reload'
    ]
    
    process = subprocess.Popen(
        cmd,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        bufsize=1,
        universal_newlines=True
    )
    
    # 实时输出日志
    def log_output():
        for line in process.stdout:
            print(line, end='')
    
    log_thread = threading.Thread(target=log_output, daemon=True)
    log_thread.start()
    
    return process


def start_frontend():
    """启动前端服务"""
    Colors.print("🎨 启动前端服务 (端口 3000)...", Colors.CYAN)
    
    frontend_dir = Path('frontend')
    if sys.platform == 'win32':
        process = subprocess.Popen(
            ['npm', 'run', 'dev'],
            cwd=frontend_dir,
            shell=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            bufsize=1,
            universal_newlines=True
        )
    else:
        process = subprocess.Popen(
            ['npm', 'run', 'dev'],
            cwd=frontend_dir,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            bufsize=1,
            universal_newlines=True
        )
    
    # 实时输出日志
    def log_output():
        for line in process.stdout:
            print(line, end='')
    
    log_thread = threading.Thread(target=log_output, daemon=True)
    log_thread.start()
    
    return process


def main():
    """主函数"""
    Colors.print("========================================", Colors.CYAN)
    Colors.print("  导航聊天机器人 - 启动脚本", Colors.CYAN)
    Colors.print("========================================", Colors.CYAN)
    print()
    
    # 检查虚拟环境
    if not check_venv():
        sys.exit(1)
    
    # 检查后端依赖
    Colors.print("🔍 检查后端依赖...", Colors.YELLOW)
    if not check_backend_deps():
        install_backend_deps()
    
    # 检查前端依赖
    Colors.print("🔍 检查前端依赖...", Colors.YELLOW)
    if not check_frontend_deps():
        install_frontend_deps()
    
    # 检查端口占用
    Colors.print("🔍 检查端口占用...", Colors.YELLOW)
    port3500_occupied = check_port(3500)
    port8000_occupied = check_port(8000)
    
    if port3500_occupied:
        Colors.print("⚠️  警告: 端口 3500 已被占用", Colors.YELLOW)
        pid = get_port_process(3500)
        if pid:
            process_name = get_process_name(pid)
            Colors.print(f"   占用进程ID: {pid}", Colors.YELLOW)
            if process_name:
                Colors.print(f"   进程名称: {process_name}", Colors.YELLOW)
            Colors.print("", Colors.RESET)
            Colors.print("   选项:", Colors.WHITE)
            Colors.print("   1. 自动关闭占用端口的进程 (k)", Colors.WHITE)
            Colors.print("   2. 继续启动（可能会失败）(y)", Colors.WHITE)
            Colors.print("   3. 退出 (n)", Colors.WHITE)
            response = input("请选择 (k/y/n): ").strip().lower()
            
            if response == 'k':
                Colors.print(f"🔄 正在关闭进程 {pid}...", Colors.CYAN)
                if kill_process(pid):
                    Colors.print("✅ 进程已关闭", Colors.GREEN)
                    time.sleep(1)  # 等待端口释放
                    # 再次检查端口
                    if check_port(3500):
                        Colors.print("⚠️  端口仍未释放，请手动检查", Colors.YELLOW)
                        response = input("是否继续? (y/n): ").strip().lower()
                        if response != 'y':
                            sys.exit(1)
                else:
                    Colors.print("❌ 无法关闭进程，可能需要管理员权限", Colors.RED)
                    response = input("是否继续? (y/n): ").strip().lower()
                    if response != 'y':
                        sys.exit(1)
            elif response != 'y':
                sys.exit(1)
        else:
            Colors.print("   无法获取占用进程信息", Colors.YELLOW)
            Colors.print("   请关闭占用端口的进程或使用其他端口", Colors.YELLOW)
            response = input("是否继续? (y/n): ").strip().lower()
            if response != 'y':
                sys.exit(1)
    
    if port8000_occupied:
        Colors.print("⚠️  警告: 端口 8000 已被占用", Colors.YELLOW)
        pid = get_port_process(8000)
        if pid:
            process_name = get_process_name(pid)
            Colors.print(f"   占用进程ID: {pid}", Colors.YELLOW)
            if process_name:
                Colors.print(f"   进程名称: {process_name}", Colors.YELLOW)
            Colors.print("", Colors.RESET)
            Colors.print("   选项:", Colors.WHITE)
            Colors.print("   1. 自动关闭占用端口的进程 (k)", Colors.WHITE)
            Colors.print("   2. 继续启动（可能会失败）(y)", Colors.WHITE)
            Colors.print("   3. 退出 (n)", Colors.WHITE)
            response = input("请选择 (k/y/n): ").strip().lower()
            
            if response == 'k':
                Colors.print(f"🔄 正在关闭进程 {pid}...", Colors.CYAN)
                if kill_process(pid):
                    Colors.print("✅ 进程已关闭", Colors.GREEN)
                    time.sleep(1)  # 等待端口释放
                    # 再次检查端口
                    if check_port(8000):
                        Colors.print("⚠️  端口仍未释放，请手动检查", Colors.YELLOW)
                        response = input("是否继续? (y/n): ").strip().lower()
                        if response != 'y':
                            sys.exit(1)
                else:
                    Colors.print("❌ 无法关闭进程，可能需要管理员权限", Colors.RED)
                    response = input("是否继续? (y/n): ").strip().lower()
                    if response != 'y':
                        sys.exit(1)
            elif response != 'y':
                sys.exit(1)
        else:
            Colors.print("   无法获取占用进程信息", Colors.YELLOW)
            Colors.print("   请关闭占用端口的进程或使用其他端口", Colors.YELLOW)
            response = input("是否继续? (y/n): ").strip().lower()
            if response != 'y':
                sys.exit(1)
    
    print()
    Colors.print("🚀 启动服务...", Colors.GREEN)
    print()
    
    backend_process = None
    frontend_process = None
    
    try:
        # 启动后端
        backend_process = start_backend()
        
        # 等待后端启动
        Colors.print("⏳ 等待后端服务启动...", Colors.GRAY)
        if wait_for_server('http://localhost:8000/api/health', timeout=15):
            Colors.print("✅ 后端服务已启动", Colors.GREEN)
        else:
            Colors.print("⚠️  后端服务启动超时，但继续启动前端...", Colors.YELLOW)
        
        time.sleep(1)  # 额外等待1秒
        
        # 启动前端
        frontend_process = start_frontend()
        
        # 等待前端启动
        Colors.print("⏳ 等待前端服务启动...", Colors.GRAY)
        if wait_for_server('http://localhost:3500', timeout=30):
            Colors.print("✅ 前端服务已启动", Colors.GREEN)
        else:
            Colors.print("⚠️  前端服务启动超时，但尝试打开浏览器...", Colors.YELLOW)
        
        print()
        Colors.print("✅ 服务已启动!", Colors.GREEN)
        print()
        Colors.print("📍 访问地址:", Colors.YELLOW)
        Colors.print("   前端: http://localhost:3500", Colors.WHITE)
        Colors.print("   后端: http://localhost:8000", Colors.WHITE)
        Colors.print("   API文档: http://localhost:8000/docs", Colors.WHITE)
        print()
        
        # 等待一下确保服务完全启动
        time.sleep(2)
        
        # 自动打开浏览器
        Colors.print("🌐 正在打开浏览器...", Colors.CYAN)
        try:
            webbrowser.open('http://localhost:3500')
            Colors.print("✅ 浏览器已打开", Colors.GREEN)
        except Exception as e:
            Colors.print(f"⚠️  无法自动打开浏览器: {e}", Colors.YELLOW)
            Colors.print("   请手动访问: http://localhost:3500", Colors.YELLOW)
        
        print()
        Colors.print("按 Ctrl+C 停止所有服务", Colors.GRAY)
        print()
        
        # 保持运行，等待用户中断
        while True:
            time.sleep(1)
            
            # 检查进程是否还在运行
            if backend_process and backend_process.poll() is not None:
                Colors.print("❌ 后端服务已停止", Colors.RED)
                break
            
            if frontend_process and frontend_process.poll() is not None:
                Colors.print("❌ 前端服务已停止", Colors.RED)
                break
    
    except KeyboardInterrupt:
        print()
        Colors.print("🛑 正在停止服务...", Colors.YELLOW)
    
    finally:
        # 停止所有进程
        if backend_process:
            try:
                backend_process.terminate()
                backend_process.wait(timeout=5)
            except:
                backend_process.kill()
        
        if frontend_process:
            try:
                frontend_process.terminate()
                frontend_process.wait(timeout=5)
            except:
                frontend_process.kill()
        
        Colors.print("✅ 服务已停止", Colors.GREEN)


if __name__ == '__main__':
    main()

