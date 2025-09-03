// Ultra-simple dashboard with minimal JavaScript for maximum speed
document.addEventListener('DOMContentLoaded', function() {
    // Only essential functionality
    const searchInput = document.getElementById('searchInput');
    
    if (searchInput) {
        searchInput.addEventListener('input', function() {
            const query = this.value.toLowerCase();
            const serviceItems = document.querySelectorAll('.service-item');
            
            serviceItems.forEach(item => {
                const serviceName = item.dataset.serviceName || '';
                item.style.display = serviceName.includes(query) ? 'block' : 'none';
            });
        });
    }
});