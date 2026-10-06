/**
 * ServiceDesk Core UI & Utility Script
 */

(function () {
    'use strict';

    // 1. Theme Management
    const THEME_KEY = 'servicedesk_theme';

    function initTheme() {
        const savedTheme = localStorage.getItem(THEME_KEY) || 'light';
        applyTheme(savedTheme);

        document.querySelectorAll('[data-set-theme]').forEach(el => {
            el.addEventListener('click', (e) => {
                e.preventDefault();
                const theme = el.getAttribute('data-set-theme');
                applyTheme(theme);
            });
        });
    }

    function applyTheme(theme) {
        document.documentElement.setAttribute('data-theme', theme);
        localStorage.setItem(THEME_KEY, theme);

        const currentLabel = document.getElementById('current-theme-label');
        if (currentLabel) {
            const icon = theme === 'dark' ? 'bi-moon-stars-fill' : 'bi-sun-fill';
            currentLabel.innerHTML = `<i class="bi ${icon}"></i> <span class="d-none d-md-inline text-capitalize">${theme}</span>`;
        }

        document.querySelectorAll('[data-set-theme]').forEach(el => {
            el.classList.toggle('active', el.getAttribute('data-set-theme') === theme);
        });
    }

    // 2. CSRF Token Helper
    function getCSRFToken() {
        const meta = document.querySelector('meta[name="csrf-token"]');
        return meta ? meta.getAttribute('content') : '';
    }

    // 3. Toast Notifications
    function showToast(message, type = 'success') {
        let container = document.getElementById('toast-container');
        if (!container) {
            container = document.createElement('div');
            container.id = 'toast-container';
            document.body.appendChild(container);
        }

        const toast = document.createElement('div');
        const bgClass = type === 'success' ? 'bg-success text-white' : type === 'danger' ? 'bg-danger text-white' : 'bg-primary text-white';
        toast.className = `toast align-items-center ${bgClass} border-0 show shadow`;
        toast.setAttribute('role', 'alert');
        toast.setAttribute('aria-live', 'assertive');
        toast.setAttribute('aria-atomic', 'true');

        toast.innerHTML = `
            <div class="d-flex">
                <div class="toast-body">
                    ${message}
                </div>
                <button type="button" class="btn-close btn-close-white me-2 m-auto" data-bs-dismiss="toast" aria-label="Close"></button>
            </div>
        `;

        container.appendChild(toast);
        setTimeout(() => {
            toast.classList.remove('show');
            setTimeout(() => toast.remove(), 250);
        }, 3500);

        toast.querySelector('.btn-close').addEventListener('click', () => toast.remove());
    }

    // 4. Client-side Table Filter
    function setupTableFilter(inputId, tableId) {
        const input = document.getElementById(inputId);
        const table = document.getElementById(tableId);
        if (!input || !table) return;

        input.addEventListener('keyup', function () {
            const query = this.value.toLowerCase().trim();
            const rows = table.querySelectorAll('tbody tr');
            rows.forEach(row => {
                const text = row.textContent.toLowerCase();
                row.style.display = text.includes(query) ? '' : 'none';
            });
        });
    }

    // 5. CSV Export Helper
    function exportTableToCSV(tableId, filename = 'report.csv') {
        const table = document.getElementById(tableId);
        if (!table) return;

        let csv = [];
        const rows = table.querySelectorAll('tr');

        rows.forEach(row => {
            if (row.style.display === 'none') return;
            const cols = row.querySelectorAll('th, td');
            let rowData = [];
            cols.forEach(col => {
                let cellText = col.innerText.replace(/"/g, '""').trim();
                cellText = cellText.replace(/\r?\n|\r/g, ' ');
                rowData.push(`"${cellText}"`);
            });
            if (rowData.length > 0) csv.push(rowData.join(','));
        });

        const csvString = csv.join('\n');
        const blob = new Blob([csvString], { type: 'text/csv;charset=utf-8;' });
        const link = document.createElement('a');
        link.href = URL.createObjectURL(blob);
        link.setAttribute('download', filename);
        document.body.appendChild(link);
        link.click();
        document.body.removeChild(link);
    }

    // Expose APIs globally
    window.ServiceDesk = {
        initTheme,
        applyTheme,
        getCSRFToken,
        showToast,
        setupTableFilter,
        exportTableToCSV
    };

    // Run theme immediately on DOM ready
    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', initTheme);
    } else {
        initTheme();
    }
})();
