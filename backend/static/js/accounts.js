// backend/static/js/accounts.js (父科目自动汇总最终版)
$(document).ready(function() {

    // --- 全局变量 ---
    const API_ACCOUNTS_URL = '/api/accounts';
    const API_BALANCES_URL = '/api/account_balances';
    const $tableBody = $('#accounts-table tbody');
    const $modal = $('#account-modal');
    const $form = $('#account-form');
    const $modalTitle = $('#modal-title');
    const $fiscalYearInput = $('#fiscal-year');
    const $balanceStatus = $('#balance-status');
    const $btnSaveBalances = $('#btn-save-balances');
    
    let accountsDataMap = {}; // 用于存储所有科目的详细信息，便于计算

    // --- 功能1: 自动汇总所有父科目余额 ---
    function updateAllParentBalances() {
        // 从层级最高的父科目开始，倒序计算
        const parentAccounts = Object.values(accountsDataMap)
            .filter(acc => !acc.is_leaf)
            .sort((a, b) => b.level - a.level);

        parentAccounts.forEach(parent => {
            let totalBalance = 0;
            // 找到所有直接下级科目
            const children = Object.values(accountsDataMap).filter(child => child.parent_code === parent.account_code);

            children.forEach(child => {
                // 从页面上获取下级科目的当前余额
                const childBalance = parseFloat($(`tr[data-code="${child.account_code}"] .opening-balance-input`).val()) || 0;
                
                // 根据余额方向进行加减
                if (child.balance_direction === parent.balance_direction) {
                    totalBalance += childBalance;
                } else {
                    totalBalance -= childBalance;
                }
            });

            // 更新父科目在页面上的余额显示
            $(`tr[data-code="${parent.account_code}"] .opening-balance-input`).val(totalBalance.toFixed(2));
        });
    }

    // --- 功能2: 加载科目列表与期初余额 ---
    function loadAccounts() {
        const year = $fiscalYearInput.val();
        if (!year) { return; }
        
        const accountsRequest = $.ajax({ url: API_ACCOUNTS_URL, type: 'GET' });
        const balancesRequest = $.ajax({ url: `${API_BALANCES_URL}?year=${year}`, type: 'GET' });

        $.when(accountsRequest, balancesRequest).done(function(accountsResponse, balancesResponse) {
            const accounts = accountsResponse[0];
            const balanceData = balancesResponse[0];
            
            accountsDataMap = {};
            $tableBody.empty();

            if (accounts && Array.isArray(accounts)) {
                accounts.forEach(function(account) {
                    accountsDataMap[account.account_code] = account; // 存储完整科目信息
                    const openingBalance = balanceData.balances[account.account_code] || 0.00;
                    const isReadOnly = !account.is_leaf ? 'readonly' : '';
                    const inputClass = !account.is_leaf ? 'parent-balance-input' : '';

                    const row = `
                        <tr data-code="${account.account_code}" data-parent-code="${account.parent_code || ''}">
                            <td>${account.account_code}</td>
                            <td>${account.account_name}</td>
                            <td>${account.balance_direction === 'debit' ? '借' : '贷'}</td>
                            <td>${account.level || ''}</td>
                            <td>
                                <input type="number" class="opening-balance-input ${inputClass}" value="${parseFloat(openingBalance).toFixed(2)}" step="0.01" ${isReadOnly}>
                            </td>
                            <td>
                                <button class="btn btn-edit" data-code="${account.account_code}">编辑</button>
                                <button class="btn btn-danger btn-delete" data-code="${account.account_code}">删除</button>
                            </td>
                        </tr>
                    `;
                    $tableBody.append(row);
                });
                
                updateAllParentBalances();
            }
        }).fail(function(xhr) {
            alert("加载会计科目或期初余额失败！" + (xhr.responseJSON ? xhr.responseJSON.error : ''));
        });
    }

    // --- 事件绑定 ---
    $fiscalYearInput.on('change', function() {
        $balanceStatus.text('').hide();
        loadAccounts();
    });

    $btnSaveBalances.on('click', function() {
        const year = $fiscalYearInput.val();
        if (!year) { return alert('请输入有效的会计年度！'); }

        let balancesToSave = [];
        $tableBody.find('tr').each(function() {
            const $row = $(this);
            balancesToSave.push({
                account_code: $row.data('code'),
                balance: parseFloat($row.find('.opening-balance-input').val()) || 0
            });
        });

        $.ajax({
            url: API_BALANCES_URL,
            type: 'POST',
            contentType: 'application/json',
            data: JSON.stringify({ year: parseInt(year), balances: balancesToSave }),
            success: function(response) {
                $balanceStatus.text(response.message).css('color', 'green').fadeIn().delay(3000).fadeOut();
            },
            error: function(xhr) {
                alert('保存失败: ' + (xhr.responseJSON ? xhr.responseJSON.error : '未知错误'));
            }
        });
    });
    
    // 为可编辑的输入框（即末级科目）绑定input事件，实时触发汇总计算
    $tableBody.on('input', '.opening-balance-input:not([readonly])', updateAllParentBalances);

    //  ---功能3 科目CRUD功能 (保持完整) ---
    $('#btn-add-account').on('click', function() {
        $modalTitle.text('新增科目');
        $form[0].reset();
        $('#account-code').prop('readonly', false);
        $modal.show();
    });

    $('.close-button').on('click', function() {
        $modal.hide();
    });

    $form.on('submit', function(event) {
        event.preventDefault();
        
        const accountCode = $('#account-code').val();
        const isUpdate = $('#account-code').prop('readonly');
        const url = isUpdate ? `${API_ACCOUNTS_URL}/${accountCode}` : API_ACCOUNTS_URL;
        const method = isUpdate ? 'PUT' : 'POST';

        const formData = {
            account_name: $('#account-name').val(),
            balance_direction: $('#balance-direction').val()
        };
        if (!isUpdate) {
            formData.account_code = accountCode;
        }

        $.ajax({
            url: url,
            type: method,
            contentType: 'application/json',
            data: JSON.stringify(formData),
            success: function(response) {
                alert(response.message);
                $modal.hide();
                loadAccounts();
            },
            error: function(xhr) {
                alert('操作失败！' + (xhr.responseJSON ? xhr.responseJSON.error : ''));
            }
        });
    });

    $tableBody.on('click', '.btn-edit', function() {
        const accountCode = $(this).data('code');
        $.ajax({
            url: `${API_ACCOUNTS_URL}/${accountCode}`,
            type: 'GET',
            success: function(account) {
                $modalTitle.text('编辑科目');
                $('#account-code').val(account.account_code).prop('readonly', true);
                $('#account-name').val(account.account_name);
                $('#balance-direction').val(account.balance_direction);
                $modal.show();
            },
            error: function(xhr) {
                alert('获取科目信息失败: ' + (xhr.responseJSON ? xhr.responseJSON.error : '未知错误'));
            }
        });
    });

    $tableBody.on('click', '.btn-delete', function() {
        if (confirm('确定要删除这个科目吗？')) {
            const accountCode = $(this).data('code');
            $.ajax({
                url: `${API_ACCOUNTS_URL}/${accountCode}`,
                type: 'DELETE',
                success: function(response) {
                    alert(response.message);
                    loadAccounts();
                },
                error: function(xhr) {
                    alert('删除失败: ' + (xhr.responseJSON ? xhr.responseJSON.error : '未知错误'));
                }
            });
        }
    });

    // --- 页面初始加载 ---
    loadAccounts();
});
