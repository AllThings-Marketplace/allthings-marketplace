document.addEventListener('DOMContentLoaded', function() {
    const packageCards = document.querySelectorAll('.package-card');
    
    packageCards.forEach(card => {
        card.addEventListener('click', function() {
            // Remove selected class from all cards
            packageCards.forEach(c => c.classList.remove('selected'));
            // Add selected class to the clicked card
            this.classList.add('selected');
        });
    });
});