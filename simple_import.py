import pandas as pd
import mysql.connector
from mysql.connector import Error
import os
from database_config import get_connection_config, test_connection

def create_connection():
    """创建数据库连接"""
    try:
        config = get_connection_config()
        connection = mysql.connector.connect(**config)
        print("数据库连接成功")
        return connection
    except Error as e:
        print(f"数据库连接失败: {e}")
        return None

def clean_data_value(value, column_name):
    """清理数据值，确保类型正确"""
    if pd.isna(value):
        return None
    
    # 转换为字符串并清理
    value_str = str(value).strip()
    
    # 如果是空字符串，返回None
    if value_str == '' or value_str == 'nan':
        return None
    
    # 根据列名处理特殊数据
    if '供货价' in column_name or '建议零售价' in column_name or '销售金额' in column_name or '结算金额' in column_name:
        # 数字列，尝试转换为数字
        try:
            # 移除可能的非数字字符
            cleaned = ''.join(c for c in value_str if c.isdigit() or c in '.-')
            if cleaned:
                return float(cleaned)
            else:
                return 0.0
        except:
            return 0.0
    
    elif '数量' in column_name or '编码' in column_name or '批次' in column_name:
        # 整数列
        try:
            cleaned = ''.join(c for c in value_str if c.isdigit())
            if cleaned:
                return int(cleaned)
            else:
                return None
        except:
            return None
    
    else:
        # 文本列，直接返回
        return value_str

def clean_column_name(col, index):
    """清理列名，确保没有特殊字符"""
    if pd.isna(col) or col == '' or str(col).lower() == 'nan':
        return f'col_{index}'
    else:
        # 清理列名，移除特殊字符
        clean_col = str(col).replace(' ', '_').replace('-', '_').replace('(', '').replace(')', '').replace('/', '_')
        return clean_col

def import_excel_data(excel_file, table_name, connection):
    """导入Excel数据到数据库表"""
    try:
        print(f"正在读取文件: {excel_file}")
        
        # 特殊处理活动方案表
        if '活动方案' in excel_file:
            # 读取原始数据
            df_raw = pd.read_excel(excel_file, header=None)
            
            # 获取第3行作为列名（索引为2）
            column_names = df_raw.iloc[2].tolist()
            
            # 从第5行开始读取数据（索引从4开始）
            df = df_raw.iloc[4:].copy()
            
            # 设置列名
            df.columns = column_names
            
            # 清理列名，确保没有特殊字符
            clean_columns = []
            for i, col in enumerate(df.columns):
                clean_columns.append(clean_column_name(col, i))
            
            df.columns = clean_columns
            
        else:
            df = pd.read_excel(excel_file)
            # 清理列名
            df.columns = [col.replace(' ', '_').replace('-', '_').replace('(', '').replace(')', '') for col in df.columns]
        
        print(f"数据行数: {len(df)}")
        print(f"数据列数: {len(df.columns)}")
        print(f"列名: {list(df.columns)}")
        
        # 清理数据
        print("正在清理数据...")
        for col in df.columns:
            df[col] = df[col].apply(lambda x: clean_data_value(x, col))
        
        # 准备插入数据
        cursor = connection.cursor()
        
        # 构建INSERT语句
        columns = ', '.join(df.columns)
        placeholders = ', '.join(['%s'] * len(df.columns))
        insert_query = f"INSERT INTO {table_name} ({columns}) VALUES ({placeholders})"
        
        print(f"INSERT语句: {insert_query}")
        
        # 准备数据
        data_to_insert = []
        for _, row in df.iterrows():
            row_data = []
            for value in row:
                row_data.append(value)
            data_to_insert.append(row_data)
        
        # 执行批量插入
        cursor.executemany(insert_query, data_to_insert)
        connection.commit()
        
        print(f"成功导入 {len(df)} 行数据到表 {table_name}")
        cursor.close()
        
    except Error as e:
        print(f"导入数据失败: {e}")
        print(f"错误详情: {e.msg}")
    except Exception as e:
        print(f"处理文件时出错: {e}")
        import traceback
        traceback.print_exc()

def main():
    print("=== 数据库连接测试 ===")
    if not test_connection():
        print("\n请先解决数据库连接问题，然后重新运行脚本。")
        print("请修改 database_config.py 中的连接信息。")
        return
    
    # 创建数据库连接
    connection = create_connection()
    if not connection:
        return
    
    # 定义要导入的文件和对应的表名（更新为新的文件名）
    files_to_import = [
        ('客户原始兑付明细.xls', 'customer_redemption_details'),
        ('客户流向.xls', 'customer_flow'),
        ('活动方案.xlsx', 'activity_plan'),
        ('输出结果.xls', 'output_results')
    ]
    
    # 导入每个文件
    for excel_file, table_name in files_to_import:
        if os.path.exists(excel_file):
            print(f"\n{'='*50}")
            print(f"开始导入: {excel_file} -> {table_name}")
            print(f"{'='*50}")
            import_excel_data(excel_file, table_name, connection)
        else:
            print(f"文件不存在: {excel_file}")
    
    connection.close()
    print("\n所有数据导入完成！")

if __name__ == "__main__":
    main() 