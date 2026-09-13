document.addEventListener("DOMContentLoaded", function() {
    const track = document.getElementById('sliderTrack');
    const slides = document.querySelectorAll('.slide');
    const prevBtn = document.getElementById('prevBtn');
    const nextBtn = document.getElementById('nextBtn');
    const dots = document.querySelectorAll('.dot');
    const sliderContainer = document.getElementById('homeSlider');

    // Exit gracefully if there are no slides to animate
    if (!track || slides.length <= 1) return; 

    let currentIndex = 0;
    let autoSlideInterval;
    const slideDelay = 4000; // Increased to 4 seconds for better readability

    function goToSlide(index) {
        // Reset to beginning or end for infinite loop effect
        if (index < 0) index = slides.length - 1;
        if (index >= slides.length) index = 0;
        
        currentIndex = index;
        track.style.transform = `translateX(-${currentIndex * 100}%)`;

        dots.forEach(dot => dot.classList.remove('active'));
        if (dots[currentIndex]) dots[currentIndex].classList.add('active');
    }

    function nextSlide() { goToSlide(currentIndex + 1); }
    function prevSlide() { goToSlide(currentIndex - 1); }

    function startAutoSlide() {
        autoSlideInterval = setInterval(nextSlide, slideDelay);
    }
    
    function stopAutoSlide() {
        clearInterval(autoSlideInterval);
    }

    // Bind physical button clicks
    if (nextBtn) nextBtn.addEventListener('click', nextSlide);
    if (prevBtn) prevBtn.addEventListener('click', prevSlide);
    
    dots.forEach((dot, index) => {
        dot.addEventListener('click', () => goToSlide(index));
    });

    // The Pause-On-Hover Logic
    sliderContainer.addEventListener('mouseenter', stopAutoSlide);
    sliderContainer.addEventListener('mouseleave', startAutoSlide);

    // Initialize the slider timer
    startAutoSlide();
});