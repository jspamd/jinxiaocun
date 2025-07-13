-- 为所有表添加当期日期列
USE jinxiaocun_db;

-- 1. 为客户原始兑付明细表添加当期日期列
ALTER TABLE customer_redemption_details 
ADD COLUMN 当期日期 DATE DEFAULT CURRENT_DATE;

-- 2. 为客户流向表添加当期日期列
ALTER TABLE customer_flow 
ADD COLUMN 当期日期 DATE DEFAULT CURRENT_DATE;

-- 3. 为活动方案表添加当期日期列
ALTER TABLE activity_plan 
ADD COLUMN 当期日期 DATE DEFAULT CURRENT_DATE;

-- 4. 为输出结果表添加当期日期列
ALTER TABLE output_results 
ADD COLUMN 当期日期 DATE DEFAULT CURRENT_DATE;

-- 显示修改后的表结构
DESCRIBE customer_redemption_details;
DESCRIBE customer_flow;
DESCRIBE activity_plan;
DESCRIBE output_results; 