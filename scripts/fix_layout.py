import shutil
import os

def fix_streamlit_layout():
    # 当前路径 (MAC_ADG_System)
    base_dir = os.getcwd()
    
    # 错误的路径: MAC_ADG_System/frontend/pages
    wrong_path = os.path.join(base_dir, "frontend", "pages")
    
    # 正确的路径: MAC_ADG_System/pages
    correct_path = os.path.join(base_dir, "pages")
    
    print(f"正在检查路径: {wrong_path}")
    
    if os.path.exists(wrong_path):
        # 如果根目录下已经有个 pages (可能是误创的空文件夹)，先删掉以免冲突
        if os.path.exists(correct_path):
            shutil.rmtree(correct_path)
            
        # 移动文件夹
        shutil.move(wrong_path, base_dir)
        print(f"✅ 成功！已将 'pages' 文件夹移动到项目根目录。")
        print(f"现在的结构是: {correct_path}")
    else:
        if os.path.exists(correct_path):
            print("✅ 'pages' 文件夹位置已经是正确的了，无需移动。")
        else:
            print("❌ 找不到 'frontend/pages' 文件夹，请确认你没有手动移动过。")

if __name__ == "__main__":
    fix_streamlit_layout()