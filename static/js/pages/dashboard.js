document.addEventListener('DOMContentLoaded', function() {
    // === 1. Bank Details Capture ===
    const bankSelect = document.getElementById('bankSelect');
    const bankNameInput = document.getElementById('bankNameInput');

    if (bankSelect && bankNameInput) {
        bankSelect.addEventListener('change', function() {
            const selectedOption = this.options[this.selectedIndex];
            bankNameInput.value = selectedOption.getAttribute('data-name');
        });
    }

    // === 2. Provider Location Capture ===
    const locationBtn = document.getElementById('getLocationBtn');
    const latInput = document.getElementById('latInput');
    const lonInput = document.getElementById('lonInput');

    if (locationBtn && latInput && lonInput) {
        locationBtn.addEventListener('click', function() {
            if (navigator.geolocation) {
                navigator.geolocation.getCurrentPosition(
                    function(position) {
                        latInput.value = position.coords.latitude;
                        lonInput.value = position.coords.longitude;
                    },
                    function(error) {
                        alert("Error getting location. Please ensure location permissions are enabled for this site.");
                    },
                    { enableHighAccuracy: true }
                );
            } else {
                alert("Geolocation is not supported by your browser.");
            }
        });
    }

    // === 3. Variant Builder Logic ===
    const addVariantBtn = document.getElementById('add-variant-btn');
    const variantContainer = document.getElementById('variant-builder-container');
    
    if (addVariantBtn && variantContainer) {
        addVariantBtn.addEventListener('click', function() {
            variantContainer.style.display = 'block';
            
            const row = document.createElement('div');
            row.className = 'variant-row';
            row.innerHTML = `
                <div class="form-group" style="margin:0;">
                    <label class="text-12-muted">Option (e.g., Color)</label>
                    <input type="text" name="variant_names[]" class="form-control" placeholder="Size, Color, etc." required>
                </div>
                <div class="form-group" style="margin:0;">
                    <label class="text-12-muted">Value (e.g., Red)</label>
                    <input type="text" name="variant_values[]" class="form-control" placeholder="Red, XL, 256GB" required>
                </div>
                <div class="form-group" style="margin:0;">
                    <label class="text-12-muted">Price Override (NGN)</label>
                    <input type="number" name="variant_prices[]" class="form-control" step="0.01" placeholder="Optional">
                </div>
                <div class="form-group" style="margin:0;">
                    <label class="text-12-muted">Stock</label>
                    <input type="number" name="variant_stocks[]" class="form-control" min="0" value="0" required>
                </div>
                <button type="button" class="btn-remove-variant" onclick="this.parentElement.remove(); if(variantContainer.children.length === 0) variantContainer.style.display = 'none';">
                    <i class="fa-solid fa-trash"></i>
                </button>
            `;
            variantContainer.appendChild(row);
        });
    }

    // === 4. Unified Category Attributes Fetching (AJAX) ===
    const categorySelector = document.getElementById('category-selector');
    const attributesContainer = document.getElementById('dynamic-attributes-container');

    if (categorySelector && attributesContainer) {
        categorySelector.addEventListener('change', function() {
            const categoryId = this.value;
            attributesContainer.innerHTML = ''; // Clear existing fields

            if (categoryId) {
                fetch(`/api/category-attributes/${categoryId}/`)
                    .then(response => response.json())
                    .then(data => {
                        // SAFELY PARSE: Protect against stringified JSON arrays
                        let schemaArray = data.schema;
                        if (typeof schemaArray === 'string') {
                            schemaArray = JSON.parse(schemaArray);
                        }

                        if (Array.isArray(schemaArray) && schemaArray.length > 0) {
                            attributesContainer.innerHTML = `<h3 class="checkout-section-title" style="grid-column: 1 / -1;"><i class="fa-solid fa-list icon-primary-spaced"></i> Specifications</h3>`;
                            
                            schemaArray.forEach(attr => {
                                // SECURE NAMING: Forces "Storage Capacity" to become "attr_storage_capacity"
                                const safeName = "attr_" + attr.name.toLowerCase().replace(/\s+/g, '_');
                                const isRequired = attr.required ? 'required' : '';
                                const star = attr.required ? '*' : '';

                                const fieldHtml = `
                                    <div class="form-group">
                                        <label>${attr.name} ${star}</label>
                                        <input type="text" name="${safeName}" class="form-control" ${isRequired}>
                                    </div>
                                `;
                                attributesContainer.innerHTML += fieldHtml;
                            });
                        }
                    })
                    .catch(error => {
                        console.error('Error fetching attributes:', error);
                    });
            }
        });

        // Fail-safe: Trigger the fetch immediately if the page loads with a category already selected
        if (categorySelector.value) {
            categorySelector.dispatchEvent(new Event('change'));
        }
    }
});

document.addEventListener('DOMContentLoaded', function() {
    const pricingSelect = document.getElementById('pricingTypeSelect');
    const basePriceGroup = document.getElementById('basePriceGroup');
    const basePriceInput = document.getElementById('basePriceInput');
    const packageBuilder = document.getElementById('packageBuilderContainer');
    const addPackageBtn = document.getElementById('add-package-btn');
    const packageRows = document.getElementById('package-rows');

    if (pricingSelect) {
        pricingSelect.addEventListener('change', function() {
            if (this.value === 'PACKAGES') {
                basePriceGroup.style.display = 'none';
                basePriceInput.removeAttribute('required');
                packageBuilder.style.display = 'block';
                packageBuilder.classList.remove('hidden-initial');
            } else if (this.value === 'QUOTE') {
                basePriceGroup.style.display = 'none';
                basePriceInput.removeAttribute('required');
                packageBuilder.style.display = 'none';
            } else {
                basePriceGroup.style.display = 'block';
                basePriceInput.setAttribute('required', 'true');
                packageBuilder.style.display = 'none';
            }
        });
    }

    if (addPackageBtn) {
        addPackageBtn.addEventListener('click', function() {
            const rowHtml = `
                <div class="variant-row package-row mt-15">
                    <div><input type="text" name="pkg_names[]" class="form-control" placeholder="Package Name"></div>
                    <div><input type="number" name="pkg_prices[]" class="form-control" step="0.01" placeholder="Price"></div>
                    <div><input type="text" name="pkg_durations[]" class="form-control" placeholder="Duration"></div>
                    <div><input type="text" name="pkg_features[]" class="form-control" placeholder="Features (comma separated)"></div>
                    <button type="button" class="btn-remove-variant" onclick="this.closest('.package-row').remove()">
                        <i class="fa-solid fa-trash"></i>
                    </button>
                </div>
            `;
            packageRows.insertAdjacentHTML('beforeend', rowHtml);
        });
    }
});