// static/js/components/modal.js
document.addEventListener("DOMContentLoaded", function () {
    // === 1. Order Confirmation Modal ===
    const confirmBtn = document.getElementById("openConfirmModal");
    const modal = document.getElementById("confirmReceiptModal");
    const cancelBtn = document.getElementById("closeConfirmModal");

    if (confirmBtn && modal && cancelBtn) {
        confirmBtn.addEventListener("click", () => {
            modal.classList.add("active");
        });

        cancelBtn.addEventListener("click", () => {
            modal.classList.remove("active");
        });

        modal.addEventListener("click", (e) => {
            if (e.target === modal) {
                modal.classList.remove("active");
            }
        });
    }

    // === 2. Global In-App Image Lightbox ===
    const lightbox = document.getElementById("globalImageLightbox");
    const lightboxImg = document.getElementById("lightboxImage");
    const lightboxCaption = document.getElementById("lightboxCaption");
    const lightboxExternal = document.getElementById("lightboxExternalLink");
    const zoomBtn = document.getElementById("lightboxZoomBtn");
    const closeBtn = document.getElementById("lightboxCloseBtn");
    const stage = document.getElementById("lightboxStage");

    if (!lightbox || !lightboxImg) return;

    const IMAGE_EXT_REGEX = /\.(jpe?g|png|webp|gif|avif|svg|bmp)(\?.*)?$/i;

    function isPreviewableImageUrl(url) {
        if (!url) return false;
        const lower = url.toLowerCase();
        if (lower.endsWith(".pdf") || lower.includes(".pdf?") || lower.includes("/raw/upload/")) {
            return false;
        }
        return (
            IMAGE_EXT_REGEX.test(lower) ||
            (lower.includes("cloudinary.com") && lower.includes("/image/upload/")) ||
            lower.startsWith("/media/") ||
            lower.startsWith("blob:") ||
            lower.startsWith("data:image/")
        );
    }

    function openLightbox(src, caption) {
        if (!src) return;
        lightboxImg.src = src;
        lightboxImg.classList.remove("zoomed");
        if (lightboxCaption) {
            lightboxCaption.textContent = (caption || "Image Preview").replace(/[↗\u2197]/g, "").trim();
        }
        if (lightboxExternal) {
            lightboxExternal.href = src;
        }
        lightbox.classList.add("active");
        lightbox.setAttribute("aria-hidden", "false");
        document.body.classList.add("lightbox-open");
    }

    function closeLightbox() {
        lightbox.classList.remove("active");
        lightbox.setAttribute("aria-hidden", "true");
        lightboxImg.classList.remove("zoomed");
        lightboxImg.src = "";
        document.body.classList.remove("lightbox-open");
    }

    function toggleZoom(e) {
        if (e) e.stopPropagation();
        lightboxImg.classList.toggle("zoomed");
    }

    if (closeBtn) closeBtn.addEventListener("click", closeLightbox);
    if (zoomBtn) zoomBtn.addEventListener("click", toggleZoom);
    lightboxImg.addEventListener("click", toggleZoom);

    if (stage) {
        stage.addEventListener("click", function (e) {
            if (e.target === stage) closeLightbox();
        });
    }

    document.addEventListener("keydown", function (e) {
        if (e.key === "Escape" && lightbox.classList.contains("active")) {
            closeLightbox();
        }
    });

    // Global Event Delegation for Links & Standalone Images
    document.addEventListener("click", function (e) {
        // Ignore clicks inside the lightbox itself
        if (e.target.closest("#globalImageLightbox")) return;

        // A. Intercept <a> tags wrapping an image or pointing directly to a media/Cloudinary image
        const link = e.target.closest("a");
        if (link && !link.classList.contains("brand-logo") && !link.classList.contains("footer-logo")) {
            const href = link.getAttribute("href") || "";
            const childImg = link.querySelector("img");
            const isExplicitMediaLink = (
                link.classList.contains("dossier-media-chip") ||
                link.classList.contains("dossier-thumb-box") ||
                link.classList.contains("attachment-link") ||
                link.classList.contains("js-lightbox-link")
            );

            // Only intercept if the link points directly to an image (not a product/service page URL)
            if ((childImg && isPreviewableImageUrl(href)) || (isExplicitMediaLink && isPreviewableImageUrl(href))) {
                e.preventDefault();
                const caption = (childImg && childImg.alt) || link.textContent.trim() || "Image Preview";
                openLightbox(href, caption);
                return;
            }
        }

        // B. Intercept clicks on standalone previewable images across the site
        const previewableSelector = [
            "img.service-thumb",
            "img.chat-attachment",
            "img.dossier-thumb-img",
            "img.portfolio-img",
            "img.review-photo-thumb",
            "img#main-product-image",
            "img.service-hero-img",
            "img.js-previewable"
        ].join(", ");

        const img = e.target.closest(previewableSelector);
        if (img && img.src) {
            // Do not intercept if the image sits inside a product card or navigation link to a page
            const parentLink = img.closest("a");
            if (parentLink) {
                const parentHref = parentLink.getAttribute("href") || "";
                if (parentHref && !isPreviewableImageUrl(parentHref) && parentHref !== "#") {
                    return;
                }
            }
            e.preventDefault();
            openLightbox(img.src, img.alt || "Image Preview");
        }
    });
});