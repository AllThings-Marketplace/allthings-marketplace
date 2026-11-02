document.addEventListener('DOMContentLoaded', function () {
    const isUserAuthenticated = document.body.getAttribute('data-user-auth') === 'true';
    const authModal = document.getElementById('authGuardModal');
    const closeModalBtn = document.getElementById('closeAuthModal');

    if (closeModalBtn && authModal) {
        closeModalBtn.addEventListener('click', () => {
            authModal.classList.remove('active');
        });
    }

    if (authModal) {
        authModal.addEventListener('click', (e) => {
            if (e.target === authModal) {
                authModal.classList.remove('active');
            }
        });

        document.addEventListener('keydown', (e) => {
            if (e.key === 'Escape' && authModal.classList.contains('active')) {
                authModal.classList.remove('active');
            }
        });
    }

    // Capture Phase Event Delegation - intercepts unauthenticated actions immediately
    document.addEventListener('click', function (event) {
        const authElement = event.target.closest('.requires-auth');

        if (authElement && !isUserAuthenticated) {
            event.preventDefault();
            event.stopImmediatePropagation();
            if (authModal) {
                authModal.classList.add('active');
            }
        }
    }, true);
});