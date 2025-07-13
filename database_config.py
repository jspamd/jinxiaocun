# 数据库连接配置
# 请根据您的MySQL设置修改以下信息

# MySQL连接配置
MYSQL_CONFIG = {
    'host': 'localhost',        # 数据库主机地址
    'user': 'root',            # 数据库用户名
    'password': '123456',            # 数据库密码（如果有密码请填写）
    'database': 'jinxiaocun_db' # 数据库名称
}

# 如果您的MySQL root用户有密码，请修改上面的password字段
# 例如：'password': 'your_password_here'

# 如果您使用其他用户，请修改user和password字段
# 例如：
# 'user': 'your_username',
# 'password': 'your_password',

def get_connection_config():
    """获取数据库连接配置"""
    return MYSQL_CONFIG.copy()

def test_connection():
    """测试数据库连接"""
    import mysql.connector
    from mysql.connector import Error
    
    try:
        # 先尝试不指定数据库连接
        connection = mysql.connector.connect(
            host=MYSQL_CONFIG['host'],
            user=MYSQL_CONFIG['user'],
            password=MYSQL_CONFIG['password']
        )
        print("✅ 数据库连接成功！")
        
        # 检查数据库是否存在
        cursor = connection.cursor()
        cursor.execute("SHOW DATABASES")
        databases = [db[0] for db in cursor.fetchall()]
        
        if MYSQL_CONFIG['database'] in databases:
            print(f"✅ 数据库 {MYSQL_CONFIG['database']} 已存在")
        else:
            print(f"⚠️  数据库 {MYSQL_CONFIG['database']} 不存在，将自动创建")
        
        cursor.close()
        connection.close()
        return True
        
    except Error as e:
        print(f"❌ 数据库连接失败: {e}")
        print("\n可能的解决方案：")
        print("1. 检查MySQL服务是否启动")
        print("2. 确认用户名和密码是否正确")
        print("3. 修改 database_config.py 中的连接信息")
        print("4. 如果root用户有密码，请在password字段中填写密码")
        return False

if __name__ == "__main__":
    import sys
    sys.stdout = open('runlog.txt', 'w', encoding='utf-8')
    sys.stderr = sys.stdout
    test_connection() 