document.addEventListener('DOMContentLoaded', function() {
    // Helper to get Django CSRF token from cookies
    function getCookie(name) {
        let cookieValue = null;
        if (document.cookie && document.cookie !== '') {
            const cookies = document.cookie.split(';');
            for (let i = 0; i < cookies.length; i++) {
                const cookie = cookies[i].trim();
                if (cookie.substring(0, name.length + 1) === (name + '=')) {
                    cookieValue = decodeURIComponent(cookie.substring(name.length + 1));
                    break;
                }
            }
        }
        return cookieValue;
    }

    const saveButtons = document.querySelectorAll('.toggle-save-btn');

    saveButtons.forEach(btn => {
        btn.addEventListener('click', function(e) {
            e.preventDefault();
            const productId = this.getAttribute('data-product-id');
            const csrftoken = getCookie('csrftoken');

            fetch(`/api/toggle-save/${productId}/`, {
                method: 'POST',
                headers: {
                    'X-CSRFToken': csrftoken,
                    'Content-Type': 'application/json'
                },
            })
            .then(response => response.json())
            .then(data => {
                if (data.is_saved === false) {
                    // If we are on the saved items page, remove the card visually
                    const card = document.getElementById(`saved-item-card-${productId}`);
                    if (card) {
                        card.style.display = 'none';
                    } else {
                        // FIX: Added 'text-muted' here so it goes back to grey!
                        this.innerHTML = '<i class="fa-regular fa-heart text-muted"></i>';
                    }
                } else if (data.is_saved === true) {
                    // If saving from homepage, swap outline heart to solid
                    this.innerHTML = '<i class="fa-solid fa-heart text-danger"></i>';
                }
            })
            .catch(error => console.error('Error toggling saved item:', error));
        });
    });
});