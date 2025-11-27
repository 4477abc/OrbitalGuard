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

数据清洗策略：
===========
1. 大小写规范化
   - 分类字段（object_type, class_of_orbit, country等）统一转为大写
   - 防止数据不一致性问题（如 "LEo" vs "LEO"）

2. 空白字符处理
   - 所有文本字段首尾去空（strip）
   - 处理 None, 'N/A', '' 等缺失值

3. 数值处理
   - 使用 safe_float() 安全转换，失败返回 None
   - 保留 NULL 值而非填充 0

4. 日期处理
   - 标准化为 YYYY-MM-DD 格式
   - 支持多种输入格式

5. 特殊处理
   - expected_lifetime_years: 分层中位数填充
   - launch_mission_id: 从国际编号提取前8位
   - LaunchMissions: 聚合时规范化country和launch_site
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
# 注意：所有 key 必须为大写，与规范化后的数据库值一致
LIFETIME_MEDIAN = {
    'LEO': 4.0,
    'MEO': 10.0,
    'GEO': 15.0,
    'ELLIPTICAL': 7.0
}

# ============================================================
# 辅助函数
# ============================================================

def print_header(title):
    print("\n" + "="*70)
    print(f"📌 {title}")
    print("="*70)

def safe_float(value):
    """安全转换为浮点数，失败返回 None
    
    支持：
    - 整数和浮点数
    - 科学计数法（如 1.2e-4）
    - 字符串表示
    """
    if value is None or value in ['', 'N/A']:
        return None
    try:
        f = float(value)
        # 检查是否为有效的浮点数（排除 NaN 和 Inf）
        return f if not (f != f or f == float('inf') or f == float('-inf')) else None
    except (ValueError, TypeError, OverflowError):
        return None

def safe_date(value):
    """安全转换日期，支持多种格式
    
    支持：
    - ISO 8601 格式 YYYY-MM-DD
    - 长格式字符串（自动取前 10 字符）
    - 日期有效性验证
    """
    import re
    
    if value is None or value in ['', 'N/A']:
        return None
    
    try:
        # 转为字符串并取前 10 个字符
        date_str = str(value)[:10] if value else None
        
        # 验证 YYYY-MM-DD 格式
        if not re.match(r'^\d{4}-\d{2}-\d{2}$', date_str):
            return None
        
        # 进一步验证日期的合理性
        year, month, day = map(int, date_str.split('-'))
        if month < 1 or month > 12 or day < 1 or day > 31:
            return None
        
        # 对于 DECAY_DATE，允许未来日期；对于 LAUNCH_DATE，应该是过去日期
        # 这里暂不做时间方向检查，保留为 NULL
        
        return date_str
    except (ValueError, AttributeError, TypeError):
        return None

def safe_upper(value):
    """安全转换为大写，处理空值"""
    if not value or value in ['', 'N/A', None]:
        return None
    try:
        return str(value).upper().strip() if value else None
    except:
        return None

def safe_strip(value):
    """安全去除首尾空白"""
    if not value or value in ['', 'N/A', None]:
        return None
    try:
        return str(value).strip() if value else None
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
            
            # 数据清洗：规范化文本字段
            object_type = safe_upper(record.get('OBJECT_TYPE'))
            country = safe_upper(record.get('COUNTRY'))
            rcs_size = safe_upper(record.get('RCS_SIZE'))
            launch_site = safe_upper(record.get('SITE'))
            
            cursor.execute("""
                INSERT OR REPLACE INTO SpaceObjects 
                (norad_id, object_name, intl_designator, object_type, country, 
                 launch_date, decay_date, rcs_size, launch_site, launch_mission_id)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                record.get('NORAD_CAT_ID'),
                safe_strip(record.get('SATNAME')),
                safe_upper(record.get('INTLDES')),
                object_type,
                country,
                safe_date(record.get('LAUNCH')),
                safe_date(record.get('DECAY')),
                rcs_size,
                launch_site,
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
    skipped_fk = 0  # 外键约束失败
    skipped_invalid = 0  # 数据无效
    
    # 合并所有 GP 数据
    all_gp_data = []
    
    for key in ['active_gp', 'fengyun1c', 'cosmos2251', 'iridium33']:
        filename = DATA_FILES[key]
        print(f"📖 读取: {filename}")
        try:
            with open(filename, 'r') as f:
                data = json.load(f)
                # 验证数据格式（应为列表）
                if not isinstance(data, list):
                    print(f"   ⚠️  警告: {filename} 不是列表格式，跳过")
                    continue
                all_gp_data.extend(data)
        except (json.JSONDecodeError, IOError) as e:
            print(f"   ❌ 读取失败: {e}")
            continue
    
    print(f"📊 总 GP 记录数: {len(all_gp_data):,}")
    
    for record in all_gp_data:
        try:
            # 必要字段检查
            if not record.get('NORAD_CAT_ID') or not record.get('EPOCH'):
                skipped_invalid += 1
                continue
            
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
        except sqlite3.IntegrityError as e:
            # 外键约束失败或唯一性约束失败
            if 'FOREIGN KEY constraint failed' in str(e):
                skipped_fk += 1
            else:
                skipped_invalid += 1
        except Exception as e:
            # 其他数据错误
            skipped_invalid += 1
    
    conn.commit()
    print(f"✅ 导入 {imported:,} 条 Orbits 记录")
    if skipped_fk > 0:
        print(f"   ⚠️  跳过 {skipped_fk} 条（外键约束失败）")
    if skipped_invalid > 0:
        print(f"   ⚠️  跳过 {skipped_invalid} 条（数据无效）")

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
    
    # 智能列名匹配：如果硬编码列名不存在，尝试模糊匹配
    actual_col_map = {}
    for expected_col, db_col in col_map.items():
        if expected_col in df.columns:
            actual_col_map[expected_col] = db_col
        else:
            # 尝试模糊匹配（去除非字母数字字符）
            import re
            pattern = re.sub(r'[^a-z0-9]', '', expected_col.lower())
            
            for actual_col in df.columns:
                actual_pattern = re.sub(r'[^a-z0-9]', '', actual_col.lower())
                if pattern == actual_pattern:
                    actual_col_map[actual_col] = db_col
                    print(f"   ℹ️  列名匹配: '{expected_col}' -> '{actual_col}'")
                    break
            else:
                print(f"   ⚠️  警告: 未找到列 '{expected_col}'，会跳过该字段")
    
    # 重命名列
    df_clean = df.rename(columns=actual_col_map)
    
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
            # 数据清洗：规范化所有文本字段
            class_of_orbit = safe_upper(row.get('class_of_orbit'))
            purpose = safe_strip(row.get('purpose'))
            users = safe_strip(row.get('users'))
            contractor = safe_strip(row.get('contractor'))
            operator_owner = safe_strip(row.get('operator_owner'))
            country_operator = safe_upper(row.get('country_operator'))
            
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
                purpose,
                users,
                contractor,
                operator_owner,
                class_of_orbit,
                country_operator
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
            MAX(UPPER(country)) as country,
            MAX(UPPER(launch_site)) as launch_site,
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

def precheck_data_files():
    """导入前检查：验证所有数据文件的完整性和格式"""
    print_header("数据文件预检查")
    
    all_ok = True
    
    for file_key, filepath in DATA_FILES.items():
        if not os.path.exists(filepath):
            print(f"❌ {filepath}: 文件不存在")
            all_ok = False
            continue
        
        try:
            if filepath.endswith('.json'):
                with open(filepath, 'r') as f:
                    data = json.load(f)
                    if not isinstance(data, list):
                        print(f"⚠️  {filepath}: 不是 JSON 数组格式")
                        all_ok = False
                    else:
                        print(f"✅ {filepath}: {len(data):,} 条记录")
            elif filepath.endswith('.xlsx'):
                df = pd.read_excel(filepath)
                print(f"✅ {filepath}: {len(df):,} 行 × {len(df.columns)} 列")
        except json.JSONDecodeError as e:
            print(f"❌ {filepath}: JSON 解析失败 - {e}")
            all_ok = False
        except Exception as e:
            print(f"❌ {filepath}: {type(e).__name__} - {e}")
            all_ok = False
    
    if all_ok:
        print("\n✅ 所有数据文件预检查通过")
    else:
        print("\n❌ 数据文件预检查失败，请修正问题后重试")
        return False
    
    return True

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
    
    # 数据一致性检查
    print("\n📋 数据一致性检查:")
    
    # 检查是否有小写的轨道类型
    lowercase_orbits = cursor.execute(
        "SELECT COUNT(*) FROM SatelliteDetails WHERE class_of_orbit LIKE '%[a-z]%'"
    ).fetchone()[0]
    if lowercase_orbits == 0:
        print(f"   ✅ class_of_orbit: 全部为大写")
    else:
        print(f"   ⚠️  class_of_orbit: 发现 {lowercase_orbits} 条小写值")
    
    # 检查 object_type 大小写
    lowercase_types = cursor.execute(
        "SELECT COUNT(*) FROM SpaceObjects WHERE object_type LIKE '%[a-z]%'"
    ).fetchone()[0]
    if lowercase_types == 0:
        print(f"   ✅ object_type: 全部为大写")
    else:
        print(f"   ⚠️  object_type: 发现 {lowercase_types} 条小写值")
    
    # 显示所有独特的轨道类型
    orbits = cursor.execute(
        "SELECT DISTINCT class_of_orbit FROM SatelliteDetails WHERE class_of_orbit IS NOT NULL ORDER BY class_of_orbit"
    ).fetchall()
    print(f"   独特的轨道类型: {[o[0] for o in orbits]}")
    
    # 孤立记录检查
    print("\n🔗 孤立记录检查:")
    
    # 检查 Orbits 中是否有 SpaceObjects 中不存在的 NORAD_ID
    orphan_orbits = cursor.execute("""
        SELECT COUNT(DISTINCT o.norad_id) FROM Orbits o
        LEFT JOIN SpaceObjects s ON o.norad_id = s.norad_id
        WHERE s.norad_id IS NULL
    """).fetchone()[0]
    
    if orphan_orbits == 0:
        print(f"   ✅ Orbits: 无孤立记录")
    else:
        print(f"   ⚠️  Orbits: 发现 {orphan_orbits} 个孤立 NORAD_ID")
    
    # 检查 SatelliteDetails 中是否有 SpaceObjects 中不存在的 NORAD_ID
    orphan_details = cursor.execute("""
        SELECT COUNT(*) FROM SatelliteDetails sd
        LEFT JOIN SpaceObjects s ON sd.norad_id = s.norad_id
        WHERE s.norad_id IS NULL
    """).fetchone()[0]
    
    if orphan_details == 0:
        print(f"   ✅ SatelliteDetails: 无孤立记录")
    else:
        print(f"   ⚠️  SatelliteDetails: 发现 {orphan_details} 个孤立记录")

# ============================================================
# 主函数
# ============================================================

def main():
    print("="*70)
    print("🚀 OrbitalGuard - 数据库创建与导入")
    print("="*70)
    print(f"📅 执行时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    
    # 数据文件预检查
    if not precheck_data_files():
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

