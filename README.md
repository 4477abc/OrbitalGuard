# 🚀 OrbitalGuard

**近地轨道空间碎片与卫星交通管理系统**

LSE ST207 数据库课程项目

---

## 📁 项目精简结构

```
OrbitalGuard/
├── 📄 PROJECT_PROPOSAL.md      # ⭐ 项目白皮书（核心文档）
├── 📄 DATABASE_DESIGN.md       # ⭐ 数据库设计（ER图 + Schema）
├── 📄 DATA_DOWNLOAD_GUIDE.md   # 数据下载指南
├── 📄 README.md                # 本文件
│
├── 🔧 config.py                # 账号配置（不上传Git）
├── 🐍 download_data.py         # ⭐ 数据下载脚本（唯一入口）
│
└── 📊 data_*.json              # 下载的数据文件（不上传Git）
```

---

## 🎯 项目核心

本项目旨在利用**真实航天数据**，构建一个空间碎片追踪与预警系统。

### 4个核心数据表 (基于真实数据)

1. **SpaceObjects** (卫星主表) - 来源: Space-Track SATCAT
2. **Orbits** (轨道参数表) - 来源: Space-Track GP Data
3. **SatelliteDetails** (详细信息表) - 来源: UCS Database
4. **LaunchMissions** (发射任务表) - 来源: 聚合生成

### 5个核心 Use Cases

1. **碰撞预警** - 基于实时TLE计算距离
2. **发射窗口** - 基于LEO物体分布寻找空窗
3. **碎片分析** - 分析Fengyun-1C等碎片群的轨道特征
4. **地面站调度** - 动态计算任意地点的卫星可见性
5. **合规报告** - 评估卫星寿命与离轨合规性

---

## 🚀 快速开始

### 1. 配置
修改 `config.py` 填入Space-Track账号。

### 2. 下载
```bash
python download_data.py
```

### 3. 补充
手动下载UCS数据库文件到项目目录。

---

**状态**: ✅ 已完成设计与数据验证  
**下一步**: 数据库搭建与数据导入
