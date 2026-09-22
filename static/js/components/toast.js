document.addEventListener('DOMContentLoaded', () => {
    const toasts = document.querySelectorAll('.premium-toast');
    
    toasts.forEach(toast => {
        // Automatically remove the toast after 5 seconds to match the CSS progress bar
        setTimeout(() => {
            // Apply the slide-out animation
            toast.style.animation = 'slideOutRight 0.4s cubic-bezier(0.16, 1, 0.3, 1) forwards';
            
            // Wait for the animation to finish before removing it from the DOM
            setTimeout(() => {
                toast.remove();
            }, 400); 
        }, 5000);
    });
});