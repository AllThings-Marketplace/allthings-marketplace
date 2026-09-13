document.addEventListener("DOMContentLoaded", function() {
            let currentSlideIndex = 0;
            const slides = document.querySelectorAll(".promo-slider .slide");
            
            if (slides.length > 1) {
                setInterval(() => {
                    slides[currentSlideIndex].classList.remove("active");
                    currentSlideIndex = (currentSlideIndex + 1) % slides.length;
                    slides[currentSlideIndex].classList.add("active");
                }, 2500); // Swaps every 2.5 seconds
            }
        });