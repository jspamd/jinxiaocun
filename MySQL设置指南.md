# MySQL设置指南

## 问题诊断

您遇到的错误是：`Access denied for user 'root'@'localhost' (using password: NO)`

这表示MySQL的root用户需要密码或者没有权限。

## 解决方案

### 方案1：设置root用户密码

1. **打开MySQL命令行**：
   ```bash
   mysql -u root
   ```

2. **如果成功进入，设置密码**：
   ```sql
   ALTER USER 'root'@'localhost' IDENTIFIED BY 'your_password';
   FLUSH PRIVILEGES;
   ```

3. **修改配置文件**：
   编辑 `database_config.py`，将password字段改为：
   ```python
   'password': 'your_password',  # 替换为您的密码
   ```

### 方案2：创建新用户

1. **以root身份登录MySQL**：
   ```bash
   mysql -u root -p
   ```

2. **创建新用户**：
   ```sql
   CREATE USER 'jinxiaocun'@'localhost' IDENTIFIED BY 'your_password';
   GRANT ALL PRIVILEGES ON jinxiaocun_db.* TO 'jinxiaocun'@'localhost';
   FLUSH PRIVILEGES;
   ```

3. **修改配置文件**：
   编辑 `database_config.py`：
   ```python
   'user': 'jinxiaocun',
   'password': 'your_password',
   ```

### 方案3：允许root无密码登录（不推荐）

1. **编辑MySQL配置文件**：
   找到 `my.ini` 或 `my.cnf` 文件

2. **添加以下内容**：
   ```ini
   [mysqld]
   skip-grant-tables
   ```

3. **重启MySQL服务**

## 检查MySQL服务状态

### Windows系统：
```bash
# 检查服务状态
net start | findstr MySQL

# 启动MySQL服务
net start MySQL80
# 或
net start MySQL

# 停止MySQL服务
net stop MySQL80
# 或
net stop MySQL
```

### 使用服务管理器：
1. 按 `Win + R`，输入 `services.msc`
2. 找到MySQL服务
3. 右键选择"启动"或"重新启动"

## 测试连接

1. **测试配置文件**：
   ```bash
   python database_config.py
   ```

2. **如果成功，运行导入脚本**：
   ```bash
   python debug_import.py
   ```

## 常见问题

### 1. 找不到MySQL服务
- 检查MySQL是否正确安装
- 检查服务名称（可能是MySQL80、MySQL等）

### 2. 端口被占用
- 检查3306端口是否被其他程序占用
- 修改MySQL端口或停止占用端口的程序

### 3. 权限不足
- 以管理员身份运行命令提示符
- 检查用户权限

## 推荐步骤

1. **首先检查MySQL服务是否启动**
2. **尝试以root身份登录**：`mysql -u root`
3. **如果成功，设置密码**（方案1）
4. **如果失败，创建新用户**（方案2）
5. **修改配置文件并测试连接**
6. **运行数据导入脚本**

## 联系支持

如果以上方案都不行，请提供：
- MySQL版本信息
- 操作系统版本
- 完整的错误信息
- MySQL安装方式（安装包、XAMPP等） 