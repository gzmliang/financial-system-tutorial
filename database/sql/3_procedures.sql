-- =================================================================
-- 清理已存在的存储过程 (为了让脚本可重复执行)
-- =================================================================
DROP PROCEDURE IF EXISTS `proc_generate_account_summary`;
DROP PROCEDURE IF EXISTS `proc_generate_general_ledger`;

-- =================================================================
-- 过程一：生成科目汇总表 (循环更新法)
-- =================================================================
DELIMITER $$
CREATE PROCEDURE `proc_generate_account_summary`(IN fiscal_year_param INT)
BEGIN
    -- 声明变量
    DECLARE max_level INT;
    DECLARE current_level INT;

    -- 准备工作：清空当年数据，并从上年结转期初余额
    DELETE FROM account_balances WHERE fiscal_year = fiscal_year_param;

    INSERT INTO account_balances (account_code, fiscal_year, opening_balance)
    SELECT 
        coa.account_code,
        fiscal_year_param,
        COALESCE(prev_year.closing_balance, 0)
    FROM 
        chart_of_accounts coa
    LEFT JOIN 
        account_balances prev_year ON coa.account_code = prev_year.account_code AND prev_year.fiscal_year = fiscal_year_param - 1;

    -- 计算所有末级科目的本期发生额
    UPDATE account_balances ab
    JOIN (
        SELECT 
            je.account_code,
            SUM(je.debit_amount) AS total_debit,
            SUM(je.credit_amount) AS total_credit
        FROM journal_entries je
        JOIN vouchers v ON je.voucher_id = v.id
        WHERE YEAR(v.voucher_date) = fiscal_year_param
          AND NOT EXISTS (SELECT 1 FROM chart_of_accounts WHERE parent_code = je.account_code) -- 确保是末级科目
        GROUP BY je.account_code
    ) AS leaf_summary ON ab.account_code = leaf_summary.account_code
    SET 
        ab.period_debit = leaf_summary.total_debit,
        ab.period_credit = leaf_summary.total_credit
    WHERE ab.fiscal_year = fiscal_year_param;

    -- 自底向上循环汇总发生额
    SELECT MAX(level) INTO max_level FROM chart_of_accounts;
    SET current_level = max_level;
    WHILE current_level > 1 DO
        UPDATE account_balances parent_ab
        JOIN (
            SELECT 
                coa.parent_code,
                SUM(child_ab.period_debit) AS total_debit,
                SUM(child_ab.period_credit) AS total_credit
            FROM account_balances child_ab
            JOIN chart_of_accounts coa ON child_ab.account_code = coa.account_code
            WHERE child_ab.fiscal_year = fiscal_year_param AND coa.level = current_level AND coa.parent_code IS NOT NULL
            GROUP BY coa.parent_code
        ) AS child_summary ON parent_ab.account_code = child_summary.parent_code
        SET 
            parent_ab.period_debit = parent_ab.period_debit + COALESCE(child_summary.total_debit, 0),
            parent_ab.period_credit = parent_ab.period_credit + COALESCE(child_summary.total_credit, 0)
        WHERE parent_ab.fiscal_year = fiscal_year_param;
        
        SET current_level = current_level - 1;
    END WHILE;

    -- 计算所有科目的期末余额
    UPDATE account_balances ab
    JOIN chart_of_accounts coa ON ab.account_code = coa.account_code
    SET ab.closing_balance = 
        CASE 
            WHEN coa.balance_direction = 'debit' THEN ab.opening_balance + ab.period_debit - ab.period_credit
            ELSE ab.opening_balance - ab.period_debit + ab.period_credit
        END
    WHERE ab.fiscal_year = fiscal_year_param;

END$$
DELIMITER ;


-- =================================================================
-- 过程二：生成指定科目的总分类账
-- =================================================================
DELIMITER $$
CREATE PROCEDURE `proc_generate_general_ledger`(IN target_account_code VARCHAR(16), IN fiscal_year_param INT)
BEGIN
    -- 声明变量
    DECLARE done INT DEFAULT FALSE;
    DECLARE running_balance DECIMAL(14, 2);
    DECLARE v_voucher_date DATE;
    DECLARE v_summary VARCHAR(255);
    DECLARE v_debit DECIMAL(12, 2);
    DECLARE v_credit DECIMAL(12, 2);
    DECLARE v_direction ENUM('debit', 'credit');

    -- 声明游标，用于遍历指定年度的凭证分录
    DECLARE cur_entries CURSOR FOR 
        SELECT v.voucher_date, je.summary, je.debit_amount, je.credit_amount 
        FROM journal_entries je
        JOIN vouchers v ON je.voucher_id = v.id
        WHERE je.account_code = target_account_code AND YEAR(v.voucher_date) = fiscal_year_param
        ORDER BY v.voucher_date, v.id;
        
    DECLARE CONTINUE HANDLER FOR NOT FOUND SET done = TRUE;

    -- 准备工作：创建临时结果表
    DROP TEMPORARY TABLE IF EXISTS `general_ledger_result`;
    CREATE TEMPORARY TABLE `general_ledger_result` (
        `entry_date` DATE,
        `summary` VARCHAR(255),
        `debit` DECIMAL(12, 2),
        `credit` DECIMAL(12, 2),
        `direction` VARCHAR(10),
        `balance` DECIMAL(14, 2)
    );

    -- 获取期初余额和余额方向
    SELECT ab.opening_balance, coa.balance_direction 
    INTO running_balance, v_direction
    FROM account_balances ab
    JOIN chart_of_accounts coa ON ab.account_code = coa.account_code
    WHERE ab.account_code = target_account_code AND ab.fiscal_year = fiscal_year_param;

    -- 插入期初行
    INSERT INTO `general_ledger_result` VALUES (
        MAKEDATE(fiscal_year_param, 1), 
        '期初余额', 
        0.00, 
        0.00, 
        IF(v_direction = 'debit', '借', '贷'), 
        running_balance
    );

    -- 打开游标并循环处理
    OPEN cur_entries;
    read_loop: LOOP
        FETCH cur_entries INTO v_voucher_date, v_summary, v_debit, v_credit;
        IF done THEN
            LEAVE read_loop;
        END IF;

        -- 计算实时余额
        IF v_direction = 'debit' THEN
            SET running_balance = running_balance + v_debit - v_credit;
        ELSE
            SET running_balance = running_balance - v_debit + v_credit;
        END IF;

        -- 将计算结果插入到结果表
        INSERT INTO `general_ledger_result` VALUES (
            v_voucher_date, 
            v_summary, 
            v_debit, 
            v_credit, 
            IF(v_direction = 'debit', '借', '贷'), 
            running_balance
        );
    END LOOP;
    CLOSE cur_entries;
    
    -- 返回最终结果
    SELECT * FROM `general_ledger_result`;

END$$
DELIMITER ;
