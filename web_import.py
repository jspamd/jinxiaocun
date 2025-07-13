import os
from flask import Flask, request, render_template_string, jsonify
from werkzeug.utils import secure_filename
from debug_import import import_excel_data, create_connection

UPLOAD_FOLDER = 'uploads'
ALLOWED_EXTENSIONS = {'xls', 'xlsx'}

# 文件名与表名的映射
FILENAME_TABLE_MAP = {
    '客户原始兑付明细': 'customer_redemption_details',
    '客户流向': 'customer_flow',
    '活动方案': 'activity_plan',
    '输出结果': 'output_results',
}

app = Flask(__name__)
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
app.config['MAX_CONTENT_LENGTH'] = 32 * 1024 * 1024  # 32MB

if not os.path.exists(UPLOAD_FOLDER):
    os.makedirs(UPLOAD_FOLDER)

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].strip().lower() in ALLOWED_EXTENSIONS

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
    return render_template_string(TEMPLATE, result_msgs=result_msgs)

TEMPLATE = '''
<!DOCTYPE html>
<html lang="zh-CN">
<head>
    <meta charset="UTF-8">
    <title>Excel数据导入系统</title>
    <style>
        body { font-family: "微软雅黑", Arial, sans-serif; background: #f7f7f7; }
        .container { max-width: 500px; margin: 60px auto; background: #fff; padding: 30px 40px; border-radius: 8px; box-shadow: 0 2px 8px #ccc; }
        h2 { text-align: center; color: #333; }
        .msg { margin: 10px 0; color: #007700; }
        .error { color: #bb2222; }
        .upload-btn { background: #007bff; color: #fff; border: none; padding: 10px 24px; border-radius: 4px; cursor: pointer; font-size: 16px; }
        .upload-btn:hover { background: #0056b3; }
        input[type=file] { margin: 20px 0; }
    </style>
</head>
<body>
<div class="container">
    <h2>Excel数据导入系统</h2>
    <form method="post" enctype="multipart/form-data">
        <label>请选择要上传的Excel文件（可多选）：</label><br>
        <input type="file" name="file" multiple required><br>
        <button class="upload-btn" type="submit">上传并导入</button>
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
        3. 遇到“进货单位”行自动停止导入。<br>
        4. 仅支持xls/xlsx格式。<br>
    </div>
</div>
</body>
</html>
'''

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True) 