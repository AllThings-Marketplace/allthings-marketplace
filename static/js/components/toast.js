document.addEventListener('DOMContentLoaded', () => {
    const toasts = document.querySelectorAll('.premium-toast');

    function dismissToast(toast) {
        if (!toast || toast.dataset.dismissing === 'true') return;
        toast.dataset.dismissing = 'true';
        toast.style.animation = 'slideOutRight 0.4s cubic-bezier(0.16, 1, 0.3, 1) forwards';
        setTimeout(() => {
            toast.remove();
        }, 400);
    }

    toasts.forEach(toast => {
        const closeBtn = toast.querySelector('.toast-close');
        if (closeBtn) {
            closeBtn.addEventListener('click', () => dismissToast(toast));
        }

        setTimeout(() => {
            dismissToast(toast);
        }, 5000);
    });
});