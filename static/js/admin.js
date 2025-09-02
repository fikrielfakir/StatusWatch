// Admin dashboard functionality
document.addEventListener('DOMContentLoaded', function() {
    loadRecentReports();
    
    // Set up form handlers
    document.getElementById('addServiceForm').addEventListener('submit', handleAddService);
    document.getElementById('editServiceForm').addEventListener('submit', handleEditService);
});

async function handleAddService(e) {
    e.preventDefault();
    
    const formData = {
        name: document.getElementById('serviceName').value,
        url: document.getElementById('serviceUrl').value
    };
    
    try {
        const response = await fetch('/api/services', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify(formData)
        });
        
        const result = await response.json();
        
        if (response.ok) {
            // Close modal
            const modal = bootstrap.Modal.getInstance(document.getElementById('addServiceModal'));
            modal.hide();
            
            // Reset form
            document.getElementById('addServiceForm').reset();
            
            // Show success message
            showNotification('Service added successfully!', 'success');
            
            // Refresh page to show new service
            setTimeout(() => {
                window.location.reload();
            }, 1000);
            
        } else {
            showNotification(result.error || 'Error adding service', 'danger');
        }
        
    } catch (error) {
        console.error('Error adding service:', error);
        showNotification('Error adding service', 'danger');
    }
}

async function handleEditService(e) {
    e.preventDefault();
    
    const serviceId = document.getElementById('editServiceId').value;
    const formData = {
        name: document.getElementById('editServiceName').value,
        url: document.getElementById('editServiceUrl').value
    };
    
    try {
        const response = await fetch(`/api/services/${serviceId}`, {
            method: 'PUT',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify(formData)
        });
        
        const result = await response.json();
        
        if (response.ok) {
            // Close modal
            const modal = bootstrap.Modal.getInstance(document.getElementById('editServiceModal'));
            modal.hide();
            
            // Show success message
            showNotification('Service updated successfully!', 'success');
            
            // Refresh page
            setTimeout(() => {
                window.location.reload();
            }, 1000);
            
        } else {
            showNotification(result.error || 'Error updating service', 'danger');
        }
        
    } catch (error) {
        console.error('Error updating service:', error);
        showNotification('Error updating service', 'danger');
    }
}

function editService(id, name, url) {
    document.getElementById('editServiceId').value = id;
    document.getElementById('editServiceName').value = name;
    document.getElementById('editServiceUrl').value = url;
    
    const modal = new bootstrap.Modal(document.getElementById('editServiceModal'));
    modal.show();
}

async function deleteService(id, name) {
    if (!confirm(`Are you sure you want to delete "${name}"? This will also delete all associated reports.`)) {
        return;
    }
    
    try {
        const response = await fetch(`/api/services/${id}`, {
            method: 'DELETE'
        });
        
        if (response.ok) {
            showNotification('Service deleted successfully!', 'success');
            
            // Remove the row from the table
            const row = document.querySelector(`tr[data-service-id="${id}"]`);
            if (row) {
                row.remove();
            }
            
        } else {
            const result = await response.json();
            showNotification(result.error || 'Error deleting service', 'danger');
        }
        
    } catch (error) {
        console.error('Error deleting service:', error);
        showNotification('Error deleting service', 'danger');
    }
}

async function loadRecentReports() {
    try {
        const response = await fetch('/api/reports/all?hours=24');
        const reports = await response.json();
        
        const container = document.getElementById('recentReports');
        
        if (reports.length === 0) {
            container.innerHTML = '<p class="text-muted">No reports in the last 24 hours</p>';
            return;
        }
        
        container.innerHTML = reports.slice(0, 20).map(report => `
            <div class="border-bottom pb-2 mb-2">
                <div class="d-flex justify-content-between align-items-start">
                    <div>
                        <strong>${report.service_name}</strong>
                        <br>
                        <small class="text-muted">${new Date(report.timestamp).toLocaleString()}</small>
                        ${report.location ? `<br><small class="text-muted">📍 ${report.location}</small>` : ''}
                    </div>
                    <a href="/service/${report.service_id}" class="btn btn-outline-primary btn-sm">
                        <i data-feather="eye"></i>
                    </a>
                </div>
                <p class="mb-0 small mt-1">${report.description || 'No description provided'}</p>
            </div>
        `).join('');
        
        // Re-initialize feather icons
        feather.replace();
        
    } catch (error) {
        console.error('Error loading recent reports:', error);
        document.getElementById('recentReports').innerHTML = 
            '<p class="text-danger">Error loading recent reports</p>';
    }
}

// Real-time updates via Socket.IO
socket.on('new_report', function(data) {
    // Refresh recent reports
    loadRecentReports();
    
    // Update service status in table
    const row = document.querySelector(`tr[data-service-id="${data.service_id}"]`);
    if (row) {
        const indicator = row.querySelector('.status-indicator');
        const statusBadge = row.querySelector('td:nth-child(4) .badge');
        
        // Update status indicator
        indicator.className = `status-indicator status-${data.new_status}`;
        
        // Update status badge
        if (data.new_status === 'up') {
            statusBadge.className = 'badge bg-success';
            statusBadge.textContent = 'Operational';
        } else if (data.new_status === 'issues') {
            statusBadge.className = 'badge bg-warning';
            statusBadge.textContent = 'Issues';
        } else {
            statusBadge.className = 'badge bg-danger';
            statusBadge.textContent = 'Down';
        }
    }
});
