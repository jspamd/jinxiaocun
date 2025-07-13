import pandas as pd
import mysql.connector
from mysql.connector import Error
import os

def create_database_connection():
    """创建数据库连接"""
    try:
        connection = mysql.connector.connect(
            host='127.0.0.1',
            user='root',  # 请根据实际情况修改
            password='123456',  # 请根据实际情况修改
            database='jinxiaocun_db'  # 数据库名称
        )
        return connection
    except Error as e:
        print(f"数据库连接错误: {e}")
        return None

def import_excel_to_database(excel_file, table_name, connection):
    """将Excel文件导入到数据库表"""
    try:
        # 读取Excel文件
        df = pd.read_excel(excel_file)
        
        # 处理列名，移除特殊字符
        df.columns = [col.replace(' ', '_').replace('-', '_').replace('(', '').replace(')', '') for col in df.columns]
        
        # 处理活动方案表的特殊结构
        if '活动方案' in excel_file:
            # 重新处理活动方案表的数据
            df = process_activity_plan_data(df)
        
        # 将数据插入数据库
        cursor = connection.cursor()
        
        # 构建INSERT语句
        columns = ', '.join(df.columns)
        placeholders = ', '.join(['%s'] * len(df.columns))
        insert_query = f"INSERT INTO {table_name} ({columns}) VALUES ({placeholders})"
        
        # 准备数据
        data_to_insert = []
        for _, row in df.iterrows():
            # 处理NaN值
            row_data = []
            for value in row:
                if pd.isna(value):
                    row_data.append(None)
                else:
                    row_data.append(value)
            data_to_insert.append(row_data)
        
        # 执行批量插入
        cursor.executemany(insert_query, data_to_insert)
        connection.commit()
        
        print(f"成功导入 {len(df)} 行数据到表 {table_name}")
        cursor.close()
        
    except Error as e:
        print(f"导入数据到表 {table_name} 时出错: {e}")

def process_activity_plan_data(df):
    """处理活动方案表的数据结构"""
    # 活动方案表的结构比较特殊，需要重新整理
    # 这里可以根据实际的数据结构进行调整
    return df

def create_database():
    """创建数据库"""
    try:
        connection = mysql.connector.connect(
            host='localhost',
            user='root',  # 请根据实际情况修改
            password='',  # 请根据实际情况修改
        )
        cursor = connection.cursor()
        
        # 创建数据库
        cursor.execute("CREATE DATABASE IF NOT EXISTS jinxiaocun_db")
        print("数据库 jinxiaocun_db 创建成功")
        
        cursor.close()
        connection.close()
        
    except Error as e:
        print(f"创建数据库时出错: {e}")

def main():
    # 创建数据库
    create_database()
    
    # 创建数据库连接
    connection = create_database_connection()
    if not connection:
        return
    
    # 读取SQL文件创建表
    try:
        with open('create_tables_simple.sql', 'r', encoding='utf-8') as file:
            sql_content = file.read()
        
        cursor = connection.cursor()
        
        # 分割SQL语句并执行
        sql_statements = sql_content.split(';')
        for statement in sql_statements:
            statement = statement.strip()
            if statement and not statement.startswith('--'):
                try:
                    cursor.execute(statement)
                    print(f"执行SQL语句: {statement[:50]}...")
                except Error as e:
                    print(f"执行SQL语句时出错: {e}")
        
        connection.commit()
        cursor.close()
        print("表创建完成")
        
    except FileNotFoundError:
        print("未找到 create_tables_simple.sql 文件")
        return
    
    # 导入Excel数据
    excel_files = [
        ('客户原始兑付明细2.xlsx', 'customer_redemption_details'),
        ('客户流向2.xlsx', 'customer_flow'),
        ('活动方案.xlsx', 'activity_plan'),
        ('输出结果.xlsx', 'output_results')
    ]
    
    for excel_file, table_name in excel_files:
        if os.path.exists(excel_file):
            print(f"\n开始导入 {excel_file} 到表 {table_name}")
            import_excel_to_database(excel_file, table_name, connection)
        else:
            print(f"文件 {excel_file} 不存在")
    
    connection.close()
    print("\n数据导入完成！")

if __name__ == "__main__":
    main() 