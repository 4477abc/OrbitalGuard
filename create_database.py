"""
OrbitalGuard - 数据库创建与数据导入脚本
===========================================
功能：
1. 创建 SQLite 数据库 (orbitalguard.db)
2. 创建 4 个核心表
3. 从 JSON/Excel 导入数据
4. 实施数据清洗和分层中位数填充策略
5. 生成统计报告

数据流：
- SpaceObjects    ← data_satcat.json
- Orbits          ← data_active_gp.json + 碎片数据
- SatelliteDetails ← data_ucs_database.xlsx
- LaunchMissions  ← 从 SpaceObjects 聚合
"""

import sqlite3
import json
import pandas as pd
from datetime import datetime
import os

# ============================================================
# 配置
# ============================================================

DB_NAME = "orbitalguard.db"
DATA_FILES = {
    'satcat': 'data_satcat.json',
    'active_gp': 'data_active_gp.json',
    'fengyun1c': 'data_fengyun1c_debris.json',
    'cosmos2251': 'data_cosmos2251_debris.json',
    'iridium33': 'data_iridium33_debris.json',
    'ucs': 'data_ucs_database.xlsx'
}

# 分层中位数填充策略（基于数据分析）
LIFETIME_MEDIAN = {
    'LEO': 4.0,
    'MEO': 10.0,
    'GEO': 15.0,
    'Elliptical': 7.0
}

# ============================================================
# 辅助函数
# ============================================================

def print_header(title):
    print("\n" + "="*70)
    print(f"📌 {title}")
    print("="*70)

def safe_float(value):
    """安全转换为浮点数，失败返回 None"""
    try:
        return float(value) if value not in [None, '', 'N/A'] else None
    except (ValueError, TypeError):
        return None

def safe_date(value):
    """安全转换日期，支持多种格式"""
    if not value or value in ['', 'N/A', None]:
        return None
    try:
        # Space-Track 日期格式通常是 YYYY-MM-DD
        if isinstance(value, str) and len(value) >= 10:
            return value[:10]  # 取前10个字符
        return value
    except:
        return None

# ============================================================
# 1. 创建数据库 Schema
# ============================================================

def create_tables(conn):
    print_header("创建数据库表结构")
    
    cursor = conn.cursor()
    
    # 表1: SpaceObjects
    print("📄 创建表: SpaceObjects")
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS SpaceObjects (
        norad_id INTEGER PRIMARY KEY,
        object_name TEXT,
        intl_designator TEXT,
        object_type TEXT,
        country TEXT,
        launch_date TEXT,
        decay_date TEXT,
        rcs_size TEXT,
        launch_site TEXT,
        launch_mission_id TEXT
    )
    """)
    
    # 表2: Orbits
    print("📄 创建表: Orbits")
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS Orbits (
        orbit_id INTEGER PRIMARY KEY AUTOINCREMENT,
        norad_id INTEGER,
        epoch TEXT,
        inclination_deg REAL,
        eccentricity REAL,
        mean_motion REAL,
        ra_of_asc_node REAL,
        arg_of_pericenter REAL,
        mean_anomaly REAL,
        bstar REAL,
        FOREIGN KEY (norad_id) REFERENCES SpaceObjects(norad_id)
    )
    """)
    
    # 表3: SatelliteDetails
    print("📄 创建表: SatelliteDetails")
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS SatelliteDetails (
        norad_id INTEGER PRIMARY KEY,
        launch_mass_kg REAL,
        dry_mass_kg REAL,
        power_watts REAL,
        expected_lifetime_years REAL,
        purpose TEXT,
        users TEXT,
        contractor TEXT,
        operator_owner TEXT,
        class_of_orbit TEXT,
        country_operator TEXT,
        FOREIGN KEY (norad_id) REFERENCES SpaceObjects(norad_id)
    )
    """)
    
    # 表4: LaunchMissions
    print("📄 创建表: LaunchMissions")
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS LaunchMissions (
        launch_mission_id TEXT PRIMARY KEY,
        launch_date TEXT,
        country TEXT,
        launch_site TEXT,
        payload_count INTEGER
    )
    """)
    
    conn.commit()
    print("✅ 所有表创建完成")

# ============================================================
# 2. 导入 SpaceObjects (SATCAT)
# ============================================================

def import_space_objects(conn):
    print_header("导入 SpaceObjects (SATCAT)")
    
    with open(DATA_FILES['satcat'], 'r') as f:
        satcat = json.load(f)
    
    cursor = conn.cursor()
    imported = 0
    
    for record in satcat:
        try:
            # 提取 launch_mission_id (国际编号的前8位，如 1998-067)
            intl_des = record.get('INTLDES', '')
            launch_mission_id = intl_des[:8] if len(intl_des) >= 8 else intl_des
            
            cursor.execute("""
                INSERT OR REPLACE INTO SpaceObjects 
                (norad_id, object_name, intl_designator, object_type, country, 
                 launch_date, decay_date, rcs_size, launch_site, launch_mission_id)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                record.get('NORAD_CAT_ID'),
                record.get('SATNAME'),
                record.get('INTLDES'),
                record.get('OBJECT_TYPE'),
                record.get('COUNTRY'),
                safe_date(record.get('LAUNCH')),
                safe_date(record.get('DECAY')),
                record.get('RCS_SIZE'),
                record.get('SITE'),
                launch_mission_id
            ))
            imported += 1
        except Exception as e:
            print(f"⚠️  跳过记录 {record.get('NORAD_CAT_ID')}: {e}")
    
    conn.commit()
    print(f"✅ 导入 {imported:,} 条 SpaceObjects 记录")

# ============================================================
# 3. 导入 Orbits (GP Data)
# ============================================================

def import_orbits(conn):
    print_header("导入 Orbits (GP + 碎片数据)")
    
    cursor = conn.cursor()
    imported = 0
    
    # 合并所有 GP 数据
    all_gp_data = []
    
    for key in ['active_gp', 'fengyun1c', 'cosmos2251', 'iridium33']:
        filename = DATA_FILES[key]
        print(f"📖 读取: {filename}")
        with open(filename, 'r') as f:
            data = json.load(f)
            all_gp_data.extend(data)
    
    print(f"📊 总 GP 记录数: {len(all_gp_data):,}")
    
    for record in all_gp_data:
        try:
            cursor.execute("""
                INSERT INTO Orbits 
                (norad_id, epoch, inclination_deg, eccentricity, mean_motion,
                 ra_of_asc_node, arg_of_pericenter, mean_anomaly, bstar)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                record.get('NORAD_CAT_ID'),
                record.get('EPOCH'),
                safe_float(record.get('INCLINATION')),
                safe_float(record.get('ECCENTRICITY')),
                safe_float(record.get('MEAN_MOTION')),
                safe_float(record.get('RA_OF_ASC_NODE')),
                safe_float(record.get('ARG_OF_PERICENTER')),
                safe_float(record.get('MEAN_ANOMALY')),
                safe_float(record.get('BSTAR'))
            ))
            imported += 1
        except Exception as e:
            # 可能因为外键约束失败（NORAD_ID 不在 SpaceObjects 中）
            pass
    
    conn.commit()
    print(f"✅ 导入 {imported:,} 条 Orbits 记录")

# ============================================================
# 4. 导入 SatelliteDetails (UCS + 分层填充)
# ============================================================

def import_satellite_details(conn):
    print_header("导入 SatelliteDetails (UCS 数据)")
    
    df = pd.read_excel(DATA_FILES['ucs'])
    
    # 列名映射（UCS 的列名可能有细微差异）
    col_map = {
        'NORAD Number': 'norad_id',
        'Launch Mass (kg.)': 'launch_mass_kg',
        'Dry Mass (kg.)': 'dry_mass_kg',
        'Power (watts)': 'power_watts',
        'Expected Lifetime (yrs.)': 'expected_lifetime_years',
        'Purpose': 'purpose',
        'Users': 'users',
        'Contractor': 'contractor',
        'Operator/Owner': 'operator_owner',
        'Class of Orbit': 'class_of_orbit',
        'Country of Operator/Owner': 'country_operator'
    }
    
    # 重命名列
    df_clean = df.rename(columns=col_map)
    
    # 分层中位数填充 Expected Lifetime
    print("🔧 应用分层中位数填充策略...")
    def fill_lifetime(row):
        if pd.isna(row['expected_lifetime_years']):
            orbit_class = row.get('class_of_orbit', 'LEO')
            return LIFETIME_MEDIAN.get(orbit_class, 4.0)  # 默认用 LEO
        return row['expected_lifetime_years']
    
    df_clean['expected_lifetime_years'] = df_clean.apply(fill_lifetime, axis=1)
    
    # 统计填充效果
    filled_count = df['Expected Lifetime (yrs.)'].isna().sum()
    print(f"   填充了 {filled_count} 条缺失的寿命数据")
    
    # 插入数据
    cursor = conn.cursor()
    imported = 0
    
    for _, row in df_clean.iterrows():
        try:
            cursor.execute("""
                INSERT OR REPLACE INTO SatelliteDetails
                (norad_id, launch_mass_kg, dry_mass_kg, power_watts, 
                 expected_lifetime_years, purpose, users, contractor, 
                 operator_owner, class_of_orbit, country_operator)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                int(row['norad_id']) if pd.notna(row['norad_id']) else None,
                safe_float(row.get('launch_mass_kg')),
                safe_float(row.get('dry_mass_kg')),
                safe_float(row.get('power_watts')),
                safe_float(row.get('expected_lifetime_years')),
                row.get('purpose'),
                row.get('users'),
                row.get('contractor'),
                row.get('operator_owner'),
                row.get('class_of_orbit'),
                row.get('country_operator')
            ))
            imported += 1
        except Exception as e:
            pass  # 跳过外键约束失败的记录
    
    conn.commit()
    print(f"✅ 导入 {imported:,} 条 SatelliteDetails 记录")

# ============================================================
# 5. 生成 LaunchMissions (聚合查询)
# ============================================================

def generate_launch_missions(conn):
    print_header("生成 LaunchMissions (聚合)")
    
    cursor = conn.cursor()
    
    cursor.execute("""
        INSERT INTO LaunchMissions (launch_mission_id, launch_date, country, launch_site, payload_count)
        SELECT 
            launch_mission_id,
            MIN(launch_date) as launch_date,
            MAX(country) as country,
            MAX(launch_site) as launch_site,
            COUNT(*) as payload_count
        FROM SpaceObjects
        WHERE launch_mission_id IS NOT NULL AND launch_mission_id != ''
        GROUP BY launch_mission_id
    """)
    
    conn.commit()
    
    count = cursor.execute("SELECT COUNT(*) FROM LaunchMissions").fetchone()[0]
    print(f"✅ 生成 {count:,} 条 LaunchMissions 记录")

# ============================================================
# 6. 数据验证与统计
# ============================================================

def validate_database(conn):
    print_header("数据库验证与统计")
    
    cursor = conn.cursor()
    
    tables = [
        ('SpaceObjects', 'norad_id'),
        ('Orbits', 'orbit_id'),
        ('SatelliteDetails', 'norad_id'),
        ('LaunchMissions', 'launch_mission_id')
    ]
    
    for table, pk in tables:
        count = cursor.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
        print(f"   {table:20s}: {count:>8,} 条记录")
    
    # 额外检查
    print("\n🔍 数据质量检查:")
    
    # 在轨物体数量
    active = cursor.execute(
        "SELECT COUNT(*) FROM SpaceObjects WHERE decay_date IS NULL"
    ).fetchone()[0]
    print(f"   仍在轨物体: {active:,} 个")
    
    # 碎片数量
    debris = cursor.execute(
        "SELECT COUNT(*) FROM SpaceObjects WHERE object_type = 'DEBRIS'"
    ).fetchone()[0]
    print(f"   碎片数量: {debris:,} 个")
    
    # 有详细信息的卫星
    detailed = cursor.execute(
        "SELECT COUNT(*) FROM SatelliteDetails"
    ).fetchone()[0]
    print(f"   有详细信息的卫星: {detailed:,} 个")
    
    # Expected Lifetime 完整率
    lifetime_filled = cursor.execute(
        "SELECT COUNT(*) FROM SatelliteDetails WHERE expected_lifetime_years IS NOT NULL"
    ).fetchone()[0]
    print(f"   寿命数据完整率: {lifetime_filled}/{detailed} = {lifetime_filled/detailed*100:.1f}%")

# ============================================================
# 主函数
# ============================================================

def main():
    print("="*70)
    print("🚀 OrbitalGuard - 数据库创建与导入")
    print("="*70)
    print(f"📅 执行时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    
    # 检查数据文件
    print("\n📋 检查数据文件...")
    for name, filepath in DATA_FILES.items():
        if os.path.exists(filepath):
            size_mb = os.path.getsize(filepath) / 1024 / 1024
            print(f"   ✅ {filepath:30s} ({size_mb:.2f} MB)")
        else:
            print(f"   ❌ {filepath:30s} (缺失!)")
            return
    
    # 删除旧数据库（如果存在）
    if os.path.exists(DB_NAME):
        print(f"\n⚠️  删除旧数据库: {DB_NAME}")
        os.remove(DB_NAME)
    
    # 创建数据库连接
    conn = sqlite3.connect(DB_NAME)
    print(f"\n✅ 创建数据库: {DB_NAME}")
    
    try:
        # 执行导入流程
        create_tables(conn)
        import_space_objects(conn)
        import_orbits(conn)
        import_satellite_details(conn)
        generate_launch_missions(conn)
        validate_database(conn)
        
        print("\n" + "="*70)
        print("🎉 数据库创建完成!")
        print("="*70)
        print(f"📁 数据库文件: {DB_NAME}")
        print(f"💾 文件大小: {os.path.getsize(DB_NAME) / 1024 / 1024:.2f} MB")
        print("\n下一步:")
        print("   1. 使用 sqlite3 命令行或 DB Browser 查看数据")
        print("   2. 开始编写 Use Case 查询")
        print("   3. 创建视图和索引优化性能")
        
    except Exception as e:
        print(f"\n❌ 错误: {e}")
        import traceback
        traceback.print_exc()
    finally:
        conn.close()

if __name__ == "__main__":
    main()

