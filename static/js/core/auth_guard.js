document.addEventListener('DOMContentLoaded', function() {
    const isUserAuthenticated = document.body.getAttribute('data-user-auth') === 'true';
    const authModal = document.getElementById('authGuardModal');
    const closeModalBtn = document.getElementById('closeAuthModal');

    if (closeModalBtn && authModal) {
        closeModalBtn.addEventListener('click', () => {
            authModal.classList.remove('active');
        });
    }

    // Capture Phase Event Delegation - Runs first, stops everything else
    document.addEventListener('click', function(event) {
        const authElement = event.target.closest('.requires-auth');
        
        if (authElement && !isUserAuthenticated) {
            event.preventDefault(); 
            event.stopImmediatePropagation(); // Kills the click
            if (authModal) {
                authModal.classList.add('active');
            }
        }
    }, true);
});