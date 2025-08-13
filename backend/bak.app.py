# backend/app.py
from flask import Flask, jsonify, render_template, request
from db_utils import get_db_connection

app = Flask(__name__)

@app.route("/")
def index():
    return "财务系统后端服务已启动"

@app.route("/accounts")
def show_accounts_page():
    """渲染会计科目页面"""
    conn = get_db_connection()
    if conn is None:
        return "数据库连接失败", 500
    
    cursor = conn.cursor(dictionary=True)
    try:
        cursor.execute("SELECT * FROM chart_of_accounts ORDER BY account_code;")
        accounts_data = cursor.fetchall()
        return render_template('accounts.html', accounts=accounts_data)
    except Exception as e:
        return f"查询失败: {e}", 500
    finally:
        cursor.close()
        conn.close()

# --- Read: 获取所有会计科目 ---
@app.route("/api/accounts", methods=['GET'])
def get_accounts_api():
    """获取所有会计科目的API接口"""
    conn = get_db_connection()
    if conn is None:
        return jsonify({"error": "数据库连接失败"}), 500
    
    cursor = conn.cursor(dictionary=True)
    try:
        cursor.execute("SELECT * FROM chart_of_accounts ORDER BY account_code;")
        accounts = cursor.fetchall()
        return jsonify(accounts)
    except Exception as e:
        return jsonify({"error": f"查询失败: {e}"}), 500
    finally:
        cursor.close()
        conn.close()

# --- Create: 新增一个会计科目 ---
@app.route("/api/accounts", methods=['POST'])
def create_account_api():
    """新增一个会计科目"""
    data = request.get_json()
    if not data:
        return jsonify({"error": "请求体中没有提供数据"}), 400

    account_code = data.get('account_code')
    account_name = data.get('account_name')
    balance_direction = data.get('balance_direction')

    if not all([account_code, account_name, balance_direction]):
        return jsonify({"error": "缺少必要的字段: account_code, account_name, balance_direction"}), 400

    conn = get_db_connection()
    if conn is None:
        return jsonify({"error": "数据库连接失败"}), 500
    
    cursor = conn.cursor()
    try:
        sql = "INSERT INTO chart_of_accounts (account_code, account_name, balance_direction) VALUES (%s, %s, %s)"
        cursor.execute(sql, (account_code, account_name, balance_direction))
        conn.commit()
        return jsonify({"message": "会计科目创建成功"}), 201
    except Exception as e:
        conn.rollback()
        return jsonify({"error": f"创建失败: {e}"}), 500
    finally:
        cursor.close()
        conn.close()


# --- Delete: 删除一个会计科目 ---
@app.route("/api/accounts/<string:account_code>", methods=['DELETE'])
def delete_account_api(account_code):
    """删除一个会计科目"""
    conn = get_db_connection()
    if conn is None:
        return jsonify({"error": "数据库连接失败"}), 500
    
    cursor = conn.cursor()
    try:
        cursor.execute("DELETE FROM chart_of_accounts WHERE account_code = %s", (account_code,))
        conn.commit()
        if cursor.rowcount > 0:
            return jsonify({"message": "删除成功"})
        else:
            return jsonify({"error": "未找到该科目"}), 404
    except Exception as e:
        conn.rollback()
        return jsonify({"error": f"删除失败: {e}"}), 500
    finally:
        cursor.close()
        conn.close()

# backend/app.py

# --- Read: 获取单个会计科目 ---
@app.route("/api/accounts/<string:account_code>", methods=['GET'])
def get_single_account_api(account_code):
    """获取单个会计科目的API接口"""
    conn = get_db_connection()
    if conn is None:
        return jsonify({"error": "数据库连接失败"}), 500
    
    cursor = conn.cursor(dictionary=True)
    try:
        cursor.execute("SELECT * FROM chart_of_accounts WHERE account_code = %s;", (account_code,))
        account = cursor.fetchone() # 使用 fetchone() 获取单条记录
        if account:
            return jsonify(account)
        else:
            return jsonify({"error": "未找到该科目"}), 404
    except Exception as e:
        return jsonify({"error": f"查询失败: {e}"}), 500
    finally:
        cursor.close()
        conn.close()


# --- Update: 修改一个会计科目 (修正版) ---
@app.route("/api/accounts/<string:account_code>", methods=['PUT'])
def update_account_api(account_code):
    """修改一个会计科目"""
    data = request.get_json()
    if not data:
        return jsonify({"error": "请求体中没有提供数据"}), 400

    new_name = data.get('account_name')
    if not new_name:
        return jsonify({"error": "缺少 account_name 字段"}), 400

    conn = get_db_connection()
    if conn is None:
        return jsonify({"error": "数据库连接失败"}), 500
    
    cursor = conn.cursor()
    try:
        # 先检查科目是否存在
        cursor.execute("SELECT 1 FROM chart_of_accounts WHERE account_code = %s", (account_code,))
        if cursor.fetchone() is None:
            return jsonify({"error": "未找到该科目"}), 404

        # 再执行更新
        sql = "UPDATE chart_of_accounts SET account_name = %s WHERE account_code = %s"
        cursor.execute(sql, (new_name, account_code))
        conn.commit()
        
        # 只要没有异常，就返回成功
        return jsonify({"message": "会计科目更新成功"})

    except Exception as e:
        conn.rollback()
        return jsonify({"error": f"更新失败: {e}"}), 500
    finally:
        cursor.close()
        conn.close()

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)

