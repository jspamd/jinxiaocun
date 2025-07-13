import os
import sys
from flask import Flask, request, render_template_string, jsonify
from werkzeug.utils import secure_filename
from debug_import import import_excel_data, create_connection

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

app = Flask(__name__, static_folder=resource_path('static'))
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
        body {
            font-family: "微软雅黑", Arial, sans-serif;
            background: 
                linear-gradient(135deg, rgba(224,231,255,0.7) 0%, rgba(247,247,247,0.8) 100%),
                url('/static/finance_bg.jpg') no-repeat center center fixed;
            background-size: cover;
            min-height: 100vh;
            margin: 0;
        }
        .container {
            max-width: 500px;
            margin: 60px auto;
            background: #fff;
            padding: 30px 40px;
            border-radius: 16px;
            box-shadow: 0 8px 32px rgba(60,60,120,0.15), 0 1.5px 4px #ccc;
            animation: fadeInCard 1s;
        }
        @keyframes fadeInCard {
            from { opacity: 0; transform: translateY(40px); }
            to { opacity: 1; transform: translateY(0); }
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
        3. 遇到“进货单位”行自动停止导入。<br>
        4. 仅支持xls/xlsx格式。<br>
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

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True) 