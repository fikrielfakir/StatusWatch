// Service detail page functionality
let map;
let reportsChart;
let userLatitude = null;
let userLongitude = null;

document.addEventListener('DOMContentLoaded', function() {
    initializeMap();
    initializeChart();
    loadReports();
    loadStatistics();
    
    // Set up form handlers
    document.getElementById('reportForm').addEventListener('submit', handleReportSubmit);
    document.getElementById('getLocationBtn').addEventListener('click', getUserLocation);
    
    // Refresh data every 30 seconds
    setInterval(() => {
        loadReports();
        loadStatistics();
        updateChart();
    }, 30000);
});

function initializeMap() {
    // Initialize Leaflet map
    map = L.map('map').setView([39.8283, -98.5795], 4); // Center on USA
    
    L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
        attribution: '© OpenStreetMap contributors'
    }).addTo(map);
}

function initializeChart() {
    const ctx = document.getElementById('reportsChart').getContext('2d');
    
    reportsChart = new Chart(ctx, {
        type: 'line',
        data: {
            labels: [],
            datasets: [{
                label: 'Reports',
                data: [],
                borderColor: 'rgb(75, 192, 192)',
                backgroundColor: 'rgba(75, 192, 192, 0.2)',
                tension: 0.1
            }]
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            scales: {
                y: {
                    beginAtZero: true,
                    ticks: {
                        stepSize: 1
                    }
                }
            },
            plugins: {
                legend: {
                    display: false
                }
            }
        }
    });
    
    updateChart();
}

async function updateChart() {
    try {
        const response = await fetch(`/api/chart-data/${SERVICE_ID}`);
        const data = await response.json();
        
        reportsChart.data.labels = data.map(item => item.time);
        reportsChart.data.datasets[0].data = data.map(item => item.reports);
        reportsChart.update();
    } catch (error) {
        console.error('Error updating chart:', error);
    }
}

async function loadReports() {
    try {
        const response = await fetch(`/api/reports/${SERVICE_ID}`);
        const reports = await response.json();
        
        // Clear existing markers
        map.eachLayer(layer => {
            if (layer instanceof L.Marker) {
                map.removeLayer(layer);
            }
        });
        
        // Add markers for reports with coordinates
        reports.forEach(report => {
            if (report.latitude && report.longitude) {
                const marker = L.marker([report.latitude, report.longitude])
                    .bindPopup(`
                        <strong>Report</strong><br>
                        <strong>Location:</strong> ${report.location || 'Unknown'}<br>
                        <strong>Time:</strong> ${new Date(report.timestamp).toLocaleString()}<br>
                        <strong>Description:</strong> ${report.description || 'No description'}
                    `);
                marker.addTo(map);
            }
        });
        
        // Update recent reports list
        updateRecentReports(reports.slice(0, 10)); // Show last 10 reports
        
    } catch (error) {
        console.error('Error loading reports:', error);
    }
}

function updateRecentReports(reports) {
    const container = document.getElementById('recentReports');
    
    if (reports.length === 0) {
        container.innerHTML = '<p class="text-muted">No recent reports</p>';
        return;
    }
    
    container.innerHTML = reports.map(report => `
        <div class="border-bottom pb-2 mb-2">
            <div class="d-flex justify-content-between">
                <small class="text-muted">${new Date(report.timestamp).toLocaleString()}</small>
                ${report.location ? `<small class="text-muted">${report.location}</small>` : ''}
            </div>
            <p class="mb-0 small">${report.description || 'No description provided'}</p>
        </div>
    `).join('');
}

async function loadStatistics() {
    try {
        const response = await fetch(`/api/reports/${SERVICE_ID}?hours=24`);
        const reports = await response.json();
        
        const now = new Date();
        const oneHourAgo = new Date(now - 60 * 60 * 1000);
        const sixHoursAgo = new Date(now - 6 * 60 * 60 * 1000);
        
        const lastHour = reports.filter(r => new Date(r.timestamp) >= oneHourAgo).length;
        const last6Hours = reports.filter(r => new Date(r.timestamp) >= sixHoursAgo).length;
        const last24Hours = reports.length;
        
        document.getElementById('lastHourCount').textContent = lastHour;
        document.getElementById('last6HourCount').textContent = last6Hours;
        document.getElementById('last24HourCount').textContent = last24Hours;
        
    } catch (error) {
        console.error('Error loading statistics:', error);
    }
}

async function handleReportSubmit(e) {
    e.preventDefault();
    
    const formData = {
        service_id: SERVICE_ID,
        location: document.getElementById('location').value,
        description: document.getElementById('description').value,
        latitude: userLatitude,
        longitude: userLongitude
    };
    
    try {
        const response = await fetch('/api/report', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify(formData)
        });
        
        const result = await response.json();
        
        if (response.ok) {
            // Close modal
            const modal = bootstrap.Modal.getInstance(document.getElementById('reportModal'));
            modal.hide();
            
            // Reset form
            document.getElementById('reportForm').reset();
            userLatitude = null;
            userLongitude = null;
            
            // Show success message
            showNotification('Report submitted successfully!', 'success');
            
            // Refresh data
            setTimeout(() => {
                loadReports();
                loadStatistics();
                updateChart();
            }, 1000);
            
        } else {
            showNotification(result.error || 'Error submitting report', 'danger');
        }
        
    } catch (error) {
        console.error('Error submitting report:', error);
        showNotification('Error submitting report', 'danger');
    }
}

function getUserLocation() {
    if (navigator.geolocation) {
        navigator.geolocation.getCurrentPosition(
            function(position) {
                userLatitude = position.coords.latitude;
                userLongitude = position.coords.longitude;
                
                // Reverse geocode to get location name
                fetch(`https://nominatim.openstreetmap.org/reverse?lat=${userLatitude}&lon=${userLongitude}&format=json`)
                    .then(response => response.json())
                    .then(data => {
                        if (data.display_name) {
                            document.getElementById('location').value = data.display_name;
                        }
                    })
                    .catch(error => {
                        console.error('Error getting location name:', error);
                    });
                
                showNotification('Location captured successfully!', 'success');
            },
            function(error) {
                console.error('Error getting location:', error);
                showNotification('Unable to get your location', 'warning');
            }
        );
    } else {
        showNotification('Geolocation is not supported by this browser', 'warning');
    }
}

// Real-time updates via Socket.IO
socket.on('new_report', function(data) {
    if (data.service_id === SERVICE_ID) {
        // Refresh data
        loadReports();
        loadStatistics();
        updateChart();
    }
});
