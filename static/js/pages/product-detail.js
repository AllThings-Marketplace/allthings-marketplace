function changeImage(src) {
    document.getElementById('mainProductImage').src = src;
    
    // Remove active border from all thumbnails
    let thumbs = document.querySelectorAll('.thumbnail');
    thumbs.forEach(t => t.classList.remove('active-thumb'));
    
    // Add active border to the clicked thumbnail
    event.target.classList.add('active-thumb');
}

// Add this below your existing changeImage function
function updatePrice(selectElement) {
    let selectedOption = selectElement.options[selectElement.selectedIndex];
    let newPrice = selectedOption.getAttribute('data-price');
    
    if (newPrice) {
        // Formats the price nicely and injects it into the main price div
        document.querySelector('.product-price').innerText = 'NGN ' + parseFloat(newPrice).toLocaleString('en-US', {minimumFractionDigits: 2});
    }
}