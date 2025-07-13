import os
import sys
from flask import Flask, request, render_template_string, jsonify, send_file
from werkzeug.utils import secure_filename
from debug_import import import_excel_data, create_connection
import mysql.connector
from mysql.connector import Error
import pandas as pd

def resource_path(relative_path):
    """获取资源的绝对路径，兼容开发环境和打包后的环境"""
    try:
        # PyInstaller创建临时文件夹，将路径存储在_MEIPASS中
        base_path = sys._MEIPASS
    except Exception:
        base_path = os.path.abspath(".")
    return os.path.join(base_path, relative_path)

UPLOAD_FOLDER = 'uploads'
ALLOWED_EXTENSIONS = {'xls', 'xlsx'}

# 文件名与表名的映射
FILENAME_TABLE_MAP = {
    '客户原始兑付明细': 'customer_redemption_details',
    '客户流向': 'customer_flow',
    '活动方案': 'activity_plan',
    '输出结果': 'output_results',
}

# 表名与中文名称的映射
TABLE_DISPLAY_NAMES = {
    'customer_redemption_details': '客户原始兑付明细',
    'customer_flow': '客户流向',
    'activity_plan': '活动方案',
    'output_results': '输出结果',
}

app = Flask(__name__, static_folder=resource_path('static'))
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
app.config['MAX_CONTENT_LENGTH'] = 32 * 1024 * 1024  # 32MB

if not os.path.exists(UPLOAD_FOLDER):
    os.makedirs(UPLOAD_FOLDER)

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].strip().lower() in ALLOWED_EXTENSIONS

def format_sql_with_params(sql, params):
    """格式化SQL语句，将参数替换到SQL中以便调试"""
    if not params:
        return sql
    
    formatted_sql = sql
    for param in params:
        if isinstance(param, str):
            formatted_sql = formatted_sql.replace('%s', f"'{param}'", 1)
        else:
            formatted_sql = formatted_sql.replace('%s', str(param), 1)
    
    return formatted_sql

def get_table_data(table_name, page=1, per_page=50, sort_field=None, sort_order='ASC', search_term=None, fields=None):
    """获取表数据，支持分页、排序和搜索，可选字段"""
    try:
        conn = create_connection()
        cursor = conn.cursor(dictionary=True)
        
        # 获取表结构
        cursor.execute(f"DESCRIBE {table_name}")
        all_columns = [row['Field'] for row in cursor.fetchall()]
        
        # 处理查询字段
        if fields:
            select_fields = [f.strip() for f in fields.split(',') if f.strip() and f.strip() in all_columns]
            if not select_fields:
                select_fields = all_columns
        else:
            select_fields = all_columns
        select_fields_sql = ', '.join(select_fields)
        
        # 构建查询条件
        where_clause = ""
        params = []
        if search_term:
            # 构建搜索条件（在所有文本字段中搜索）
            search_conditions = []
            for col in select_fields:
                if col != 'id' and col != '当期日期':  # 排除id和日期字段
                    search_conditions.append(f"{col} LIKE %s")
                    params.append(f"%{search_term}%")
            if search_conditions:
                where_clause = "WHERE " + " OR ".join(search_conditions)
        
        # 构建多字段排序
        order_clause = ""
        if sort_field:
            sort_fields = [f.strip() for f in sort_field.split(',') if f.strip() and f.strip() in select_fields]
            sort_orders = [o.strip().upper() for o in sort_order.split(',')] if sort_order else []
            order_items = []
            for idx, field in enumerate(sort_fields):
                order = sort_orders[idx] if idx < len(sort_orders) and sort_orders[idx] in ('ASC', 'DESC') else 'ASC'
                order_items.append(f"{field} {order}")
            if order_items:
                order_clause = "ORDER BY " + ", ".join(order_items)
        
        # 获取总记录数
        count_query = f"SELECT COUNT(*) as total FROM {table_name} {where_clause}"
        print(f"=== 执行SQL查询 ===")
        print(f"计数查询: {count_query}")
        print(f"格式化后的计数查询: {format_sql_with_params(count_query, params)}")
        cursor.execute(count_query, params)
        total_records = cursor.fetchone()['total']
        
        # 计算分页
        offset = (page - 1) * per_page
        
        # 获取数据
        query = f"""
            SELECT {select_fields_sql} FROM {table_name} 
            {where_clause} 
            {order_clause}
            LIMIT {per_page} OFFSET {offset}
        """
        print(f"数据查询: {query}")
        print(f"格式化后的数据查询: {format_sql_with_params(query, params)}")
        print(f"=== SQL查询结束 ===")
        cursor.execute(query, params)
        data = cursor.fetchall()
        
        # 获取表结构信息（只返回选中的字段）
        columns = [row for row in all_columns if row in select_fields]
        columns = [{'Field': col} for col in columns]
        
        cursor.close()
        conn.close()
        
        return {
            'data': data,
            'columns': columns,
            'total_records': total_records,
            'total_pages': (total_records + per_page - 1) // per_page,
            'current_page': page,
            'per_page': per_page
        }
    except Error as e:
        print(f"数据库查询错误: {e}")
        return None

@app.route('/', methods=['GET', 'POST'])
def upload_file():
    result_msgs = []
    if request.method == 'POST':
        print("收到POST请求")  # 调试输出
        print("request.files:", request.files)  # 调试输出
        files = request.files.getlist('file')
        print("files内容:", files)  # 调试输出
        if files:
            print("第一个文件名:", files[0].filename)  # 调试输出
        if not files or files[0].filename == '':
            result_msgs.append('请选择要上传的文件！')
        else:
            conn = create_connection()
            for file in files:
                filename = file.filename  # 先用原始文件名
                print(f"收到文件: {filename}")  # 调试输出
                ext = filename.rsplit('.', 1)[1].strip().lower() if '.' in filename else ''
                print(f"扩展名: {ext}")         # 调试输出
                if allowed_file(filename):
                    # 判断文件名对应的表
                    base = filename.split('.')[0]
                    table_name = FILENAME_TABLE_MAP.get(base)
                    if not table_name:
                        result_msgs.append(f'文件 {filename} 未识别为有效数据文件，已跳过。')
                        continue
                    safe_filename = secure_filename(filename)  # 只在保存时用
                    save_path = os.path.join(app.config['UPLOAD_FOLDER'], safe_filename)
                    file.save(save_path)
                    try:
                        import_excel_data(save_path, table_name, conn)
                        result_msgs.append(f'文件 {filename} 导入成功！')
                    except Exception as e:
                        result_msgs.append(f'文件 {filename} 导入失败：{e}')
                else:
                    result_msgs.append(f'文件 {filename} 格式不支持，仅支持xls/xlsx。')
            if conn:
                conn.close()
    return render_template_string(r'''
<!DOCTYPE html>
<html lang="zh-CN">
<head>
    <meta charset="UTF-8">
    <title>Excel数据导入系统</title>
    <style>
        body, html {
            margin: 0;
            padding: 0;
            width: 100vw;
            height: 100vh;
            background: #f6f8fa;
            background-image: url('/static/finance_bg.jpg');
            background-size: cover;
            background-position: center center;
            background-repeat: no-repeat;
            background-attachment: fixed; /* 可选，让背景固定不随内容滚动 */
        }
        .container {
            width: 420px;
            margin: 48px auto 0 auto;
            background: #fff;
            border-radius: 18px;
            box-shadow: 0 4px 24px rgba(60,60,120,0.13);
            overflow: hidden;
            padding: 32px 32px 24px 32px;
            min-height: unset;
        }
        .logo {
            display: block;
            margin: 0 auto 18px auto;
            width: 80px;
            height: 80px;
            object-fit: contain;
            border-radius: 16px;
            box-shadow: 0 2px 8px rgba(60,60,120,0.10);
            background: #fff;
            animation: logoPop 1.2s cubic-bezier(.5,-0.2,.5,1.4);
        }
        @keyframes logoPop {
            0% { opacity: 0; transform: scale(0.5) rotate(-20deg); }
            60% { opacity: 1; transform: scale(1.1) rotate(8deg); }
            100% { opacity: 1; transform: scale(1) rotate(0); }
        }
        h2 {
            text-align: center;
            color: #333;
            letter-spacing: 2px;
        }
        .msg {
            margin: 10px 0;
            color: #007700;
        }
        .error {
            color: #bb2222;
        }
       
        .upload-btn {
            background: linear-gradient(90deg, #4f8cff 0%, #6ed0ff 100%);
            color: #fff;
            border: none;
            padding: 12px 32px;
            border-radius: 24px;
            cursor: pointer;
            font-size: 18px;
            font-weight: bold;
            box-shadow: 0 2px 8px rgba(79,140,255,0.15);
            transition: background 0.2s, box-shadow 0.2s;
            position: relative;
            overflow: hidden;
        }
        .upload-btn:hover {
            background: linear-gradient(90deg, #3578e5 0%, #4fd0ff 100%);
            box-shadow: 0 4px 16px rgba(79,140,255,0.25);
        }
        /* 波纹动画 */
        .ripple {
            position: absolute;
            border-radius: 50%;
            transform: scale(0);
            animation: ripple 0.6s linear;
            background-color: rgba(255,255,255,0.5);
            pointer-events: none;
        }
        @keyframes ripple {
            to {
                transform: scale(2.5);
                opacity: 0;
            }
        }
        .file-input-wrapper {
            position: relative;
            display: inline-block;
            width: 100%;
            margin: 20px 0 30px 0;
        }
        .file-input {
            opacity: 0;
            width: 100%;
            height: 48px;
            position: absolute;
            left: 0;
            top: 0;
            cursor: pointer;
        }
        .file-label {
            display: block;
            width: 100%;
            height: 48px;
            background: #f0f4ff;
            border: 2px dashed #4f8cff;
            border-radius: 12px;
            text-align: center;
            line-height: 48px;
            color: #3578e5;
            font-size: 16px;
            font-weight: 500;
            cursor: pointer;
            transition: background 0.2s, border 0.2s;
        }
        .file-label:hover {
            background: #e6f0ff;
            border-color: #3578e5;
        }
        input[type=file] {
            display: none;
        }
        .nav-buttons {
            text-align: center;
            margin-top: 20px;
        }
        .nav-btn {
            background: linear-gradient(90deg, #28a745 0%, #20c997 100%);
            color: #fff;
            border: none;
            padding: 10px 20px;
            border-radius: 20px;
            cursor: pointer;
            font-size: 14px;
            font-weight: bold;
            margin: 0 10px;
            text-decoration: none;
            display: inline-block;
            transition: background 0.2s;
        }
        .nav-btn:hover {
            background: linear-gradient(90deg, #218838 0%, #1ea085 100%);
        }
        .container .msg, .container .error {
            text-align: center;
        }
        .container .nav-buttons {
            margin-bottom: 0;
        }
    </style>
</head>
<body>
<div class="container">
    <img src="/static/monicaLogo.png" alt="Logo" class="logo">
    <h2>Excel数据导入系统</h2>
    <form method="post" enctype="multipart/form-data">
        <label class="file-label" for="file">请选择要上传的Excel文件（可多选）：</label>
        <div class="file-input-wrapper">
            <input class="file-input" id="file" type="file" name="file" multiple required onchange="document.getElementById('file-name').innerText = this.files.length ? Array.from(this.files).map(f=>f.name).join(', ') : '未选择文件'">
            <span id="file-name" style="display:block;margin-top:8px;color:#888;font-size:14px;">未选择文件</span>
        </div>
        <button class="upload-btn" type="submit" id="uploadBtn">上传并导入</button>
    </form>
    {% if result_msgs %}
        <div style="margin-top:20px;">
        {% for msg in result_msgs %}
            <div class="msg">{{ msg }}</div>
        {% endfor %}
        </div>
    {% endif %}
    <div style="margin-top:30px; color:#888; font-size:13px;">
        <b>说明：</b><br>
        1. 支持文件名：客户原始兑付明细.xls、客户流向.xls、活动方案.xlsx、输出结果.xls<br>
        2. 每次导入会自动删除今天的数据，避免重复。<br>
        3. 遇到"进货单位"行自动停止导入。<br>
        4. 仅支持xls/xlsx格式。<br>
    </div>
    <div class="nav-buttons">
        <a href="/query" class="nav-btn">查看数据</a>
    </div>
</div>
<script>
// 上传按钮波纹动画
const btn = document.getElementById('uploadBtn');
btn.addEventListener('click', function(e) {
    const ripple = document.createElement('span');
    ripple.className = 'ripple';
    ripple.style.left = (e.offsetX - 25) + 'px';
    ripple.style.top = (e.offsetY - 25) + 'px';
    ripple.style.width = ripple.style.height = '50px';
    btn.appendChild(ripple);
    setTimeout(() => ripple.remove(), 600);
});
</script>
</body>
</html>
''', result_msgs=result_msgs)

# 修改query_data和api_data，增加fields参数
@app.route('/query')
def query_data():
    """查询数据页面"""
    table_name = request.args.get('table', 'customer_redemption_details')
    page = int(request.args.get('page', 1))
    per_page = int(request.args.get('per_page', 50))  # 默认每页50条
    sort_field = request.args.get('sort_field')
    sort_order = request.args.get('sort_order', 'ASC')
    search_term = request.args.get('search', '')
    fields = request.args.get('fields')
    
    # 获取数据
    result = get_table_data(table_name, page, per_page, sort_field, sort_order, search_term, fields)
    
    if result is None:
        return "数据库连接错误", 500
    
    # 获取所有字段
    all_columns = []
    try:
        conn = create_connection()
        cursor = conn.cursor()
        cursor.execute(f"DESCRIBE {table_name}")
        all_columns = [row[0] for row in cursor.fetchall()]
        cursor.close()
        conn.close()
    except Exception as e:
        print(f"获取所有字段失败: {e}")
    
    return render_template_string(r'''
<!DOCTYPE html>
<html lang="zh-CN">
<head>
    <meta charset="UTF-8">
    <title>数据查询 - {{ table_display_name }}</title>
    <link rel="stylesheet" href="{{ url_for('static', filename='choices.min.css') }}">
    <style>
        body, html {
            margin: 0;
            padding: 0;
            width: 100vw;
            height: 100vh;
        }
        .container {
            width: 100vw;
            min-height: 100vh;
            margin: 0;
            background: #fff;
            border-radius: 0;
            box-shadow: none;
            overflow: auto;
            padding: 0;
        }
        .header {
            background: linear-gradient(90deg, #4f8cff 0%, #6ed0ff 100%);
            color: #fff;
            padding: 20px 30px;
            display: flex;
            justify-content: space-between;
            align-items: center;
        }
        .header h1 {
            margin: 0;
            font-size: 24px;
        }
        .nav-buttons {
            display: flex;
            gap: 10px;
        }
        .nav-btn {
            background: rgba(255,255,255,0.2);
            color: #fff;
            border: none;
            padding: 8px 16px;
            border-radius: 20px;
            cursor: pointer;
            text-decoration: none;
            font-size: 14px;
            transition: background 0.2s;
        }
        .nav-btn:hover {
            background: rgba(255,255,255,0.3);
        }
        .content {
            padding: 30px 40px;
        }
        .controls {
            display: flex;
            gap: 20px;
            margin-bottom: 20px;
            align-items: center;
            flex-wrap: wrap;
        }
        .table-selector {
            display: flex;
            gap: 10px;
            align-items: center;
        }
        .table-selector select {
            padding: 8px 12px;
            border: 1px solid #ddd;
            border-radius: 6px;
            font-size: 14px;
        }
        .field-selector {
            display: flex;
            gap: 10px;
            align-items: center;
        }
        .field-selector select {
            padding: 8px 12px;
            border: 1px solid #ddd;
            border-radius: 6px;
            font-size: 14px;
            min-width: 120px;
            min-height: 32px;
        }
        .choices__inner {
            min-height: 32px;
        }
        .search-box {
            display: flex;
            gap: 10px;
            align-items: center;
        }
        .search-box input {
            padding: 8px 12px;
            border: 1px solid #ddd;
            border-radius: 6px;
            font-size: 14px;
            width: 200px;
        }
        .search-btn {
            background: #28a745;
            color: #fff;
            border: none;
            padding: 8px 16px;
            border-radius: 6px;
            cursor: pointer;
            font-size: 14px;
        }
        .search-btn:hover {
            background: #218838;
        }
        .data-table {
            width: 100%;
            border-collapse: separate;
            border-spacing: 0;
            margin-top: 20px;
            background: #fff;
            border-radius: 12px;
            overflow: hidden;
            box-shadow: 0 2px 12px rgba(0,0,0,0.08);
            border: 1px solid #bfc4cc;
            font-size: 15px;
        }
        .data-table th, .data-table td {
            border: 1px solid #e3e6ee;
            padding: 10px 8px;
        }
        .data-table th {
            background: #e3f0fb;
            font-weight: bold;
            border-bottom: 2px solid #dee2e6;
            cursor: pointer;
            user-select: none;
            color: #2a3b4d;
        }
        .data-table th:hover {
            background: #d0e7fa;
        }
        .data-table tr:nth-child(even) {
            background: #f6f8fa;
        }
        .data-table tr:hover {
            background: #e6f0ff;
        }
        .data-table td {
            font-size: 14px;
        }
        .data-table thead tr:first-child th:first-child {
            border-top-left-radius: 12px;
        }
        .data-table thead tr:first-child th:last-child {
            border-top-right-radius: 12px;
        }
        .data-table tbody tr:last-child td:first-child {
            border-bottom-left-radius: 12px;
        }
        .data-table tbody tr:last-child td:last-child {
            border-bottom-right-radius: 12px;
        }
        /* 新增：活动对象字段省略号样式 */
        .ellipsis-col {
            max-width: 5em;
            min-width: 5em;
            width: 5em;
            overflow: hidden;
            text-overflow: ellipsis;
            white-space: nowrap;
        }
        .pagination {
            display: flex;
            justify-content: center;
            align-items: center;
            gap: 10px;
            margin-top: 20px;
        }
        .pagination a {
            padding: 8px 12px;
            border: 1px solid #ddd;
            text-decoration: none;
            color: #333;
            border-radius: 4px;
        }
        .pagination a:hover {
            background: #f8f9fa;
        }
        .pagination .current {
            background: #4f8cff;
            color: #fff;
            border-color: #4f8cff;
        }
        .stats {
            margin-bottom: 20px;
            color: #666;
            font-size: 14px;
        }
        .sort-indicator {
            margin-left: 5px;
            font-size: 12px;
        }
        .loading {
            text-align: center;
            padding: 40px;
            color: #666;
        }
        .choices {
            min-width: 220px !important;
            font-size: 16px;
        }
        .choices__inner {
            min-height: 40px;
            font-size: 16px;
        }
        .choices__list--dropdown .choices__item {
            display: flex !important;
            align-items: center !important;
            font-size: 16px;
            min-height: 36px;
            padding-left: 0.5em;
            padding-right: 1em;
            position: relative;
            white-space: nowrap;
        }
        .choices__list--dropdown .choices__item::before {
            content: '';
            display: inline-block;
            width: 20px;
            height: 20px;
            border: 2px solid #4f8cff;
            border-radius: 4px;
            background: #fff;
            margin-right: 10px;
            flex-shrink: 0;
        }
        .choices__list--dropdown .choices__item.is-selected::before {
            background: #4f8cff;
            border-color: #3578e5;
            box-shadow: 0 0 0 2px #b3d1ff;
        }
        .choices__list--dropdown .choices__item.is-selected::after {
            content: '\2714';
            color: #fff;
            font-size: 14px;
            position: absolute;
            left: 13px;
            top: 50%;
            transform: translateY(-50%);
            pointer-events: none;
        }
    </style>
    <script src="{{ url_for('static', filename='choices.min.js') }}"></script>
</head>
<body>
<div class="container">
    <div class="header">
        <h1>{{ table_display_name }} - 数据查询</h1>
        <div class="nav-buttons">
            <button class="nav-btn" onclick="batchDelete()">批量删除</button>
            <button class="nav-btn" onclick="exportExcel()">导出 Excel</button>
            <a href="/" class="nav-btn">返回上传</a>
        </div>
    </div>
    
    <div style="background:#f6f8fa;padding:32px 0;min-height:100vh;">
        <div class="content">
            <div class="controls" style="display: flex; flex-wrap: wrap; align-items: center; gap: 24px; margin-bottom: 18px;">
                <div class="table-selector">
                    <label>选择表：</label>
                    <select id="tableSelect" onchange="changeTable()" class="nice-input">
                        {% for table_key, display_name in all_tables.items() %}
                            <option value="{{ table_key }}" {% if table_key == table_name %}selected{% endif %}>
                                {{ display_name }}
                            </option>
                        {% endfor %}
                    </select>
                </div>
                <div class="field-selector">
                    <label>选择字段：</label>
                    <select id="fieldsSelect" multiple class="nice-input">
                        {% for col in all_columns %}
                            <option value="{{ col }}" {% if fields and col in fields.split(',') %}selected{% endif %}>{{ col }}</option>
                        {% endfor %}
                    </select>
                </div>
                <div class="field-selector">
                    <label>排序字段：</label>
                    <select id="sortFieldsSelect" multiple>
                        {% for col in all_columns %}
                            <option value="{{ col }}" {% if sort_field and col in sort_field.split(',') %}selected{% endif %}>{{ col }}</option>
                        {% endfor %}
                    </select>
                    <label style="margin-left:10px;">排序方向：</label>
                    <select id="sortOrdersSelect" multiple></select>
                </div>
                <div class="search-box" style="display: flex; align-items: center; gap: 10px;">
                    <button class="search-btn" style="margin:0;" onclick="openAddDialog()">新增</button>
                    <div style="position:relative;display:inline-block;">
                        <input type="text" id="searchInput" class="nice-input" placeholder="搜索关键词..." value="{{ search_term }}" style="padding-right:28px;">
                        <span id="clearSearchBtn" style="display:none;position:absolute;right:8px;top:50%;transform:translateY(-50%);cursor:pointer;font-size:18px;color:#bbb;">×</span>
                    </div>
                    <button class="search-btn" onclick="searchData()">搜索</button>
                </div>
                <div class="controls">
                    <label for="perPageSelect">每页显示行数：</label>
                    <select id="perPageSelect" onchange="changePerPage()">
                        <option value="100">100</option>
                        <option value="500" selected>500</option>
                        <option value="1000">1000</option>
                    </select>
                </div>
            </div>
            
            <div class="stats">
                共 {{ result.total_records }} 条记录，当前第 {{ result.current_page }}/{{ result.total_pages }} 页
            </div>
            
            <div class="pagination" style="justify-content:center;">
                {% if result.current_page > 1 %}
                    <a href="javascript:void(0)" onclick="changePage(1)" class="page-btn">首页</a>
                    <a href="javascript:void(0)" onclick="changePage({{ result.current_page - 1 }})" class="page-btn">上一页</a>
                {% endif %}
                {% for page in range(max(1, result.current_page - 2), min(result.total_pages + 1, result.current_page + 3)) %}
                    <a href="javascript:void(0)" onclick="changePage({{ page }})" 
                       class="page-btn {% if page == result.current_page %}current{% endif %}">
                        {{ page }}
                    </a>
                {% endfor %}
                {% if result.current_page < result.total_pages %}
                    <a href="javascript:void(0)" onclick="changePage({{ result.current_page + 1 }})" class="page-btn">下一页</a>
                    <a href="javascript:void(0)" onclick="changePage({{ result.total_pages }})" class="page-btn">末页</a>
                {% endif %}
            </div>
            <div class="table-container">
                <table class="data-table">
                    {% set show_columns = result.columns|rejectattr('Field', 'equalto', 'id')|list %}
                    <thead>
                        <tr>
                            <th><input type="checkbox" id="selectAll" onclick="toggleSelectAll(this)"></th>
                            <th style="width:60px;">序号</th>
                            {% for column in show_columns %}
                                <th onclick="sortTable('{{ column.Field }}')" {% if table_name == 'customer_redemption_details' and column.Field == '活动对象' %}class="ellipsis-col"{% endif %}>
                                    {{ column.Field }}
                                    {% if sort_field and column.Field in sort_field.split(',') %}
                                        <span class="sort-indicator">
                                            {% if sort_order and column.Field in sort_order.split(',') and sort_order.split(',')[sort_field.split(',').index(column.Field)].upper() == 'ASC' %}↑{% else %}↓{% endif %}
                                        </span>
                                    {% endif %}
                                </th>
                            {% endfor %}
                            <th>操作</th>
                        </tr>
                    </thead>
                    <tbody>
                        {% for row in result.data %}
                            <tr>
                                <td><input type="checkbox" data-id="{{ row.id }}"></td>
                                <td>{{ (result.current_page-1)*result.per_page + loop.index }}</td>
                                {% for column in show_columns %}
                                    <td {% if table_name == 'customer_redemption_details' and column.Field == '活动对象' %}class="ellipsis-col" title="{{ row[column.Field] }}"{% endif %}>{{ row[column.Field] or '' }}</td>
                                {% endfor %}
                                <td>
                                    <button onclick="openEditDialog({{ loop.index0 }})">编辑</button>
                                    <button onclick="deleteRow({{ loop.index0 }})">删除</button>
                                </td>
                            </tr>
                        {% endfor %}
                    </tbody>
                </table>
            </div>
        </div>
    </div>

<div id="modalMask" style="display:none;position:fixed;left:0;top:0;width:100vw;height:100vh;background:rgba(0,0,0,0.15);z-index:1000;"></div>
<div id="editDialog" style="display:none;position:fixed;left:50%;top:50%;transform:translate(-50%,-50%);background:#fff;padding:24px 32px;box-shadow:0 2px 16px #888;border-radius:8px;z-index:1001;min-width:320px;">
    <form id="editForm">
        <div id="editFields"></div>
        <div style="margin-top:18px;text-align:right;">
            <button type="button" onclick="closeDialog()">取消</button>
            <button type="submit">保存</button>
        </div>
    </form>
</div>
<div id="addDialog" style="display:none;position:fixed;left:50%;top:50%;transform:translate(-50%,-50%);background:#fff;padding:24px 32px;box-shadow:0 2px 16px #888;border-radius:8px;z-index:1001;min-width:320px;">
    <form id="addForm">
        <div id="addFields"></div>
        <div style="margin-top:18px;text-align:right;">
            <button type="button" onclick="closeDialog()">取消</button>
            <button type="submit">新增</button>
        </div>
    </form>
</div>

<script>
var sort_order = "{{ sort_order|default('') }}";
var sort_field = "{{ sort_field|default('') }}";
var fields = "{{ fields|default('') }}";

let currentSortField = '{{ sort_field }}';
let currentSortOrder = '{{ sort_order }}';
let currentFields = '{{ fields if fields else '' }}';

let sortFieldsChoices, sortOrdersChoices;

// 初始化Choices美化多选
window.addEventListener('DOMContentLoaded', function() {
    // 先初始化排序方向
    sortOrdersChoices = new Choices('#sortOrdersSelect', {
        removeItemButton: true,
        searchResultLimit: 20,
        placeholder: true,
        placeholderValue: '请选择排序方向',
        noResultsText: '无匹配',
        noChoicesText: '无可选',
        itemSelectText: '选择',
        shouldSort: false,
        renderChoiceLimit: -1
    });
    // 再初始化排序字段
    sortFieldsChoices = new Choices('#sortFieldsSelect', {
        removeItemButton: true,
        searchResultLimit: 10,
        placeholder: true,
        placeholderValue: '请选择排序字段',
        noResultsText: '无匹配字段',
        noChoicesText: '无可选字段',
        itemSelectText: '选择',
        shouldSort: false,
        renderChoiceLimit: -1
    });
    // 先设置排序字段选中，再刷新排序方向
    if (typeof sort_field !== 'undefined' && sort_field) {
        setTimeout(() => {
            sortFieldsChoices.setChoiceByValue(sort_field.split(','));
            updateSortOrdersChoices();
        }, 0);
    } else {
        updateSortOrdersChoices();
    }
    // 字段多选
    new Choices('#fieldsSelect', {
        removeItemButton: true,
        searchResultLimit: 10,
        placeholder: true,
        placeholderValue: '请选择字段',
        noResultsText: '无匹配字段',
        noChoicesText: '无可选字段',
        itemSelectText: '选择',
        shouldSort: false,
        searchEnabled: true,
        renderChoiceLimit: -1 // 确保下拉时全部显示
    });

    // 联动逻辑
    document.getElementById('sortFieldsSelect').addEventListener('addItem', updateSortOrdersChoices, false);
    document.getElementById('sortFieldsSelect').addEventListener('removeItem', updateSortOrdersChoices, false);

    // 替换排序方向下拉框的事件监听，避免递归死循环
    document.getElementById('sortOrdersSelect').addEventListener('change', function(e) {
        const sel = document.getElementById('sortOrdersSelect');
        const selected = Array.from(sel.selectedOptions).map(o => o.value);
        const fieldMap = {};
        selected.forEach(val => {
            const match = val.match(/(ASC|DESC)\((.+)\)/);
            if (match) fieldMap[match[2]] = val;
        });
        // 只保留每个字段的最后一个方向
        for (let i = 0; i < sel.options.length; i++) {
            sel.options[i].selected = false;
        }
        Object.values(fieldMap).forEach(val => {
            for (let i = 0; i < sel.options.length; i++) {
                if (sel.options[i].value === val) sel.options[i].selected = true;
            }
        });
        // 不再调用 setChoiceByValue，避免递归
    });

    // 页面初始时也要同步一次
    updateSortOrdersChoices();
});

function updateSortOrdersChoices() {
    const sortFieldsSel = document.getElementById('sortFieldsSelect');
    const selectedFields = Array.from(sortFieldsSel.selectedOptions).map(o => o.value);
    sortOrdersChoices.clearChoices();
    if (selectedFields.length === 0) {
        sortOrdersChoices.setChoices([{ value: '', label: '请选择排序字段', disabled: true }], 'value', 'label', false);
        return;
    }
    const newChoices = selectedFields.flatMap(field => [
        { value: `ASC(${field})`, label: `升序(${field})` },
        { value: `DESC(${field})`, label: `降序(${field})` }
    ]);
    sortOrdersChoices.setChoices(newChoices, 'value', 'label', false);
    setTimeout(() => {
        if (sort_order) {
            const sel = document.getElementById('sortOrdersSelect');
            let restore = sort_order.split(',').filter(val => [...sel.options].some(opt => opt.value === val));
            restore.forEach(val => {
                for (let i = 0; i < sel.options.length; i++) {
                    if (sel.options[i].value === val) sel.options[i].selected = true;
                }
            });
            sortOrdersChoices.removeActiveItems();
            sortOrdersChoices.setChoiceByValue(restore);
        }
    }, 0);
}

// 多选值获取函数
function getSelectedFields() {
    const sel = document.getElementById('fieldsSelect');
    return Array.from(sel.selectedOptions).map(o => o.value).join(',');
}
function getSelectedSortFields() {
    const sel = document.getElementById('sortFieldsSelect');
    return Array.from(sel.selectedOptions).map(o => o.value).join(',');
}
function getSelectedSortOrders() {
    const sel = document.getElementById('sortOrdersSelect');
    // 保留完整的 value（如 ASC(结算金额)）
    return Array.from(sel.selectedOptions).map(o => o.value).join(',');
}

function changeTable() {
    const table = document.getElementById('tableSelect').value;
    const fields = getSelectedFields();
    const sortFields = getSelectedSortFields();
    const sortOrders = getSelectedSortOrders();
    const searchTerm = document.getElementById('searchInput').value.trim();
    let url = `/query?table=${table}`;
    if (fields) url += `&fields=${encodeURIComponent(fields)}`;
    if (sortFields) url += `&sort_field=${encodeURIComponent(sortFields)}`;
    if (sortOrders) url += `&sort_order=${encodeURIComponent(sortOrders)}`;
    if (searchTerm) url += `&search=${encodeURIComponent(searchTerm)}`;
    window.location.href = url;
}

function searchData() {
    const searchTerm = document.getElementById('searchInput').value.trim();
    const table = document.getElementById('tableSelect').value;
    const fields = getSelectedFields();
    const sortFields = getSelectedSortFields();
    const sortOrders = getSelectedSortOrders();
    let url = `/query?table=${table}`;
    if (fields) url += `&fields=${encodeURIComponent(fields)}`;
    if (searchTerm) url += `&search=${encodeURIComponent(searchTerm)}`;
    if (sortFields) url += `&sort_field=${encodeURIComponent(sortFields)}`;
    if (sortOrders) url += `&sort_order=${encodeURIComponent(sortOrders)}`;
    window.location.href = url;
}

function sortTable(field) {
    // 兼容表头点击单字段排序，优先级最高
    let newOrder = 'ASC';
    if (currentSortField && currentSortField.split(',')[0] === field && currentSortOrder.split(',')[0] === 'ASC') {
        newOrder = 'DESC';
    }
    currentSortField = field;
    currentSortOrder = newOrder;
    const table = document.getElementById('tableSelect').value;
    const searchTerm = document.getElementById('searchInput').value.trim();
    const fields = getSelectedFields();
    let url = `/query?table=${table}`;
    if (fields) url += `&fields=${encodeURIComponent(fields)}`;
    if (searchTerm) url += `&search=${encodeURIComponent(searchTerm)}`;
    url += `&sort_field=${field}&sort_order=${newOrder}`;
    window.location.href = url;
}

function changePage(page) {
    const table = document.getElementById('tableSelect').value;
    const searchTerm = document.getElementById('searchInput').value.trim();
    const fields = getSelectedFields();
    const sortFields = getSelectedSortFields();
    const sortOrders = getSelectedSortOrders();
    let url = `/query?table=${table}&page=${page}`;
    if (fields) url += `&fields=${encodeURIComponent(fields)}`;
    if (searchTerm) url += `&search=${encodeURIComponent(searchTerm)}`;
    if (sortFields) url += `&sort_field=${encodeURIComponent(sortFields)}`;
    if (sortOrders) url += `&sort_order=${encodeURIComponent(sortOrders)}`;
    window.location.href = url;
}

// 回车键搜索
document.getElementById('searchInput').addEventListener('keypress', function(e) {
    if (e.key === 'Enter') {
        searchData();
    }
});

// 搜索框清空按钮逻辑
const searchInput = document.getElementById('searchInput');
const clearBtn = document.getElementById('clearSearchBtn');
if (searchInput && clearBtn) {
    function toggleClearBtn() {
        clearBtn.style.display = searchInput.value ? 'block' : 'none';
    }
    searchInput.addEventListener('input', toggleClearBtn);
    toggleClearBtn();
    clearBtn.onclick = function() {
        searchInput.value = '';
        searchInput.focus();
        toggleClearBtn();
    };
}

// 数据缓存
const tableName = '{{ table_name }}';
const columns = {{ result.columns|tojson }};
const data = {{ result.data|tojson }};
const pk = columns[0].Field; // 默认第一个字段为主键

// JS部分，columns包含Field和Type，data为行数据
// 工具函数：判断是否日期/时间字段
function isDateField(col) {
    let name = col.Field;
    let type = (col.Type||'').toLowerCase();
    return name.includes('日期') || type.startsWith('date');
}
function isDateTimeField(col) {
    let type = (col.Type||'').toLowerCase();
    return type.startsWith('datetime') || type.startsWith('timestamp');
}
// 工具函数：格式化日期为YYYY-MM-DD
function formatDate(val) {
    if (!val) return '';
    let d = new Date(val.replace(/-/g,'/').replace(/\./g,'/'));
    if (isNaN(d.getTime())) return val;
    let m = (d.getMonth()+1).toString().padStart(2,'0');
    let day = d.getDate().toString().padStart(2,'0');
    return d.getFullYear()+'-'+m+'-'+day;
}
// 工具函数：格式化为input type=datetime-local
function formatDateTime(val) {
    if (!val) return '';
    let d = new Date(val.replace(/-/g,'/').replace(/\./g,'/'));
    if (isNaN(d.getTime())) return val;
    let m = (d.getMonth()+1).toString().padStart(2,'0');
    let day = d.getDate().toString().padStart(2,'0');
    let h = d.getHours().toString().padStart(2,'0');
    let min = d.getMinutes().toString().padStart(2,'0');
    return d.getFullYear()+'-'+m+'-'+day+'T'+h+':'+min;
}
// 工具函数：判断是否数字字段
function isNumberField(col) {
    let type = (col.Type||'').toLowerCase();
    return type.startsWith('int') || type.startsWith('decimal') || type.startsWith('float') || type.startsWith('double') || type.startsWith('numeric');
}
// 新增弹窗表单生成
function openAddDialog() {
    document.getElementById('modalMask').style.display = 'block';
    document.getElementById('addDialog').style.display = 'block';
    let html = '';
    for (let col of columns) {
        if (col.Field === pk) continue;
        if (isDateTimeField(col)) {
            html += `<div style='margin-bottom:12px;'><label>${col.Field}：</label><input type='datetime-local' name='${col.Field}' style='width:180px;'></div>`;
        } else if (isDateField(col)) {
            html += `<div style='margin-bottom:12px;'><label>${col.Field}：</label><input type='date' name='${col.Field}' style='width:180px;'></div>`;
        } else {
            html += `<div style='margin-bottom:12px;'><label>${col.Field}：</label><input name='${col.Field}' style='width:180px;'></div>`;
        }
    }
    document.getElementById('addFields').innerHTML = html;
}
// 编辑弹窗表单生成
function openEditDialog(idx) {
    document.getElementById('modalMask').style.display = 'block';
    document.getElementById('editDialog').style.display = 'block';
    let row = data[idx];
    let html = '';
    for (let col of columns) {
        let val = row[col.Field] || '';
        if (col.Field === pk) {
            html += `<div style='margin-bottom:12px;'><label>${col.Field}：</label><input name='${col.Field}' value='${val}' readonly style='width:180px;background:#eee;'></div>`;
        } else if (isDateTimeField(col)) {
            html += `<div style='margin-bottom:12px;'><label>${col.Field}：</label><input type='datetime-local' name='${col.Field}' value='${formatDateTime(val)}' style='width:180px;'></div>`;
        } else if (isDateField(col)) {
            html += `<div style='margin-bottom:12px;'><label>${col.Field}：</label><input type='date' name='${col.Field}' value='${formatDate(val)}' style='width:180px;'></div>`;
        } else {
            html += `<div style='margin-bottom:12px;'><label>${col.Field}：</label><input name='${col.Field}' value='${val}' style='width:180px;'></div>`;
        }
    }
    document.getElementById('editFields').innerHTML = html;
    document.getElementById('editForm').onsubmit = function(e) {
        e.preventDefault();
        let form = e.target;
        let postData = {};
        for (let el of form.elements) {
            if (el.name) {
                let col = columns.find(c=>c.Field===el.name);
                if (el.type === 'date' && el.value) {
                    postData[el.name] = el.value;
                } else if (el.type === 'datetime-local' && el.value) {
                    postData[el.name] = el.value.replace('T',' ');
                } else if (col && isNumberField(col) && el.value === '') {
                    postData[el.name] = null;
                } else {
                    postData[el.name] = el.value;
                }
            }
        }
        let pkValue = postData[pk];
        delete postData[pk];
        fetch('/api/update_row', {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({table: tableName, pk_name: pk, pk_value: pkValue, data: postData})
        }).then(async r => {
            let res;
            try {
                res = await r.json();
            } catch (e) {
                res = {success: false, msg: '服务器未返回有效JSON'};
            }
            if (r.ok && res.success) {
                location.reload();
            } else {
                alert('修改失败：' + (res && res.msg ? res.msg : `HTTP ${r.status}`));
            }
        });
    };
}
function deleteRow(idx) {
    if(!confirm('确定要删除这条数据吗？')) return;
    let row = data[idx];
    let pkValue = row[pk];
    fetch('/api/delete_row', {
        method: 'POST',
        headers: {'Content-Type': 'application/json'},
        body: JSON.stringify({table: tableName, pk_name: pk, pk_value: pkValue})
    }).then(r=>r.json()).then(res=>{
        if(res.success){ location.reload(); } else { alert('删除失败：'+res.msg); }
    });
}
function closeDialog() {
    document.getElementById('modalMask').style.display = 'none';
    document.getElementById('editDialog').style.display = 'none';
    document.getElementById('addDialog').style.display = 'none';
}
document.getElementById('addForm').onsubmit = function(e) {
    e.preventDefault();
    let form = e.target;
    let postData = {};
    for (let el of form.elements) {
        if (el.name) {
            let col = columns.find(c=>c.Field===el.name);
            if (el.type === 'date' && el.value) {
                postData[el.name] = el.value;
            } else if (el.type === 'datetime-local' && el.value) {
                postData[el.name] = el.value.replace('T',' ');
            } else if (col && isNumberField(col) && el.value === '') {
                postData[el.name] = null;
            } else {
                postData[el.name] = el.value;
            }
        }
    }
    fetch('/api/add_row', {
        method: 'POST',
        headers: {'Content-Type': 'application/json'},
        body: JSON.stringify({table: tableName, data: postData})
    }).then(r=>r.json()).then(res=>{
        if(res.success){ location.reload(); } else { alert('新增失败：'+res.msg); }
    });
};

document.getElementById('fieldsSelect').addEventListener('focus', function() {
    this.parentNode.querySelector('.choices').click();
});


function toggleSelectAll(selectAllCheckbox) {
    const checkboxes = document.querySelectorAll('.data-table input[type=checkbox]');
    checkboxes.forEach(checkbox => {
        checkbox.checked = selectAllCheckbox.checked;
    });
}

function exportExcel() {
    const table = tableName; // 替换为实际的表名
    const selectedRows = Array.from(document.querySelectorAll('.data-table input[type=checkbox]:checked'));
    if (selectedRows.length === 0) {
        alert('请至少选择一条记录进行导出。');
        return;
    }
    const ids = selectedRows.map(row => row.dataset.id);
    
    fetch('/api/export_excel', {
        method: 'POST',
        headers: {'Content-Type': 'application/json'},
        body: JSON.stringify({table: table, ids: ids})
    })
    .then(response => {
        if (response.ok) {
            return response.blob(); // 获取文件 Blob
        } else {
            return response.json().then(res => { throw new Error(res.msg); });
        }
    })
    .then(blob => {
        const url = window.URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.href = url;
        a.download = `${table}.xlsx`; // 设置下载文件名
        document.body.appendChild(a);
        a.click();
        a.remove();
    })
    .catch(error => {
        alert('导出失败：' + error.message);
    });
}

function changePerPage() {
    const perPage = document.getElementById('perPageSelect').value;
    const table = document.getElementById('tableSelect').value;
    const searchTerm = document.getElementById('searchInput').value.trim();
    const fields = getSelectedFields();
    const sortFields = getSelectedSortFields();
    const sortOrders = getSelectedSortOrders();
    let url = `/query?table=${table}&per_page=${perPage}`;
    if (fields) url += `&fields=${encodeURIComponent(fields)}`;
    if (searchTerm) url += `&search=${encodeURIComponent(searchTerm)}`;
    if (sortFields) url += `&sort_field=${encodeURIComponent(sortFields)}`;
    if (sortOrders) url += `&sort_order=${encodeURIComponent(sortOrders)}`;
    window.location.href = url;
}
</script>
</body>
</html>
''', result=result, table_name=table_name, table_display_name=TABLE_DISPLAY_NAMES.get(table_name, table_name), all_tables=TABLE_DISPLAY_NAMES, search_term=search_term, sort_field=sort_field, sort_order=sort_order, fields=fields, all_columns=all_columns, max=max, min=min)

@app.route('/api/data')
def api_data():
    """API接口，返回JSON格式的数据"""
    table_name = request.args.get('table', 'customer_redemption_details')
    page = int(request.args.get('page', 1))
    per_page = int(request.args.get('per_page', 50))
    sort_field = request.args.get('sort_field')
    sort_order = request.args.get('sort_order', 'ASC')
    search_term = request.args.get('search', '')
    fields = request.args.get('fields')
    
    result = get_table_data(table_name, page, per_page, sort_field, sort_order, search_term, fields)
    
    if result is None:
        return jsonify({'error': '数据库连接错误'}), 500
    
    return jsonify(result)

@app.route('/api/add_row', methods=['POST'])
def api_add_row():
    table = request.json.get('table')
    data = request.json.get('data')  # dict
    if not table or not data:
        return jsonify({'success': False, 'msg': '参数缺失'}), 400
    # 把空字符串转为None
    for k, v in data.items():
        if isinstance(v, str) and v.strip() == '':
            data[k] = None
    try:
        conn = create_connection()
        cursor = conn.cursor()
        fields = ','.join([f'`{k}`' for k in data.keys()])
        values = ','.join(['%s'] * len(data))
        sql = f"INSERT INTO `{table}` ({fields}) VALUES ({values})"
        cursor.execute(sql, list(data.values()))
        conn.commit()
        cursor.close()
        conn.close()
        return jsonify({'success': True})
    except Exception as e:
        return jsonify({'success': False, 'msg': str(e)}), 500

@app.route('/api/update_row', methods=['POST'])
def api_update_row():
    table = request.json.get('table')
    pk_name = request.json.get('pk_name')
    pk_value = request.json.get('pk_value')
    data = request.json.get('data')  # dict
    if not table or not pk_name or pk_value is None or not data:
        print('参数缺失:', table, pk_name, pk_value, data)
        return jsonify({'success': False, 'msg': '参数缺失'}), 400
    # 把空字符串转为None
    for k, v in data.items():
        if isinstance(v, str) and v.strip() == '':
            data[k] = None
    try:
        conn = create_connection()
        cursor = conn.cursor()
        set_clause = ','.join([f'`{k}`=%s' for k in data.keys()])
        sql = f"UPDATE `{table}` SET {set_clause} WHERE `{pk_name}`=%s"
        params = list(data.values()) + [pk_value]
        print('UPDATE SQL:', sql)
        print('PARAMS:', params)
        cursor.execute(sql, params)
        conn.commit()
        cursor.close()
        conn.close()
        return jsonify({'success': True})
    except Exception as e:
        print('UPDATE SQL ERROR:', sql)
        print('PARAMS:', params)
        print('EXCEPTION:', e)
        return jsonify({'success': False, 'msg': str(e)}), 500

@app.route('/api/delete_row', methods=['POST'])
def api_delete_row():
    table = request.json.get('table')
    pk_name = request.json.get('pk_name')
    pk_value = request.json.get('pk_value')
    if not table or not pk_name or pk_value is None:
        return jsonify({'success': False, 'msg': '参数缺失'}), 400
    try:
        conn = create_connection()
        cursor = conn.cursor()
        sql = f"DELETE FROM `{table}` WHERE `{pk_name}`=%s"
        cursor.execute(sql, (pk_value,))
        conn.commit()
        cursor.close()
        conn.close()
        return jsonify({'success': True})
    except Exception as e:
        return jsonify({'success': False, 'msg': str(e)}), 500

@app.route('/api/batch_delete', methods=['POST'])
def api_batch_delete():
    table = request.json.get('table')
    ids = request.json.get('ids')  # list
    if not table or not ids:
        return jsonify({'success': False, 'msg': '参数缺失'}), 400
    try:
        conn = create_connection()
        cursor = conn.cursor()
        sql = f"DELETE FROM `{table}` WHERE `id` IN ({','.join(['%s'] * len(ids))})"
        cursor.execute(sql, ids)
        conn.commit()
        cursor.close()
        conn.close()
        return jsonify({'success': True})
    except Exception as e:
        return jsonify({'success': False, 'msg': str(e)}), 500

@app.route('/api/export_excel', methods=['POST'])
def export_excel():
    table_name = request.json.get('table') 
    ids = request.json.get('ids')  # list
    if not table_name or not ids:
        return jsonify({'success': False, 'msg': '参数缺失'}), 400
    try:
        conn = create_connection()
        cursor = conn.cursor(dictionary=True)
        
        # 查询时排除 id 和当前日期字段
        cursor.execute(f"SELECT * FROM `{table_name}` WHERE id IN ({','.join(['%s'] * len(ids))})", ids)
        data = cursor.fetchall()
        
        # 排除不需要的字段
        for row in data:
            row.pop('id', None)  # 去掉 id 字段
            row.pop('当前日期', None)  # 去掉当前日期字段（请根据实际字段名替换）

        cursor.close()
        conn.close()

        # 创建 Excel 文件
        import pandas as pd
        df = pd.DataFrame(data)
        output = f"{table_name}.xlsx"
        df.to_excel(output, index=False)

        # 发送文件到浏览器
        return send_file(output, as_attachment=True)
    except Exception as e:
        return jsonify({'success': False, 'msg': str(e)}), 500

UPLOAD_TEMPLATE = r'''
<!DOCTYPE html>
<html lang="zh-CN">
<head>
    <meta charset="UTF-8">
    <title>Excel数据导入系统</title>
    <style>
        body, html {
            margin: 0;
            padding: 0;
            width: 100vw;
            height: 100vh;
            background: #f6f8fa;
            background-image: url('/static/finance_bg.jpg');
            background-size: cover;
            background-position: center center;
            background-repeat: no-repeat;
            background-attachment: fixed; /* 可选，让背景固定不随内容滚动 */
        }
        .container {
            width: 420px;
            margin: 48px auto 0 auto;
            background: #fff;
            border-radius: 18px;
            box-shadow: 0 4px 24px rgba(60,60,120,0.13);
            overflow: hidden;
            padding: 32px 32px 24px 32px;
            min-height: unset;
        }
        .logo {
            display: block;
            margin: 0 auto 18px auto;
            width: 80px;
            height: 80px;
            object-fit: contain;
            border-radius: 16px;
            box-shadow: 0 2px 8px rgba(60,60,120,0.10);
            background: #fff;
            animation: logoPop 1.2s cubic-bezier(.5,-0.2,.5,1.4);
        }
        @keyframes logoPop {
            0% { opacity: 0; transform: scale(0.5) rotate(-20deg); }
            60% { opacity: 1; transform: scale(1.1) rotate(8deg); }
            100% { opacity: 1; transform: scale(1) rotate(0); }
        }
        h2 {
            text-align: center;
            color: #333;
            letter-spacing: 2px;
        }
        .msg {
            margin: 10px 0;
            color: #007700;
        }
        .error {
            color: #bb2222;
        }
       
        .upload-btn {
            background: linear-gradient(90deg, #4f8cff 0%, #6ed0ff 100%);
            color: #fff;
            border: none;
            padding: 12px 32px;
            border-radius: 24px;
            cursor: pointer;
            font-size: 18px;
            font-weight: bold;
            box-shadow: 0 2px 8px rgba(79,140,255,0.15);
            transition: background 0.2s, box-shadow 0.2s;
            position: relative;
            overflow: hidden;
        }
        .upload-btn:hover {
            background: linear-gradient(90deg, #3578e5 0%, #4fd0ff 100%);
            box-shadow: 0 4px 16px rgba(79,140,255,0.25);
        }
        /* 波纹动画 */
        .ripple {
            position: absolute;
            border-radius: 50%;
            transform: scale(0);
            animation: ripple 0.6s linear;
            background-color: rgba(255,255,255,0.5);
            pointer-events: none;
        }
        @keyframes ripple {
            to {
                transform: scale(2.5);
                opacity: 0;
            }
        }
        .file-input-wrapper {
            position: relative;
            display: inline-block;
            width: 100%;
            margin: 20px 0 30px 0;
        }
        .file-input {
            opacity: 0;
            width: 100%;
            height: 48px;
            position: absolute;
            left: 0;
            top: 0;
            cursor: pointer;
        }
        .file-label {
            display: block;
            width: 100%;
            height: 48px;
            background: #f0f4ff;
            border: 2px dashed #4f8cff;
            border-radius: 12px;
            text-align: center;
            line-height: 48px;
            color: #3578e5;
            font-size: 16px;
            font-weight: 500;
            cursor: pointer;
            transition: background 0.2s, border 0.2s;
        }
        .file-label:hover {
            background: #e6f0ff;
            border-color: #3578e5;
        }
        input[type=file] {
            display: none;
        }
        .nav-buttons {
            text-align: center;
            margin-top: 20px;
        }
        .nav-btn {
            background: linear-gradient(90deg, #28a745 0%, #20c997 100%);
            color: #fff;
            border: none;
            padding: 10px 20px;
            border-radius: 20px;
            cursor: pointer;
            font-size: 14px;
            font-weight: bold;
            margin: 0 10px;
            text-decoration: none;
            display: inline-block;
            transition: background 0.2s;
        }
        .nav-btn:hover {
            background: linear-gradient(90deg, #218838 0%, #1ea085 100%);
        }
        .container .msg, .container .error {
            text-align: center;
        }
        .container .nav-buttons {
            margin-bottom: 0;
        }
    </style>
</head>
<body>
<div class="container">
    <img src="/static/monicaLogo.png" alt="Logo" class="logo">
    <h2>Excel数据导入系统</h2>
    <form method="post" enctype="multipart/form-data">
        <label class="file-label" for="file">请选择要上传的Excel文件（可多选）：</label>
        <div class="file-input-wrapper">
            <input class="file-input" id="file" type="file" name="file" multiple required onchange="document.getElementById('file-name').innerText = this.files.length ? Array.from(this.files).map(f=>f.name).join(', ') : '未选择文件'">
            <span id="file-name" style="display:block;margin-top:8px;color:#888;font-size:14px;">未选择文件</span>
        </div>
        <button class="upload-btn" type="submit" id="uploadBtn">上传并导入</button>
    </form>
    {% if result_msgs %}
        <div style="margin-top:20px;">
        {% for msg in result_msgs %}
            <div class="msg">{{ msg }}</div>
        {% endfor %}
        </div>
    {% endif %}
    <div style="margin-top:30px; color:#888; font-size:13px;">
        <b>说明：</b><br>
        1. 支持文件名：客户原始兑付明细.xls、客户流向.xls、活动方案.xlsx、输出结果.xls<br>
        2. 每次导入会自动删除今天的数据，避免重复。<br>
        3. 遇到"进货单位"行自动停止导入。<br>
        4. 仅支持xls/xlsx格式。<br>
    </div>
    <div class="nav-buttons">
        <a href="/query" class="nav-btn">查看数据</a>
    </div>
</div>
<script>
// 上传按钮波纹动画
const btn = document.getElementById('uploadBtn');
btn.addEventListener('click', function(e) {
    const ripple = document.createElement('span');
    ripple.className = 'ripple';
    ripple.style.left = (e.offsetX - 25) + 'px';
    ripple.style.top = (e.offsetY - 25) + 'px';
    ripple.style.width = ripple.style.height = '50px';
    btn.appendChild(ripple);
    setTimeout(() => ripple.remove(), 600);
});
</script>
</body>
</html>
'''

QUERY_TEMPLATE = r'''
<!DOCTYPE html>
<html lang="zh-CN">
<head>
    <meta charset="UTF-8">
    <title>数据查询 - {{ table_display_name }}</title>
    <link rel="stylesheet" href="{{ url_for('static', filename='choices.min.css') }}">
    <style>
        body, html {
            margin: 0;
            padding: 0;
            width: 100vw;
            height: 100vh;
        }
        .container {
            width: 100vw;
            min-height: 100vh;
            margin: 0;
            background: #fff;
            border-radius: 0;
            box-shadow: none;
            overflow: auto;
            padding: 0;
        }
        .header {
            background: linear-gradient(90deg, #4f8cff 0%, #6ed0ff 100%);
            color: #fff;
            padding: 20px 30px;
            display: flex;
            justify-content: space-between;
            align-items: center;
        }
        .header h1 {
            margin: 0;
            font-size: 24px;
        }
        .nav-buttons {
            display: flex;
            gap: 10px;
        }
        .nav-btn {
            background: rgba(255,255,255,0.2);
            color: #fff;
            border: none;
            padding: 8px 16px;
            border-radius: 20px;
            cursor: pointer;
            text-decoration: none;
            font-size: 14px;
            transition: background 0.2s;
        }
        .nav-btn:hover {
            background: rgba(255,255,255,0.3);
        }
        .content {
            padding: 30px 40px;
        }
        .controls {
            display: flex;
            gap: 20px;
            margin-bottom: 20px;
            align-items: center;
            flex-wrap: wrap;
        }
        .table-selector {
            display: flex;
            gap: 10px;
            align-items: center;
        }
        .table-selector select {
            padding: 8px 12px;
            border: 1px solid #ddd;
            border-radius: 6px;
            font-size: 14px;
        }
        .field-selector {
            display: flex;
            gap: 10px;
            align-items: center;
        }
        .field-selector select {
            padding: 8px 12px;
            border: 1px solid #ddd;
            border-radius: 6px;
            font-size: 14px;
            min-width: 120px;
            min-height: 32px;
        }
        .choices__inner {
            min-height: 32px;
        }
        .search-box {
            display: flex;
            gap: 10px;
            align-items: center;
        }
        .search-box input {
            padding: 8px 12px;
            border: 1px solid #ddd;
            border-radius: 6px;
            font-size: 14px;
            width: 200px;
        }
        .search-btn {
            background: #28a745;
            color: #fff;
            border: none;
            padding: 8px 16px;
            border-radius: 6px;
            cursor: pointer;
            font-size: 14px;
        }
        .search-btn:hover {
            background: #218838;
        }
        .data-table {
            width: 100%;
            border-collapse: separate;
            border-spacing: 0;
            margin-top: 20px;
            background: #fff;
            border-radius: 12px;
            overflow: hidden;
            box-shadow: 0 2px 12px rgba(0,0,0,0.08);
            border: 1px solid #bfc4cc;
            font-size: 15px;
        }
        .data-table th, .data-table td {
            border: 1px solid #e3e6ee;
            padding: 10px 8px;
        }
        .data-table th {
            background: #e3f0fb;
            font-weight: bold;
            border-bottom: 2px solid #dee2e6;
            cursor: pointer;
            user-select: none;
            color: #2a3b4d;
        }
        .data-table th:hover {
            background: #d0e7fa;
        }
        .data-table tr:nth-child(even) {
            background: #f6f8fa;
        }
        .data-table tr:hover {
            background: #e6f0ff;
        }
        .data-table td {
            font-size: 14px;
        }
        .data-table thead tr:first-child th:first-child {
            border-top-left-radius: 12px;
        }
        .data-table thead tr:first-child th:last-child {
            border-top-right-radius: 12px;
        }
        .data-table tbody tr:last-child td:first-child {
            border-bottom-left-radius: 12px;
        }
        .data-table tbody tr:last-child td:last-child {
            border-bottom-right-radius: 12px;
        }
        /* 新增：活动对象字段省略号样式 */
        .ellipsis-col {
            max-width: 5em;
            min-width: 5em;
            width: 5em;
            overflow: hidden;
            text-overflow: ellipsis;
            white-space: nowrap;
        }
        .pagination {
            display: flex;
            justify-content: center;
            align-items: center;
            gap: 10px;
            margin-top: 20px;
        }
        .pagination a {
            padding: 8px 12px;
            border: 1px solid #ddd;
            text-decoration: none;
            color: #333;
            border-radius: 4px;
        }
        .pagination a:hover {
            background: #f8f9fa;
        }
        .pagination .current {
            background: #4f8cff;
            color: #fff;
            border-color: #4f8cff;
        }
        .stats {
            margin-bottom: 20px;
            color: #666;
            font-size: 14px;
        }
        .sort-indicator {
            margin-left: 5px;
            font-size: 12px;
        }
        .loading {
            text-align: center;
            padding: 40px;
            color: #666;
        }
        .choices {
            min-width: 220px !important;
            font-size: 16px;
        }
        .choices__inner {
            min-height: 40px;
            font-size: 16px;
        }
        .choices__list--dropdown .choices__item {
            display: flex !important;
            align-items: center !important;
            font-size: 16px;
            min-height: 36px;
            padding-left: 0.5em;
            padding-right: 1em;
            position: relative;
            white-space: nowrap;
        }
        .choices__list--dropdown .choices__item::before {
            content: '';
            display: inline-block;
            width: 20px;
            height: 20px;
            border: 2px solid #4f8cff;
            border-radius: 4px;
            background: #fff;
            margin-right: 10px;
            flex-shrink: 0;
        }
        .choices__list--dropdown .choices__item.is-selected::before {
            background: #4f8cff;
            border-color: #3578e5;
            box-shadow: 0 0 0 2px #b3d1ff;
        }
        .choices__list--dropdown .choices__item.is-selected::after {
            content: '\2714';
            color: #fff;
            font-size: 14px;
            position: absolute;
            left: 13px;
            top: 50%;
            transform: translateY(-50%);
            pointer-events: none;
        }
    </style>
    <script src="{{ url_for('static', filename='choices.min.js') }}"></script>
</head>
<body>
<div class="container">
    <div class="header">
        <h1>{{ table_display_name }} - 数据查询</h1>
        <div class="nav-buttons">
            <button class="nav-btn" onclick="batchDelete()">批量删除</button>
            <button class="nav-btn" onclick="exportExcel()">导出 Excel</button>
            <a href="/" class="nav-btn">返回上传</a>
        </div>
    </div>
    
    <div style="background:#f6f8fa;padding:32px 0;min-height:100vh;">
        <div class="content">
            <div class="controls" style="display: flex; flex-wrap: wrap; align-items: center; gap: 24px; margin-bottom: 18px;">
                <div class="table-selector">
                    <label>选择表：</label>
                    <select id="tableSelect" onchange="changeTable()" class="nice-input">
                        {% for table_key, display_name in all_tables.items() %}
                            <option value="{{ table_key }}" {% if table_key == table_name %}selected{% endif %}>
                                {{ display_name }}
                            </option>
                        {% endfor %}
                    </select>
                </div>
                <div class="field-selector">
                    <label>选择字段：</label>
                    <select id="fieldsSelect" multiple class="nice-input">
                        {% for col in all_columns %}
                            <option value="{{ col }}" {% if fields and col in fields.split(',') %}selected{% endif %}>{{ col }}</option>
                        {% endfor %}
                    </select>
                </div>
                <div class="field-selector">
                    <label>排序字段：</label>
                    <select id="sortFieldsSelect" multiple>
                        {% for col in all_columns %}
                            <option value="{{ col }}" {% if sort_field and col in sort_field.split(',') %}selected{% endif %}>{{ col }}</option>
                        {% endfor %}
                    </select>
                    <label style="margin-left:10px;">排序方向：</label>
                    <select id="sortOrdersSelect" multiple></select>
                </div>
                <div class="search-box" style="display: flex; align-items: center; gap: 10px;">
                    <button class="search-btn" style="margin:0;" onclick="openAddDialog()">新增</button>
                    <div style="position:relative;display:inline-block;">
                        <input type="text" id="searchInput" class="nice-input" placeholder="搜索关键词..." value="{{ search_term }}" style="padding-right:28px;">
                        <span id="clearSearchBtn" style="display:none;position:absolute;right:8px;top:50%;transform:translateY(-50%);cursor:pointer;font-size:18px;color:#bbb;">×</span>
                    </div>
                    <button class="search-btn" onclick="searchData()">搜索</button>
                </div>
                <div class="controls">
                    <label for="perPageSelect">每页显示行数：</label>
                    <select id="perPageSelect" onchange="changePerPage()">
                        <option value="10">10</option>
                        <option value="25">25</option>
                        <option value="50" selected>50</option>
                        <option value="100">100</option>
                    </select>
                </div>
            </div>
            
            <div class="stats">
                共 {{ result.total_records }} 条记录，当前第 {{ result.current_page }}/{{ result.total_pages }} 页
            </div>
            
            <div class="pagination" style="justify-content:center;">
                {% if result.current_page > 1 %}
                    <a href="javascript:void(0)" onclick="changePage(1)" class="page-btn">首页</a>
                    <a href="javascript:void(0)" onclick="changePage({{ result.current_page - 1 }})" class="page-btn">上一页</a>
                {% endif %}
                {% for page in range(max(1, result.current_page - 2), min(result.total_pages + 1, result.current_page + 3)) %}
                    <a href="javascript:void(0)" onclick="changePage({{ page }})" 
                       class="page-btn {% if page == result.current_page %}current{% endif %}">
                        {{ page }}
                    </a>
                {% endfor %}
                {% if result.current_page < result.total_pages %}
                    <a href="javascript:void(0)" onclick="changePage({{ result.current_page + 1 }})" class="page-btn">下一页</a>
                    <a href="javascript:void(0)" onclick="changePage({{ result.total_pages }})" class="page-btn">末页</a>
                {% endif %}
            </div>
            <div class="table-container">
                <table class="data-table">
                    {% set show_columns = result.columns|rejectattr('Field', 'equalto', 'id')|list %}
                    <thead>
                        <tr>
                            <th><input type="checkbox" id="selectAll" onclick="toggleSelectAll(this)"></th>
                            <th style="width:60px;">序号</th>
                            {% for column in show_columns %}
                                <th onclick="sortTable('{{ column.Field }}')" {% if table_name == 'customer_redemption_details' and column.Field == '活动对象' %}class="ellipsis-col"{% endif %}>
                                    {{ column.Field }}
                                    {% if sort_field and column.Field in sort_field.split(',') %}
                                        <span class="sort-indicator">
                                            {% if sort_order and column.Field in sort_order.split(',') and sort_order.split(',')[sort_field.split(',').index(column.Field)].upper() == 'ASC' %}↑{% else %}↓{% endif %}
                                        </span>
                                    {% endif %}
                                </th>
                            {% endfor %}
                            <th>操作</th>
                        </tr>
                    </thead>
                    <tbody>
                        {% for row in result.data %}
                            <tr>
                                <td><input type="checkbox" data-id="{{ row.id }}"></td>
                                <td>{{ (result.current_page-1)*result.per_page + loop.index }}</td>
                                {% for column in show_columns %}
                                    <td {% if table_name == 'customer_redemption_details' and column.Field == '活动对象' %}class="ellipsis-col" title="{{ row[column.Field] }}"{% endif %}>{{ row[column.Field] or '' }}</td>
                                {% endfor %}
                                <td>
                                    <button onclick="openEditDialog({{ loop.index0 }})">编辑</button>
                                    <button onclick="deleteRow({{ loop.index0 }})">删除</button>
                                </td>
                            </tr>
                        {% endfor %}
                    </tbody>
                </table>
            </div>
        </div>
    </div>

<div id="modalMask" style="display:none;position:fixed;left:0;top:0;width:100vw;height:100vh;background:rgba(0,0,0,0.15);z-index:1000;"></div>
<div id="editDialog" style="display:none;position:fixed;left:50%;top:50%;transform:translate(-50%,-50%);background:#fff;padding:24px 32px;box-shadow:0 2px 16px #888;border-radius:8px;z-index:1001;min-width:320px;">
    <form id="editForm">
        <div id="editFields"></div>
        <div style="margin-top:18px;text-align:right;">
            <button type="button" onclick="closeDialog()">取消</button>
            <button type="submit">保存</button>
        </div>
    </form>
</div>
<div id="addDialog" style="display:none;position:fixed;left:50%;top:50%;transform:translate(-50%,-50%);background:#fff;padding:24px 32px;box-shadow:0 2px 16px #888;border-radius:8px;z-index:1001;min-width:320px;">
    <form id="addForm">
        <div id="addFields"></div>
        <div style="margin-top:18px;text-align:right;">
            <button type="button" onclick="closeDialog()">取消</button>
            <button type="submit">新增</button>
        </div>
    </form>
</div>

<script>
var sort_order = "{{ sort_order|default('') }}";
var sort_field = "{{ sort_field|default('') }}";
var fields = "{{ fields|default('') }}";

let currentSortField = '{{ sort_field }}';
let currentSortOrder = '{{ sort_order }}';
let currentFields = '{{ fields if fields else '' }}';

let sortFieldsChoices, sortOrdersChoices;

// 初始化Choices美化多选
window.addEventListener('DOMContentLoaded', function() {
    // 先初始化排序方向
    sortOrdersChoices = new Choices('#sortOrdersSelect', {
        removeItemButton: true,
        searchResultLimit: 20,
        placeholder: true,
        placeholderValue: '请选择排序方向',
        noResultsText: '无匹配',
        noChoicesText: '无可选',
        itemSelectText: '选择',
        shouldSort: false,
        renderChoiceLimit: -1
    });
    // 再初始化排序字段
    sortFieldsChoices = new Choices('#sortFieldsSelect', {
        removeItemButton: true,
        searchResultLimit: 10,
        placeholder: true,
        placeholderValue: '请选择排序字段',
        noResultsText: '无匹配字段',
        noChoicesText: '无可选字段',
        itemSelectText: '选择',
        shouldSort: false,
        renderChoiceLimit: -1
    });
    // 先设置排序字段选中，再刷新排序方向
    if (typeof sort_field !== 'undefined' && sort_field) {
        setTimeout(() => {
            sortFieldsChoices.setChoiceByValue(sort_field.split(','));
            updateSortOrdersChoices();
        }, 0);
    } else {
        updateSortOrdersChoices();
    }
    // 字段多选
    new Choices('#fieldsSelect', {
        removeItemButton: true,
        searchResultLimit: 10,
        placeholder: true,
        placeholderValue: '请选择字段',
        noResultsText: '无匹配字段',
        noChoicesText: '无可选字段',
        itemSelectText: '选择',
        shouldSort: false,
        searchEnabled: true,
        renderChoiceLimit: -1 // 确保下拉时全部显示
    });

    // 联动逻辑
    document.getElementById('sortFieldsSelect').addEventListener('addItem', updateSortOrdersChoices, false);
    document.getElementById('sortFieldsSelect').addEventListener('removeItem', updateSortOrdersChoices, false);

    // 替换排序方向下拉框的事件监听，避免递归死循环
    document.getElementById('sortOrdersSelect').addEventListener('change', function(e) {
        const sel = document.getElementById('sortOrdersSelect');
        const selected = Array.from(sel.selectedOptions).map(o => o.value);
        const fieldMap = {};
        selected.forEach(val => {
            const match = val.match(/(ASC|DESC)\((.+)\)/);
            if (match) fieldMap[match[2]] = val;
        });
        // 只保留每个字段的最后一个方向
        for (let i = 0; i < sel.options.length; i++) {
            sel.options[i].selected = false;
        }
        Object.values(fieldMap).forEach(val => {
            for (let i = 0; i < sel.options.length; i++) {
                if (sel.options[i].value === val) sel.options[i].selected = true;
            }
        });
        // 不再调用 setChoiceByValue，避免递归
    });

    // 页面初始时也要同步一次
    updateSortOrdersChoices();
});

function updateSortOrdersChoices() {
    const sortFieldsSel = document.getElementById('sortFieldsSelect');
    const selectedFields = Array.from(sortFieldsSel.selectedOptions).map(o => o.value);
    sortOrdersChoices.clearChoices();
    if (selectedFields.length === 0) {
        sortOrdersChoices.setChoices([{ value: '', label: '请选择排序字段', disabled: true }], 'value', 'label', false);
        return;
    }
    const newChoices = selectedFields.flatMap(field => [
        { value: `ASC(${field})`, label: `升序(${field})` },
        { value: `DESC(${field})`, label: `降序(${field})` }
    ]);
    sortOrdersChoices.setChoices(newChoices, 'value', 'label', false);
    setTimeout(() => {
        if (sort_order) {
            const sel = document.getElementById('sortOrdersSelect');
            let restore = sort_order.split(',').filter(val => [...sel.options].some(opt => opt.value === val));
            restore.forEach(val => {
                for (let i = 0; i < sel.options.length; i++) {
                    if (sel.options[i].value === val) sel.options[i].selected = true;
                }
            });
            sortOrdersChoices.removeActiveItems();
            sortOrdersChoices.setChoiceByValue(restore);
        }
    }, 0);
}

// 多选值获取函数
function getSelectedFields() {
    const sel = document.getElementById('fieldsSelect');
    return Array.from(sel.selectedOptions).map(o => o.value).join(',');
}
function getSelectedSortFields() {
    const sel = document.getElementById('sortFieldsSelect');
    return Array.from(sel.selectedOptions).map(o => o.value).join(',');
}
function getSelectedSortOrders() {
    const sel = document.getElementById('sortOrdersSelect');
    // 保留完整的 value（如 ASC(结算金额)）
    return Array.from(sel.selectedOptions).map(o => o.value).join(',');
}

function changeTable() {
    const table = document.getElementById('tableSelect').value;
    const fields = getSelectedFields();
    const sortFields = getSelectedSortFields();
    const sortOrders = getSelectedSortOrders();
    const searchTerm = document.getElementById('searchInput').value.trim();
    let url = `/query?table=${table}`;
    if (fields) url += `&fields=${encodeURIComponent(fields)}`;
    if (sortFields) url += `&sort_field=${encodeURIComponent(sortFields)}`;
    if (sortOrders) url += `&sort_order=${encodeURIComponent(sortOrders)}`;
    if (searchTerm) url += `&search=${encodeURIComponent(searchTerm)}`;
    window.location.href = url;
}

function searchData() {
    const searchTerm = document.getElementById('searchInput').value.trim();
    const table = document.getElementById('tableSelect').value;
    const fields = getSelectedFields();
    const sortFields = getSelectedSortFields();
    const sortOrders = getSelectedSortOrders();
    let url = `/query?table=${table}`;
    if (fields) url += `&fields=${encodeURIComponent(fields)}`;
    if (searchTerm) url += `&search=${encodeURIComponent(searchTerm)}`;
    if (sortFields) url += `&sort_field=${encodeURIComponent(sortFields)}`;
    if (sortOrders) url += `&sort_order=${encodeURIComponent(sortOrders)}`;
    window.location.href = url;
}

function sortTable(field) {
    // 兼容表头点击单字段排序，优先级最高
    let newOrder = 'ASC';
    if (currentSortField && currentSortField.split(',')[0] === field && currentSortOrder.split(',')[0] === 'ASC') {
        newOrder = 'DESC';
    }
    currentSortField = field;
    currentSortOrder = newOrder;
    const table = document.getElementById('tableSelect').value;
    const searchTerm = document.getElementById('searchInput').value.trim();
    const fields = getSelectedFields();
    let url = `/query?table=${table}`;
    if (fields) url += `&fields=${encodeURIComponent(fields)}`;
    if (searchTerm) url += `&search=${encodeURIComponent(searchTerm)}`;
    url += `&sort_field=${field}&sort_order=${newOrder}`;
    window.location.href = url;
}

function changePage(page) {
    const table = document.getElementById('tableSelect').value;
    const searchTerm = document.getElementById('searchInput').value.trim();
    const fields = getSelectedFields();
    const sortFields = getSelectedSortFields();
    const sortOrders = getSelectedSortOrders();
    let url = `/query?table=${table}&page=${page}`;
    if (fields) url += `&fields=${encodeURIComponent(fields)}`;
    if (searchTerm) url += `&search=${encodeURIComponent(searchTerm)}`;
    if (sortFields) url += `&sort_field=${encodeURIComponent(sortFields)}`;
    if (sortOrders) url += `&sort_order=${encodeURIComponent(sortOrders)}`;
    window.location.href = url;
}

// 回车键搜索
document.getElementById('searchInput').addEventListener('keypress', function(e) {
    if (e.key === 'Enter') {
        searchData();
    }
});

// 搜索框清空按钮逻辑
const searchInput = document.getElementById('searchInput');
const clearBtn = document.getElementById('clearSearchBtn');
if (searchInput && clearBtn) {
    function toggleClearBtn() {
        clearBtn.style.display = searchInput.value ? 'block' : 'none';
    }
    searchInput.addEventListener('input', toggleClearBtn);
    toggleClearBtn();
    clearBtn.onclick = function() {
        searchInput.value = '';
        searchInput.focus();
        toggleClearBtn();
    };
}

// 数据缓存
const tableName = '{{ table_name }}';
const columns = {{ result.columns|tojson }};
const data = {{ result.data|tojson }};
const pk = columns[0].Field; // 默认第一个字段为主键

// JS部分，columns包含Field和Type，data为行数据
// 工具函数：判断是否日期/时间字段
function isDateField(col) {
    let name = col.Field;
    let type = (col.Type||'').toLowerCase();
    return name.includes('日期') || type.startsWith('date');
}
function isDateTimeField(col) {
    let type = (col.Type||'').toLowerCase();
    return type.startsWith('datetime') || type.startsWith('timestamp');
}
// 工具函数：格式化日期为YYYY-MM-DD
function formatDate(val) {
    if (!val) return '';
    let d = new Date(val.replace(/-/g,'/').replace(/\./g,'/'));
    if (isNaN(d.getTime())) return val;
    let m = (d.getMonth()+1).toString().padStart(2,'0');
    let day = d.getDate().toString().padStart(2,'0');
    return d.getFullYear()+'-'+m+'-'+day;
}
// 工具函数：格式化为input type=datetime-local
function formatDateTime(val) {
    if (!val) return '';
    let d = new Date(val.replace(/-/g,'/').replace(/\./g,'/'));
    if (isNaN(d.getTime())) return val;
    let m = (d.getMonth()+1).toString().padStart(2,'0');
    let day = d.getDate().toString().padStart(2,'0');
    let h = d.getHours().toString().padStart(2,'0');
    let min = d.getMinutes().toString().padStart(2,'0');
    return d.getFullYear()+'-'+m+'-'+day+'T'+h+':'+min;
}
// 工具函数：判断是否数字字段
function isNumberField(col) {
    let type = (col.Type||'').toLowerCase();
    return type.startsWith('int') || type.startsWith('decimal') || type.startsWith('float') || type.startsWith('double') || type.startsWith('numeric');
}
// 新增弹窗表单生成
function openAddDialog() {
    document.getElementById('modalMask').style.display = 'block';
    document.getElementById('addDialog').style.display = 'block';
    let html = '';
    for (let col of columns) {
        if (col.Field === pk) continue;
        if (isDateTimeField(col)) {
            html += `<div style='margin-bottom:12px;'><label>${col.Field}：</label><input type='datetime-local' name='${col.Field}' style='width:180px;'></div>`;
        } else if (isDateField(col)) {
            html += `<div style='margin-bottom:12px;'><label>${col.Field}：</label><input type='date' name='${col.Field}' style='width:180px;'></div>`;
        } else {
            html += `<div style='margin-bottom:12px;'><label>${col.Field}：</label><input name='${col.Field}' style='width:180px;'></div>`;
        }
    }
    document.getElementById('addFields').innerHTML = html;
}
// 编辑弹窗表单生成
function openEditDialog(idx) {
    document.getElementById('modalMask').style.display = 'block';
    document.getElementById('editDialog').style.display = 'block';
    let row = data[idx];
    let html = '';
    for (let col of columns) {
        let val = row[col.Field] || '';
        if (col.Field === pk) {
            html += `<div style='margin-bottom:12px;'><label>${col.Field}：</label><input name='${col.Field}' value='${val}' readonly style='width:180px;background:#eee;'></div>`;
        } else if (isDateTimeField(col)) {
            html += `<div style='margin-bottom:12px;'><label>${col.Field}：</label><input type='datetime-local' name='${col.Field}' value='${formatDateTime(val)}' style='width:180px;'></div>`;
        } else if (isDateField(col)) {
            html += `<div style='margin-bottom:12px;'><label>${col.Field}：</label><input type='date' name='${col.Field}' value='${formatDate(val)}' style='width:180px;'></div>`;
        } else {
            html += `<div style='margin-bottom:12px;'><label>${col.Field}：</label><input name='${col.Field}' value='${val}' style='width:180px;'></div>`;
        }
    }
    document.getElementById('editFields').innerHTML = html;
    document.getElementById('editForm').onsubmit = function(e) {
        e.preventDefault();
        let form = e.target;
        let postData = {};
        for (let el of form.elements) {
            if (el.name) {
                let col = columns.find(c=>c.Field===el.name);
                if (el.type === 'date' && el.value) {
                    postData[el.name] = el.value;
                } else if (el.type === 'datetime-local' && el.value) {
                    postData[el.name] = el.value.replace('T',' ');
                } else if (col && isNumberField(col) && el.value === '') {
                    postData[el.name] = null;
                } else {
                    postData[el.name] = el.value;
                }
            }
        }
        let pkValue = postData[pk];
        delete postData[pk];
        fetch('/api/update_row', {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({table: tableName, pk_name: pk, pk_value: pkValue, data: postData})
        }).then(async r => {
            let res;
            try {
                res = await r.json();
            } catch (e) {
                res = {success: false, msg: '服务器未返回有效JSON'};
            }
            if (r.ok && res.success) {
                location.reload();
            } else {
                alert('修改失败：' + (res && res.msg ? res.msg : `HTTP ${r.status}`));
            }
        });
    };
}
function deleteRow(idx) {
    if(!confirm('确定要删除这条数据吗？')) return;
    let row = data[idx];
    let pkValue = row[pk];
    fetch('/api/delete_row', {
        method: 'POST',
        headers: {'Content-Type': 'application/json'},
        body: JSON.stringify({table: tableName, pk_name: pk, pk_value: pkValue})
    }).then(r=>r.json()).then(res=>{
        if(res.success){ location.reload(); } else { alert('删除失败：'+res.msg); }
    });
}
function closeDialog() {
    document.getElementById('modalMask').style.display = 'none';
    document.getElementById('editDialog').style.display = 'none';
    document.getElementById('addDialog').style.display = 'none';
}
document.getElementById('addForm').onsubmit = function(e) {
    e.preventDefault();
    let form = e.target;
    let postData = {};
    for (let el of form.elements) {
        if (el.name) {
            let col = columns.find(c=>c.Field===el.name);
            if (el.type === 'date' && el.value) {
                postData[el.name] = el.value;
            } else if (el.type === 'datetime-local' && el.value) {
                postData[el.name] = el.value.replace('T',' ');
            } else if (col && isNumberField(col) && el.value === '') {
                postData[el.name] = null;
            } else {
                postData[el.name] = el.value;
            }
        }
    }
    fetch('/api/add_row', {
        method: 'POST',
        headers: {'Content-Type': 'application/json'},
        body: JSON.stringify({table: tableName, data: postData})
    }).then(r=>r.json()).then(res=>{
        if(res.success){ location.reload(); } else { alert('新增失败：'+res.msg); }
    });
};

document.getElementById('fieldsSelect').addEventListener('focus', function() {
    this.parentNode.querySelector('.choices').click();
});


function toggleSelectAll(selectAllCheckbox) {
    const checkboxes = document.querySelectorAll('.data-table input[type=checkbox]');
    checkboxes.forEach(checkbox => {
        checkbox.checked = selectAllCheckbox.checked;
    });
}

function exportExcel() {
    const table = tableName; // 替换为实际的表名
    const selectedRows = Array.from(document.querySelectorAll('.data-table input[type=checkbox]:checked'));
    if (selectedRows.length === 0) {
        alert('请至少选择一条记录进行导出。');
        return;
    }
    const ids = selectedRows.map(row => row.dataset.id);
    
    fetch('/api/export_excel', {
        method: 'POST',
        headers: {'Content-Type': 'application/json'},
        body: JSON.stringify({table: table, ids: ids})
    })
    .then(response => {
        if (response.ok) {
            return response.blob(); // 获取文件 Blob
        } else {
            return response.json().then(res => { throw new Error(res.msg); });
        }
    })
    .then(blob => {
        const url = window.URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.href = url;
        a.download = `${table}.xlsx`; // 设置下载文件名
        document.body.appendChild(a);
        a.click();
        a.remove();
    })
    .catch(error => {
        alert('导出失败：' + error.message);
    });
}

function changePerPage() {
    const perPage = document.getElementById('perPageSelect').value;
    const table = document.getElementById('tableSelect').value;
    const searchTerm = document.getElementById('searchInput').value.trim();
    const fields = getSelectedFields();
    const sortFields = getSelectedSortFields();
    const sortOrders = getSelectedSortOrders();
    let url = `/query?table=${table}&per_page=${perPage}`;
    if (fields) url += `&fields=${encodeURIComponent(fields)}`;
    if (searchTerm) url += `&search=${encodeURIComponent(searchTerm)}`;
    if (sortFields) url += `&sort_field=${encodeURIComponent(sortFields)}`;
    if (sortOrders) url += `&sort_order=${encodeURIComponent(sortOrders)}`;
    window.location.href = url;
}
</script>
</body>
</html>
'''

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True) 