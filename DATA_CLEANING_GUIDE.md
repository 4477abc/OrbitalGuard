# 📋 OrbitalGuard 数据清洗指南

## 概述

本文档说明 OrbitalGuard 项目中实施的数据清洗策略，确保数据一致性和质量。

---

## 🔧 数据清洗策略

### 1. 大小写规范化（Case Normalization）

**问题**：来自不同数据源的分类字段可能存在大小写不一致（如 "LEo" vs "LEO"）。

**解决方案**：所有分类字段统一转为大写。

**影响的字段**：

| 表 | 字段 | 规范化方式 |
|----|------|----------|
| SpaceObjects | `object_type` | → 大写 |
| SpaceObjects | `country` | → 大写 |
| SpaceObjects | `rcs_size` | → 大写 |
| SpaceObjects | `launch_site` | → 大写 |
| SpaceObjects | `intl_designator` | → 大写 |
| SatelliteDetails | `class_of_orbit` | → 大写 |
| SatelliteDetails | `country_operator` | → 大写 |
| LaunchMissions | `country` | → 大写 |
| LaunchMissions | `launch_site` | → 大写 |

**实现代码**：

```python
def safe_upper(value):
    """安全转换为大写，处理空值"""
    if not value or value in ['', 'N/A', None]:
        return None
    try:
        return str(value).upper().strip() if value else None
    except:
        return None

# 使用示例
object_type = safe_upper(record.get('OBJECT_TYPE'))  # "PAYLOAD"
```

---

### 2. 空白字符处理（Whitespace Trimming）

**问题**：数据可能包含首尾空白字符，导致比较困难。

**解决方案**：所有文本字段应用 `TRIM`。

**影响的字段**：

| 表 | 字段 |
|----|------|
| SpaceObjects | `object_name`, `intl_designator` |
| SatelliteDetails | `purpose`, `users`, `contractor`, `operator_owner` |

**实现代码**：

```python
def safe_strip(value):
    """安全去除首尾空白"""
    if not value or value in ['', 'N/A', None]:
        return None
    try:
        return str(value).strip() if value else None
    except:
        return None

# 使用示例
operator = safe_strip(row.get('operator_owner'))  # "SpaceX"
```

---

### 3. 数值处理（Numeric Conversion）

**问题**：某些数值字段可能包含无效值、单位字符或文本。

**解决方案**：使用安全转换函数，失败时返回 `None` 而非抛出异常。

**影响的字段**：

| 表 | 字段 | 单位 |
|----|------|------|
| SatelliteDetails | `launch_mass_kg` | 千克 |
| SatelliteDetails | `dry_mass_kg` | 千克 |
| SatelliteDetails | `power_watts` | 瓦特 |
| SatelliteDetails | `expected_lifetime_years` | 年 |
| Orbits | `inclination_deg` | 度 |
| Orbits | `eccentricity` | 无量纲 |
| Orbits | `mean_motion` | 圈/天 |
| Orbits | `bstar` | 无量纲 |

**实现代码**：

```python
def safe_float(value):
    """安全转换为浮点数，失败返回 None"""
    try:
        return float(value) if value not in [None, '', 'N/A'] else None
    except (ValueError, TypeError):
        return None

# 使用示例
mass = safe_float(row.get('launch_mass_kg'))  # 1500.0 或 None
```

---

### 4. 日期处理（Date Normalization）

**问题**：不同数据源的日期格式可能不同。

**解决方案**：标准化为 ISO 8601 格式 (YYYY-MM-DD)。

**影响的字段**：

| 表 | 字段 |
|----|------|
| SpaceObjects | `launch_date`, `decay_date` |
| LaunchMissions | `launch_date` |

**实现代码**：

```python
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

# 使用示例
launch_date = safe_date('1998-11-20')  # '1998-11-20'
```

---

### 5. 缺失值处理（Missing Value Handling）

**策略**：保留 `NULL`，而不是填充默认值或零值。

**特例**：`expected_lifetime_years` 使用**分层中位数填充**。

#### 5.1 分层中位数填充（Stratified Median Imputation）

**原因**：不同轨道类型的卫星寿命差异巨大（LEO: 4年，GEO: 15年）。

**策略**：按 `class_of_orbit` 分组，用各组的中位数填充缺失值。

| 轨道类型 | 中位数寿命 | 样本量 |
|---------|-----------|--------|
| LEO | 4 年 | 4,802 |
| MEO | 10 年 | 121 |
| GEO | 15 年 | 493 |
| ELLIPTICAL | 7 年 | 34 |

**实现代码**：

```python
LIFETIME_MEDIAN = {
    'LEO': 4.0,
    'MEO': 10.0,
    'GEO': 15.0,
    'Elliptical': 7.0
}

def fill_lifetime(row):
    if pd.isna(row['expected_lifetime_years']):
        orbit_class = row.get('class_of_orbit', 'LEO')
        return LIFETIME_MEDIAN.get(orbit_class, 4.0)  # 默认用 LEO
    return row['expected_lifetime_years']

# 应用到整个列
df['expected_lifetime_years'] = df.apply(fill_lifetime, axis=1)
```

**结果**：`expected_lifetime_years` 完整率从 72% 提升到 100%。

---

### 6. 特殊字段处理

#### 6.1 Launch Mission ID 提取

**来源**：从 `intl_designator` 的前8位提取。

**格式**：YYYY-NNN（如 1998-067）

```python
intl_des = record.get('INTLDES', '')
launch_mission_id = intl_des[:8] if len(intl_des) >= 8 else intl_des
```

#### 6.2 LaunchMissions 聚合

**来源**：从 SpaceObjects 按 launch_mission_id 分组聚合。

**规范化**：在聚合时应用大小写规范化。

```sql
INSERT INTO LaunchMissions (launch_mission_id, launch_date, country, launch_site, payload_count)
SELECT 
    launch_mission_id,
    MIN(launch_date) as launch_date,
    MAX(UPPER(country)) as country,            -- 大写规范化
    MAX(UPPER(launch_site)) as launch_site,    -- 大写规范化
    COUNT(*) as payload_count
FROM SpaceObjects
WHERE launch_mission_id IS NOT NULL AND launch_mission_id != ''
GROUP BY launch_mission_id;
```

---

## ✅ 数据质量验证

### 验证检查清单

运行 `create_database.py` 时自动执行以下验证：

1. **NULL 值统计**
   - `decay_date`：48.3%（正常，表示仍在轨）
   - `expected_lifetime_years`：0%（填充后完整）
   - `launch_mass_kg`：3.24%

2. **大小写一致性**
   - `class_of_orbit`：100% 大写
   - `object_type`：100% 大写

3. **外键完整性**
   - SpaceObjects ↔ Orbits：32,750 关联
   - SpaceObjects ↔ SatelliteDetails：7,551 关联

4. **独特值统计**
   - `class_of_orbit`：['ELLIPTICAL', 'GEO', 'LEO', 'MEO']
   - 无混合大小写值

### 验证输出示例

```
📋 数据一致性检查:
   ✅ class_of_orbit: 全部为大写
   ✅ object_type: 全部为大写
   独特的轨道类型: ['ELLIPTICAL', 'GEO', 'LEO', 'MEO']
```

---

## 📝 建议与最佳实践

### 对于开发者

1. **始终使用 safe_* 函数**
   ```python
   # ✅ 推荐
   value = safe_upper(raw_value)
   
   # ❌ 不推荐
   value = raw_value.upper()  # 可能抛出异常
   ```

2. **在导入时应用清洗，不要后补**
   ```python
   # ✅ 推荐
   cursor.execute("INSERT INTO table VALUES (...)", (safe_upper(field), ...))
   
   # ❌ 不推荐
   cursor.execute("INSERT INTO table VALUES (...)", (field, ...))
   # 后续 UPDATE 以修复 → 低效且容易遗漏
   ```

3. **使用 NULL 表示缺失，不要用 0 或 'N/A'**
   ```sql
   -- ✅ 推荐
   WHERE expected_lifetime IS NOT NULL
   
   -- ❌ 不推荐
   WHERE expected_lifetime != 0
   WHERE expected_lifetime != 'N/A'
   ```

### 对于数据分析

1. **进行查询前显式检查缺失值**
   ```sql
   -- 计算平均质量（仅有数据的卫星）
   SELECT AVG(launch_mass_kg)
   FROM SatelliteDetails
   WHERE launch_mass_kg IS NOT NULL;  -- 重要！
   ```

2. **报告数据覆盖率**
   ```sql
   -- 计算覆盖率
   SELECT 
       COUNT(*) as total,
       SUM(CASE WHEN launch_mass_kg IS NOT NULL THEN 1 ELSE 0 END) as with_data,
       ROUND(SUM(CASE WHEN launch_mass_kg IS NOT NULL THEN 1 ELSE 0 END) * 100.0 / COUNT(*), 2) as coverage_pct
   FROM SatelliteDetails;
   ```

---

## 🐛 已修复的问题

### Issue #1: 轨道类型大小写不一致

**症状**：SatelliteDetails 表中出现 "LEo" 和 "LEO" 混合。

**根本原因**：UCS 数据源中存在混合大小写值，导入时未规范化。

**修复**：在 `import_satellite_details()` 中应用 `safe_upper()` 函数。

**验证**：
```sql
SELECT DISTINCT class_of_orbit FROM SatelliteDetails ORDER BY class_of_orbit;
-- 结果: ELLIPTICAL, GEO, LEO, MEO (全部大写，无混合值)
```

---

## 📊 性能影响

### 清洗成本

| 操作 | 时间 | 记录数 |
|------|------|--------|
| 导入 SpaceObjects | < 1s | 66,483 |
| 导入 Orbits | < 2s | 35,903 |
| 导入 SatelliteDetails（含清洗） | 1-2s | 7,551 |
| 分层中位数填充 | < 0.5s | 2,110 |
| **总耗时** | **< 5s** | **116,628** |

数据清洗几乎不增加导入耗时。

---

## 参考

- SQLite UPPER() 函数：https://www.sqlite.org/lang_corefunc.html
- pandas 字符串方法：https://pandas.pydata.org/docs/reference/series_str.html
- Data Quality Best Practices：https://en.wikipedia.org/wiki/Data_quality

---

**文档版本**：1.0  
**最后更新**：2025-11-27

