# backend/app.py (最终修正版)
from flask import Flask, jsonify, render_template, request
from db_utils import get_db_connection

app = Flask(__name__)

# --- 页面渲染路由 ---

@app.route("/")
def index():
    """渲染首页或一个简单的欢迎页面"""
    # 在实践中，这里可以重定向到/accounts，或者渲染一个dashboard
    return render_template('layout.html') # 假设渲染基础布局作为首页

@app.route("/accounts")
def show_accounts_page():
    """渲染会计科目管理页面（仅作为模板框架）"""
    return render_template('accounts.html')

@app.route("/reports")
def show_reports_page():
    """渲染财务报表页面"""
    return render_template('reports.html')

# --- API 路由：科目管理 (CRUD) ---

@app.route("/api/accounts", methods=['GET'])
def get_accounts_api():
    """【关键补充】获取所有会计科目的API接口"""
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

@app.route("/api/accounts/<string:account_code>", methods=['GET'])
def get_single_account_api(account_code):
    """获取单个会计科目的API接口"""
    conn = get_db_connection()
    if conn is None: return jsonify({"error": "数据库连接失败"}), 500
    
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

@app.route("/api/accounts", methods=['POST'])
def create_account_api():
    """新增一个会计科目"""
    data = request.get_json()
    if not data: return jsonify({"error": "请求体中没有提供数据"}), 400

    account_code = data.get('account_code')
    account_name = data.get('account_name')
    balance_direction = data.get('balance_direction')

    if not all([account_code, account_name, balance_direction]):
        return jsonify({"error": "缺少必要的字段"}), 400

    conn = get_db_connection()
    if conn is None: return jsonify({"error": "数据库连接失败"}), 500
    
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

@app.route("/api/accounts/<string:account_code>", methods=['PUT'])
def update_account_api(account_code):
    """修改一个会计科目"""
    data = request.get_json()
    if not data: return jsonify({"error": "请求体中没有提供数据"}), 400

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

    values.append(account_code)
    conn = get_db_connection()
    if conn is None: return jsonify({"error": "数据库连接失败"}), 500
    
    cursor = conn.cursor()
    try:
        sql = f"UPDATE chart_of_accounts SET {', '.join(fields_to_update)} WHERE account_code = %s"
        cursor.execute(sql, tuple(values))
        conn.commit()
        return jsonify({"message": "会计科目更新成功"})
    except Exception as e:
        conn.rollback()
        return jsonify({"error": f"更新失败: {e}"}), 500
    finally:
        cursor.close()
        conn.close()

@app.route("/api/accounts/<string:account_code>", methods=['DELETE'])
def delete_account_api(account_code):
    """删除一个会计科目"""
    conn = get_db_connection()
    if conn is None: return jsonify({"error": "数据库连接失败"}), 500
    
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

# --- API 路由：期初余额管理 ---

@app.route("/api/account_balances", methods=['GET'])
def get_account_balances_api():
    """根据年份获取所有科目的期初余额，并判断是否为初始年份"""
    year = request.args.get('year', type=int)
    if not year: return jsonify({"error": "必须提供年份参数"}), 400

    conn = get_db_connection()
    if conn is None: return jsonify({"error": "数据库连接失败"}), 500
    
    cursor = conn.cursor(dictionary=True)
    try:
        cursor.execute("SELECT MIN(fiscal_year) as min_year FROM account_balances WHERE opening_balance != 0 OR period_debit != 0 OR period_credit != 0")
        result = cursor.fetchone()
        min_year = result['min_year'] if result and result['min_year'] is not None else year
        is_initial_year = (year <= min_year)

        sql = """
            SELECT coa.account_code, ab.opening_balance
            FROM chart_of_accounts coa
            LEFT JOIN account_balances ab ON coa.account_code = ab.account_code AND ab.fiscal_year = %s
            ORDER BY coa.account_code;
        """
        cursor.execute(sql, (year,))
        balances = cursor.fetchall()
        balance_map = {b['account_code']: b['opening_balance'] for b in balances}

        return jsonify({
            "balances": balance_map,
            "is_initial_year": is_initial_year
        })
    except Exception as e:
        return jsonify({"error": f"查询期初余额失败: {e}"}), 500
    finally:
        cursor.close()
        conn.close()

@app.route("/api/account_balances", methods=['POST'])
def save_account_balances_api():
    """批量保存或更新指定年份的期初余额"""
    data = request.get_json()
    year = data.get('year')
    balances = data.get('balances')
    if not year or balances is None:
        return jsonify({"error": "缺少年份或余额数据"}), 400

    conn = get_db_connection()
    if conn is None: return jsonify({"error": "数据库连接失败"}), 500
    
    cursor = conn.cursor()
    try:
        sql = """
            INSERT INTO account_balances (account_code, fiscal_year, opening_balance)
            VALUES (%s, %s, %s)
            ON DUPLICATE KEY UPDATE opening_balance = VALUES(opening_balance)
        """
        data_to_insert = [(item['account_code'], year, item['balance']) for item in balances]
        cursor.executemany(sql, data_to_insert)
        conn.commit()
        return jsonify({"message": f"{year}年度的期初余额已成功保存"})
    except Exception as e:
        conn.rollback()
        return jsonify({"error": f"保存期初余额失败: {e}"}), 500
    finally:
        cursor.close()
        conn.close()

# --- API 路由：报表 ---

@app.route("/api/reports/generate_summary", methods=['POST'])
def generate_summary_api():
    """调用存储过程，计算指定年度的科目汇总数据"""
    data = request.get_json()
    year = data.get('year')
    if not year: return jsonify({"error": "必须提供年份"}), 400
    
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

# 获取报表数据的API
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
        cursor.execute("SELECT * FROM balance_sheet_report ORDER BY line_index;")
        report_data = cursor.fetchall()
        return jsonify(report_data)
    except Exception as e:
        return jsonify({"error": f"获取报表失败: {e}"}), 500
    finally:
        cursor.close()
        conn.close()
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
        cursor.callproc('proc_generate_cash_flow_statement', (year,))
        cursor.execute("SELECT * FROM cash_flow_statement_report ORDER BY line_index;")
        report_data = cursor.fetchall()
        results = []
        for row in report_data:
            results.append({
                'item': row.get('item'),
                'amount': row.get('amount') or row.get('current_period_amount')
            })

        return jsonify(results)
    except Exception as e:
        return jsonify({"error": f"获取报表失败: {e}"}), 500
    finally:
        cursor.close()
        conn.close()
@app.route("/api/reports/trial_balance", methods=['GET'])
def get_trial_balance_api():
    """获取试算平衡表数据"""
    year = request.args.get('year', type=int)
    if not year:
        return jsonify({"error": "必须提供年份参数"}), 400

    conn = get_db_connection()
    if conn is None: return jsonify({"error": "数据库连接失败"}), 500
    
    cursor = conn.cursor(dictionary=True)
    try:
        # 1. 调用存储过程执行计算
        cursor.callproc('proc_generate_trial_balance', (year,))
        
        # 2. 查询计算结果
        cursor.execute("SELECT * FROM trial_balance_report;")
        report_data = cursor.fetchall()

        # 3. 返回结果
        return jsonify(report_data)
    except Exception as e:
        return jsonify({"error": f"获取试算平衡表失败: {e}"}), 500
    finally:
        # 确保在存储过程调用后提交，使其结果对后续查询可见
        conn.commit()
        cursor.close()
        conn.close()



if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)

