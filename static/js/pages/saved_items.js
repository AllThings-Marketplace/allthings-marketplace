document.addEventListener('DOMContentLoaded', function() {
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

    document.addEventListener('click', function(e) {
        const btn = e.target.closest('.toggle-save-btn');
        if (!btn) return;

        e.preventDefault(); 
        
        const productId = btn.getAttribute('data-product-id');
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
                const card = document.getElementById(`saved-item-card-${productId}`);
                if (card) {
                    card.style.display = 'none';
                } else {
                    btn.innerHTML = '<i class="fa-regular fa-heart text-muted"></i>';
                }
            } else if (data.is_saved === true) {
                btn.innerHTML = '<i class="fa-solid fa-heart text-danger"></i>';
            }
        })
        .catch(error => console.error('Error toggling saved item:', error));
    });
});