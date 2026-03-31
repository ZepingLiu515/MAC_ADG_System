#!/usr/bin/env python
# -*- coding: utf-8 -*-

import sys

print("=" * 60)
print("🔍 Playwright 诊断工具")
print("=" * 60)

# 第1步：检查 playwright 包
print("\n[1/5] 检查 playwright 包...")
try:
    import playwright
    # 修复版本获取方式
    try:
        from importlib.metadata import version
        print(f"✅ playwright 版本: {version('playwright')}")
    except:
        print("✅ playwright 已安装（版本检测略）")
except ImportError as e:
    print(f"❌ 无法导入 playwright: {e}")
    sys.exit(1)

# 第2步：检查 sync_api
print("\n[2/5] 检查 sync_api...")
try:
    from playwright.sync_api import sync_playwright
    print("✅ sync_playwright 可用")
except Exception as e:
    print(f"❌ 导入 sync_playwright 失败: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)

# 第3步：检查 stealth
print("\n[3/5] 检查 playwright_stealth...")
try:
    from playwright_stealth import stealth_sync
    print("✅ stealth_sync 可用")
except ImportError as e:
    print(f"⚠️  playwright_stealth 未安装: {e}")

# 第4步：检查浏览器驱动
print("\n[4/5] 检查浏览器驱动...")
try:
    with sync_playwright() as p:
        print("✅ 浏览器驱动已安装")
except Exception as e:
    print(f"❌ 浏览器驱动缺失或损坏: {e}")
    print("\n💡 解决方法: 运行下面的命令")
    print("   playwright install")
    sys.exit(1)

# 第5步：尝试启动浏览器
print("\n[5/5] 尝试启动浏览器...")
try:
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        print("✅ Chromium 浏览器启动成功")
        browser.close()
except Exception as e:
    print(f"❌ 启动浏览器失败: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)

print("\n" + "=" * 60)
print("✅ 所有检查通过！Playwright 已就绪")
print("=" * 60)