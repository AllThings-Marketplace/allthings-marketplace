function changeImage(src) {
    document.getElementById('mainProductImage').src = src;
    
    // Remove active border from all thumbnails
    let thumbs = document.querySelectorAll('.thumbnail');
    thumbs.forEach(t => t.classList.remove('active-thumb'));
    
    // Add active border to the clicked thumbnail
    event.target.classList.add('active-thumb');
}