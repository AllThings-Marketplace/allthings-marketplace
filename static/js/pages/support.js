// static/js/pages/support.js
document.addEventListener("DOMContentLoaded", function () {
    const searchInput = document.getElementById("faqSearchInput");
    const filterBar = document.getElementById("faqFilterBar");
    const faqItems = document.querySelectorAll("#faqAccordionList .faq-item");
    const emptyState = document.getElementById("faqEmptyState");

    if (!faqItems.length) return;

    let activeCategory = "all";

    function applyFaqFilter() {
        const query = searchInput ? searchInput.value.trim().toLowerCase() : "";
        let visibleCount = 0;

        faqItems.forEach(item => {
            const itemCat = item.getAttribute("data-faq-category") || "";
            const textContent = item.textContent.toLowerCase();

            const matchesCat = activeCategory === "all" || itemCat === activeCategory;
            const matchesSearch = !query || textContent.includes(query);

            if (matchesCat && matchesSearch) {
                item.classList.remove("hidden-initial");
                if (query) item.setAttribute("open", "open");
                visibleCount += 1;
            } else {
                item.classList.add("hidden-initial");
            }
        });

        if (emptyState) {
            if (visibleCount === 0) {
                emptyState.classList.remove("hidden-initial");
            } else {
                emptyState.classList.add("hidden-initial");
            }
        }
    }

    if (searchInput) {
        searchInput.addEventListener("input", applyFaqFilter);
    }

    if (filterBar) {
        const buttons = filterBar.querySelectorAll(".faq-filter-btn");
        buttons.forEach(btn => {
            btn.addEventListener("click", function () {
                buttons.forEach(b => b.classList.remove("active"));
                this.classList.add("active");
                activeCategory = this.getAttribute("data-faq-cat") || "all";
                applyFaqFilter();
            });
        });
    }
});