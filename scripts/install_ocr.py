"""
快速安装 OCR 依赖
"""
import subprocess
import sys

def install_ocr_deps():
    """安装 PaddleOCR 和相关依赖"""
    print("\n" + "="*70)
    print("📦 安装 PaddleOCR 依赖")
    print("="*70 + "\n")
    
    packages = [
        "paddleocr>=2.7.0",
        "paddlepaddle>=2.5.0",
        "numpy>=1.20.0",
    ]
    
    for package in packages:
        print(f"[安装] {package}")
        try:
            subprocess.check_call([sys.executable, "-m", "pip", "install", "-q", package])
            print(f"  ✅ 安装成功\n")
        except subprocess.CalledProcessError as e:
            print(f"  ❌ 安装失败: {e}\n")
            return False
    
    print("="*70)
    print("✅ 所有依赖安装完成！")
    print("="*70)
    print("\n🚀 现在可以运行测试了:")
    print("   python test_ocr_vision.py")
    print()
    
    return True

if __name__ == "__main__":
    install_ocr_deps()
