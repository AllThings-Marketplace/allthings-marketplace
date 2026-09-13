document.addEventListener('DOMContentLoaded', function() {
    const isUserAuthenticated = document.body.getAttribute('data-user-auth') === 'true';
    const authModal = document.getElementById('authGuardModal');
    const closeModalBtn = document.getElementById('closeAuthModal');

    if (closeModalBtn && authModal) {
        closeModalBtn.addEventListener('click', () => {
            authModal.classList.remove('active');
        });
    }

    // Intercept clicks on anything possessing the 'requires-auth' class
    document.querySelectorAll('.requires-auth').forEach(element => {
        element.addEventListener('click', function(event) {
            if (!isUserAuthenticated) {
                event.preventDefault(); 
                authModal.classList.add('active');
            }
        });
    });
});