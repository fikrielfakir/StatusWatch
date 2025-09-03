// Modern Dashboard functionality with smooth animations
document.addEventListener('DOMContentLoaded', function() {
    const searchInput = document.getElementById('searchInput');
    const serviceItems = document.querySelectorAll('.service-item');
    const serviceCards = document.querySelectorAll('.service-card');
    
    // Add smooth scroll behavior
    document.documentElement.style.scrollBehavior = 'smooth';
    
    // Progressive loading animation
    animateCardsIn();
    
    // Enhanced search functionality with debouncing
    let searchTimeout;
    if (searchInput) {
        searchInput.addEventListener('input', function() {
            clearTimeout(searchTimeout);
            searchTimeout = setTimeout(() => {
                performSearch(this.value.toLowerCase());
            }, 300);
        });
        
        // Add search placeholder animation
        animateSearchPlaceholder();
    }
    
    // Add hover effects
    addHoverEffects();
    
    // Update status counts
    updateStatusCounts();
    
    // Refresh data every 30 seconds with visual feedback
    setInterval(refreshDashboard, 30000);
    
    // Add keyboard navigation
    addKeyboardNavigation();
});

// Animation functions
function animateCardsIn() {
    const cards = document.querySelectorAll('.service-card');
    cards.forEach((card, index) => {
        card.style.opacity = '0';
        card.style.transform = 'translateY(20px)';
        card.style.transition = 'opacity 0.6s ease, transform 0.6s ease';
        
        setTimeout(() => {
            card.style.opacity = '1';
            card.style.transform = 'translateY(0)';
        }, index * 100);
    });
}

function animateSearchPlaceholder() {
    const searchInput = document.getElementById('searchInput');
    if (!searchInput) return;
    
    const placeholders = [
        'Search for a service...',
        'Try "Discord", "Instagram", "Gmail"...',
        'Find your favorite services...',
        'Search 100+ monitored services...'
    ];
    
    let currentIndex = 0;
    setInterval(() => {
        currentIndex = (currentIndex + 1) % placeholders.length;
        searchInput.placeholder = placeholders[currentIndex];
    }, 3000);
}

function addHoverEffects() {
    const cards = document.querySelectorAll('.service-card');
    cards.forEach(card => {
        card.addEventListener('mouseenter', function() {
            this.style.transform = 'translateY(-5px)';
            this.style.boxShadow = '0 8px 25px rgba(0,0,0,0.15)';
        });
        
        card.addEventListener('mouseleave', function() {
            this.style.transform = 'translateY(0)';
            this.style.boxShadow = '0 4px 15px rgba(0,0,0,0.1)';
        });
    });
}

function addKeyboardNavigation() {
    const searchInput = document.getElementById('searchInput');
    if (!searchInput) return;
    
    searchInput.addEventListener('keydown', function(e) {
        if (e.key === 'Escape') {
            this.blur();
            this.value = '';
            performSearch('');
        }
    });
}

function performSearch(query) {
    const serviceItems = document.querySelectorAll('.service-item');
    let visibleCount = 0;
    
    serviceItems.forEach(item => {
        const serviceName = item.dataset.serviceName || '';
        const shouldShow = serviceName.includes(query) || query === '';
        
        if (shouldShow) {
            item.style.display = 'block';
            item.style.opacity = '1';
            visibleCount++;
        } else {
            item.style.opacity = '0';
            setTimeout(() => {
                if (item.style.opacity === '0') {
                    item.style.display = 'none';
                }
            }, 300);
        }
    });
    
    // Show "no results" message if needed
    const existingMessage = document.getElementById('noResults');
    if (existingMessage) existingMessage.remove();
    
    if (visibleCount === 0 && query !== '') {
        const noResultsDiv = document.createElement('div');
        noResultsDiv.id = 'noResults';
        noResultsDiv.className = 'text-center my-4';
        noResultsDiv.innerHTML = `
            <p class="text-muted">
                <i data-feather="search" class="me-2"></i>
                No services found for "${query}"
            </p>
        `;
        document.getElementById('servicesGrid').appendChild(noResultsDiv);
        feather.replace();
    }
}

function updateStatusCounts() {
    let upCount = 0;
    let issuesCount = 0;
    let downCount = 0;
    
    document.querySelectorAll('.wave').forEach(wave => {
        if (wave.classList.contains('status-up')) {
            upCount++;
        } else if (wave.classList.contains('status-issues')) {
            issuesCount++;
        } else if (wave.classList.contains('status-down')) {
            downCount++;
        }
    });
    
    // Update counts if elements exist
    const upCountEl = document.getElementById('upCount');
    const issuesCountEl = document.getElementById('issuesCount');
    const downCountEl = document.getElementById('downCount');
    
    if (upCountEl) upCountEl.textContent = upCount;
    if (issuesCountEl) issuesCountEl.textContent = issuesCount;
    if (downCountEl) downCountEl.textContent = downCount;
}

async function refreshDashboard() {
    try {
        const response = await fetch('/api/services');
        if (!response.ok) {
            throw new Error(`HTTP error! status: ${response.status}`);
        }
        const services = await response.json();
        
        services.forEach(service => {
            const serviceCard = document.querySelector(`[data-service-id="${service.id}"]`);
            if (serviceCard) {
                const indicator = serviceCard.querySelector('.status-indicator');
                const reportsCount = serviceCard.querySelector('.card-text');
                const statusText = serviceCard.querySelector('.text-muted small');
                
                // Update wave status
                const wave = serviceCard.querySelector('.wave');
                if (wave) {
                    wave.className = `wave status-${service.status}`;
                }
                if (indicator) {
                    indicator.className = `status-indicator status-${service.status} me-2`;
                }
                
                // Update reports count with response time
                if (reportsCount) {
                    let reportText = `${service.recent_reports} reports in last 24h`;
                    if (service.response_time) {
                        reportText += ` • ${Math.round(service.response_time)}ms response`;
                    }
                    reportsCount.textContent = reportText;
                }
                
                // Update status text
                if (statusText) {
                    let statusIcon = 'check';
                    let statusClass = 'text-success';
                    let statusLabel = 'Operational';
                    
                    if (service.status === 'issues') {
                        statusIcon = 'alert-triangle';
                        statusClass = 'text-warning';
                        statusLabel = 'Issues';
                    } else if (service.status === 'down') {
                        statusIcon = 'x';
                        statusClass = 'text-danger';
                        statusLabel = 'Down';
                    }
                    
                    statusText.innerHTML = `<i data-feather="${statusIcon}" class="${statusClass}"></i> ${statusLabel}`;
                    feather.replace();
                }
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
        const wave = serviceCard.querySelector('.wave');
        const indicator = serviceCard.querySelector('.status-indicator');
        if (wave) {
            wave.className = `wave status-${data.new_status}`;
        }
        if (indicator) {
            indicator.className = `status-indicator status-${data.new_status} me-2`;
        }
        
        // Update counts
        updateStatusCounts();
    }
});

// Listen for real-time status updates from monitoring
socket.on('status_updates', function(updates) {
    updates.forEach(update => {
        const serviceCard = document.querySelector(`[data-service-id="${update.service_id}"]`);
        if (serviceCard) {
            const indicator = serviceCard.querySelector('.status-indicator');
            const reportsCount = serviceCard.querySelector('.card-text');
            const statusText = serviceCard.querySelector('.text-muted small');
            
            // Update wave and status indicator
            const wave = serviceCard.querySelector('.wave');
            if (wave) {
                wave.className = `wave status-${update.new_status}`;
            }
            if (indicator) {
                indicator.className = `status-indicator status-${update.new_status} me-2`;
            }
            
            // Show a brief notification
            console.log(`Service ${update.name} status changed: ${update.old_status} → ${update.new_status}`);
            
            // Add response time if available
            if (update.response_time && reportsCount) {
                const currentText = reportsCount.textContent.split(' •')[0];
                reportsCount.textContent = `${currentText} • ${Math.round(update.response_time)}ms response`;
            }
        }
    });
    
    updateStatusCounts();
});

// Listen for periodic dashboard refresh
socket.on('dashboard_refresh', function(services) {
    services.forEach(service => {
        const serviceCard = document.querySelector(`[data-service-id="${service.id}"]`);
        if (serviceCard) {
            const indicator = serviceCard.querySelector('.status-indicator');
            const reportsCount = serviceCard.querySelector('.card-text');
            
            // Update wave and status indicator
            const wave = serviceCard.querySelector('.wave');
            if (wave) {
                wave.className = `wave status-${service.status}`;
            }
            if (indicator) {
                indicator.className = `status-indicator status-${service.status} me-2`;
            }
            
            // Update reports count with response time
            if (reportsCount) {
                let reportText = `${service.recent_reports} reports in last 24h`;
                if (service.response_time) {
                    reportText += ` • ${Math.round(service.response_time)}ms response`;
                }
                reportsCount.textContent = reportText;
            }
        }
    });
    
    updateStatusCounts();
});
