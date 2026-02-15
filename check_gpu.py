"""
AI TradeBot - GPU 环境检测与自动降级

功能：
1. 检测 CUDA 环境是否可用
2. 检测 CuPy 和 PyTorch GPU 支持
3. 自动选择最佳计算后端
4. 提供 GPU 状态报告

运行方式:
    python check_gpu.py
"""
import os
import sys
import time
from typing import Dict, Any, Tuple
from dataclasses import dataclass


@dataclass
class GPUInfo:
    """GPU 信息"""
    available: bool
    backend: str
    device_name: str
    compute_capability: str
    memory_total: str
    memory_free: str
    cuda_version: str


def check_cuda() -> Tuple[bool, str]:
    """检查 CUDA 运行时"""
    try:
        import subprocess
        result = subprocess.run(
            ["nvidia-smi"],
            capture_output=True,
            text=True,
            timeout=10
        )
        if result.returncode == 0:
            # 提取 CUDA 版本
            for line in result.stdout.split('\n'):
                if 'CUDA Version' in line:
                    version = line.split('CUDA Version:')[1].split()[0]
                    return True, f"CUDA {version}"
            return True, "CUDA 可用"
        return False, "nvidia-smi 执行失败"
    except FileNotFoundError:
        return False, "未找到 nvidia-smi，可能未安装 NVIDIA 驱动"
    except subprocess.TimeoutExpired:
        return False, "nvidia-smi 执行超时"
    except Exception as e:
        return False, f"CUDA 检测异常: {e}"


def check_cupy() -> Tuple[bool, str, Dict[str, Any]]:
    """检查 CuPy GPU 支持"""
    info = {}
    try:
        import cupy as cp

        # 测试基本功能
        array = cp.array([1, 2, 3])
        result = cp.sum(array)
        del array

        # 获取设备信息
        device = cp.cuda.Device()
        info["compute_capability"] = str(device.compute_capability)

        try:
            info["device_name"] = cp.cuda.runtime.getDeviceProperties(0)["name"].decode()
        except:
            info["device_name"] = "Unknown"

        # 内存信息
        mempool = cp.get_default_memory_pool()
        info["memory_used"] = f"{mempool.used_bytes() / 1024**3:.2f} GB"
        info["memory_total"] = f"{mempool.total_bytes() / 1024**3:.2f} GB"

        return True, f"CuPy 可用 ({info['device_name']})", info

    except ImportError:
        return False, "CuPy 未安装", info
    except Exception as e:
        return False, f"CuPy 检测失败: {e}", info


def check_pytorch_gpu() -> Tuple[bool, str, Dict[str, Any]]:
    """检查 PyTorch GPU 支持"""
    info = {}
    try:
        import torch

        if not torch.cuda.is_available():
            return False, "PyTorch 已安装但 CUDA 不可用", info

        # 获取设备信息
        device_count = torch.cuda.device_count()
        info["device_count"] = device_count
        info["device_name"] = torch.cuda.get_device_name(0)
        info["cuda_version"] = torch.version.cuda

        # 内存信息
        info["memory_allocated"] = f"{torch.cuda.memory_allocated(0) / 1024**3:.2f} GB"
        info["memory_reserved"] = f"{torch.cuda.memory_reserved(0) / 1024**3:.2f} GB"

        # 测试基本功能
        x = torch.randn(1000, 1000, device="cuda")
        y = torch.randn(1000, 1000, device="cuda")
        z = torch.mm(x, y)
        del x, y, z

        return True, f"PyTorch GPU 可用 ({info['device_name']})", info

    except ImportError:
        return False, "PyTorch 未安装", info
    except Exception as e:
        return False, f"PyTorch GPU 检测失败: {e}", info


def benchmark_gpu(num_iterations: int = 100) -> Tuple[float, str]:
    """
    GPU 性能基准测试

    执行矩阵乘法基准测试
    """
    try:
        import cupy as cp
        import time as t

        # 预热
        a = cp.random.randn(1000, 1000)
        b = cp.random.randn(1000, 1000)
        cp.dot(a, b)
        cp.cuda.Stream.null.synchronize()

        # 基准测试
        start = t.time()
        for _ in range(num_iterations):
            c = cp.dot(a, b)
        cp.cuda.Stream.null.synchronize()
        elapsed = t.time() - start

        del a, b, c

        return elapsed, "CuPy"

    except ImportError:
        pass

    try:
        import torch
        import time as t

        device = torch.device("cuda:0")

        # 预热
        a = torch.randn(1000, 1000, device=device)
        b = torch.randn(1000, 1000, device=device)
        torch.mm(a, b)
        torch.cuda.synchronize()

        # 基准测试
        start = t.time()
        for _ in range(num_iterations):
            c = torch.mm(a, b)
        torch.cuda.synchronize()
        elapsed = t.time() - start

        del a, b, c

        return elapsed, "PyTorch"

    except ImportError:
        pass

    return -1, "无可用 GPU"


def benchmark_cpu(num_iterations: int = 100) -> float:
    """CPU 性能基准测试"""
    import numpy as np
    import time as t

    a = np.random.randn(1000, 1000)
    b = np.random.randn(1000, 1000)

    start = t.time()
    for _ in range(num_iterations):
        c = np.dot(a, b)
    elapsed = t.time() - start

    del a, b, c

    return elapsed


def get_system_info() -> Dict[str, Any]:
    """获取系统信息"""
    import platform
    import multiprocessing as mp

    info = {
        "os": platform.system(),
        "os_version": platform.version(),
        "python_version": platform.python_version(),
        "cpu_count": mp.cpu_count(),
        "machine": platform.machine(),
    }

    # CPU 信息
    try:
        if platform.system() == "Windows":
            import subprocess
            result = subprocess.run(
                ["wmic", "cpu", "get", "name"],
                capture_output=True,
                text=True
            )
            lines = [l.strip() for l in result.stdout.split('\n') if l.strip()]
            if len(lines) > 1:
                info["cpu_name"] = lines[1]
    except:
        pass

    return info


def run_gpu_check() -> Dict[str, Any]:
    """运行完整的 GPU 检测"""
    results = {
        "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
        "system": get_system_info(),
        "cuda": {},
        "cupy": {},
        "pytorch": {},
        "benchmark": {},
        "recommendation": "",
    }

    print("=" * 60)
    print("AI TradeBot - GPU Environment Check")
    print("=" * 60)

    # 系统信息
    print(f"\n[System Info]")
    print(f"  OS: {results['system']['os']}")
    print(f"  Python: {results['system']['python_version']}")
    print(f"  CPU Cores: {results['system']['cpu_count']}")
    if "cpu_name" in results["system"]:
        print(f"  CPU: {results['system']['cpu_name']}")

    # CUDA 检测
    print(f"\n[CUDA Runtime]")
    cuda_ok, cuda_msg = check_cuda()
    results["cuda"]["available"] = cuda_ok
    results["cuda"]["message"] = cuda_msg
    status = "[OK]" if cuda_ok else "[X]"
    print(f"  {status} {cuda_msg}")

    # CuPy 检测
    print(f"\n[CuPy GPU]")
    cupy_ok, cupy_msg, cupy_info = check_cupy()
    results["cupy"]["available"] = cupy_ok
    results["cupy"]["message"] = cupy_msg
    results["cupy"]["info"] = cupy_info
    status = "[OK]" if cupy_ok else "[X]"
    print(f"  {status} {cupy_msg}")
    if cupy_ok:
        print(f"  Device: {cupy_info.get('device_name', 'Unknown')}")
        print(f"  Compute: {cupy_info.get('compute_capability', 'Unknown')}")

    # PyTorch 检测
    print(f"\n[PyTorch GPU]")
    pytorch_ok, pytorch_msg, pytorch_info = check_pytorch_gpu()
    results["pytorch"]["available"] = pytorch_ok
    results["pytorch"]["message"] = pytorch_msg
    results["pytorch"]["info"] = pytorch_info
    status = "[OK]" if pytorch_ok else "[X]"
    print(f"  {status} {pytorch_msg}")
    if pytorch_ok:
        print(f"  Device: {pytorch_info.get('device_name', 'Unknown')}")
        print(f"  CUDA: {pytorch_info.get('cuda_version', 'Unknown')}")

    # 性能基准测试
    print(f"\n[Benchmark Test]")
    print(f"  Test: 100x 1000x1000 matrix multiplication")

    # GPU 基准
    gpu_time, gpu_backend = benchmark_gpu(100)
    results["benchmark"]["gpu_time"] = gpu_time
    results["benchmark"]["gpu_backend"] = gpu_backend

    # CPU 基准
    cpu_time = benchmark_cpu(100)
    results["benchmark"]["cpu_time"] = cpu_time

    if gpu_time > 0:
        speedup = cpu_time / gpu_time
        print(f"  GPU ({gpu_backend}): {gpu_time:.3f}s")
        print(f"  CPU (NumPy): {cpu_time:.3f}s")
        print(f"  Speedup: {speedup:.1f}x")
        results["benchmark"]["speedup"] = speedup
    else:
        print(f"  GPU: Not available")
        print(f"  CPU (NumPy): {cpu_time:.3f}s")
        results["benchmark"]["speedup"] = 1.0

    # 推荐设置
    print(f"\n[Recommendation]")
    if cupy_ok:
        results["recommendation"] = "cupy"
        print(f"  [OK] CuPy GPU backend recommended")
        print(f"  System will use GPU-accelerated Monte Carlo simulation")
    elif pytorch_ok:
        results["recommendation"] = "pytorch"
        print(f"  [OK] PyTorch GPU backend recommended")
        print(f"  System will use GPU-accelerated Monte Carlo simulation")
    else:
        results["recommendation"] = "numpy"
        print(f"  [!!] GPU not available, using CPU multiprocessing mode")
        print(f"  Suggestion: Install CuPy (pip install cupy-cuda11x) or PyTorch GPU")

    print(f"\n" + "=" * 60)

    return results


def install_instructions():
    """显示安装说明"""
    print("""
【安装 GPU 支持库】

1. 安装 CuPy (推荐):
   # CUDA 11.x
   pip install cupy-cuda11x

   # CUDA 12.x
   pip install cupy-cuda12x

2. 安装 PyTorch GPU:
   # 访问 https://pytorch.org/get-started/locally/
   # 选择对应的 CUDA 版本

3. 验证安装:
   python check_gpu.py

【故障排查】

如果 GPU 检测失败:
1. 确保安装了最新的 NVIDIA 驱动
2. 确保 CUDA 版本与库版本匹配
3. 检查环境变量 CUDA_PATH 是否设置
4. 尝试重启系统
""")


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="AI TradeBot GPU 环境检测")
    parser.add_argument("--install", action="store_true", help="显示安装说明")
    parser.add_argument("--json", action="store_true", help="输出 JSON 格式")
    args = parser.parse_args()

    if args.install:
        install_instructions()
    else:
        results = run_gpu_check()

        if args.json:
            import json
            print(json.dumps(results, indent=2, ensure_ascii=False))
