document.addEventListener('DOMContentLoaded', function () {

    // === 1. Bank Details Capture ===
    const bankSelect = document.getElementById('bankSelect');
    const bankNameInput = document.getElementById('bankNameInput');

    if (bankSelect && bankNameInput) {
        bankSelect.addEventListener('change', function () {
            const selectedOption = this.options[this.selectedIndex];
            bankNameInput.value = selectedOption ? (selectedOption.getAttribute('data-name') || '') : '';
        });
    }

    // === 2. Provider Location Capture ===
    const locationBtn = document.getElementById('getLocationBtn');
    const latInput = document.getElementById('latInput');
    const lonInput = document.getElementById('lonInput');

    if (locationBtn && latInput && lonInput) {
        locationBtn.addEventListener('click', function () {
            if (navigator.geolocation) {
                const originalHtml = locationBtn.innerHTML;
                locationBtn.disabled = true;
                locationBtn.innerHTML = '<i class="fa-solid fa-spinner fa-spin icon-spaced"></i> Capturing GPS...';

                navigator.geolocation.getCurrentPosition(
                    function (position) {
                        latInput.value = position.coords.latitude.toFixed(7);
                        lonInput.value = position.coords.longitude.toFixed(7);
                        locationBtn.disabled = false;
                        locationBtn.innerHTML = '<i class="fa-solid fa-circle-check icon-spaced"></i> GPS Coordinates Captured';
                    },
                    function () {
                        locationBtn.disabled = false;
                        locationBtn.innerHTML = originalHtml;
                        alert("Error getting location. Please ensure location permissions are enabled for this site.");
                    },
                    { enableHighAccuracy: true, timeout: 10000 }
                );
            } else {
                alert("Geolocation is not supported by your browser.");
            }
        });
    }

    // === 3. Variant Builder Logic (Add & Edit Product) ===
    const addVariantBtn = document.getElementById('add-variant-btn');
    const variantContainer = document.getElementById('variant-builder-container');

    if (addVariantBtn && variantContainer) {
        addVariantBtn.addEventListener('click', function () {
            variantContainer.classList.remove('hidden-initial');

            const row = document.createElement('div');
            row.className = 'variant-row';
            row.innerHTML = `
                <div class="form-group m-0">
                    <label class="text-12-muted">Option (e.g., Size, Color, Storage)</label>
                    <input type="text" name="variant_names[]" class="form-control" placeholder="Size, Color, Storage" required>
                </div>
                <div class="form-group m-0">
                    <label class="text-12-muted">Value (e.g., XL, Black, 256GB)</label>
                    <input type="text" name="variant_values[]" class="form-control" placeholder="XL, Black, 256GB" required>
                </div>
                <div class="form-group m-0">
                    <label class="text-12-muted">Price Override (NGN)</label>
                    <input type="number" name="variant_prices[]" class="form-control" step="0.01" placeholder="Optional">
                </div>
                <div class="form-group m-0">
                    <label class="text-12-muted">Stock</label>
                    <input type="number" name="variant_stocks[]" class="form-control" min="0" value="1" required>
                </div>
                <button type="button" class="btn-remove-variant" aria-label="Remove Option">
                    <i class="fa-solid fa-trash"></i>
                </button>
            `;
            variantContainer.appendChild(row);
        });
    }

    // Delegated Removal for Variant & Package Rows
    document.addEventListener('click', function (e) {
        const removeBtn = e.target.closest('.btn-remove-variant');
        if (!removeBtn) return;

        const row = removeBtn.closest('.variant-row');
        if (row) {
            row.remove();
            if (variantContainer && variantContainer.children.length === 0) {
                variantContainer.classList.add('hidden-initial');
            }
        }
    });

    // === 4. Unified Category Attributes Fetching (AJAX + Pre-fill on Edit) ===
    const categorySelector = document.getElementById('category-selector');
    const attributesContainer = document.getElementById('dynamic-attributes-container');
    const existingAttrsScript = document.getElementById('existingProductAttributes');
    let existingAttributes = {};

    if (existingAttrsScript) {
        try {
            existingAttributes = JSON.parse(existingAttrsScript.textContent || '{}') || {};
        } catch (err) {
            existingAttributes = {};
        }
    }

    if (categorySelector && attributesContainer) {
        categorySelector.addEventListener('change', function () {
            const categoryId = this.value;
            attributesContainer.innerHTML = '';

            if (categoryId) {
                fetch(`/api/category-attributes/${categoryId}/`)
                    .then(response => response.json())
                    .then(data => {
                        let schemaArray = data.schema;
                        if (typeof schemaArray === 'string') {
                            schemaArray = JSON.parse(schemaArray);
                        }

                        if (Array.isArray(schemaArray) && schemaArray.length > 0) {
                            const heading = document.createElement('h3');
                            heading.className = 'checkout-section-title full-grid-span m-0';
                            heading.innerHTML = '<i class="fa-solid fa-list icon-primary-spaced"></i> Category Specifications';
                            attributesContainer.appendChild(heading);

                            schemaArray.forEach(attr => {
                                const rawName = attr.name || '';
                                const safeName = "attr_" + rawName.toLowerCase().replace(/\s+/g, '_');
                                const savedValue = existingAttributes[rawName] || '';

                                const group = document.createElement('div');
                                group.className = 'form-group m-0';

                                const label = document.createElement('label');
                                label.className = 'form-label-dark';
                                label.textContent = rawName + (attr.required ? ' *' : '');

                                const input = document.createElement('input');
                                input.type = 'text';
                                input.name = safeName;
                                input.className = 'form-control';
                                input.value = savedValue;
                                if (attr.required) {
                                    input.required = true;
                                }

                                group.appendChild(label);
                                group.appendChild(input);
                                attributesContainer.appendChild(group);
                            });
                        }
                    })
                    .catch(error => {
                        console.error('Error fetching attributes:', error);
                    });
            }
        });

        if (categorySelector.value) {
            categorySelector.dispatchEvent(new Event('change'));
        }
    }

    // === 5. Service Mode & Pricing / Package Builder ===
    const serviceModeSelect = document.getElementById('serviceModeSelect');
    const serviceRadiusGroup = document.getElementById('serviceRadiusGroup');
    const serviceRadiusInput = document.getElementById('serviceRadiusInput');

    if (serviceModeSelect && serviceRadiusGroup) {
        function syncServiceModeUI() {
            const mode = serviceModeSelect.value;
            if (mode === 'PROVIDER_LOC' || mode === 'REMOTE') {
                serviceRadiusGroup.classList.add('hidden-initial');
                if (serviceRadiusInput) serviceRadiusInput.value = '';
            } else {
                serviceRadiusGroup.classList.remove('hidden-initial');
            }
        }
        serviceModeSelect.addEventListener('change', syncServiceModeUI);
        syncServiceModeUI();
    }

    const pricingSelect = document.getElementById('pricingTypeSelect');
    const basePriceGroup = document.getElementById('basePriceGroup');
    const basePriceInput = document.getElementById('basePriceInput');
    const packageBuilder = document.getElementById('packageBuilderContainer');
    const addPackageBtn = document.getElementById('add-package-btn');
    const packageRows = document.getElementById('package-rows');

    if (pricingSelect) {
        function syncPricingUI() {
            if (pricingSelect.value === 'PACKAGES') {
                if (basePriceGroup) basePriceGroup.classList.add('hidden-initial');
                if (basePriceInput) basePriceInput.removeAttribute('required');
                if (packageBuilder) packageBuilder.classList.remove('hidden-initial');
            } else if (pricingSelect.value === 'QUOTE') {
                if (basePriceGroup) basePriceGroup.classList.add('hidden-initial');
                if (basePriceInput) basePriceInput.removeAttribute('required');
                if (packageBuilder) packageBuilder.classList.add('hidden-initial');
            } else {
                if (basePriceGroup) basePriceGroup.classList.remove('hidden-initial');
                if (basePriceInput) basePriceInput.setAttribute('required', 'true');
                if (packageBuilder) packageBuilder.classList.add('hidden-initial');
            }
        }
        pricingSelect.addEventListener('change', syncPricingUI);
        syncPricingUI();
    }

    if (addPackageBtn && packageRows) {
        addPackageBtn.addEventListener('click', function () {
            const rowHtml = `
                <div class="variant-row package-row mt-15">
                    <div>
                        <small>Package Name</small>
                        <input type="text" name="pkg_names[]" class="form-control" placeholder="e.g., Standard">
                    </div>
                    <div>
                        <small>Price (NGN)</small>
                        <input type="number" name="pkg_prices[]" class="form-control" step="0.01" placeholder="25000">
                    </div>
                    <div>
                        <small>Est. Duration</small>
                        <input type="text" name="pkg_durations[]" class="form-control" placeholder="e.g., 2 Days">
                    </div>
                    <div>
                        <small>Features (comma separated)</small>
                        <input type="text" name="pkg_features[]" class="form-control" placeholder="Core delivery, Support">
                    </div>
                    <button type="button" class="btn-remove-variant" aria-label="Remove Package">
                        <i class="fa-solid fa-trash"></i>
                    </button>
                </div>
            `;
            packageRows.insertAdjacentHTML('beforeend', rowHtml);
        });
    }

    // === 6. Service Scope-of-Work Live Comma Pill Previews ===
    function bindScopePreview(textareaId, containerId, pillClass, iconClass) {
        const input = document.getElementById(textareaId);
        const container = document.getElementById(containerId);
        if (!input || !container) return;

        function renderPills() {
            const items = input.value.split(',').map(s => s.trim()).filter(Boolean);
            container.innerHTML = '';
            items.forEach(item => {
                const span = document.createElement('span');
                span.className = `scope-pill ${pillClass}`;
                const icon = document.createElement('i');
                icon.className = `fa-solid ${iconClass}`;
                span.appendChild(icon);
                span.appendChild(document.createTextNode(' ' + item));
                container.appendChild(span);
            });
        }
        input.addEventListener('input', renderPills);
        renderPills();
    }

    bindScopePreview('whatsIncludedInput', 'includedPreviewPills', 'scope-pill-inc', 'fa-check');
    bindScopePreview('whatsExcludedInput', 'excludedPreviewPills', 'scope-pill-exc', 'fa-xmark');

    // === 7. Unified Multi-Photo Dropzone Previews & Max-Photo Guard ===
    function initMultiPhotoPreview(config) {
        const fileInput = document.getElementById(config.inputId);
        const previewGrid = document.getElementById(config.gridId);
        const warningBox = config.warningId ? document.getElementById(config.warningId) : null;
        const countBadge = config.badgeId ? document.getElementById(config.badgeId) : null;
        const submitBtn = config.submitId ? document.getElementById(config.submitId) : null;

        if (!fileInput || !previewGrid) return;

        fileInput.addEventListener('change', function () {
            previewGrid.innerHTML = '';
            const files = Array.from(this.files || []);

            if (files.length === 0) {
                previewGrid.classList.add('hidden-initial');
                if (warningBox) warningBox.classList.add('hidden-initial');
                if (countBadge) countBadge.classList.add('hidden-initial');
                if (submitBtn) submitBtn.disabled = false;
                return;
            }

            if (countBadge) {
                countBadge.classList.remove('hidden-initial');
                countBadge.textContent = `${files.length} / ${config.maxFiles} Selected`;
            }

            if (config.maxFiles && files.length > config.maxFiles) {
                if (warningBox) {
                    warningBox.innerHTML = `<i class="fa-solid fa-triangle-exclamation"></i> You selected ${files.length} photos. Maximum allowed is ${config.maxFiles} photos.`;
                    warningBox.classList.remove('hidden-initial');
                }
                if (submitBtn) submitBtn.disabled = true;
            } else {
                if (warningBox) warningBox.classList.add('hidden-initial');
                if (submitBtn) submitBtn.disabled = false;
            }

            previewGrid.classList.remove('hidden-initial');

            const limit = config.maxFiles || files.length;
            files.slice(0, limit).forEach((file, idx) => {
                const reader = new FileReader();
                const roleLabel = config.roleFormatter ? config.roleFormatter(idx) : `Photo #${idx + 1}`;
                const card = document.createElement('div');
                card.className = 'existing-photo-card';
                card.innerHTML = `
                    <div class="photo-thumb-wrapper">
                        <img src="" alt="Preview" class="preview-thumb-img">
                        <span class="photo-role-badge">${roleLabel}</span>
                    </div>
                    <div class="photo-meta-bar">
                        <small class="text-12-muted truncate-text block"></small>
                    </div>
                `;
                card.querySelector('small').textContent = file.name;
                previewGrid.appendChild(card);

                reader.onload = function (e) {
                    const imgEl = card.querySelector('.preview-thumb-img');
                    if (imgEl) imgEl.src = e.target.result;
                };
                reader.readAsDataURL(file);
            });
        });
    }

    // Bind Add Product Photos (Matches MAX_PRODUCT_IMAGES = 6 in validators.py)
    initMultiPhotoPreview({
        inputId: 'addProductImagesInput',
        gridId: 'addProductPreviewGrid',
        warningId: 'addProductUploadWarning',
        badgeId: 'productPhotoCountBadge',
        submitId: 'addProductSubmitBtn',
        maxFiles: 6,
        roleFormatter: idx => (idx === 0 ? 'Main Cover' : `Gallery #${idx + 1}`)
    });

    // Bind Manage Product Photos Page (Max 6)
    initMultiPhotoPreview({
        inputId: 'productImagesInput',
        gridId: 'uploadPreviewGrid',
        warningId: 'uploadCountWarning',
        submitId: 'uploadSubmitBtn',
        maxFiles: 6,
        roleFormatter: () => 'Ready'
    });

    // Bind Service Portfolio Photos (Matches MAX_PORTFOLIO_IMAGES = 8 in validators.py)
    initMultiPhotoPreview({
        inputId: 'servicePortfolioInput',
        gridId: 'portfolioPreviewGrid',
        maxFiles: 8,
        roleFormatter: idx => `Portfolio #${idx + 1}`
    });

    // Bind Service Primary Cover Banner Preview
    const coverInput = document.getElementById('serviceCoverInput');
    const coverBox = document.getElementById('coverPreviewBox');
    const coverImg = document.getElementById('coverPreviewImg');
    const coverName = document.getElementById('coverPreviewName');

    if (coverInput && coverBox && coverImg) {
        coverInput.addEventListener('change', function () {
            const file = this.files && this.files[0];
            if (!file) {
                coverBox.classList.add('hidden-initial');
                return;
            }
            if (coverName) coverName.textContent = file.name;
            const reader = new FileReader();
            reader.onload = function (e) {
                coverImg.src = e.target.result;
                coverBox.classList.remove('hidden-initial');
            };
            reader.readAsDataURL(file);
        });
    }

    // === 8. Provider Dashboard Workspace Tabs & Catalog Search ===
    const tabButtons = document.querySelectorAll('#dashboardTabsBar .dash-tab-btn');
    const tabSections = document.querySelectorAll('.dash-tab-section');

    if (tabButtons.length > 0) {
        tabButtons.forEach(btn => {
            btn.addEventListener('click', function () {
                const target = this.dataset.tab;
                tabButtons.forEach(b => b.classList.remove('active'));
                this.classList.add('active');

                tabSections.forEach(sec => {
                    if (target === 'all' || sec.dataset.section === target) {
                        sec.classList.remove('hidden-initial');
                    } else {
                        sec.classList.add('hidden-initial');
                    }
                });
            });
        });
    }

    const catalogSearch = document.getElementById('catalogSearchInput');
    if (catalogSearch) {
        catalogSearch.addEventListener('input', function () {
            const query = this.value.trim().toLowerCase();
            document.querySelectorAll('.catalog-product-row').forEach(row => {
                const haystack = row.dataset.search || '';
                row.classList.toggle('hidden-initial', !haystack.includes(query));
            });
        });
    }

    // === 9. Vendor Store Orders Filter & Search ===
    const orderFilterBtns = document.querySelectorAll('#orderStatusFilters .dash-tab-btn');
    const vendorOrderSearch = document.getElementById('vendorOrderSearch');
    const vendorOrderRows = document.querySelectorAll('.vendor-order-row');

    if (orderFilterBtns.length > 0 || vendorOrderSearch) {
        let activeStatuses = 'ALL';

        function applyVendorOrderFilters() {
            const q = (vendorOrderSearch ? vendorOrderSearch.value : '').trim().toLowerCase();
            vendorOrderRows.forEach(row => {
                const rowStatus = row.dataset.status || '';
                const rowSearch = row.dataset.search || '';
                const statusMatch = activeStatuses === 'ALL' || activeStatuses.split(',').includes(rowStatus);
                const searchMatch = !q || rowSearch.includes(q);
                row.classList.toggle('hidden-initial', !(statusMatch && searchMatch));
            });
        }

        orderFilterBtns.forEach(btn => {
            btn.addEventListener('click', function () {
                orderFilterBtns.forEach(b => b.classList.remove('active'));
                this.classList.add('active');
                activeStatuses = this.dataset.status;
                applyVendorOrderFilters();
            });
        });

        if (vendorOrderSearch) {
            vendorOrderSearch.addEventListener('input', applyVendorOrderFilters);
        }
    }

    // === 10. Max Withdrawal Amount Button ===
    const maxWithdrawBtn = document.getElementById('maxWithdrawBtn');
    const withdrawAmountInput = document.getElementById('withdrawAmountInput');

    if (maxWithdrawBtn && withdrawAmountInput) {
        maxWithdrawBtn.addEventListener('click', function () {
            withdrawAmountInput.value = this.dataset.max || '';
        });
    }

    // === 11. Smart Category Auto-Guesser & Live Category Search ===
    const titleInput = document.getElementById('listingTitleInput') || document.querySelector('input[name="name"]');
    const catSelect = document.getElementById('category-selector');
    const catSearchInput = document.getElementById('categorySearchInput');
    const suggestionBar = document.getElementById('smartCategorySuggestionBar');
    const suggestionPills = document.getElementById('smartCategoryPills');
    const matchStatus = document.getElementById('categoryMatchStatus');

    if (catSelect) {
        // Multi-department synonym dictionary covering all 13 product & 8 service departments
        const DOMAIN_SYNONYMS = {
            phone: ['iphone', 'samsung', 'galaxy', 'redmi', 'xiaomi', 'tecno', 'infinix', 'itel', 'smartphone', 'android', 'ios', 'tablet', 'ipad', 'earbuds', 'airpods', 'powerbank', 'charger', 'oraimo', 'smartwatch'],
            laptop: ['macbook', 'hp', 'dell', 'lenovo', 'thinkpad', 'elitebook', 'pavilion', 'asus', 'acer', 'pc', 'desktop', 'monitor', 'ssd', 'ram', 'keyboard', 'mouse', 'router', 'mifi', 'starlink', 'printer'],
            electronics: ['tv', 'television', 'qled', 'oled', 'hisense', 'lg', 'sony', 'soundbar', 'speaker', 'home theatre', 'ps5', 'ps4', 'playstation', 'xbox', 'nintendo', 'camera', 'canon', 'drone', 'gimbal'],
            appliance: ['fridge', 'refrigerator', 'freezer', 'dispenser', 'ac', 'air conditioner', 'split', 'fan', 'rechargeable', 'washing machine', 'blender', 'microwave', 'air fryer', 'cooker', 'gas', 'kettle', 'iron'],
            solar: ['inverter', 'battery', 'panel', 'mppt', 'tubular', 'lithium', 'lifepo4', 'felicity', 'luminous', 'deye', 'growatt', 'kva', 'hybrid', 'charge controller'],
            wire: ['cable', 'wires', 'cables', 'wiring', 'coil', 'copper', 'armoured', 'mm', 'coleman', 'cutix', 'trunking', 'conduit', 'breaker', 'mcb', 'mccb', 'changeover', 'stabilizer', 'avr', 'socket', 'switch', 'chandelier', 'led', 'floodlight'],
            fashion: ['shirt', 'trouser', 'jeans', 'senator', 'kaftan', 'agbada', 'dress', 'gown', 'abaya', 'ankara', 'lace', 'aso ebi', 'sneakers', 'shoes', 'heels', 'loafers', 'handbag', 'bag', 'watch', 'jewelry', 'sunglasses'],
            beauty: ['wig', 'frontal', 'closure', 'human hair', 'bone straight', 'braids', 'perfume', 'fragrance', 'skincare', 'cream', 'serum', 'makeup', 'lipstick', 'foundation', 'lashes', 'nails', 'clipper', 'spa'],
            grocery: ['rice', 'beans', 'garri', 'yam', 'noodles', 'indomie', 'pasta', 'spaghetti', 'oil', 'groundnut', 'palm oil', 'tomato', 'seasoning', 'maggi', 'milk', 'milo', 'cereal', 'juice', 'wine', 'water', 'biscuit'],
            furniture: ['sofa', 'couch', 'chair', 'table', 'desk', 'bed', 'mattress', 'mouka', 'wardrobe', 'shelf', 'curtain', 'blind', 'rug', 'carpet', 'bedsheet', 'duvet', 'pillow'],
            baby: ['diaper', 'pampers', 'huggies', 'wipes', 'stroller', 'cot', 'walker', 'feeding bottle', 'formula', 'toy', 'lego'],
            auto: ['tyre', 'tire', 'engine oil', 'mobil', 'total', 'castrol', 'car battery', 'wiper', 'brake pad', 'spark plug', 'dashcam', 'helmet', 'motorcycle'],
            software: ['website', 'web', 'django', 'python', 'react', 'frontend', 'backend', 'fullstack', 'app', 'mobile app', 'ui', 'ux', 'graphic', 'logo', 'flyer', 'branding', 'video editing', 'seo', 'marketing'],
            salon: ['hair', 'braiding', 'wig installation', 'barbing', 'haircut', 'locks', 'dreadlocks', 'gele', 'bridal', 'pedicure', 'manicure', 'microblading', 'tailor', 'tailoring', 'bespoke'],
            cleaning: ['deep cleaning', 'fumigation', 'pest control', 'laundry', 'dry cleaning', 'ironing', 'janitorial', 'post construction'],
            catering: ['catering', 'cake', 'small chops', 'chef', 'food tray', 'event', 'decorator', 'dj', 'mc', 'photography', 'videography'],
            mechanic: ['mechanic', 'mechatronics', 'obd', 'diagnostics', 'car wash', 'detailing', 'panel beating', 'painting', 'haulage', 'relocation', 'dispatch', 'delivery'],
            tutoring: ['tutor', 'tutoring', 'mentorship', 'coding', 'training', 'lesson', 'waec', 'jamb', 'ielts', 'music', 'driving', 'cac', 'tax', 'legal', 'architect', 'interior design']
        };

        const allOptions = Array.from(catSelect.options).map(opt => ({
            value: opt.value,
            text: opt.text,
            cleanName: opt.getAttribute('data-clean-name') || opt.text.replace(/^[-—\s]+/, '').trim(),
            keywords: (opt.getAttribute('data-keywords') || opt.text).toLowerCase(),
            className: opt.className,
            isSubcategory: opt.text.trim().startsWith('-')
        }));

        let userManuallySelectedCategory = Boolean(catSelect.value);
        catSelect.addEventListener('change', function (e) {
            if (e.isTrusted) {
                userManuallySelectedCategory = true;
            }
        });

        // A. Live Category Dropdown Search Filter
        if (catSearchInput) {
            catSearchInput.addEventListener('input', function () {
                const query = this.value.trim().toLowerCase();
                const currentSelectedVal = catSelect.value;

                catSelect.innerHTML = '';
                let matchCount = 0;

                allOptions.forEach(item => {
                    if (!item.value) {
                        const placeholderOpt = document.createElement('option');
                        placeholderOpt.value = '';
                        placeholderOpt.textContent = item.text;
                        catSelect.appendChild(placeholderOpt);
                        return;
                    }

                    const matches = !query || item.text.toLowerCase().includes(query) || item.keywords.includes(query);
                    if (matches) {
                        matchCount++;
                        const opt = document.createElement('option');
                        opt.value = item.value;
                        opt.textContent = item.text;
                        opt.className = item.className;
                        opt.setAttribute('data-keywords', item.keywords);
                        opt.setAttribute('data-clean-name', item.cleanName);
                        if (item.value === currentSelectedVal) {
                            opt.selected = true;
                        }
                        catSelect.appendChild(opt);
                    }
                });

                if (matchStatus) {
                    matchStatus.textContent = query ? `${matchCount} match${matchCount === 1 ? '' : 'es'}` : '';
                }
            });
        }

        // B. Smart Category Guesser from Product / Service Name
        if (titleInput && suggestionBar && suggestionPills) {
            titleInput.addEventListener('input', function () {
                const rawTitle = this.value.trim().toLowerCase();
                const tokens = rawTitle.split(/[\s,./\-()]+/).filter(t => t.length >= 2);

                if (tokens.length === 0) {
                    suggestionBar.classList.add('hidden-initial');
                    return;
                }

                const expandedTokens = new Set(tokens);
                tokens.forEach(token => {
                    Object.entries(DOMAIN_SYNONYMS).forEach(([groupKey, words]) => {
                        if (token.includes(groupKey) || words.some(w => token === w || (token.length >= 3 && w.startsWith(token)))) {
                            expandedTokens.add(groupKey);
                            words.forEach(w => expandedTokens.add(w));
                        }
                    });
                });

                const scored = [];
                allOptions.forEach(item => {
                    if (!item.value) return;
                    let score = 0;
                    const haystack = `${item.cleanName.toLowerCase()} ${item.keywords}`;

                    tokens.forEach(tok => {
                        if (item.cleanName.toLowerCase().includes(tok)) {
                            score += 6;
                        } else if (haystack.includes(tok)) {
                            score += 4;
                        }
                    });

                    expandedTokens.forEach(syn => {
                        if (haystack.includes(syn)) {
                            score += 2;
                        }
                    });

                    if (score > 0 && item.isSubcategory) {
                        score += 1;
                    }

                    if (score > 0) {
                        scored.push({ ...item, score });
                    }
                });

                scored.sort((a, b) => b.score - a.score);
                const topMatches = scored.slice(0, 3);

                if (topMatches.length === 0) {
                    suggestionBar.classList.add('hidden-initial');
                    return;
                }

                suggestionPills.innerHTML = '';
                topMatches.forEach((match, idx) => {
                    const pill = document.createElement('button');
                    pill.type = 'button';
                    pill.className = `smart-cat-pill ${catSelect.value === match.value ? 'active' : ''}`;
                    pill.innerHTML = `<i class="fa-solid ${idx === 0 ? 'fa-bolt' : 'fa-tag'}"></i> `;
                    pill.appendChild(document.createTextNode(match.cleanName));

                    pill.addEventListener('click', function () {
                        userManuallySelectedCategory = true;
                        if (catSearchInput && catSearchInput.value) {
                            catSearchInput.value = '';
                            catSearchInput.dispatchEvent(new Event('input'));
                        }
                        catSelect.value = match.value;
                        catSelect.dispatchEvent(new Event('change'));
                        suggestionPills.querySelectorAll('.smart-cat-pill').forEach(p => p.classList.remove('active'));
                        pill.classList.add('active');
                    });
                    suggestionPills.appendChild(pill);
                });

                suggestionBar.classList.remove('hidden-initial');

                if (!userManuallySelectedCategory && topMatches[0].score >= 6 && catSelect.value !== topMatches[0].value) {
                    catSelect.value = topMatches[0].value;
                    catSelect.dispatchEvent(new Event('change'));
                    const firstPill = suggestionPills.querySelector('.smart-cat-pill');
                    if (firstPill) firstPill.classList.add('active');
                }
            });
        }
    }
});