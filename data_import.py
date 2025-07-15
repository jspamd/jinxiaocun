import pandas as pd
import mysql.connector
from mysql.connector import Error
import os
from datetime import datetime, date
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

def check_table_structure(connection, table_name):
    """检查表结构"""
    try:
        cursor = connection.cursor()
        cursor.execute(f"DESCRIBE {table_name}")
        columns = cursor.fetchall()
        print(f"\n=== {table_name} 表结构 ===")
        for col in columns:
            print(f"字段: {col[0]}, 类型: {col[1]}, 允许NULL: {col[2]}, 键: {col[3]}, 默认值: {col[4]}, 额外: {col[5]}")
        cursor.close()
        return [col[0] for col in columns if col[0] != 'id']
    except Error as e:
        print(f"检查表结构失败: {e}")
        return []

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
    if '流入方编码' in column_name:
        # 确保流入方编码作为字符串处理
        return value_str
    
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
        print(f"\n正在读取文件: {excel_file}")
        
        # 获取今天的日期
        today = date.today()
        print(f"今天日期: {today}")
        
        # 删除今天日期的数据
        cursor = connection.cursor()
        delete_query = f"DELETE FROM {table_name} WHERE 当期日期 = %s"
        cursor.execute(delete_query, (today,))
        deleted_count = cursor.rowcount
        connection.commit()
        print(f"已删除 {deleted_count} 条今天日期的数据")
        
        # 特殊处理活动方案表
        if 'activity_plan' in table_name:
            print("检测到活动方案表，使用特殊处理...")
            # 读取原始数据时，强制将流入方编码列作为字符串处理
            df_raw = pd.read_excel(excel_file, header=None, dtype={'流入方编码': str})
            print(f"原始数据行数: {len(df_raw)}")
            print(f"原始数据列数: {len(df_raw.columns)}")
            
            # 获取第3行作为列名（索引为4）
            column_names = df_raw.iloc[2].tolist()
            print(f"原始列名: {column_names}")
            
            # 从第5行开始读取数据（索引从4开始），但需要检查是否遇到"进货单位"
            start_row = 4
            end_row = len(df_raw)
            
            # 查找"进货单位"行
            for i in range(start_row, len(df_raw)):
                row_data = df_raw.iloc[i].tolist()
                # 检查这一行是否包含"进货单位"
                if any('进货单位' in str(cell) for cell in row_data if pd.notna(cell)):
                    end_row = i
                    print(f"在第{i+1}行发现'进货单位'，停止读取数据")
                    break
            
            # 读取指定范围的数据
            df = df_raw.iloc[start_row:end_row].copy()
            print(f"数据行数: {len(df)}")
            
            # 设置列名
            df.columns = column_names
            
            # 清理列名，确保没有特殊字符
            clean_columns = []
            for i, col in enumerate(df.columns):
                clean_columns.append(clean_column_name(col, i))
            
            df.columns = clean_columns
            print(f"清理后列名: {list(df.columns)}")
            
        else:
            # 在导入数据时，强制将物料编码、流出方编码、出库单价、批次、金额列作为字符串处理
            if 'customer_flow' in table_name:
                df = pd.read_excel(excel_file, dtype={'物料编码': str, '流出方编码': str, '出库单价': str, '批次': str, '金额': str})

            if 'output_results' in table_name:
                df = pd.read_excel(excel_file, dtype={'物料编码': str, '流出方编码': str, '批次': str})
            else:
                df = pd.read_excel(excel_file, dtype={'流入方编码': str})
            # 清理列名
            df.columns = [col.replace(' ', '_').replace('-', '_').replace('(', '').replace(')', '') for col in df.columns]
        
        print(f"最终数据行数: {len(df)}")
        print(f"最终数据列数: {len(df.columns)}")
        print(f"最终列名: {list(df.columns)}")
        
        # 检查表结构
        table_columns = check_table_structure(connection, table_name)
        print(f"数据库表字段: {table_columns}")
        
        # 检查列名是否匹配
        excel_columns = list(df.columns)
        missing_columns = [col for col in excel_columns if col not in table_columns]
        extra_columns = [col for col in table_columns if col not in excel_columns]
        
        if missing_columns:
            print(f"警告: Excel中有但数据库表中没有的列: {missing_columns}")
        if extra_columns:
            print(f"警告: 数据库表中有但Excel中没有的列: {extra_columns}")
        
        # 只使用数据库表中存在的列，并过滤掉无效列名
        valid_columns = [col for col in excel_columns if col in table_columns and str(col).lower() != 'nan' and col != '']
        df = df[valid_columns]
        
        print(f"将使用的列: {valid_columns}")
        
        # 清理数据
        print("正在清理数据...")
        for col in valid_columns:
            df[col] = df[col].apply(lambda x: clean_data_value(x, col))
        
        # 准备插入数据
        cursor = connection.cursor()
        
        # 构建INSERT语句，包含当期日期列
        columns_with_date = valid_columns + ['当期日期']
        columns_str = ', '.join(columns_with_date)
        placeholders = ', '.join(['%s'] * len(columns_with_date))
        insert_query = f"INSERT INTO {table_name} ({columns_str}) VALUES ({placeholders})"
        
        print(f"INSERT语句: {insert_query}")
        
        # 准备数据，包含当期日期
        data_to_insert = []
        for idx, row in df.iterrows():
            row_data = []
            for col in valid_columns:
                value = row[col]
                row_data.append(value)
            # 添加当期日期
            row_data.append(today)
            data_to_insert.append(row_data)
            
            # 打印前几行数据用于调试
            if idx < 3:
                print(f"第{idx+1}行数据: {row_data}")
        
        # 执行批量插入
        cursor.executemany(insert_query, data_to_insert)
        connection.commit()
        
        print(f"成功导入 {len(df)} 行数据到表 {table_name}")
        cursor.close()
        
    except Error as e:
        print(f"导入数据失败: {e}")
        print(f"错误代码: {e.errno}")
        print(f"错误消息: {e.msg}")
    except Exception as e:
        print(f"处理文件时出错: {e}")
        import traceback
        traceback.print_exc()

def main():
    print("=== 数据库连接测试 ===")
    if not test_connection():
        print("\n请先解决数据库连接问题，然后重新运行脚本。")
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