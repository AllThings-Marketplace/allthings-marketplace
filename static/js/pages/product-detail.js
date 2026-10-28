// static/js/pages/product-detail.js

// 1. Scroll to a specific slide when a thumbnail is tapped
function scrollToGallerySlide(index, thumbElement) {
    const track = document.getElementById("productGalleryTrack");
    if (track) {
        const slideWidth = track.clientWidth;
        track.scrollTo({
            left: slideWidth * index,
            behavior: "smooth"
        });
    }
    setActiveThumbnail(index, thumbElement);
}

// Backward-compatible helper in case changeImage() is called directly
function changeImage(newSrc, thumbElement) {
    const idx = thumbElement && thumbElement.dataset.index
        ? parseInt(thumbElement.dataset.index, 10)
        : 0;
    scrollToGallerySlide(idx, thumbElement);
}

function setActiveThumbnail(activeIndex, clickedThumb) {
    const thumbnails = document.querySelectorAll(".thumbnail");
    thumbnails.forEach((thumb, idx) => {
        if (idx === activeIndex || thumb === clickedThumb) {
            thumb.classList.add("active-thumb");
            thumb.scrollIntoView({ behavior: "smooth", block: "nearest", inline: "center" });
        } else {
            thumb.classList.remove("active-thumb");
        }
    });

    const counterEl = document.getElementById("galleryCurrentIndex");
    if (counterEl) {
        counterEl.textContent = activeIndex + 1;
    }
}

// 2. Dynamic Variant Price Updater
function updatePrice(selectElement) {
    const selectedOption = selectElement.options[selectElement.selectedIndex];
    const rawPrice = selectedOption.getAttribute("data-price");
    const priceDisplay = document.getElementById("displayProductPrice");

    if (rawPrice && priceDisplay) {
        const formattedPrice = Math.round(parseFloat(rawPrice)).toLocaleString("en-US");
        priceDisplay.textContent = "NGN " + formattedPrice;
    }
}

// 3. Touch-Swipe & Mouse-Drag Carousel Controller
document.addEventListener("DOMContentLoaded", function () {
    const track = document.getElementById("productGalleryTrack");
    const prevBtn = document.getElementById("galleryPrevBtn");
    const nextBtn = document.getElementById("galleryNextBtn");

    if (!track) return;

    const slides = track.querySelectorAll(".gallery-slide");
    const totalSlides = slides.length;
    let currentIndex = 0;

    // Update active thumbnail & counter as user swipes with their finger
    let scrollTimeout;
    track.addEventListener("scroll", function () {
        clearTimeout(scrollTimeout);
        scrollTimeout = setTimeout(function () {
            if (track.clientWidth > 0) {
                const newIndex = Math.round(track.scrollLeft / track.clientWidth);
                if (newIndex !== currentIndex && newIndex >= 0 && newIndex < totalSlides) {
                    currentIndex = newIndex;
                    setActiveThumbnail(currentIndex);
                }
            }
        }, 40);
    }, { passive: true });

    // Prev / Next Arrow Buttons
    if (prevBtn) {
        prevBtn.addEventListener("click", function () {
            const targetIndex = currentIndex > 0 ? currentIndex - 1 : totalSlides - 1;
            scrollToGallerySlide(targetIndex);
        });
    }

    if (nextBtn) {
        nextBtn.addEventListener("click", function () {
            const targetIndex = currentIndex < totalSlides - 1 ? currentIndex + 1 : 0;
            scrollToGallerySlide(targetIndex);
        });
    }

    // Desktop Mouse Drag-to-Scroll Support
    let isDown = false;
    let startX = 0;
    let scrollStart = 0;

    track.addEventListener("mousedown", function (e) {
        isDown = true;
        track.classList.add("is-dragging");
        startX = e.pageX - track.offsetLeft;
        scrollStart = track.scrollLeft;
    });

    function endDrag() {
        if (!isDown) return;
        isDown = false;
        track.classList.remove("is-dragging");
        if (track.clientWidth > 0) {
            const snappedIndex = Math.round(track.scrollLeft / track.clientWidth);
            scrollToGallerySlide(Math.max(0, Math.min(totalSlides - 1, snappedIndex)));
        }
    }

    track.addEventListener("mouseleave", endDrag);
    track.addEventListener("mouseup", endDrag);

    track.addEventListener("mousemove", function (e) {
        if (!isDown) return;
        e.preventDefault();
        const x = e.pageX - track.offsetLeft;
        const walk = (x - startX) * 1.25;
        track.scrollLeft = scrollStart - walk;
    });
});