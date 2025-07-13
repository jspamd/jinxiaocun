import pandas as pd
import os

def analyze_excel_file(filename):
    """分析Excel文件结构"""
    try:
        # 读取Excel文件
        df = pd.read_excel(filename)
        
        print(f"\n=== 分析文件: {filename} ===")
        print(f"数据行数: {len(df)}")
        print(f"数据列数: {len(df.columns)}")
        print("\n列名和数据类型:")
        for i, col in enumerate(df.columns):
            # 获取列的数据类型
            dtype = df[col].dtype
            # 获取非空值的数量
            non_null_count = df[col].count()
            print(f"  {i+1}. {col} ({dtype}) - 非空值: {non_null_count}")
        
        # 显示前几行数据
        print(f"\n前5行数据:")
        print(df.head())
        
        return df.columns.tolist(), df.dtypes.to_dict()
        
    except Exception as e:
        print(f"读取文件 {filename} 时出错: {e}")
        return None, None

def generate_sql_create_table(table_name, columns, dtypes):
    """生成SQL CREATE TABLE语句"""
    sql = f"CREATE TABLE {table_name} (\n"
    sql += "    id INT AUTO_INCREMENT PRIMARY KEY,\n"
    
    type_mapping = {
        'object': 'VARCHAR(255)',
        'int64': 'INT',
        'float64': 'DECIMAL(10,2)',
        'datetime64[ns]': 'DATETIME',
        'bool': 'BOOLEAN'
    }
    
    for col in columns:
        if col == 'id':  # 跳过id列，因为已经定义了主键
            continue
            
        # 获取数据类型
        dtype = str(dtypes.get(col, 'object'))
        sql_type = type_mapping.get(dtype, 'VARCHAR(255)')
        
        # 处理列名中的特殊字符
        safe_col_name = col.replace(' ', '_').replace('-', '_').replace('(', '').replace(')', '')
        
        sql += f"    {safe_col_name} {sql_type},\n"
    
    sql = sql.rstrip(',\n') + "\n);"
    return sql

def main():
    # 获取当前目录下的所有Excel文件
    excel_files = [f for f in os.listdir('.') if f.endswith('.xlsx')]
    
    print("找到的Excel文件:")
    for file in excel_files:
        print(f"  - {file}")
    
    # 分析每个文件
    for file in excel_files:
        columns, dtypes = analyze_excel_file(file)
        
        if columns and dtypes:
            # 生成表名（去掉.xlsx扩展名，替换特殊字符）
            table_name = file.replace('.xlsx', '').replace(' ', '_').replace('-', '_')
            
            # 生成SQL CREATE TABLE语句
            sql = generate_sql_create_table(table_name, columns, dtypes)
            
            print(f"\n=== 生成的SQL CREATE TABLE语句 ===")
            print(sql)
            print("\n" + "="*50)

if __name__ == "__main__":
    main() 