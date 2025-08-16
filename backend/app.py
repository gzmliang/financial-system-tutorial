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

# --- API 路由 ---

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
        account = cursor.fetchone()
        if account:
            return jsonify(account)
        else:
            return jsonify({"error": "未找到该科目"}), 404
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

# --- Update: 修改一个会计科目 (最终修正版) ---
@app.route("/api/accounts/<string:account_code>", methods=['PUT'])
def update_account_api(account_code):
    """修改一个会计科目"""
    data = request.get_json()
    if not data:
        return jsonify({"error": "请求体中没有提供数据"}), 400

    # 准备要更新的字段和值
    fields_to_update = []
    values = []

    if 'account_name' in data:
        fields_to_update.append("account_name = %s")
        values.append(data['account_name'])
    
    if 'balance_direction' in data:
        fields_to_update.append("balance_direction = %s")
        values.append(data['balance_direction'])

    if not fields_to_update:
        return jsonify({"error": "没有提供可更新的字段"}), 400

    values.append(account_code) # 将 account_code 添加到值的末尾用于 WHERE 子句

    conn = get_db_connection()
    if conn is None:
        return jsonify({"error": "数据库连接失败"}), 500
    
    cursor = conn.cursor()
    try:
        # 动态构建 SQL 语句
        sql = f"UPDATE chart_of_accounts SET {', '.join(fields_to_update)} WHERE account_code = %s"
        
        cursor.execute(sql, tuple(values))
        conn.commit()
        
        if cursor.rowcount > 0:
            return jsonify({"message": "会计科目更新成功"})
        else:
            # 这种情况可能是因为提交的数据和数据库中完全一样，没有实际更新
            # 但我们仍然认为这是一个成功的操作
            return jsonify({"message": "会计科目更新成功 (数据无变化)"})

    except Exception as e:
        conn.rollback()
        return jsonify({"error": f"更新失败: {e}"}), 500
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

# --- 页面渲染路由 ---
@app.route("/reports")
def show_reports_page():
    """渲染财务报表页面"""
    return render_template('reports.html')

# --- API 路由 ---

# 1. 触发汇总计算的API
@app.route("/api/reports/generate_summary", methods=['POST'])
def generate_summary_api():
    """调用存储过程，计算指定年度的科目汇总数据"""
    data = request.get_json()
    year = data.get('year')
    if not year:
        return jsonify({"error": "必须提供年份"}), 400
    
    conn = get_db_connection()
    if conn is None: return jsonify({"error": "数据库连接失败"}), 500
    
    cursor = conn.cursor()
    try:
        cursor.callproc('proc_generate_account_summary', (year,))
        conn.commit()
        return jsonify({"message": f"{year}年度科目汇总数据已生成"})
    except Exception as e:
        conn.rollback()
        return jsonify({"error": f"汇总计算失败: {e}"}), 500
    finally:
        cursor.close()
        conn.close()

# 2. 获取科目汇总表的API
@app.route("/api/reports/account_summary", methods=['GET'])
def get_account_summary_api():
    """获取指定年度的科目汇总表数据"""
    year = request.args.get('year', type=int)
    if not year:
        return jsonify({"error": "必须提供年份参数"}), 400

    conn = get_db_connection()
    if conn is None: return jsonify({"error": "数据库连接失败"}), 500
    
    cursor = conn.cursor(dictionary=True)
    try:
        # 联结科目定义表以获取科目名称
        sql = """
            SELECT 
                ab.account_code,
                coa.account_name,
                ab.opening_balance,
                ab.period_debit,
                ab.period_credit,
                ab.closing_balance
            FROM account_balances ab
            JOIN chart_of_accounts coa ON ab.account_code = coa.account_code
            WHERE ab.fiscal_year = %s
            ORDER BY ab.account_code;
        """
        cursor.execute(sql, (year,))
        summary_data = cursor.fetchall()
        return jsonify(summary_data)
    except Exception as e:
        return jsonify({"error": f"获取科目汇总表失败: {e}"}), 500
    finally:
        cursor.close()
        conn.close()



# 3. 获取资产负债表的API
@app.route("/api/reports/balance_sheet", methods=['GET'])
def get_balance_sheet_api():
    """获取资产负债表数据"""
    year = request.args.get('year', type=int)
    if not year:
        return jsonify({"error": "必须提供年份参数"}), 400

    conn = get_db_connection()
    if conn is None: return jsonify({"error": "数据库连接失败"}), 500
    
    cursor = conn.cursor(dictionary=True)
    try:
        cursor.callproc('proc_generate_balance_sheet', (year,))
        # 存储过程执行后，数据已在 balance_sheet_report 表中，直接查询即可
        cursor.execute("SELECT * FROM balance_sheet_report ORDER BY line_index;")
        report_data = cursor.fetchall()
        return jsonify(report_data)
    except Exception as e:
        return jsonify({"error": f"获取报表失败: {e}"}), 500
    finally:
        cursor.close()
        conn.close()
# 4. 获取利润表的API
@app.route("/api/reports/income_statement", methods=['GET'])
def get_income_statement_api():
    """获取利润表数据"""
    year = request.args.get('year', type=int)
    if not year:
        return jsonify({"error": "必须提供年份参数"}), 400
        
    conn = get_db_connection()
    if conn is None: return jsonify({"error": "数据库连接失败"}), 500
    
    cursor = conn.cursor(dictionary=True)
    try:
        cursor.callproc('proc_generate_income_statement', (year,))
        cursor.execute("SELECT * FROM income_statement_report ORDER BY line_index;")
        report_data = cursor.fetchall()
        return jsonify(report_data)
    except Exception as e:
        return jsonify({"error": f"获取报表失败: {e}"}), 500
    finally:
        cursor.close()
        conn.close()

# 3. 获取现金流量表的API (已修正)
@app.route("/api/reports/cash_flow_statement", methods=['GET'])
def get_cash_flow_statement_api():
    """获取现金流量表数据"""
    year = request.args.get('year', type=int)
    if not year:
        return jsonify({"error": "必须提供年份参数"}), 400

    conn = get_db_connection()
    if conn is None: return jsonify({"error": "数据库连接失败"}), 500
    
    cursor = conn.cursor(dictionary=True)
    try:
        # 步骤1：调用存储过程生成最新数据
        cursor.callproc('proc_generate_cash_flow_statement', (year,))
        
        # 步骤2：查询生成的结果，但只选择我们需要的字段
        cursor.execute("SELECT item, current_period_amount FROM cash_flow_statement_report ORDER BY line_index;")
        report_data = cursor.fetchall()

        # <<< 核心修改在这里 >>>
        # 步骤3：手动构建符合前端JS要求的JSON结构
        # 我们将数据库中的 'current_period_amount' 改名为 'amount' 再发给前端
        results = []
        for row in report_data:
            results.append({
                'item': row['item'],
                'amount': row['current_period_amount'] # 将key重命名为'amount'
            })
        
        return jsonify(results)

    except Exception as e:
        return jsonify({"error": f"获取报表失败: {e}"}), 500
    finally:
        cursor.close()
        conn.close()

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)

