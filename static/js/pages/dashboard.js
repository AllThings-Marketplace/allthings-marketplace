document.addEventListener('DOMContentLoaded', function () {

    // === 1. Bank Details Capture ===
    const bankSelect = document.getElementById('bankSelect');
    const bankNameInput = document.getElementById('bankNameInput');

    if (bankSelect && bankNameInput) {
        bankSelect.addEventListener('change', function () {
            const selectedOption = this.options[this.selectedIndex];
            bankNameInput.value = selectedOption.getAttribute('data-name');
        });
    }

    // === 2. Provider Location Capture ===
    const locationBtn = document.getElementById('getLocationBtn');
    const latInput = document.getElementById('latInput');
    const lonInput = document.getElementById('lonInput');

    if (locationBtn && latInput && lonInput) {
        locationBtn.addEventListener('click', function () {
            if (navigator.geolocation) {
                navigator.geolocation.getCurrentPosition(
                    function (position) {
                        latInput.value = position.coords.latitude;
                        lonInput.value = position.coords.longitude;
                    },
                    function () {
                        alert("Error getting location. Please ensure location permissions are enabled for this site.");
                    },
                    { enableHighAccuracy: true }
                );
            } else {
                alert("Geolocation is not supported by your browser.");
            }
        });
    }

    // === 3. Variant Builder Logic (Add Product) ===
    const addVariantBtn = document.getElementById('add-variant-btn');
    const variantContainer = document.getElementById('variant-builder-container');

    if (addVariantBtn && variantContainer) {
        addVariantBtn.addEventListener('click', function () {
            variantContainer.classList.remove('hidden-initial');
            variantContainer.style.display = 'block';

            const row = document.createElement('div');
            row.className = 'variant-row';
            row.innerHTML = `
                <div class="form-group m-0">
                    <label class="text-12-muted">Option (e.g., Color)</label>
                    <input type="text" name="variant_names[]" class="form-control" placeholder="Size, Color, etc." required>
                </div>
                <div class="form-group m-0">
                    <label class="text-12-muted">Value (e.g., Red)</label>
                    <input type="text" name="variant_values[]" class="form-control" placeholder="Red, XL, 256GB" required>
                </div>
                <div class="form-group m-0">
                    <label class="text-12-muted">Price Override (NGN)</label>
                    <input type="number" name="variant_prices[]" class="form-control" step="0.01" placeholder="Optional">
                </div>
                <div class="form-group m-0">
                    <label class="text-12-muted">Stock</label>
                    <input type="number" name="variant_stocks[]" class="form-control" min="0" value="0" required>
                </div>
                <button type="button" class="btn-remove-variant" aria-label="Remove Option">
                    <i class="fa-solid fa-trash"></i>
                </button>
            `;
            variantContainer.appendChild(row);
        });
    }

    // Delegated Removal for Variant & Package Rows (No inline onclick needed)
    document.addEventListener('click', function (e) {
        const removeBtn = e.target.closest('.btn-remove-variant');
        if (!removeBtn) return;

        const row = removeBtn.closest('.variant-row');
        if (row) {
            row.remove();
            if (variantContainer && variantContainer.children.length === 0) {
                variantContainer.style.display = 'none';
            }
        }
    });

    // === 4. Unified Category Attributes Fetching (AJAX) ===
    const categorySelector = document.getElementById('category-selector');
    const attributesContainer = document.getElementById('dynamic-attributes-container');

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
                            attributesContainer.innerHTML = `<h3 class="checkout-section-title" style="grid-column: 1 / -1;"><i class="fa-solid fa-list icon-primary-spaced"></i> Specifications</h3>`;

                            schemaArray.forEach(attr => {
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

        if (categorySelector.value) {
            categorySelector.dispatchEvent(new Event('change'));
        }
    }

    // === 5. Service Pricing & Package Builder ===
    const pricingSelect = document.getElementById('pricingTypeSelect');
    const basePriceGroup = document.getElementById('basePriceGroup');
    const basePriceInput = document.getElementById('basePriceInput');
    const packageBuilder = document.getElementById('packageBuilderContainer');
    const addPackageBtn = document.getElementById('add-package-btn');
    const packageRows = document.getElementById('package-rows');

    if (pricingSelect) {
        function syncPricingUI() {
            if (pricingSelect.value === 'PACKAGES') {
                if (basePriceGroup) basePriceGroup.style.display = 'none';
                if (basePriceInput) basePriceInput.removeAttribute('required');
                if (packageBuilder) {
                    packageBuilder.style.display = 'block';
                    packageBuilder.classList.remove('hidden-initial');
                }
            } else if (pricingSelect.value === 'QUOTE') {
                if (basePriceGroup) basePriceGroup.style.display = 'none';
                if (basePriceInput) basePriceInput.removeAttribute('required');
                if (packageBuilder) packageBuilder.style.display = 'none';
            } else {
                if (basePriceGroup) basePriceGroup.style.display = 'block';
                if (basePriceInput) basePriceInput.setAttribute('required', 'true');
                if (packageBuilder) packageBuilder.style.display = 'none';
            }
        }
        pricingSelect.addEventListener('change', syncPricingUI);
        syncPricingUI();
    }

    if (addPackageBtn && packageRows) {
        addPackageBtn.addEventListener('click', function () {
            const rowHtml = `
                <div class="variant-row package-row mt-15">
                    <div><input type="text" name="pkg_names[]" class="form-control" placeholder="Package Name"></div>
                    <div><input type="number" name="pkg_prices[]" class="form-control" step="0.01" placeholder="Price"></div>
                    <div><input type="text" name="pkg_durations[]" class="form-control" placeholder="Duration"></div>
                    <div><input type="text" name="pkg_features[]" class="form-control" placeholder="Features (comma separated)"></div>
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
            container.innerHTML = items.map(item =>
                `<span class="scope-pill ${pillClass}"><i class="fa-solid ${iconClass}"></i> ${item}</span>`
            ).join('');
        }
        input.addEventListener('input', renderPills);
        renderPills();
    }

    bindScopePreview('whatsIncludedInput', 'includedPreviewPills', 'scope-pill-inc', 'fa-check');
    bindScopePreview('whatsExcludedInput', 'excludedPreviewPills', 'scope-pill-exc', 'fa-xmark');

    // === 7. Unified Multi-Photo Dropzone Previews & 8-Photo Guard ===
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
                previewGrid.style.display = 'none';
                if (warningBox) {
                    warningBox.classList.add('hidden-initial');
                    warningBox.style.display = 'none';
                }
                if (countBadge) {
                    countBadge.classList.add('hidden-initial');
                    countBadge.style.display = 'none';
                }
                if (submitBtn) submitBtn.disabled = false;
                return;
            }

            if (countBadge) {
                countBadge.classList.remove('hidden-initial');
                countBadge.style.display = 'inline-block';
                countBadge.textContent = `${files.length} / ${config.maxFiles} Selected`;
            }

            if (config.maxFiles && files.length > config.maxFiles) {
                if (warningBox) {
                    warningBox.innerHTML = `<i class="fa-solid fa-triangle-exclamation"></i> You selected ${files.length} photos. Please select a maximum of ${config.maxFiles} photos.`;
                    warningBox.classList.remove('hidden-initial');
                    warningBox.style.display = 'block';
                }
                if (submitBtn) submitBtn.disabled = true;
            } else {
                if (warningBox) {
                    warningBox.classList.add('hidden-initial');
                    warningBox.style.display = 'none';
                }
                if (submitBtn) submitBtn.disabled = false;
            }

            previewGrid.classList.remove('hidden-initial');
            previewGrid.style.display = 'grid';

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
                        <small class="text-12-muted truncate-text block">${file.name}</small>
                    </div>
                `;
                previewGrid.appendChild(card);

                reader.onload = function (e) {
                    const imgEl = card.querySelector('.preview-thumb-img');
                    if (imgEl) imgEl.src = e.target.result;
                };
                reader.readAsDataURL(file);
            });
        });
    }

    // Bind Add Product Photos (Max 8, First = Main Cover)
    initMultiPhotoPreview({
        inputId: 'addProductImagesInput',
        gridId: 'addProductPreviewGrid',
        warningId: 'addProductUploadWarning',
        badgeId: 'productPhotoCountBadge',
        submitId: 'addProductSubmitBtn',
        maxFiles: 8,
        roleFormatter: idx => (idx === 0 ? 'Main Cover' : `Gallery #${idx + 1}`)
    });

    // Bind Manage Product Photos Page (Max 8)
    initMultiPhotoPreview({
        inputId: 'productImagesInput',
        gridId: 'uploadPreviewGrid',
        warningId: 'uploadCountWarning',
        submitId: 'uploadSubmitBtn',
        maxFiles: 8,
        roleFormatter: () => 'Ready'
    });

    // Bind Service Portfolio Photos
    initMultiPhotoPreview({
        inputId: 'servicePortfolioInput',
        gridId: 'portfolioPreviewGrid',
        maxFiles: 12,
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
                coverBox.style.display = 'none';
                return;
            }
            if (coverName) coverName.textContent = file.name;
            const reader = new FileReader();
            reader.onload = function (e) {
                coverImg.src = e.target.result;
                coverBox.classList.remove('hidden-initial');
                coverBox.style.display = 'block';
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
                        sec.style.display = 'block';
                    } else {
                        sec.style.display = 'none';
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
                row.style.display = haystack.includes(query) ? '' : 'none';
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
                row.style.display = (statusMatch && searchMatch) ? '' : 'none';
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
});

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
        // Built-in electrical & service domain synonym dictionary
        const DOMAIN_SYNONYMS = {
            wire: ['cable', 'wires', 'cables', 'wiring', 'coil', 'copper', 'armoured', 'mm', 'coleman', 'cutix', 'trunking', 'conduit'],
            solar: ['inverter', 'battery', 'panel', 'mppt', 'charge', 'tubular', 'lithium', 'felicity', 'luminous', 'kva', 'hybrid'],
            lighting: ['bulb', 'led', 'chandelier', 'floodlight', 'lamp', 'spotlight', 'strip', 'ceiling', 'downlight', 'watt'],
            breaker: ['distribution', 'mcb', 'mccb', 'changeover', 'gear', 'fuse', 'isolator', 'contactor', 'stabilizer', 'avr', 'surge'],
            socket: ['switch', 'switches', 'sockets', 'extension', 'plug', 'wall', 'dimmer', 'gang'],
            tool: ['multimeter', 'tester', 'drill', 'plier', 'crimping', 'screwdriver', 'meter', 'clamp'],
            appliance: ['fan', 'heater', 'ac', 'air', 'conditioner', 'hvac', 'fridge', 'freezer', 'pump', 'extractor'],
            installation: ['install', 'wiring', 'rewiring', 'setup', 'mounting', 'earthing', 'piping', 'conduit'],
            repair: ['fix', 'fault', 'diagnosis', 'troubleshooting', 'maintenance', 'servicing', 'refill', 'compressor']
        };

        // Snapshot all original options for live search filtering
        const allOptions = Array.from(catSelect.options).map(opt => ({
            value: opt.value,
            text: opt.text,
            cleanName: opt.getAttribute('data-clean-name') || opt.text.replace(/^[-—\s]+/, '').trim(),
            keywords: (opt.getAttribute('data-keywords') || opt.text).toLowerCase(),
            className: opt.className,
            isSubcategory: opt.text.trim().startsWith('-')
        }));

        let userManuallySelectedCategory = false;
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
                    suggestionBar.style.display = 'none';
                    return;
                }

                // Expand tokens using domain synonyms
                const expandedTokens = new Set(tokens);
                tokens.forEach(token => {
                    Object.entries(DOMAIN_SYNONYMS).forEach(([groupKey, words]) => {
                        if (token.includes(groupKey) || words.some(w => token === w || (token.length >= 3 && w.startsWith(token)))) {
                            expandedTokens.add(groupKey);
                            words.forEach(w => expandedTokens.add(w));
                        }
                    });
                });

                // Score each category option
                const scored = [];
                allOptions.forEach(item => {
                    if (!item.value) return;
                    let score = 0;
                    const haystack = `${item.cleanName.toLowerCase()} ${item.keywords}`;

                    tokens.forEach(tok => {
                        if (item.cleanName.toLowerCase().includes(tok)) {
                            score += 6; // Direct category name hit
                        } else if (haystack.includes(tok)) {
                            score += 4; // Explicit keyword hit
                        }
                    });

                    expandedTokens.forEach(syn => {
                        if (haystack.includes(syn)) {
                            score += 2; // Synonym group hit
                        }
                    });

                    // Slight preference for specific subcategories over broad parent categories
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
                    suggestionBar.style.display = 'none';
                    return;
                }

                // Render clickable Smart Suggestion Pills
                suggestionPills.innerHTML = '';
                topMatches.forEach((match, idx) => {
                    const pill = document.createElement('button');
                    pill.type = 'button';
                    pill.className = `smart-cat-pill ${catSelect.value === match.value ? 'active' : ''}`;
                    pill.innerHTML = `<i class="fa-solid ${idx === 0 ? 'fa-bolt' : 'fa-tag'}"></i> ${match.cleanName}`;
                    pill.addEventListener('click', function () {
                        userManuallySelectedCategory = true;
                        // Reset search filter if option was hidden
                        if (catSearchInput && catSearchInput.value) {
                            catSearchInput.value = '';
                            catSearchInput.dispatchEvent(new Event('input'));
                        }
                        catSelect.value = match.value;
                        catSelect.dispatchEvent(new Event('change')); // Triggers dynamic attributes AJAX!
                        suggestionPills.querySelectorAll('.smart-cat-pill').forEach(p => p.classList.remove('active'));
                        pill.classList.add('active');
                    });
                    suggestionPills.appendChild(pill);
                });

                suggestionBar.classList.remove('hidden-initial');
                suggestionBar.style.display = 'flex';

                // Auto-select top high-confidence category if user hasn't manually picked one yet
                if (!userManuallySelectedCategory && topMatches[0].score >= 6 && catSelect.value !== topMatches[0].value) {
                    catSelect.value = topMatches[0].value;
                    catSelect.dispatchEvent(new Event('change'));
                    const firstPill = suggestionPills.querySelector('.smart-cat-pill');
                    if (firstPill) firstPill.classList.add('active');
                }
            });
        }
    } 