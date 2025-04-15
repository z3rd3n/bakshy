document.addEventListener('DOMContentLoaded', function() {
    // Auto-hide flash messages after 5 seconds
    const flashMessages = document.querySelectorAll('.flash-message');
    if (flashMessages.length > 0) {
        setTimeout(function() {
            flashMessages.forEach(function(message) {
                message.style.opacity = '0';
                message.style.transition = 'opacity 0.5s';
                
                // Remove from DOM after fade out
                setTimeout(function() {
                    message.remove();
                }, 500);
            });
        }, 5000);
    }
    
    // Enable confirm dialogs for delete actions
    const confirmActions = document.querySelectorAll('[data-confirm]');
    confirmActions.forEach(function(element) {
        element.addEventListener('click', function(e) {
            const message = this.getAttribute('data-confirm') || 'Are you sure?';
            if (!confirm(message)) {
                e.preventDefault();
                return false;
            }
        });
    });
});