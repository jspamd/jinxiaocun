import mysql.connector
from mysql.connector import Error
from database_config import get_connection_config

def check_and_modify_tables():
    """检查并修改表结构，添加当期日期列"""
    try:
        # 创建数据库连接
        config = get_connection_config()
        connection = mysql.connector.connect(**config)
        cursor = connection.cursor()
        
        # 要修改的表列表
        tables = [
            'customer_redemption_details',
            'customer_flow', 
            'activity_plan',
            'output_results'
        ]
        
        for table_name in tables:
            print(f"\n=== 检查表 {table_name} ===")
            
            # 检查表是否存在当期日期列
            cursor.execute(f"SHOW COLUMNS FROM {table_name} LIKE '当期日期'")
            result = cursor.fetchone()
            
            if result:
                print(f"表 {table_name} 已存在当期日期列")
            else:
                print(f"表 {table_name} 不存在当期日期列，正在添加...")
                try:
                    cursor.execute(f"ALTER TABLE {table_name} ADD COLUMN 当期日期 DATE")
                    connection.commit()
                    print(f"成功为表 {table_name} 添加当期日期列")
                except Error as e:
                    print(f"为表 {table_name} 添加当期日期列失败: {e}")
            
            # 显示表结构
            cursor.execute(f"DESCRIBE {table_name}")
            columns = cursor.fetchall()
            print(f"表 {table_name} 的结构:")
            for col in columns:
                print(f"  {col[0]} - {col[1]}")
        
        cursor.close()
        connection.close()
        print("\n表结构检查和修改完成！")
        
    except Error as e:
        print(f"数据库操作失败: {e}")

if __name__ == "__main__":
    check_and_modify_tables() 