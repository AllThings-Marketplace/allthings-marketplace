// === Order Confirmation Modal ===
document.addEventListener("DOMContentLoaded", function() {
    const confirmBtn = document.getElementById('openConfirmModal');
    const modal = document.getElementById('confirmReceiptModal');
    const cancelBtn = document.getElementById('closeConfirmModal');

    if (confirmBtn && modal && cancelBtn) {
        confirmBtn.addEventListener('click', () => {
            modal.classList.add('active');
        });
        
        cancelBtn.addEventListener('click', () => {
            modal.classList.remove('active');
        });

        // Close if clicking outside the card
        modal.addEventListener('click', (e) => {
            if (e.target === modal) {
                modal.classList.remove('active');
            }
        });
    }
});