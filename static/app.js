// Local cache for rates to enable instant client-side calculation
let cachedRates = {
    USD: 0,
    EUR: 0,
    GBP: 0,
    AUD: 0,
    JPY: 0,
    AED: 0,
    SAR: 0,
    INR: 0,
    CNY: 0,
    QAR: 0
};

// Formats number values with commas
function formatNumber(num) {
    return num.toString().replace(/\B(?=(\d{3})+(?!\n))/g, ",");
}

// Simple digit counter animation
function animateValue(id, start, end, duration) {
    const obj = document.getElementById(id);
    if (!obj) return;
    
    if (start === end) {
        obj.textContent = formatNumber(end);
        return;
    }
    
    let startTimestamp = null;
    const step = (timestamp) => {
        if (!startTimestamp) startTimestamp = timestamp;
        const progress = Math.min((timestamp - startTimestamp) / duration, 1);
        obj.textContent = formatNumber(Math.floor(progress * (end - start) + start));
        if (progress < 1) {
            window.requestAnimationFrame(step);
        }
    };
    window.requestAnimationFrame(step);
}

// Fetch dashboard data
async function fetchStats() {
    try {
        const response = await fetch('/api/stats');
        if (!response.ok) throw new Error('API down');
        
        const data = await response.json();
        
        // Update stats with nice animations
        const subCount = data.subscribers || 0;
        const activeSubCount = data.active_subscriptions || 0;
        const thresholdCount = data.active_thresholds || 0;
        
        const currentSubs = parseInt(document.getElementById('stats-subscribers').textContent) || 0;
        const currentActive = parseInt(document.getElementById('stats-subscriptions').textContent) || 0;
        const currentThresholds = parseInt(document.getElementById('stats-thresholds').textContent) || 0;
        
        animateValue('stats-subscribers', currentSubs, subCount, 800);
        animateValue('stats-subscriptions', currentActive, activeSubCount, 800);
        animateValue('stats-thresholds', currentThresholds, thresholdCount, 800);
        
        // Update exchange rates
        if (data.rates) {
            Object.keys(data.rates).forEach(cur => {
                const rate = data.rates[cur] || 0;
                cachedRates[cur] = rate;
                
                const valEl = document.getElementById(`val-${cur.toLowerCase()}`);
                if (valEl) {
                    valEl.innerHTML = `${rate.toFixed(2)} <span class="tag">LKR</span>`;
                }
            });
            // Re-trigger calculator logic
            calculateConversion();
        }
        
        // Update System Status indicators
        const statusTextEl = document.getElementById('system-status-text');
        const pulseEl = document.querySelector('.pulse-dot');
        
        if (data.system_status === 'online' && data.db_status === 'connected') {
            statusTextEl.textContent = 'SYSTEM ACTIVE';
            pulseEl.style.backgroundColor = 'var(--accent-green)';
            pulseEl.style.boxShadow = '0 0 10px var(--accent-green)';
        } else if (data.db_status === 'error') {
            statusTextEl.textContent = 'DATABASE ERROR';
            pulseEl.style.backgroundColor = 'var(--accent-pink)';
            pulseEl.style.boxShadow = '0 0 10px var(--accent-pink)';
        } else {
            statusTextEl.textContent = 'SYSTEM MAINTENANCE';
            pulseEl.style.backgroundColor = 'var(--accent-purple)';
            pulseEl.style.boxShadow = '0 0 10px var(--accent-purple)';
        }
        
    } catch (error) {
        console.error('Error fetching dashboard stats:', error);
        
        // Display offline/error states
        const statusTextEl = document.getElementById('system-status-text');
        const pulseEl = document.querySelector('.pulse-dot');
        if (statusTextEl && pulseEl) {
            statusTextEl.textContent = 'SYSTEM OFFLINE';
            pulseEl.style.backgroundColor = 'var(--accent-pink)';
            pulseEl.style.boxShadow = '0 0 10px var(--accent-pink)';
        }
    }
}

// Handle currency conversion calculations
function calculateConversion() {
    const amountInput = document.getElementById('convert-amount');
    const currencySelect = document.getElementById('convert-from');
    const resultOutput = document.getElementById('conversion-output');
    
    if (!amountInput || !currencySelect || !resultOutput) return;
    
    const amount = parseFloat(amountInput.value) || 0;
    const fromCur = currencySelect.value;
    const rate = cachedRates[fromCur] || 0;
    
    // Apply visual prefixes
    const prefixEl = document.querySelector('.converter-form .prefix');
    if (prefixEl) {
        if (fromCur === 'USD' || fromCur === 'AUD') {
            prefixEl.textContent = '$';
        } else if (fromCur === 'GBP') {
            prefixEl.textContent = '£';
        } else if (fromCur === 'EUR') {
            prefixEl.textContent = '€';
        } else if (fromCur === 'JPY' || fromCur === 'CNY') {
            prefixEl.textContent = '¥';
        } else if (fromCur === 'INR') {
            prefixEl.textContent = '₹';
        } else if (fromCur === 'AED') {
            prefixEl.textContent = 'DH';
        } else if (fromCur === 'SAR') {
            prefixEl.textContent = 'SR';
        } else if (fromCur === 'QAR') {
            prefixEl.textContent = 'QR';
        } else {
            prefixEl.textContent = '';
        }
    }

    if (amount <= 0 || rate === 0) {
        resultOutput.innerHTML = `0.00 <span class="currency-tag">LKR</span>`;
        return;
    }
    
    const total = amount * rate;
    resultOutput.innerHTML = `${total.toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })} <span class="currency-tag">LKR</span>`;
}

// Chart.js Trends Visualization Logic
let trendsChart = null;

const currencyColors = {
    USD: { border: '#06B6D4', glow: 'rgba(6, 182, 212, 0.25)', fill: 'rgba(6, 182, 212, 0.05)' },
    EUR: { border: '#8B5CF6', glow: 'rgba(139, 92, 246, 0.25)', fill: 'rgba(139, 92, 246, 0.05)' },
    GBP: { border: '#EC4899', glow: 'rgba(236, 72, 153, 0.25)', fill: 'rgba(236, 72, 153, 0.05)' },
    AUD: { border: '#3B82F6', glow: 'rgba(59, 130, 246, 0.25)', fill: 'rgba(59, 130, 246, 0.05)' },
    JPY: { border: '#10B981', glow: 'rgba(16, 185, 129, 0.25)', fill: 'rgba(16, 185, 129, 0.05)' },
    AED: { border: '#F59E0B', glow: 'rgba(245, 158, 11, 0.25)', fill: 'rgba(245, 158, 11, 0.05)' },
    SAR: { border: '#14B8A6', glow: 'rgba(20, 184, 166, 0.25)', fill: 'rgba(20, 184, 166, 0.05)' },
    INR: { border: '#EF4444', glow: 'rgba(239, 68, 68, 0.25)', fill: 'rgba(239, 68, 68, 0.05)' },
    CNY: { border: '#F43F5E', glow: 'rgba(244, 63, 94, 0.25)', fill: 'rgba(244, 63, 94, 0.05)' },
    QAR: { border: '#6366F1', glow: 'rgba(99, 102, 241, 0.25)', fill: 'rgba(99, 102, 241, 0.05)' }
};

async function updateTrendsChart() {
    const currencySelect = document.getElementById('chart-currency-select');
    const daysSelect = document.getElementById('chart-days-select');
    const canvas = document.getElementById('trends-chart');
    if (!currencySelect || !daysSelect || !canvas) return;
    
    const currency = currencySelect.value;
    const days = parseInt(daysSelect.value) || 30;
    
    try {
        const response = await fetch(`/api/history?days=${days}`);
        if (!response.ok) throw new Error('API down');
        
        const historyData = await response.json();
        const records = historyData[currency] || [];
        
        const labels = records.map(r => r.date);
        const dataPoints = records.map(r => r.rate);
        
        const theme = currencyColors[currency] || currencyColors.USD;
        
        const ctx = canvas.getContext('2d');
        
        // Dynamic gradient area under line
        const gradient = ctx.createLinearGradient(0, 0, 0, 300);
        gradient.addColorStop(0, theme.glow);
        gradient.addColorStop(1, 'rgba(11, 15, 25, 0)');
        
        const chartData = {
            labels: labels,
            datasets: [{
                label: `${currency} to LKR`,
                data: dataPoints,
                borderColor: theme.border,
                borderWidth: 3,
                backgroundColor: gradient,
                fill: true,
                tension: 0.4,
                pointBackgroundColor: theme.border,
                pointBorderColor: '#FFFFFF',
                pointBorderWidth: 1.5,
                pointRadius: labels.length > 15 ? 2.5 : 4,
                pointHoverRadius: 6,
                pointHoverBackgroundColor: theme.border,
                pointHoverBorderColor: '#FFFFFF',
                pointHoverBorderWidth: 2
            }]
        };
        
        if (trendsChart) {
            trendsChart.data = chartData;
            trendsChart.update();
        } else {
            trendsChart = new Chart(ctx, {
                type: 'line',
                data: chartData,
                options: {
                    responsive: true,
                    maintainAspectRatio: false,
                    plugins: {
                        legend: { display: false },
                        tooltip: {
                            backgroundColor: 'rgba(17, 24, 39, 0.95)',
                            titleColor: '#F3F4F6',
                            bodyColor: '#F3F4F6',
                            borderColor: 'rgba(255, 255, 255, 0.12)',
                            borderWidth: 1,
                            padding: 12,
                            displayColors: false,
                            callbacks: {
                                label: function(context) {
                                    return `1 ${currency} = ${context.parsed.y.toFixed(2)} LKR`;
                                }
                            }
                        }
                    },
                    scales: {
                        x: {
                            grid: { color: 'rgba(255, 255, 255, 0.03)' },
                            ticks: {
                                color: '#9CA3AF',
                                font: { family: 'Plus Jakarta Sans', size: 11 },
                                maxRotation: 45,
                                autoSkip: true,
                                maxTicksLimit: 10
                            }
                        },
                        y: {
                            grid: { color: 'rgba(255, 255, 255, 0.03)' },
                            ticks: {
                                color: '#9CA3AF',
                                font: { family: 'Plus Jakarta Sans', size: 11 },
                                callback: function(value) {
                                    return value.toFixed(1) + ' LKR';
                                }
                            }
                        }
                    }
                }
            });
        }
    } catch (error) {
        console.error('Error drawing chart:', error);
    }
}

// Event Listeners initialization
document.addEventListener('DOMContentLoaded', () => {
    // Initial fetch
    fetchStats();
    
    // Setup inputs
    const amountInput = document.getElementById('convert-amount');
    const currencySelect = document.getElementById('convert-from');
    
    if (amountInput) amountInput.addEventListener('input', calculateConversion);
    if (currencySelect) currencySelect.addEventListener('change', calculateConversion);
    
    // Setup Chart dynamic bindings
    updateTrendsChart();
    
    const chartCurrency = document.getElementById('chart-currency-select');
    const chartDays = document.getElementById('chart-days-select');
    if (chartCurrency) chartCurrency.addEventListener('change', updateTrendsChart);
    if (chartDays) chartDays.addEventListener('change', updateTrendsChart);
    
    // Auto-update dashboard metrics and rates every 60 seconds
    setInterval(fetchStats, 60000);
});
