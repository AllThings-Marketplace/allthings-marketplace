// === Dynamic Cart Calculation ===
document.addEventListener("DOMContentLoaded", function() {
    const selectAllCheckbox = document.getElementById('selectAllItems');
    const itemCheckboxes = document.querySelectorAll('.item-checkbox');
    const cartTotalDisplay = document.getElementById('cartTotalDisplay');

    if (!selectAllCheckbox || !cartTotalDisplay) return;

    function calculateTotal() {
        let total = 0;
        itemCheckboxes.forEach(box => {
            if (box.checked) {
                total += parseFloat(box.getAttribute('data-price'));
            }
        });
        // Format the total dynamically
        cartTotalDisplay.textContent = 'NGN ' + total.toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 });
    }

    // Toggle all checkboxes when 'Select All' is clicked
    selectAllCheckbox.addEventListener('change', function() {
        itemCheckboxes.forEach(box => box.checked = this.checked);
        calculateTotal();
    });

    // Handle individual checkbox clicks
    itemCheckboxes.forEach(box => {
        box.addEventListener('change', function() {
            if (!this.checked) {
                selectAllCheckbox.checked = false;
            } else {
                const allChecked = Array.from(itemCheckboxes).every(b => b.checked);
                if (allChecked) selectAllCheckbox.checked = true;
            }
            calculateTotal();
        });
    });
});

document.addEventListener("DOMContentLoaded", function() {
    const cartButtons = document.querySelectorAll('.ajax-cart-btn');

    cartButtons.forEach(button => {
        button.addEventListener('click', function(e) {
            e.preventDefault(); 
            
            // 1. Strict Lock: If it is already loading, ignore any extra clicks entirely
            if (this.dataset.loading === "true") return;
            this.dataset.loading = "true";
            
            // 2. Safely capture the original text only once
            if (!this.dataset.originalText) {
                this.dataset.originalText = this.innerHTML;
            }

            const url = this.href;

            // Trigger loading state
            this.innerHTML = '<i class="fa-solid fa-spinner fa-spin"></i> Adding...';
            this.classList.add('btn-loading');

            const serverRequest = fetch(url, {
                headers: { 'X-Requested-With': 'XMLHttpRequest' }
            });

            // Reduced delay to 800ms (0.8 seconds)
            const minimumDelay = new Promise(resolve => setTimeout(resolve, 800));

            Promise.all([serverRequest, minimumDelay])
            .then(([response]) => {
                // Show success state
                this.classList.remove('btn-loading');
                this.classList.add('btn-added');
                this.innerHTML = '<i class="fa-solid fa-check"></i> Added!';
                
                // Revert to original state after 1.5 seconds and unlock the button
                setTimeout(() => {
                    this.innerHTML = this.dataset.originalText;
                    this.classList.remove('btn-added');
                    this.dataset.loading = "false";
                }, 1500);
            })
            .catch(error => {
                this.classList.remove('btn-loading');
                this.innerHTML = 'Error';
                
                setTimeout(() => {
                    this.innerHTML = this.dataset.originalText;
                    this.dataset.loading = "false";
                }, 1500);
            });
        });
    });
});