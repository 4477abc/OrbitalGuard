"""
OrbitalGuard - 核心数据下载脚本 (Final Verified Version)
=======================================================
经过全面检查的最终版本。
只下载真实存在的、公开的数据集。

修正记录:
  - 增加 active_gp 的 limit/30000 以确保下载所有在轨物体
  - 增加 timeout 时间以应对大数据量传输
  - 优化了状态提示信息

目标数据集：
  1. data_satcat.json           : 完整卫星目录 (基础数据)
  2. data_active_gp.json        : 所有在轨物体GP (约2.7万条, 含卫星和碎片)
  3. data_fengyun1c_debris.json : 核心案例碎片
  4. data_cosmos2251_debris.json: 对比案例碎片
  5. data_iridium33_debris.json : 对比案例碎片
"""

import requests
import json
import time
import os
from datetime import datetime

# 导入账号配置
try:
    from config import SPACETRACK_USERNAME, SPACETRACK_PASSWORD
except ImportError:
    print("❌ 错误：未找到config.py配置文件！")
    print("   请创建一个config.py文件，内容如下：")
    print('   SPACETRACK_USERNAME = "your_email"')
    print('   SPACETRACK_PASSWORD = "your_password"')
    exit(1)

BASE_URL = "https://www.space-track.org"

# ============================================================
# 工具函数
# ============================================================

def print_header(title, step, total):
    print("\n" + "="*70)
    print(f"[{step}/{total}] {title}")
    print("="*70)

def save_json(data, filename):
    with open(filename, 'w', encoding='utf-8') as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
    size_mb = os.path.getsize(filename) / 1024 / 1024
    return size_mb

def login_spacetrack():
    print("\n" + "="*70)
    print("🔐 1. 验证身份 & 登录")
    print("="*70)
    print(f"账号: {SPACETRACK_USERNAME}")
    
    session = requests.Session()
    login_url = f"{BASE_URL}/ajaxauth/login"
    
    try:
        response = session.post(
            login_url,
            data={'identity': SPACETRACK_USERNAME, 'password': SPACETRACK_PASSWORD},
            timeout=30
        )
        if response.status_code == 200:
            print("✅ 登录成功！Session已建立。")
            return session
        else:
            print(f"❌ 登录失败！状态码: {response.status_code}")
            print("   请检查 config.py 中的账号密码是否正确。")
            return None
    except Exception as e:
        print(f"❌ 网络连接错误: {e}")
        return None

# ============================================================
# 数据下载函数
# ============================================================

def download_satcat(session):
    """[1/5] SATCAT完整卫星目录"""
    print_header("SATCAT卫星目录 (Master Log)", 1, 5)
    # orderby/NORAD_CAT_ID asc 确保顺序
    url = f"{BASE_URL}/basicspacedata/query/class/satcat/format/json/orderby/NORAD_CAT_ID asc"
    
    try:
        print("📡 请求中... (下载完整目录，约50MB，请耐心等待)")
        start_time = time.time()
        response = session.get(url, timeout=180) # 增加超时时间
        
        if response.status_code == 200:
            data = response.json()
            filename = "data_satcat.json"
            size_mb = save_json(data, filename)
            duration = time.time() - start_time
            
            print(f"✅ 下载成功！({duration:.1f}秒)")
            print(f"   📊 记录总数: {len(data):,}")
            print(f"   💾 文件大小: {size_mb:.2f} MB")
            print(f"   📁 已保存至: {filename}")
            return True
        else:
            print(f"❌ 下载失败！状态码: {response.status_code}")
            print(f"   信息: {response.text[:200]}")
            return False
    except Exception as e:
        print(f"❌ 下载出错: {e}")
        return False

def download_active_gp(session):
    """[2/5] 活跃卫星GP数据"""
    print_header("活跃物体GP数据 (Active Orbit Data)", 2, 5)
    # 修正：添加 limit/30000 确保获取所有数据
    url = f"{BASE_URL}/basicspacedata/query/class/gp/decay_date/null-val/orderby/NORAD_CAT_ID asc/limit/30000/format/json"
    
    try:
        print("📡 请求中... (获取所有在轨物体TLE，约20MB)")
        start_time = time.time()
        response = session.get(url, timeout=180)
        
        if response.status_code == 200:
            data = response.json()
            filename = "data_active_gp.json"
            size_mb = save_json(data, filename)
            duration = time.time() - start_time
            
            print(f"✅ 下载成功！({duration:.1f}秒)")
            print(f"   📊 记录总数: {len(data):,}")
            print(f"   💾 文件大小: {size_mb:.2f} MB")
            print(f"   📁 已保存至: {filename}")
            
            # 简单的数据质量检查
            if len(data) < 10000:
                print("   ⚠️ 警告: 下载的数据量似乎偏少 (<10000)，请检查API限制。")
            
            return True
        else:
            print(f"❌ 下载失败！状态码: {response.status_code}")
            return False
    except Exception as e:
        print(f"❌ 下载出错: {e}")
        return False

def download_debris_data(session):
    """[3-5/5] 碎片数据下载"""
    targets = [
        ("FENGYUN 1C", "data_fengyun1c_debris.json", 3),
        ("COSMOS 2251", "data_cosmos2251_debris.json", 4),
        ("IRIDIUM 33", "data_iridium33_debris.json", 5)
    ]
    
    success_count = 0
    
    for name, filename, step in targets:
        print_header(f"{name} 碎片数据", step, 5)
        # URL编码空格为%20, ~~表示模糊匹配
        encoded_name = name.replace(" ", "%20")
        url = f"{BASE_URL}/basicspacedata/query/class/gp/OBJECT_NAME/{encoded_name}~~/orderby/NORAD_CAT_ID asc/format/json"
        
        try:
            print(f"📡 请求中... (搜索 '{name}' 相关碎片)")
            response = session.get(url, timeout=60)
            if response.status_code == 200:
                data = response.json()
                size_mb = save_json(data, filename)
                debris_count = len([d for d in data if 'DEB' in d.get('OBJECT_NAME', '')])
                
                print(f"✅ 下载成功！")
                print(f"   🧩 碎片数量: {debris_count}")
                print(f"   📁 已保存至: {filename}")
                success_count += 1
            else:
                print(f"❌ 下载失败！状态码: {response.status_code}")
        except Exception as e:
            print(f"❌ 出错: {e}")
        
        time.sleep(2)  # 增加延时，避免触发速率限制
        
    return success_count

# ============================================================
# 主函数
# ============================================================

def main():
    print("\n" + "="*70)
    print("🚀 OrbitalGuard - 核心数据下载 (Final Execution)")
    print("="*70)
    
    session = login_spacetrack()
    if not session:
        return
    
    # 1. 下载 SATCAT
    if download_satcat(session):
        print("\n💤 等待 3 秒 (遵守API速率限制)...")
        time.sleep(3)
        
        # 2. 下载 Active GP
        if download_active_gp(session):
            print("\n💤 等待 3 秒...")
            time.sleep(3)
            
            # 3-5. 下载碎片数据
            download_debris_data(session)
    
    print("\n" + "="*70)
    print("🎉 所有自动化下载任务结束！")
    print("="*70)
    print("\n📝 最后一步检查 (Checklist):")
    print("   [ ] 检查当前目录下是否生成了 5 个 .json 文件")
    print("   [ ] 手动下载 UCS 数据库 (data_ucs_database.xlsx)")
    print("   [ ] 确认文件大小是否合理 (SATCAT > 40MB, GP > 15MB)")
    print("\n🚀 Ready for Database Import!")
    print("="*70)

if __name__ == "__main__":
    main()
