document.addEventListener('DOMContentLoaded', function() {
    // === 1. Package Selection Cards ===
    const packageCards = document.querySelectorAll('.package-card');
    
    packageCards.forEach(card => {
        card.addEventListener('click', function() {
            packageCards.forEach(c => c.classList.remove('selected'));
            this.classList.add('selected');
        });
    });

    // === 2. Saved Address Location Pills (Zero Inline onclick) ===
    const savedLocButtons = document.querySelectorAll('.js-saved-loc-btn');
    const serviceLocationInput = document.getElementById('serviceLocationInput');

    if (savedLocButtons.length > 0 && serviceLocationInput) {
        savedLocButtons.forEach(btn => {
            btn.addEventListener('click', function () {
                const fullAddress = this.getAttribute('data-full-address');
                if (fullAddress) {
                    serviceLocationInput.value = fullAddress;
                }
            });
        });
    }
});