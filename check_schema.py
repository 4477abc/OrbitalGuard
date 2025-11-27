"""
Schema Compatibility Check Script
检查实际数据文件与数据库Schema设计的一致性
"""

import json
import pandas as pd
import os

def check_schema_compatibility():
    print("🔍 开始 Schema 兼容性检查...\n")
    
    # ============================================================
    # 1. 检查 SATCAT -> SpaceObjects 表
    # ============================================================
    print("[1/3] 检查 SpaceObjects 表 (数据源: data_satcat.json)")
    try:
        with open('data_satcat.json', 'r') as f:
            data = json.load(f)
            sample = data[0]
            
        # 数据库字段 vs 实际JSON字段
        mapping = {
            "norad_id": "NORAD_CAT_ID",
            "object_name": "SATNAME",  # 注意：SATCAT中叫SATNAME, GP中叫OBJECT_NAME
            "intl_designator": "INTLDES",
            "object_type": "OBJECT_TYPE",
            "country": "COUNTRY",
            "launch_date": "LAUNCH",
            "decay_date": "DECAY",
            "rcs_size": "RCS_SIZE",
            "launch_site": "SITE"
        }
        
        print(f"   ✅ 样本记录字段: {list(sample.keys())[:8]}...")
        
        missing = []
        for db_field, json_field in mapping.items():
            if json_field not in sample:
                missing.append(f"{db_field} -> {json_field}")
        
        if missing:
            print(f"   ⚠️  字段缺失/名称不匹配: {missing}")
            print("   👉 建议: 更新导入脚本中的字段映射")
        else:
            print("   ✅ 所有核心字段均存在")
            
    except Exception as e:
        print(f"   ❌ 检查失败: {e}")

    # ============================================================
    # 2. 检查 Active GP -> Orbits 表
    # ============================================================
    print("\n[2/3] 检查 Orbits 表 (数据源: data_active_gp.json)")
    try:
        with open('data_active_gp.json', 'r') as f:
            data = json.load(f)
            sample = data[0]
            
        mapping = {
            "norad_id": "NORAD_CAT_ID",
            "epoch": "EPOCH",
            "inclination_deg": "INCLINATION",
            "eccentricity": "ECCENTRICITY",
            "mean_motion": "MEAN_MOTION",
            "ra_of_asc_node": "RA_OF_ASC_NODE",
            "arg_of_pericenter": "ARG_OF_PERICENTER",
            "mean_anomaly": "MEAN_ANOMALY",
            "bstar": "BSTAR" # 额外检查
        }
        
        print(f"   ✅ 样本记录字段: {list(sample.keys())[:8]}...")
        
        missing = []
        for db_field, json_field in mapping.items():
            if json_field not in sample:
                missing.append(f"{db_field} -> {json_field}")
        
        if missing:
            print(f"   ⚠️  字段缺失: {missing}")
        else:
            print("   ✅ 所有轨道参数字段均存在")
            
    except Exception as e:
        print(f"   ❌ 检查失败: {e}")

    # ============================================================
    # 3. 检查 UCS -> SatelliteDetails 表
    # ============================================================
    print("\n[3/3] 检查 SatelliteDetails 表 (数据源: data_ucs_database.xlsx)")
    try:
        df = pd.read_excel('data_ucs_database.xlsx')
        cols = df.columns.tolist()
        
        mapping = {
            "norad_id": "NORAD Number",
            "launch_mass_kg": "Launch Mass (kg.)", # 注意这里的点
            "dry_mass_kg": "Dry Mass (kg.)",
            "power_watts": "Power (watts)",
            "expected_lifetime_years": "Expected Lifetime (yrs.)",
            "purpose": "Purpose",
            "users": "Users",
            "contractor": "Contractor",
            "operator_owner": "Operator/Owner",
            "class_of_orbit": "Class of Orbit"
        }
        
        print(f"   ✅ Excel列名示例: {cols[:5]}")
        
        missing = []
        for db_field, excel_col in mapping.items():
            if excel_col not in cols:
                # 尝试模糊匹配
                found = False
                for c in cols:
                    if excel_col.replace('.','').lower() in c.lower():
                        print(f"   ℹ️  字段名微调: '{excel_col}' -> '{c}'")
                        found = True
                        break
                if not found:
                    missing.append(f"{db_field} -> {excel_col}")
        
        if missing:
            print(f"   ⚠️  关键列名不匹配: {missing}")
            print("   👉 建议: 在导入时需严格匹配Excel的列头")
        else:
            print("   ✅ 所有详细信息字段均能匹配")
            
    except Exception as e:
        print(f"   ❌ 检查失败: {e}")

if __name__ == "__main__":
    check_schema_compatibility()

