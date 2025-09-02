// Dashboard functionality
document.addEventListener('DOMContentLoaded', function() {
    const searchInput = document.getElementById('searchInput');
    const serviceItems = document.querySelectorAll('.service-item');
    
    // Search functionality
    searchInput.addEventListener('input', function() {
        const searchTerm = this.value.toLowerCase();
        
        serviceItems.forEach(item => {
            const serviceName = item.dataset.serviceName;
            if (serviceName.includes(searchTerm)) {
                item.style.display = 'block';
            } else {
                item.style.display = 'none';
            }
        });
    });
    
    // Update status counts
    updateStatusCounts();
    
    // Refresh data every 30 seconds
    setInterval(refreshDashboard, 30000);
});

function updateStatusCounts() {
    let upCount = 0;
    let issuesCount = 0;
    let downCount = 0;
    
    document.querySelectorAll('.status-indicator').forEach(indicator => {
        if (indicator.classList.contains('status-up')) {
            upCount++;
        } else if (indicator.classList.contains('status-issues')) {
            issuesCount++;
        } else if (indicator.classList.contains('status-down')) {
            downCount++;
        }
    });
    
    document.getElementById('upCount').textContent = upCount;
    document.getElementById('issuesCount').textContent = issuesCount;
    document.getElementById('downCount').textContent = downCount;
}

async function refreshDashboard() {
    try {
        const response = await fetch('/api/services');
        const services = await response.json();
        
        services.forEach(service => {
            const serviceCard = document.querySelector(`[data-service-id="${service.id}"]`);
            if (serviceCard) {
                const indicator = serviceCard.querySelector('.status-indicator');
                const reportsCount = serviceCard.querySelector('.card-text');
                
                // Update status indicator
                indicator.className = `status-indicator status-${service.status}`;
                
                // Update reports count
                reportsCount.textContent = `${service.recent_reports} reports in last 24h`;
            }
        });
        
        updateStatusCounts();
    } catch (error) {
        console.error('Error refreshing dashboard:', error);
    }
}

// Real-time updates via Socket.IO
socket.on('new_report', function(data) {
    // Update the specific service card
    const serviceCard = document.querySelector(`[data-service-id="${data.service_id}"]`);
    if (serviceCard) {
        const indicator = serviceCard.querySelector('.status-indicator');
        indicator.className = `status-indicator status-${data.new_status}`;
        
        // Update counts
        updateStatusCounts();
    }
});
