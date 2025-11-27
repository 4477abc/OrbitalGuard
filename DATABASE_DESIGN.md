# 🗄️ OrbitalGuard 数据库设计文档 (精简版 v2.0)

## 📐 实体关系图 (ER Diagram)

只包含基于真实数据源（SATCAT, GP, UCS）的核心实体。不包含任何合成数据或手动整理的历史事件表。

```mermaid
erDiagram
    SpaceObjects ||--o{ Orbits : "has_history"
    SpaceObjects ||--o| SatelliteDetails : "has_details"
    LaunchMissions ||--o{ SpaceObjects : "launched"

    SpaceObjects {
        int norad_id PK "NORAD目录号"
        string object_name "物体名称"
        string intl_designator "国际编号"
        string object_type "物体类型(PAYLOAD/DEBRIS/ROCKET_BODY)"
        string country "所属国家/组织"
        string launch_site "发射场代码"
        date launch_date "发射日期"
        date decay_date "衰减日期(null表示仍在轨)"
        string rcs_size "雷达截面积(SMALL/MEDIUM/LARGE)"
    }

    Orbits {
        int orbit_id PK "轨道记录ID"
        int norad_id FK "NORAD目录号"
        datetime epoch "历元时间"
        float inclination_deg "倾角"
        float eccentricity "偏心率"
        float mean_motion "平均运动"
        float ra_of_asc_node "升交点赤经"
        float arg_of_pericenter "近地点幅角"
        float mean_anomaly "平近点角"
        float altitude_km "轨道高度(计算值)"
    }

    SatelliteDetails {
        int norad_id PK_FK "NORAD目录号"
        float launch_mass_kg "发射质量"
        float dry_mass_kg "干质量"
        float power_watts "功率"
        float expected_lifetime_years "预期寿命"
        string purpose "用途"
        string users "用户类型"
        string contractor "承包商"
        string operator_owner "运营商/所有者"
        string class_of_orbit "轨道类别"
    }

    LaunchMissions {
        string launch_id PK "国际编号前缀(如1998-067)"
        date launch_date "发射日期"
        string country "发射国家"
        int payload_count "载荷数量"
    }
```

---

## 📊 表结构详细设计

### 表1: SpaceObjects（空间物体主表）
**数据来源**: `data_satcat.json`

```sql
CREATE TABLE SpaceObjects (
    norad_id INTEGER PRIMARY KEY,
    object_name VARCHAR(100),
    intl_designator VARCHAR(20),
    object_type VARCHAR(20),
    country VARCHAR(50),
    launch_date DATE,
    decay_date DATE,
    rcs_size VARCHAR(10),
    launch_mission_id VARCHAR(20) -- 提取自intl_designator (e.g. 1998-067)
);
```

### 表2: Orbits（轨道参数表）
**数据来源**: `data_active_gp.json` 以及碎片数据文件

```sql
CREATE TABLE Orbits (
    orbit_id SERIAL PRIMARY KEY,
    norad_id INTEGER,
    epoch TIMESTAMP,
    inclination_deg DECIMAL(8,4),
    eccentricity DECIMAL(10,8),
    mean_motion DECIMAL(12,8),
    ra_of_asc_node DECIMAL(8,4),
    arg_of_pericenter DECIMAL(8,4),
    mean_anomaly DECIMAL(8,4),
    FOREIGN KEY (norad_id) REFERENCES SpaceObjects(norad_id)
);
```

### 表3: SatelliteDetails（详细信息表）
**数据来源**: `data_ucs_database.xlsx` (手动下载)

```sql
CREATE TABLE SatelliteDetails (
    norad_id INTEGER PRIMARY KEY,
    launch_mass_kg DECIMAL(10,2),
    power_watts DECIMAL(10,2),
    expected_lifetime_years DECIMAL(5,2),
    purpose VARCHAR(100),
    operator_owner VARCHAR(100),
    FOREIGN KEY (norad_id) REFERENCES SpaceObjects(norad_id)
);
```

### 表4: LaunchMissions（发射任务表）
**数据来源**: 从SATCAT数据中聚合生成（不是外部数据源）

```sql
-- 通过查询生成，无需单独下载
CREATE TABLE LaunchMissions AS
SELECT 
    SUBSTRING(intl_designator, 1, 8) as launch_id,
    MIN(launch_date) as launch_date,
    MAX(country) as country,
    COUNT(*) as payload_count
FROM SpaceObjects
GROUP BY 1;
```

---

## 🔄 Use Case 实现逻辑调整

### Use Case 3: 碎片分析 (不依赖解体事件表)
- **原逻辑**: JOIN DebrisEvents表查询解体时间
- **新逻辑**: 直接查询 `object_name LIKE '%FENGYUN 1C%'` 的所有物体，分析其当前的 `Orbits` 数据（高度、倾角分布）。我们关注的是**现状**，而不是历史那一刻。

### Use Case 4: 地面站调度 (不依赖地面站表)
- **原逻辑**: JOIN GroundStations表
- **新逻辑**: 用户输入任意坐标 (lat, lon)，系统实时计算可见性。
  - SQL示例:
  ```sql
  -- 这是一个概念查询，实际计算可能在Python层完成
  SELECT * FROM Orbits 
  WHERE calculate_visibility(lat, lon, epoch, inclination...) = TRUE
  ```

---

**版本**: v2.0 (纯真实数据版)
**设计日期**: 2025-11-27
