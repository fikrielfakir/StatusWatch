// Admin Dashboard JavaScript
class AdminDashboard {
    constructor() {
        this.currentTab = 'overview';
        this.currentPage = 1;
        this.servicesPerPage = 25;
        this.services = [];
        this.charts = {};
        this.init();
    }

    init() {
        this.setupTabNavigation();
        this.setupEventListeners();
        this.loadOverviewData();
        this.initializeCharts();
        this.startRealTimeUpdates();
    }

    setupTabNavigation() {
        document.querySelectorAll('[data-tab]').forEach(link => {
            link.addEventListener('click', (e) => {
                e.preventDefault();
                const tab = e.target.closest('[data-tab]').dataset.tab;
                this.switchTab(tab);
            });
        });
    }

    switchTab(tab) {
        // Hide all tabs
        document.querySelectorAll('.tab-content').forEach(content => {
            content.style.display = 'none';
            content.classList.remove('active');
        });

        // Remove active class from all nav links
        document.querySelectorAll('.nav-link').forEach(link => {
            link.classList.remove('active');
        });

        // Show selected tab
        const tabContent = document.getElementById(`${tab}-tab`);
        if (tabContent) {
            tabContent.style.display = 'block';
            tabContent.classList.add('active');
        }

        // Add active class to selected nav link
        document.querySelector(`[data-tab="${tab}"]`).classList.add('active');

        this.currentTab = tab;

        // Load tab-specific data
        switch (tab) {
            case 'services':
                this.loadServices();
                break;
            case 'monitoring':
                this.loadMonitoringData();
                break;
            case 'reports':
                this.loadReportsData();
                break;
        }
    }

    setupEventListeners() {
        // Search functionality
        const searchInput = document.getElementById('service-search');
        if (searchInput) {
            searchInput.addEventListener('input', this.debounce(() => {
                this.filterServices();
            }, 300));
        }

        // Filter dropdowns
        ['status-filter', 'category-filter'].forEach(filterId => {
            const filter = document.getElementById(filterId);
            if (filter) {
                filter.addEventListener('change', () => this.filterServices());
            }
        });

        // Per page selector
        const perPageSelect = document.getElementById('per-page');
        if (perPageSelect) {
            perPageSelect.addEventListener('change', (e) => {
                this.servicesPerPage = parseInt(e.target.value);
                this.currentPage = 1;
                this.loadServices();
            });
        }

        // Select all checkbox
        const selectAllCheckbox = document.getElementById('select-all');
        if (selectAllCheckbox) {
            selectAllCheckbox.addEventListener('change', (e) => {
                this.toggleSelectAll(e.target.checked);
            });
        }
    }

    async loadOverviewData() {
        try {
            const response = await fetch('/api/analytics/overview');
            const data = await response.json();
            
            this.updateOverviewStats(data);
            this.updateStatusChart(data);
        } catch (error) {
            console.error('Error loading overview data:', error);
        }
    }

    updateOverviewStats(data) {
        const stats = data.summary || {};
        
        document.getElementById('total-services').textContent = stats.total_services || 0;
        document.getElementById('services-up').textContent = stats.status_breakdown?.up || 0;
        document.getElementById('services-issues').textContent = stats.status_breakdown?.issues || 0;
        document.getElementById('services-down').textContent = stats.status_breakdown?.down || 0;
    }

    async loadServices() {
        try {
            const params = new URLSearchParams({
                page: this.currentPage,
                per_page: this.servicesPerPage,
                search: document.getElementById('service-search')?.value || '',
                status: document.getElementById('status-filter')?.value || '',
                category: document.getElementById('category-filter')?.value || ''
            });

            const response = await fetch(`/api/services?${params}`);
            const data = await response.json();
            
            this.services = data.services || [];
            this.renderServicesTable();
            this.renderPagination(data.pagination);
        } catch (error) {
            console.error('Error loading services:', error);
        }
    }

    renderServicesTable() {
        const tbody = document.getElementById('services-table-body');
        if (!tbody) return;

        tbody.innerHTML = this.services.map(service => `
            <tr>
                <td><input type="checkbox" class="service-checkbox" value="${service.id}"></td>
                <td>
                    <div class="d-flex align-items-center">
                        ${service.icon_path ? 
                            `<img src="/static/${service.icon_path}" alt="${service.name}" width="24" height="24" class="mr-2">` :
                            '<i data-feather="globe" class="mr-2"></i>'
                        }
                        <div>
                            <strong>${service.name}</strong>
                            <br><small class="text-muted">${service.url}</small>
                        </div>
                    </div>
                </td>
                <td>
                    <span class="status-badge status-${service.status}">
                        ${service.status.toUpperCase()}
                    </span>
                </td>
                <td>
                    <span class="badge badge-secondary">${this.getServiceCategory(service)}</span>
                </td>
                <td>
                    <small>${service.last_checked ? new Date(service.last_checked).toLocaleString() : 'Never'}</small>
                </td>
                <td>
                    <span class="text-${service.response_time > 1000 ? 'danger' : service.response_time > 500 ? 'warning' : 'success'}">
                        ${service.response_time || 0}ms
                    </span>
                </td>
                <td>
                    <span class="badge badge-${service.recent_reports > 10 ? 'danger' : service.recent_reports > 0 ? 'warning' : 'success'}">
                        ${service.recent_reports || 0}
                    </span>
                </td>
                <td>
                    <div class="btn-group btn-group-sm">
                        <button class="btn btn-outline-primary" onclick="adminDashboard.editService(${service.id})" title="Edit">
                            <i data-feather="edit-2"></i>
                        </button>
                        <button class="btn btn-outline-success" onclick="adminDashboard.checkService(${service.id})" title="Check Now">
                            <i data-feather="refresh-cw"></i>
                        </button>
                        <button class="btn btn-outline-danger" onclick="adminDashboard.deleteService(${service.id})" title="Delete">
                            <i data-feather="trash-2"></i>
                        </button>
                    </div>
                </td>
            </tr>
        `).join('');

        // Re-initialize feather icons
        if (typeof feather !== 'undefined') {
            feather.replace();
        }
    }

    getServiceCategory(service) {
        // Determine category based on service name or URL
        const name = service.name.toLowerCase();
        if (['facebook', 'twitter', 'instagram', 'linkedin', 'tiktok', 'snapchat', 'discord'].some(social => name.includes(social))) {
            return 'Social Media';
        } else if (['gmail', 'outlook', 'yahoo'].some(email => name.includes(email))) {
            return 'Email';
        } else if (['aws', 'azure', 'google cloud', 'cloudflare'].some(cloud => name.includes(cloud))) {
            return 'Cloud';
        } else if (['steam', 'epic', 'xbox', 'playstation'].some(gaming => name.includes(gaming))) {
            return 'Gaming';
        }
        return 'Other';
    }

    renderPagination(pagination) {
        const paginationContainer = document.getElementById('services-pagination');
        if (!paginationContainer || !pagination) return;

        const totalPages = pagination.pages;
        const currentPage = pagination.page;

        let paginationHtml = '<nav><ul class="pagination pagination-sm mb-0">';

        // Previous button
        if (pagination.has_prev) {
            paginationHtml += `<li class="page-item"><a class="page-link" href="#" onclick="adminDashboard.changePage(${currentPage - 1})" data-page="${currentPage - 1}">Previous</a></li>`;
        } else {
            paginationHtml += '<li class="page-item disabled"><span class="page-link">Previous</span></li>';
        }

        // Page numbers
        const startPage = Math.max(1, currentPage - 2);
        const endPage = Math.min(totalPages, currentPage + 2);

        for (let i = startPage; i <= endPage; i++) {
            if (i === currentPage) {
                paginationHtml += `<li class="page-item active"><span class="page-link">${i}</span></li>`;
            } else {
                paginationHtml += `<li class="page-item"><a class="page-link" href="#" onclick="adminDashboard.changePage(${i})" data-page="${i}">${i}</a></li>`;
            }
        }

        // Next button
        if (pagination.has_next) {
            paginationHtml += `<li class="page-item"><a class="page-link" href="#" onclick="adminDashboard.changePage(${currentPage + 1})" data-page="${currentPage + 1}">Next</a></li>`;
        } else {
            paginationHtml += '<li class="page-item disabled"><span class="page-link">Next</span></li>';
        }

        paginationHtml += '</ul></nav>';
        paginationContainer.innerHTML = paginationHtml;
    }

    changePage(page) {
        this.currentPage = page;
        this.loadServices();
    }

    filterServices() {
        this.currentPage = 1;
        this.loadServices();
    }

    resetFilters() {
        document.getElementById('service-search').value = '';
        document.getElementById('status-filter').value = '';
        document.getElementById('category-filter').value = '';
        this.filterServices();
    }

    toggleSelectAll(checked) {
        document.querySelectorAll('.service-checkbox').forEach(checkbox => {
            checkbox.checked = checked;
        });
    }

    getSelectedServices() {
        return Array.from(document.querySelectorAll('.service-checkbox:checked')).map(cb => cb.value);
    }

    async bulkAction(action) {
        const selectedServices = this.getSelectedServices();
        if (selectedServices.length === 0) {
            alert('Please select at least one service.');
            return;
        }

        if (action === 'delete') {
            if (!confirm(`Are you sure you want to delete ${selectedServices.length} selected services?`)) {
                return;
            }
        }

        try {
            const response = await fetch('/api/services/bulk', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify({
                    action: action,
                    service_ids: selectedServices
                })
            });

            if (response.ok) {
                this.loadServices();
                this.showNotification(`Bulk ${action} completed successfully.`, 'success');
            } else {
                this.showNotification(`Bulk ${action} failed.`, 'error');
            }
        } catch (error) {
            console.error('Bulk action error:', error);
            this.showNotification('An error occurred during bulk action.', 'error');
        }
    }

    async editService(serviceId) {
        // Implementation for editing a service
        console.log('Edit service:', serviceId);
    }

    async checkService(serviceId) {
        try {
            const response = await fetch(`/api/services/${serviceId}/check`, {
                method: 'POST'
            });

            if (response.ok) {
                this.showNotification('Service check initiated.', 'success');
                // Refresh the services table after a delay
                setTimeout(() => this.loadServices(), 2000);
            }
        } catch (error) {
            console.error('Service check error:', error);
        }
    }

    async deleteService(serviceId) {
        if (!confirm('Are you sure you want to delete this service?')) {
            return;
        }

        try {
            const response = await fetch(`/api/services/${serviceId}`, {
                method: 'DELETE'
            });

            if (response.ok) {
                this.loadServices();
                this.showNotification('Service deleted successfully.', 'success');
            }
        } catch (error) {
            console.error('Delete service error:', error);
        }
    }

    initializeCharts() {
        // Status Chart
        const statusCtx = document.getElementById('statusChart');
        if (statusCtx) {
            this.charts.status = new Chart(statusCtx, {
                type: 'line',
                data: {
                    labels: [],
                    datasets: [{
                        label: 'Services Up',
                        data: [],
                        borderColor: '#28a745',
                        backgroundColor: 'rgba(40, 167, 69, 0.1)',
                        tension: 0.4
                    }, {
                        label: 'Services Down',
                        data: [],
                        borderColor: '#dc3545',
                        backgroundColor: 'rgba(220, 53, 69, 0.1)',
                        tension: 0.4
                    }]
                },
                options: {
                    responsive: true,
                    maintainAspectRatio: false,
                    scales: {
                        y: {
                            beginAtZero: true
                        }
                    }
                }
            });
        }

        // Response Time Chart
        const responseCtx = document.getElementById('responseTimeChart');
        if (responseCtx) {
            this.charts.responseTime = new Chart(responseCtx, {
                type: 'bar',
                data: {
                    labels: [],
                    datasets: [{
                        label: 'Response Time (ms)',
                        data: [],
                        backgroundColor: 'rgba(54, 162, 235, 0.6)',
                        borderColor: 'rgba(54, 162, 235, 1)',
                        borderWidth: 1
                    }]
                },
                options: {
                    responsive: true,
                    maintainAspectRatio: false,
                    scales: {
                        y: {
                            beginAtZero: true
                        }
                    }
                }
            });
        }
    }

    updateStatusChart(data) {
        if (!this.charts.status) return;

        // Add sample data for demo
        const now = new Date();
        const labels = [];
        const upData = [];
        const downData = [];

        for (let i = 23; i >= 0; i--) {
            const time = new Date(now - i * 60 * 60 * 1000);
            labels.push(time.getHours() + ':00');
            upData.push(Math.floor(Math.random() * 20) + 180); // Random data for demo
            downData.push(Math.floor(Math.random() * 5));
        }

        this.charts.status.data.labels = labels;
        this.charts.status.data.datasets[0].data = upData;
        this.charts.status.data.datasets[1].data = downData;
        this.charts.status.update();
    }

    async loadMonitoringData() {
        // Load real-time monitoring data
        console.log('Loading monitoring data...');
    }

    async loadReportsData() {
        // Load reports and analytics data
        console.log('Loading reports data...');
    }

    startRealTimeUpdates() {
        // Update data every 30 seconds
        setInterval(() => {
            if (this.currentTab === 'overview') {
                this.loadOverviewData();
            } else if (this.currentTab === 'monitoring') {
                this.loadMonitoringData();
            }
        }, 30000);
    }

    showNotification(message, type = 'info') {
        // Create a simple notification
        const notification = document.createElement('div');
        notification.className = `alert alert-${type === 'error' ? 'danger' : type} alert-dismissible fade show`;
        notification.style.position = 'fixed';
        notification.style.top = '20px';
        notification.style.right = '20px';
        notification.style.zIndex = '9999';
        notification.innerHTML = `
            ${message}
            <button type="button" class="close" onclick="this.parentElement.remove()">
                <span>&times;</span>
            </button>
        `;
        
        document.body.appendChild(notification);
        
        // Auto-remove after 5 seconds
        setTimeout(() => {
            if (notification.parentElement) {
                notification.remove();
            }
        }, 5000);
    }

    debounce(func, wait) {
        let timeout;
        return function executedFunction(...args) {
            const later = () => {
                clearTimeout(timeout);
                func(...args);
            };
            clearTimeout(timeout);
            timeout = setTimeout(later, wait);
        };
    }
}

// Global functions for onclick handlers
function refreshData() {
    adminDashboard.loadOverviewData();
    adminDashboard.loadServices();
}

function addNewService() {
    $('#addServiceModal').modal('show');
}

function importServices() {
    // Implementation for importing services
    console.log('Import services');
}

function filterServices() {
    adminDashboard.filterServices();
}

function resetFilters() {
    adminDashboard.resetFilters();
}

function bulkAction(action) {
    adminDashboard.bulkAction(action);
}

function saveNewService() {
    const form = document.getElementById('add-service-form');
    const formData = new FormData(form);
    
    fetch('/api/services', {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json',
        },
        body: JSON.stringify(Object.fromEntries(formData))
    })
    .then(response => response.json())
    .then(data => {
        $('#addServiceModal').modal('hide');
        adminDashboard.loadServices();
        adminDashboard.showNotification('Service added successfully!', 'success');
    })
    .catch(error => {
        console.error('Error adding service:', error);
        adminDashboard.showNotification('Error adding service.', 'error');
    });
}

function addCategory() {
    const name = prompt('Enter category name:');
    if (name) {
        // Implementation for adding category
        console.log('Add category:', name);
    }
}

// Initialize dashboard when DOM is loaded
document.addEventListener('DOMContentLoaded', function() {
    window.adminDashboard = new AdminDashboard();
});