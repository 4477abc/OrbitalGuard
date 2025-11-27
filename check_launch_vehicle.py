import json
import pandas as pd

def check_launch_vehicle():
    print("🔍 正在检查运载火箭数据...")
    
    # 1. 检查 SATCAT 数据
    print("\n[1/2] 检查 Space-Track SATCAT 数据 (data_satcat.json)")
    try:
        with open('data_satcat.json', 'r') as f:
            satcat = json.load(f)
            
        if len(satcat) > 0:
            sample = satcat[0]
            print(f"   示例字段: {list(sample.keys())}")
            
            # 检查是否有火箭相关字段
            vehicle_fields = [k for k in sample.keys() if 'VEHICLE' in k or 'LAUNCH' in k]
            print(f"   可能的火箭字段: {vehicle_fields}")
            
            if not vehicle_fields:
                print("   ⚠️  未发现明显的运载火箭字段")
        else:
            print("   ❌ SATCAT数据为空")
    except Exception as e:
        print(f"   ❌ 读取SATCAT失败: {e}")

    # 2. 检查 UCS 数据库
    print("\n[2/2] 检查 UCS 数据库 (data_ucs_database.xlsx)")
    try:
        # UCS通常包含 'Launch Vehicle' 列
        df = pd.read_excel('data_ucs_database.xlsx')
        print(f"   总列数: {len(df.columns)}")
        
        # 查找包含 'Vehicle' 的列
        vehicle_cols = [col for col in df.columns if 'Vehicle' in str(col) or 'vehicle' in str(col)]
        print(f"   发现火箭相关列: {vehicle_cols}")
        
        if vehicle_cols:
            # 统计非空值
            count = df[vehicle_cols[0]].count()
            total = len(df)
            print(f"   数据覆盖率: {count}/{total} ({count/total*100:.1f}%)")
            
            # 显示前5个独特的火箭型号
            print("   示例火箭型号:")
            print(df[vehicle_cols[0]].unique()[:5])
            return True
        else:
            print("   ⚠️  UCS数据中未找到运载火箭列")
            return False
            
    except Exception as e:
        print(f"   ❌ 读取UCS数据失败: {e}")
        return False

if __name__ == "__main__":
    result = check_launch_vehicle()
    if result:
        print("\n✅ 结论: 风险已化解！UCS数据库包含运载火箭信息。")
    else:
        print("\n⚠️ 结论: 风险仍存在。需确认是否保留该字段。")

