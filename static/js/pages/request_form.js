document.addEventListener("DOMContentLoaded", function () {
    const tabs = document.querySelectorAll(".req-type-tab");
    const typeInput = document.getElementById("requestTypeInput");
    const titleLabel = document.getElementById("requestTitleLabel");
    const titleInput = document.getElementById("requestTitleInput");

    const prodCatGroup = document.getElementById("productCategoryGroup");
    const srvCatGroup = document.getElementById("serviceCategoryGroup");
    const prodCatSelect = document.getElementById("productCategorySelect");
    const srvCatSelect = document.getElementById("serviceCategorySelect");

    const prodFields = document.getElementById("productSpecificFields");
    const srvFields = document.getElementById("serviceSpecificFields");
    const prodBrandInput = document.getElementById("productBrandInput");
    const prodConditionSelect = document.getElementById("productConditionSelect");
    const prodSpecsInput = document.getElementById("productSpecsInput");
    const srvDateInput = document.getElementById("serviceDateInput");
    const srvSpecsInput = document.getElementById("serviceSpecsInput");

    if (!tabs.length || !typeInput) return;

    function syncRequestType(selectedType) {
        typeInput.value = selectedType;

        tabs.forEach(t => {
            t.classList.toggle("active", t.dataset.type === selectedType);
        });

        const isService = selectedType === "SERVICE";

        if (titleLabel) {
            titleLabel.textContent = isService ? "Service Needed *" : "Product Name / Model *";
        }
        if (titleInput) {
            const newPlaceholder = isService
                ? titleInput.getAttribute("data-service-placeholder")
                : titleInput.getAttribute("data-product-placeholder");
            if (newPlaceholder) {
                titleInput.setAttribute("placeholder", newPlaceholder);
            }
        }

        if (prodCatGroup) prodCatGroup.classList.toggle("hidden-initial", isService);
        if (prodCatSelect) prodCatSelect.disabled = isService;

        if (srvCatGroup) srvCatGroup.classList.toggle("hidden-initial", !isService);
        if (srvCatSelect) srvCatSelect.disabled = !isService;

        if (prodFields) prodFields.classList.toggle("hidden-initial", isService);
        if (prodBrandInput) prodBrandInput.disabled = isService;
        if (prodConditionSelect) prodConditionSelect.disabled = isService;
        if (prodSpecsInput) prodSpecsInput.disabled = isService;

        if (srvFields) srvFields.classList.toggle("hidden-initial", !isService);
        if (srvDateInput) srvDateInput.disabled = !isService;
        if (srvSpecsInput) srvSpecsInput.disabled = !isService;
    }

    tabs.forEach(tab => {
        tab.addEventListener("click", function () {
            syncRequestType(this.dataset.type);
        });
    });

    syncRequestType(typeInput.value || "PRODUCT");
});