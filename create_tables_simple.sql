-- Active: 1748437189209@@127.0.0.1@3306@jinxiaocun_db
-- 创建数据库
CREATE DATABASE IF NOT EXISTS jinxiaocun_db CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;

USE jinxiaocun_db;

-- 1. 客户原始兑付明细表
CREATE TABLE IF NOT EXISTS customer_redemption_details (
    id INT AUTO_INCREMENT PRIMARY KEY,
    业务日期 VARCHAR(255),
    三级公司客户名称 VARCHAR(255),
    数量 INT,
    规格 VARCHAR(255),
    批号 VARCHAR(255),
    本次结算金额 DECIMAL(10,2),
    商品名称 VARCHAR(255),
    金额 DECIMAL(10,2),
    当期日期 DATE DEFAULT (CURRENT_DATE)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- 2. 客户流向表
CREATE TABLE IF NOT EXISTS customer_flow (
    id INT AUTO_INCREMENT PRIMARY KEY,
    进货日期 VARCHAR(255),
    流入方编码 VARCHAR(255),
    流入方别名 VARCHAR(255),
    流入方名称 VARCHAR(255),
    物料编码 VARCHAR(255),
    物料名称 VARCHAR(255),
    销售数量 INT,
    出库单价 DECIMAL(10,2),
    金额 DECIMAL(10,2),
    流出方编码 VARCHAR(255),
    流出方名称 VARCHAR(255),
    批次 VARCHAR(255),
    规格型号 VARCHAR(255),
    流入方组织 VARCHAR(255),
    客户分线 VARCHAR(255),
    供货价 DECIMAL(10,2),
    流出方组织 VARCHAR(255),
    当期日期 DATE DEFAULT (CURRENT_DATE)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- 3. 活动方案表（字段名与Excel列名完全匹配）
CREATE TABLE IF NOT EXISTS activity_plan (
    id INT AUTO_INCREMENT PRIMARY KEY,
    产品名称 VARCHAR(255),
    剂型 VARCHAR(255),
    规格 VARCHAR(255),
    每件数量 VARCHAR(255),
    供货价 DECIMAL(10,2),
    建议零售价 DECIMAL(10,2),
    订货数量 INT,
    活动政策 VARCHAR(500),
    活动对象 VARCHAR(500),
    当期日期 DATE DEFAULT (CURRENT_DATE)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- 4. 输出结果表
CREATE TABLE IF NOT EXISTS output_results (
    id INT AUTO_INCREMENT PRIMARY KEY,
    进货日期 DATETIME,
    流入方编码 VARCHAR(255),
    流入方别名 VARCHAR(255),
    流入方名称 VARCHAR(255),
    物料编码 VARCHAR(255),
    物料名称 VARCHAR(255),
    销售数量 INT,
    出库单价 DECIMAL(10,2),
    活动政策 INT,
    赠品金额 INT,
    销售金额 DECIMAL(10,2),
    流出方编码 VARCHAR(255),
    流出方名称 VARCHAR(255),
    批次 VARCHAR(255),
    规格型号 VARCHAR(255),
    渠道关系 DECIMAL(10,2),
    流入人代码 VARCHAR(255),
    流入人名称 VARCHAR(255),
    流入方组织 VARCHAR(255),
    当期日期 DATE DEFAULT (CURRENT_DATE)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci; 