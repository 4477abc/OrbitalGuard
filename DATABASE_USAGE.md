# 🗄️ OrbitalGuard 数据库使用指南

## 📊 数据库概览

**数据库文件**: `orbitalguard.db` (SQLite 3)  
**文件大小**: ~10 MB  
**记录总数**: 116,628 条

### 数据表统计

| 表名 | 记录数 | 说明 |
|------|--------|------|
| `SpaceObjects` | 66,483 | 所有空间物体（卫星、碎片、火箭体） |
| `Orbits` | 35,903 | 轨道参数（TLE数据） |
| `SatelliteDetails` | 7,551 | 卫星详细信息（UCS数据） |
| `LaunchMissions` | 6,691 | 发射任务聚合 |

---

## 🚀 快速开始

### 方法1：命令行 (sqlite3)

```bash
# 打开数据库
sqlite3 orbitalguard.db

# 启用列模式和表头
.mode column
.headers on

# 查看所有表
.tables

# 查看表结构
.schema SpaceObjects

# 执行查询
SELECT * FROM SpaceObjects LIMIT 5;

# 退出
.quit
```

### 方法2：Python

```python
import sqlite3

# 连接数据库
conn = sqlite3.connect('orbitalguard.db')
cursor = conn.cursor()

# 执行查询
cursor.execute("SELECT COUNT(*) FROM SpaceObjects WHERE decay_date IS NULL")
active_count = cursor.fetchone()[0]
print(f"在轨物体数量: {active_count}")

conn.close()
```

### 方法3：DB Browser for SQLite (GUI)

1. 下载: https://sqlitebrowser.org/
2. 打开 `orbitalguard.db`
3. 可视化浏览表、执行查询、查看数据

---

## 📋 表结构详解

### 1. SpaceObjects（空间物体主表）

| 字段 | 类型 | 说明 | 示例 |
|------|------|------|------|
| `norad_id` | INTEGER PK | NORAD目录号 | 25544 |
| `object_name` | TEXT | 物体名称 | ISS (ZARYA) |
| `intl_designator` | TEXT | 国际编号 | 1998-067A |
| `object_type` | TEXT | 类型 | PAYLOAD/DEBRIS/ROCKET BODY |
| `country` | TEXT | 所属国家 | US |
| `launch_date` | TEXT | 发射日期 | 1998-11-20 |
| `decay_date` | TEXT | 衰减日期 | NULL表示仍在轨 |
| `rcs_size` | TEXT | 雷达截面积 | LARGE/MEDIUM/SMALL |
| `launch_site` | TEXT | 发射场 | TYMSC |
| `launch_mission_id` | TEXT | 发射任务ID | 1998-067 |

**关键查询**：
```sql
-- 查询所有在轨的有效载荷
SELECT * FROM SpaceObjects 
WHERE decay_date IS NULL AND object_type = 'PAYLOAD';

-- 统计各国的在轨物体数量
SELECT country, COUNT(*) as count
FROM SpaceObjects
WHERE decay_date IS NULL
GROUP BY country
ORDER BY count DESC;
```

---

### 2. Orbits（轨道参数表）

| 字段 | 类型 | 说明 | 单位 |
|------|------|------|------|
| `orbit_id` | INTEGER PK | 自增ID | - |
| `norad_id` | INTEGER FK | NORAD目录号 | - |
| `epoch` | TEXT | 历元时间 | ISO 8601 |
| `inclination_deg` | REAL | 轨道倾角 | 度 |
| `eccentricity` | REAL | 偏心率 | 无量纲 |
| `mean_motion` | REAL | 平均运动 | 圈/天 |
| `ra_of_asc_node` | REAL | 升交点赤经 | 度 |
| `arg_of_pericenter` | REAL | 近地点幅角 | 度 |
| `mean_anomaly` | REAL | 平近点角 | 度 |
| `bstar` | REAL | BSTAR拖曳项 | - |

**关键查询**：
```sql
-- 查询低倾角轨道（赤道轨道）
SELECT s.object_name, o.inclination_deg, o.mean_motion
FROM Orbits o
JOIN SpaceObjects s ON o.norad_id = s.norad_id
WHERE o.inclination_deg < 10
  AND s.decay_date IS NULL;

-- 统计不同倾角区间的物体数量
SELECT 
    CASE 
        WHEN inclination_deg < 30 THEN 'Low (0-30°)'
        WHEN inclination_deg < 60 THEN 'Medium (30-60°)'
        WHEN inclination_deg < 90 THEN 'High (60-90°)'
        ELSE 'Polar (90°+)'
    END as inclination_class,
    COUNT(*) as count
FROM Orbits
GROUP BY inclination_class;
```

---

### 3. SatelliteDetails（卫星详细信息）

| 字段 | 类型 | 说明 | 完整度 |
|------|------|------|--------|
| `norad_id` | INTEGER PK/FK | NORAD目录号 | 100% |
| `launch_mass_kg` | REAL | 发射质量 | 97% |
| `dry_mass_kg` | REAL | 干质量 | 10% |
| `power_watts` | REAL | 功率 | 8% |
| `expected_lifetime_years` | REAL | 预期寿命（**已填充**） | **100%** |
| `purpose` | TEXT | 用途 | 100% |
| `users` | TEXT | 用户类型 | 100% |
| `contractor` | TEXT | 承包商 | ~80% |
| `operator_owner` | TEXT | 运营商/所有者 | 100% |
| `class_of_orbit` | TEXT | 轨道类别 | 100% |
| `country_operator` | TEXT | 运营国家 | 100% |

**重要说明**：
- `expected_lifetime_years` 使用**分层中位数填充**策略，缺失值已按轨道类型填充（LEO=4年, MEO=10年, GEO=15年）

**关键查询**：
```sql
-- 查询超过预期寿命的卫星
SELECT 
    s.object_name,
    sd.operator_owner,
    sd.expected_lifetime_years,
    ROUND((JULIANDAY('now') - JULIANDAY(s.launch_date)) / 365.25, 2) as years_in_orbit
FROM SpaceObjects s
JOIN SatelliteDetails sd ON s.norad_id = sd.norad_id
WHERE s.decay_date IS NULL
  AND (JULIANDAY('now') - JULIANDAY(s.launch_date)) / 365.25 > sd.expected_lifetime_years
ORDER BY years_in_orbit DESC;

-- 统计不同用途的卫星分布
SELECT purpose, COUNT(*) as count
FROM SatelliteDetails
GROUP BY purpose
ORDER BY count DESC
LIMIT 10;
```

---

### 4. LaunchMissions（发射任务）

| 字段 | 类型 | 说明 |
|------|------|------|
| `launch_mission_id` | TEXT PK | 发射任务ID (如 1998-067) |
| `launch_date` | TEXT | 发射日期 |
| `country` | TEXT | 发射国家 |
| `launch_site` | TEXT | 发射场 |
| `payload_count` | INTEGER | 载荷数量 |

**关键查询**：
```sql
-- 查询载荷数量最多的发射任务（一箭多星）
SELECT 
    launch_mission_id,
    launch_date,
    country,
    payload_count
FROM LaunchMissions
ORDER BY payload_count DESC
LIMIT 10;

-- 每年的发射次数趋势
SELECT 
    SUBSTR(launch_date, 1, 4) as year,
    COUNT(*) as launches,
    SUM(payload_count) as total_payloads
FROM LaunchMissions
WHERE year >= '2010'
GROUP BY year
ORDER BY year;
```

---

## 💡 常用查询示例

### 示例1：碎片群分析（Use Case 3）

```sql
-- FENGYUN 1C 碎片的轨道倾角分布
SELECT 
    ROUND(o.inclination_deg, 0) as inclination_bucket,
    COUNT(*) as debris_count
FROM Orbits o
JOIN SpaceObjects s ON o.norad_id = s.norad_id
WHERE s.object_name LIKE '%FENGYUN 1C%'
GROUP BY inclination_bucket
ORDER BY inclination_bucket;
```

### 示例2：碰撞风险评估（Use Case 1）

```sql
-- 查询高密度轨道区域（根据平均运动聚类）
SELECT 
    ROUND(mean_motion, 1) as mm_bucket,
    COUNT(*) as object_count,
    ROUND(AVG(inclination_deg), 2) as avg_inclination
FROM Orbits
GROUP BY mm_bucket
HAVING COUNT(*) > 100
ORDER BY object_count DESC;
```

### 示例3：合规性报告（Use Case 5）

```sql
-- 在轨超过25年的物体（违反IADC准则）
SELECT 
    country,
    COUNT(*) as overdue_count,
    ROUND(AVG((JULIANDAY('now') - JULIANDAY(launch_date)) / 365.25), 2) as avg_years_in_orbit
FROM SpaceObjects
WHERE decay_date IS NULL
  AND (JULIANDAY('now') - JULIANDAY(launch_date)) / 365.25 > 25
GROUP BY country
ORDER BY overdue_count DESC;
```

---

## 🔍 数据质量说明

### 完整度
- **100% 完整**: NORAD_ID, 物体名称, 发射日期, 轨道参数（GP数据）
- **97% 完整**: 发射质量
- **72% 完整（原始）→ 100%（填充后）**: 预期寿命

### 缺失值处理
- `decay_date` 为 NULL：表示物体仍在轨，**不是缺失数据**
- `expected_lifetime_years`：采用**分层中位数填充**
  - LEO: 4年（基于4,802个样本）
  - MEO: 10年（基于121个样本）
  - GEO: 15年（基于493个样本）

### 数据来源
- **SpaceObjects**: Space-Track.org SATCAT
- **Orbits**: Space-Track.org GP (General Perturbations)
- **SatelliteDetails**: UCS Satellite Database
- **LaunchMissions**: 从 SpaceObjects 聚合生成

---

## 📚 参考资源

- **Space-Track.org**: https://www.space-track.org/
- **UCS Satellite Database**: https://www.ucsusa.org/resources/satellite-database
- **SQLite Documentation**: https://www.sqlite.org/docs.html
- **TLE格式说明**: https://en.wikipedia.org/wiki/Two-line_element_set

---

**数据库版本**: v1.0  
**创建日期**: 2025-11-27  
**数据快照日期**: 2025-11-27

