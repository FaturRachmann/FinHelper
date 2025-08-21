// Dashboard JavaScript
class FinHelperDashboard {
    constructor() {
        this.charts = {};
        this.init();
    }

    async init() {
        await this.loadDashboardData();
        this.setupEventListeners();
        this.updateLastUpdated();
        
        // Auto-refresh every 5 minutes
        setInterval(() => this.loadDashboardData(false), 5 * 60 * 1000);
    }

    async loadDashboardData(showLoading = true) {
        try {
            if (showLoading) this.showLoadingState();
        
            const [dashboardData, budgetStatus, transactions] = await Promise.all([
               this.fetchAPI('/api/reports/dashboard'),
               this.fetchAPI('/api/budgets/current/status'),
                this.fetchAPI('/api/transactions/?limit=5')
            ]);

            console.log('Dashboard Data:', dashboardData);
            console.log('Expense Categories:', dashboardData.expense_by_category);
        
            this.updateBalanceCards(dashboardData);
            this.updateCharts(dashboardData);
            this.updateBudgetStatus(budgetStatus);
            this.updateRecentTransactions(transactions);
            this.hideLoadingState();
            this.updateLastUpdated();

        } catch (error) {
            console.error('Error loading dashboard:', error);
            this.showNotification('Error', 'Failed to load dashboard data', 'error');
            this.hideLoadingState();
        }
    }

    async fetchAPI(endpoint) {
        const response = await fetch(endpoint);
        if (!response.ok) throw new Error(`HTTP ${response.status}`);
        return response.json();
    }

    updateBalanceCards(data) {
        const formatCurrency = (amount) => `Rp ${amount.toLocaleString('id-ID')}`;
        
        document.getElementById('totalBalance').textContent = formatCurrency(data.total_balance || 0);
        document.getElementById('monthlyIncome').textContent = formatCurrency(data.monthly_income || 0);
        document.getElementById('monthlyExpenses').textContent = formatCurrency(data.monthly_expenses || 0);
        document.getElementById('monthlySavings').textContent = formatCurrency(data.monthly_savings || 0);

        // Add color coding for savings
        const savingsElement = document.getElementById('monthlySavings');
        const savings = data.monthly_savings || 0;
        if (savings > 0) {
            savingsElement.className = savingsElement.className.replace('text-red-600', 'text-green-600');
        } else if (savings < 0) {
            savingsElement.className = savingsElement.className.replace('text-green-600', 'text-red-600');
        }
    }

    updateCharts(data) {
        this.updateExpensePieChart(data.expense_by_category || []);
        this.updateCashflowChart(data.daily_flow || []);
    }

    updateExpensePieChart(expenseData) {
        const ctx = document.getElementById('expensePieChart').getContext('2d');
        
        if (this.charts.expensePie) {
            this.charts.expensePie.destroy();
        }

        if (!expenseData.length) {
            ctx.font = "16px Arial";
            ctx.fillStyle = "#6B7280";
            ctx.textAlign = "center";
            ctx.fillText("No expense data", ctx.canvas.width/2, ctx.canvas.height/2);
            return;
        }

        const colors = [
            '#3B82F6', '#EF4444', '#10B981', '#F59E0B', '#8B5CF6',
            '#EC4899', '#6366F1', '#84CC16', '#06B6D4', '#F97316'
        ];

        this.charts.expensePie = new Chart(ctx, {
            type: 'doughnut',
            data: {
                labels: expenseData.map(item => item.category),
                datasets: [{
                    data: expenseData.map(item => item.amount),
                    backgroundColor: colors.slice(0, expenseData.length),
                    borderWidth: 2,
                    borderColor: '#ffffff'
                }]
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                plugins: {
                    legend: {
                        position: 'bottom',
                        labels: {
                            padding: 15,
                            usePointStyle: true,
                            font: { size: 12 }
                        }
                    },
                    tooltip: {
                        callbacks: {
                            label: function(context) {
                                const value = context.raw;
                                const total = context.dataset.data.reduce((a, b) => a + b, 0);
                                const percentage = ((value / total) * 100).toFixed(1);
                                return `${context.label}: Rp ${value.toLocaleString('id-ID')} (${percentage}%)`;
                            }
                        }
                    }
                }
            }
        });
    }

    updateCashflowChart(dailyFlow) {
        const ctx = document.getElementById('cashflowChart').getContext('2d');
        
        if (this.charts.cashflow) {
            this.charts.cashflow.destroy();
        }

        if (!dailyFlow.length) {
            ctx.font = "16px Arial";
            ctx.fillStyle = "#6B7280";
            ctx.textAlign = "center";
            ctx.fillText("No cashflow data", ctx.canvas.width/2, ctx.canvas.height/2);
            return;
        }

        this.charts.cashflow = new Chart(ctx, {
            type: 'line',
            data: {
                labels: dailyFlow.map(item => new Date(item.date).toLocaleDateString('id-ID')),
                datasets: [{
                    label: 'Income',
                    data: dailyFlow.map(item => item.income || 0),
                    borderColor: '#10B981',
                    backgroundColor: 'rgba(16, 185, 129, 0.1)',
                    fill: true,
                    tension: 0.4
                }, {
                    label: 'Expenses',
                    data: dailyFlow.map(item => item.expenses || 0),
                    borderColor: '#EF4444',
                    backgroundColor: 'rgba(239, 68, 68, 0.1)',
                    fill: true,
                    tension: 0.4
                }]
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                interaction: {
                    intersect: false,
                    mode: 'index'
                },
                plugins: {
                    legend: {
                        position: 'top',
                        labels: {
                            usePointStyle: true,
                            padding: 15
                        }
                    },
                    tooltip: {
                        callbacks: {
                            label: function(context) {
                                return `${context.dataset.label}: Rp ${context.raw.toLocaleString('id-ID')}`;
                            }
                        }
                    }
                },
                scales: {
                    y: {
                        beginAtZero: true,
                        ticks: {
                            callback: function(value) {
                                return 'Rp ' + value.toLocaleString('id-ID');
                            }
                        }
                    }
                }
            }
        });
    }

    updateBudgetStatus(budgetData) {
        const budgetSection = document.getElementById('budgetSection');
        const currentMonth = document.getElementById('currentMonth');
        
        currentMonth.textContent = budgetData.month || new Date().toLocaleString('id-ID', { month: 'long', year: 'numeric' });

        if (!budgetData.budgets || !budgetData.budgets.length) {
            budgetSection.innerHTML = `
                <div class="text-center py-8 text-gray-500">
                    <i class="fas fa-chart-bar text-4xl mb-3 opacity-50"></i>
                    <p>No budgets set for this month</p>
                    <a href="/budgets" class="text-blue-600 hover:text-blue-800 text-sm font-medium mt-2 inline-block">
                        Set up your first budget <i class="fas fa-arrow-right ml-1"></i>
                    </a>
                </div>
            `;
            return;
        }

        let budgetHTML = `
            <div class="mb-4 p-4 bg-gray-50 rounded-lg">
                <div class="flex justify-between items-center mb-2">
                    <span class="font-medium">Overall Budget Status</span>
                    <span class="text-sm text-gray-600">${budgetData.overall_percentage || 0}% used</span>
                </div>
                <div class="w-full bg-gray-200 rounded-full h-2">
                    <div class="h-2 rounded-full transition-all duration-300 ${budgetData.overall_percentage > 100 ? 'bg-red-500' : budgetData.overall_percentage > 80 ? 'bg-yellow-500' : 'bg-green-500'}" 
                         style="width: ${Math.min(budgetData.overall_percentage || 0, 100)}%"></div>
                </div>
                <div class="flex justify-between text-sm text-gray-600 mt-1">
                    <span>Spent: Rp ${(budgetData.total_spent || 0).toLocaleString('id-ID')}</span>
                    <span>Budget: Rp ${(budgetData.total_budget || 0).toLocaleString('id-ID')}</span>
                </div>
            </div>
        `;

        if (budgetData.alerts && budgetData.alerts.length > 0) {
            budgetHTML += `
                <div class="mb-4 space-y-2">
                    ${budgetData.alerts.map(alert => `
                        <div class="flex items-center p-3 bg-red-50 border-l-4 border-red-400 rounded-r-lg">
                            <i class="fas fa-exclamation-triangle text-red-500 mr-3"></i>
                            <div class="flex-1">
                                <p class="text-sm font-medium text-red-800">${alert.message}</p>
                                ${alert.amount_over > 0 ? `<p class="text-xs text-red-600">Over budget by Rp ${alert.amount_over.toLocaleString('id-ID')}</p>` : ''}
                            </div>
                        </div>
                    `).join('')}
                </div>
            `;
        }

        budgetHTML += `
            <div class="space-y-3">
                ${budgetData.budgets.map(budget => {
                    const statusColors = {
                        'on_track': 'green',
                        'near_limit': 'yellow',
                        'over_budget': 'red'
                    };
                    const color = statusColors[budget.status] || 'gray';
                    
                    return `
                        <div class="border border-gray-200 rounded-lg p-4">
                            <div class="flex justify-between items-start mb-2">
                                <div>
                                    <h4 class="font-medium text-gray-900">${budget.category}</h4>
                                    <p class="text-sm text-gray-600">
                                        Rp ${budget.amount_spent.toLocaleString('id-ID')} / Rp ${budget.budget_limit.toLocaleString('id-ID')}
                                    </p>
                                </div>
                                <span class="px-2 py-1 text-xs font-medium rounded-full bg-${color}-100 text-${color}-800">
                                    ${budget.percentage_used}%
                                </span>
                            </div>
                            <div class="w-full bg-gray-200 rounded-full h-2">
                                <div class="h-2 rounded-full transition-all duration-300 bg-${color}-500" 
                                     style="width: ${Math.min(budget.percentage_used, 100)}%"></div>
                            </div>
                            <div class="flex justify-between text-xs text-gray-600 mt-1">
                                <span>Remaining: Rp ${Math.max(0, budget.remaining).toLocaleString('id-ID')}</span>
                                <span class="capitalize">${budget.status.replace('_', ' ')}</span>
                            </div>
                        </div>
                    `;
                }).join('')}
            </div>
        `;

        budgetSection.innerHTML = budgetHTML;
    }

    updateRecentTransactions(transactions) {
        const container = document.getElementById('recentTransactions');
        
        if (!transactions || !transactions.length) {
            container.innerHTML = `
                <div class="text-center py-8 text-gray-500">
                    <i class="fas fa-receipt text-4xl mb-3 opacity-50"></i>
                    <p>No recent transactions</p>
                    <button onclick="showAddTransactionModal()" class="text-blue-600 hover:text-blue-800 text-sm font-medium mt-2 inline-block">
                        Add your first transaction <i class="fas fa-plus ml-1"></i>
                    </button>
                </div>
            `;
            return;
        }

        const transactionHTML = transactions.map(transaction => {
            const isIncome = transaction.transaction_type === 'income';
            const amount = transaction.amount || 0;
            const date = new Date(transaction.timestamp).toLocaleDateString('id-ID', {
                month: 'short', day: 'numeric', hour: '2-digit', minute: '2-digit'
            });

            return `
                <div class="flex items-center justify-between p-4 border border-gray-200 rounded-lg hover:bg-gray-50 transition-colors duration-200">
                    <div class="flex items-center space-x-3">
                        <div class="p-2 rounded-full ${isIncome ? 'bg-green-100' : 'bg-red-100'}">
                            <i class="fas ${isIncome ? 'fa-arrow-up text-green-600' : 'fa-arrow-down text-red-600'}"></i>
                        </div>
                        <div>
                            <p class="font-medium text-gray-900">
                                ${transaction.merchant || 'Unknown Merchant'}
                            </p>
                            <p class="text-sm text-gray-600">
                                ${transaction.category?.name || 'Uncategorized'} • ${date}
                            </p>
                            ${transaction.description ? `<p class="text-xs text-gray-500 mt-1">${transaction.description}</p>` : ''}
                        </div>
                    </div>
                    <div class="text-right">
                        <p class="font-semibold ${isIncome ? 'text-green-600' : 'text-red-600'}">
                            ${isIncome ? '+' : '-'}Rp ${amount.toLocaleString('id-ID')}
                        </p>
                        <p class="text-xs text-gray-500">
                            ${transaction.account?.name || 'Unknown Account'}
                        </p>
                    </div>
                </div>
            `;
        }).join('');

        container.innerHTML = transactionHTML;
    }

    setupEventListeners() {
        // Refresh button
        document.getElementById('refreshBtn').addEventListener('click', () => {
            this.loadDashboardData(true);
            this.showNotification('Success', 'Dashboard refreshed', 'success');
        });

        // Add transaction form
        document.getElementById('addTransactionForm').addEventListener('submit', async (e) => {
            e.preventDefault();
            await this.handleAddTransaction(e);
        });
    }

    async handleAddTransaction(event) {
        const formData = new FormData(event.target);
        const transactionData = {
            amount: parseFloat(document.getElementById('amount').value),
            transaction_type: document.getElementById('transactionType').value,
            merchant: document.getElementById('merchant').value,
            description: document.getElementById('description').value,
            timestamp: new Date().toISOString(),
            account_id: 1 // Default account - should be made configurable
        };

        try {
            const response = await fetch('/api/transactions/', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(transactionData)
            });

            if (response.ok) {
                this.closeAddTransactionModal();
                this.loadDashboardData(false);
                this.showNotification('Success', 'Transaction added successfully', 'success');
                document.getElementById('addTransactionForm').reset();
            } else {
                throw new Error('Failed to add transaction');
            }
        } catch (error) {
            console.error('Error adding transaction:', error);
            this.showNotification('Error', 'Failed to add transaction', 'error');
        }
    }

    async syncToSheets() {
        try {
            const response = await fetch('/api/transactions/sync-to-sheets', {
                method: 'POST'
            });
            
            if (response.ok) {
                const result = await response.json();
                this.showNotification('Success', `Synced ${result.data.synced_count} transactions to Google Sheets`, 'success');
            } else {
                throw new Error('Sync failed');
            }
        } catch (error) {
            console.error('Error syncing to sheets:', error);
            this.showNotification('Error', 'Failed to sync to Google Sheets', 'error');
        }
    }

    async exportReport() {
        try {
            const currentMonth = new Date().toISOString().slice(0, 7); // YYYY-MM format
            const response = await fetch(`/api/reports/monthly-export?month=${currentMonth}`, {
                method: 'POST'
            });
            
            if (response.ok) {
                this.showNotification('Success', 'Monthly report exported to Google Sheets', 'success');
            } else {
                throw new Error('Export failed');
            }
        } catch (error) {
            console.error('Error exporting report:', error);
            this.showNotification('Error', 'Failed to export report', 'error');
        }
    }

    showAddTransactionModal() {
        document.getElementById('addTransactionModal').classList.remove('hidden');
    }

    closeAddTransactionModal() {
        document.getElementById('addTransactionModal').classList.add('hidden');
        document.getElementById('addTransactionForm').reset();
    }

    showLoadingState() {
        document.querySelectorAll('.loading-skeleton').forEach(el => {
            el.classList.add('pulse-animation');
            el.classList.add('bg-gray-200');
        });
    }

    hideLoadingState() {
        document.querySelectorAll('.loading-skeleton').forEach(el => {
            el.classList.remove('pulse-animation');
            el.classList.remove('bg-gray-200');
        });
    }

    showNotification(title, message, type = 'info') {
        const notification = document.getElementById('notification');
        const icon = document.getElementById('notificationIcon');
        const titleEl = document.getElementById('notificationTitle');
        const messageEl = document.getElementById('notificationMessage');

        // Set content
        titleEl.textContent = title;
        messageEl.textContent = message;

        // Set icon and colors based on type
        const types = {
            success: { icon: 'fa-check-circle', color: 'green' },
            error: { icon: 'fa-exclamation-circle', color: 'red' },
            warning: { icon: 'fa-exclamation-triangle', color: 'yellow' },
            info: { icon: 'fa-info-circle', color: 'blue' }
        };

        const typeConfig = types[type] || types.info;
        icon.className = `fas ${typeConfig.icon} text-${typeConfig.color}-500 mr-3`;
        
        // Update border color
        notification.firstElementChild.className = 
            notification.firstElementChild.className.replace(/border-\w+-500/, `border-${typeConfig.color}-500`);

        // Show notification
        notification.classList.remove('hidden');

        // Auto hide after 5 seconds
        setTimeout(() => {
            notification.classList.add('hidden');
        }, 5000);
    }

    updateLastUpdated() {
        document.getElementById('lastUpdated').textContent = 
            new Date().toLocaleString('id-ID', { 
                hour: '2-digit', 
                minute: '2-digit',
                second: '2-digit'
            });
    }
}

// Global functions for button handlers
function showAddTransactionModal() {
    window.dashboard.showAddTransactionModal();
}

function closeAddTransactionModal() {
    window.dashboard.closeAddTransactionModal();
}

function syncToSheets() {
    window.dashboard.syncToSheets();
}

function exportReport() {
    window.dashboard.exportReport();
}

// Initialize dashboard when DOM is loaded
document.addEventListener('DOMContentLoaded', () => {
    window.dashboard = new FinHelperDashboard();
});