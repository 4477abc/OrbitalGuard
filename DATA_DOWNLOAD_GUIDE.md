# 📥 数据下载指南

## 🎯 核心数据集 (Core Datasets)

本项目只使用真实存在的、公开的航天数据。不使用任何合成数据。

| 数据集 | 来源 | 获取方式 | 用途 |
|--------|------|----------|------|
| **1. SATCAT卫星目录** | Space-Track | `download_data.py` | 卫星基础信息 (ID, 国家, 发射日期) |
| **2. 活跃卫星GP数据** | Space-Track | `download_data.py` | 实时轨道参数 (TLE, 高度, 倾角) |
| **3. 碎片数据 (Fengyun-1C等)** | Space-Track | `download_data.py` | 碎片分布分析 (Use Case 3) |
| **4. UCS卫星数据库** | UCS官网 | **手动下载** | 卫星物理属性 (质量, 寿命, 用途) |

---

## 🚀 自动化下载步骤

### 1. 配置账号
确保 `config.py` 文件存在且包含你的Space-Track账号：
```python
SPACETRACK_USERNAME = "your_email@example.com"
SPACETRACK_PASSWORD = "your_password"
```

### 2. 运行脚本
```bash
python download_data.py
```
脚本将自动下载：
- `data_satcat.json` (~50MB)
- `data_active_gp.json` (~5MB)
- `data_fengyun1c_debris.json` (~1MB)
- `data_cosmos2251_debris.json`
- `data_iridium33_debris.json`

---

## 🖐️ 手动下载步骤 (UCS数据库)

由于UCS官网不提供API，需手动下载补充数据：

1. 访问: [UCS Satellite Database](https://www.ucs.org/resources/satellite-database)
2. 点击下载 **"Database (Excel format)"**
3. 将文件重命名为: `data_ucs_database.xlsx`
4. 放入项目根目录

---

## ⚠️ 注意事项

- **API限流**: 脚本已内置延时，请勿频繁（<1分钟）重复运行。
- **文件安全**: `config.py` 和所有数据文件已加入 `.gitignore`，**切勿**上传到GitHub。
