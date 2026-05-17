// Local cache for rates to enable instant client-side calculation
let cachedRates = {
    USD: 0,
    EUR: 0,
    GBP: 0,
    AUD: 0,
    JPY: 0
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
        } else if (fromCur === 'JPY') {
            prefixEl.textContent = '¥';
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

// Event Listeners initialization
document.addEventListener('DOMContentLoaded', () => {
    // Initial fetch
    fetchStats();
    
    // Setup inputs
    const amountInput = document.getElementById('convert-amount');
    const currencySelect = document.getElementById('convert-from');
    
    if (amountInput) amountInput.addEventListener('input', calculateConversion);
    if (currencySelect) currencySelect.addEventListener('change', calculateConversion);
    
    // Auto-update dashboard metrics and rates every 60 seconds
    setInterval(fetchStats, 60000);
});
