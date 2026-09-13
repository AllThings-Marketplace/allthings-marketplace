// === Checkout Date Validation ===
document.addEventListener("DOMContentLoaded", function() {
    const scheduleInput = document.getElementById("scheduled_time");
    if (scheduleInput) {
        // Adjust for local timezone to ensure accurate cutoff
        const now = new Date();
        now.setMinutes(now.getMinutes() - now.getTimezoneOffset());
        
        // Slices the ISO string to format YYYY-MM-DDTHH:MM perfectly for the input
        scheduleInput.min = now.toISOString().slice(0, 16);
    }
});


document.addEventListener('DOMContentLoaded', function() {
    const radios = document.querySelectorAll('.address-radio');
    const newAddressForm = document.getElementById('new-address-form');
    const newInputs = document.querySelectorAll('.new-address-input');
    const cards = document.querySelectorAll('.address-card');

    if (radios.length > 0) {
        radios.forEach(radio => {
            radio.addEventListener('change', function() {
                // 1. Update visual selection borders
                cards.forEach(card => card.classList.remove('selected'));
                this.closest('.address-card').classList.add('selected');

                // 2. Toggle form visibility and requirements
                if (this.value === 'new') {
                    newAddressForm.style.display = 'block';
                    newInputs.forEach(input => input.setAttribute('required', 'required'));
                } else {
                    newAddressForm.style.display = 'none';
                    newInputs.forEach(input => input.removeAttribute('required'));
                }
            });
        });
    }
});