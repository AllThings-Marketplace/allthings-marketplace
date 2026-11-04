document.addEventListener("DOMContentLoaded", function () {
    // === 1. Dynamic Time-of-Day Greeting ===
    const greetingElements = document.querySelectorAll('.dynamic-greeting');
    if (greetingElements.length > 0) {
        const hour = new Date().getHours();
        let greeting = 'Good evening';

        if (hour >= 5 && hour < 12) {
            greeting = 'Good morning';
        } else if (hour >= 12 && hour < 18) {
            greeting = 'Good afternoon';
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

    // === 3. Auto-Submit Smart Filters (Zero Inline onchange) ===
    const autoSubmitInputs = document.querySelectorAll('.js-auto-submit-filter');
    autoSubmitInputs.forEach(input => {
        input.addEventListener('change', function () {
            if (this.form) {
                this.form.submit();
            }
        });
    });

    // === 4. Collapsible Sidebar Subcategory Accordions ===
    const deptItems = document.querySelectorAll('.sidebar-dept-item');
    deptItems.forEach(item => {
        const hasActiveLink = item.querySelector('.sidebar-parent-link.active, .sidebar-child-link.active');
        const toggleBtn = item.querySelector('.sidebar-sub-toggle');

        if (hasActiveLink) {
            item.classList.add('is-open');
            if (toggleBtn) toggleBtn.setAttribute('aria-expanded', 'true');
        }

        if (toggleBtn) {
            toggleBtn.addEventListener('click', function (e) {
                e.preventDefault();
                e.stopPropagation();
                const isOpen = item.classList.toggle('is-open');
                this.setAttribute('aria-expanded', isOpen ? 'true' : 'false');
            });
        }
    });

    // === 5. Sidebar "See All Departments / Show Less" Toggle (Products) ===
    const productDeptList = document.getElementById('sidebarProductDeptList');
    const seeMoreDeptsBtn = document.getElementById('sidebarSeeMoreDeptsBtn');
    const SIDEBAR_DEPT_LIMIT = 7;

    if (productDeptList && seeMoreDeptsBtn) {
        const productDepts = Array.from(productDeptList.querySelectorAll(':scope > li.sidebar-dept-item'));
        const extraDepts = productDepts.slice(SIDEBAR_DEPT_LIMIT);

        if (extraDepts.length > 0) {
            const activeInExtra = extraDepts.some(item => item.classList.contains('is-open'));
            let isExpanded = activeInExtra;

            function syncSidebarDeptsUI() {
                extraDepts.forEach(item => {
                    item.classList.toggle('hidden-initial', !isExpanded);
                });
                if (isExpanded) {
                    seeMoreDeptsBtn.innerHTML = 'Show Fewer Departments <i class="fa-solid fa-angle-up"></i>';
                } else {
                    seeMoreDeptsBtn.innerHTML = `See All Departments (${productDepts.length}) <i class="fa-solid fa-angle-down"></i>`;
                }
            }

            seeMoreDeptsBtn.classList.remove('hidden-initial');
            syncSidebarDeptsUI();

            seeMoreDeptsBtn.addEventListener('click', function () {
                isExpanded = !isExpanded;
                syncSidebarDeptsUI();
            });
        }
    }

    // === 6. Promo Slider Logic ===
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

    if (sliderContainer) {
        sliderContainer.addEventListener('mouseenter', stopAutoSlide);
        sliderContainer.addEventListener('mouseleave', startAutoSlide);
    }

    startAutoSlide();
});