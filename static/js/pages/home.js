document.addEventListener("DOMContentLoaded", function() {
    // === 1. Dynamic Time-of-Day Greeting ===
    const greetingElements = document.querySelectorAll('.dynamic-greeting');
    if (greetingElements.length > 0) {
        const hour = new Date().getHours();
        let greeting = 'Good evening'; // 6:00 PM - 4:59 AM
        
        if (hour >= 5 && hour < 12) {
            greeting = 'Good morning'; // 5:00 AM - 11:59 AM
        } else if (hour >= 12 && hour < 18) {
            greeting = 'Good afternoon'; // 12:00 PM - 5:59 PM
        }
        
        greetingElements.forEach(el => {
            el.textContent = greeting;
        });
    }

    // === 2. Mobile Filter Sidebar Toggle ===
    const mobileFilterBtn = document.getElementById('mobileFilterToggleBtn');
    const closeSidebarBtn = document.getElementById('closeSidebarBtn');
    const sidebar = document.getElementById('marketplaceSidebar');

    if (mobileFilterBtn && sidebar) {
        mobileFilterBtn.addEventListener('click', () => {
            sidebar.classList.add('active');
            document.body.style.overflow = 'hidden';
        });
    }

    if (closeSidebarBtn && sidebar) {
        closeSidebarBtn.addEventListener('click', () => {
            sidebar.classList.remove('active');
            document.body.style.overflow = '';
        });
    }

    // === 3. Promo Slider Logic ===
    const track = document.getElementById('sliderTrack');
    const slides = document.querySelectorAll('.slide');
    const prevBtn = document.getElementById('prevBtn');
    const nextBtn = document.getElementById('nextBtn');
    const dots = document.querySelectorAll('.dot');
    const sliderContainer = document.getElementById('homeSlider');

    if (!track || slides.length <= 1) return; 

    let currentIndex = 0;
    let autoSlideInterval;
    const slideDelay = 4000;

    function goToSlide(index) {
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

    if (nextBtn) nextBtn.addEventListener('click', nextSlide);
    if (prevBtn) prevBtn.addEventListener('click', prevSlide);
    
    dots.forEach((dot, index) => {
        dot.addEventListener('click', () => goToSlide(index));
    });

    sliderContainer.addEventListener('mouseenter', stopAutoSlide);
    sliderContainer.addEventListener('mouseleave', startAutoSlide);

    startAutoSlide();
});