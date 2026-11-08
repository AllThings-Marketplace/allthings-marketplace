document.addEventListener('DOMContentLoaded', function () {
    const CUSTOMER_TOUR_KEY = 'allthings_customer_tour_done_v1';
    const PROVIDER_TOUR_KEY = 'allthings_provider_tour_done_v1';
    const CHECKLIST_DISMISSED_KEY = 'allthings_setup_checklist_hidden_v1';

    // === 1. Role-Aware Tour Step Definitions (Desktop & Compact Mobile Targets) ===
    const TOUR_SETS = {
        customer: [
            {
                selector: '#globalSearchForm',
                mobileSelector: '#globalSearchForm',
                badge: 'Customer Tour',
                title: 'Find Products & Professionals Fast',
                body: 'Search by product name, brand, budget (e.g. "solar inverter under 250k"), or service specialty across Nigeria.'
            },
            {
                selector: '.trust-strip',
                mobileSelector: '.trust-strip, .feed-greeting-box',
                badge: 'Escrow Protection',
                title: '100% Escrow-Protected Shopping',
                body: 'Your payment is held safely in AllThings Escrow and released to the vendor only after you inspect your delivery and share your 6-digit PIN.'
            },
            {
                selector: '#marketplaceSidebar',
                mobileSelector: '#mobileFilterToggleBtn, #mobileMenuBtn',
                badge: 'Departments & Filters',
                title: 'Browse Products & Service Categories',
                body: 'Tap the menu or filter button to browse Product and Service departments, set your NGN budget, or filter by rating.'
            },
            {
                selector: '.sourcing-home-callout',
                mobileSelector: '.sourcing-home-callout, #mobileMenuBtn',
                badge: 'Custom Sourcing',
                title: "Can't Find an Item? Request It",
                body: 'Post what you need and verified AllThings vendors and service professionals will pitch matching offers to you.'
            },
            {
                selector: '.nav-cart-wrapper',
                mobileSelector: '.nav-cart-wrapper',
                badge: 'Checkout & PINs',
                title: 'Compare Live Courier Rates at Checkout',
                body: 'Add items to your cart to compare live delivery rates from AllThings Express, GIG Logistics, and Inter-State Waybill.'
            }
        ],
        vendor: [
            {
                selector: '#providerSetupChecklist',
                mobileSelector: '.setup-checklist-header',
                badge: 'Vendor Tour',
                title: 'Complete Your Store Setup Checklist',
                body: 'Track your 5 core store milestones here so your products rank higher in AllThings search results.'
            },
            {
                selector: '.kpi-grid',
                mobileSelector: '.kpi-card:first-child',
                badge: 'Escrow Wallet',
                title: 'Track Escrow & Cleared Earnings',
                body: 'Paid customer orders appear in "Locked in Escrow" first and move to "Available for Withdrawal" once the buyer confirms their 6-digit Delivery PIN.'
            },
            {
                selector: '#tourStoreOrdersBtn',
                mobileSelector: '#tourStoreOrdersBtn, .dashboard-actions',
                badge: 'Order Fulfillment',
                title: 'Accept Orders & Dispatch with Pickup PINs',
                body: 'Open Store Orders to accept paid items, mark packages Ready for Pickup, and hand them to the courier using your 6-digit Pickup PIN.'
            },
            {
                selector: '#tourAddProductBtn',
                mobileSelector: '#tourAddProductBtn, .dashboard-actions',
                badge: 'Add Inventory',
                title: 'Publish Products with Studio Photo AI',
                body: 'Upload up to 6 photos per product. Our smart category guesser and background processor prepare your listing automatically.'
            },
            {
                selector: '#dashboardTabsBar',
                mobileSelector: '#dashboardTabsBar',
                badge: 'Workspace Tabs',
                title: 'Switch Between Catalog, Buyer Leads & Payouts',
                body: 'Use these workspace tabs to filter your product catalog, pitch products to open Buyer Leads, or withdraw cleared funds to your Nigerian bank.'
            }
        ],
        service: [
            {
                selector: '#providerSetupChecklist',
                mobileSelector: '.setup-checklist-header',
                badge: 'Service Pro Tour',
                title: 'Complete Your Practice Setup',
                body: 'Finish your 5 setup milestones so clients in your state can discover and book your services.'
            },
            {
                selector: '.kpi-grid',
                mobileSelector: '.kpi-card:first-child',
                badge: 'Escrow Wallet',
                title: 'Escrow-Backed Service Earnings',
                body: 'Clients fund escrow before you begin work. Once the job is confirmed completed, your earnings unlock for instant bank withdrawal.'
            },
            {
                selector: '#tourAddServiceBtn',
                mobileSelector: '#tourAddServiceBtn, .dashboard-actions',
                badge: 'Service Listings',
                title: 'List Fixed, Package, or Custom Quote Services',
                body: 'Publish your service packages, travel radius, included scope of work, and portfolio photos.'
            },
            {
                selector: '#dashboardTabsBar',
                mobileSelector: '#dashboardTabsBar',
                badge: 'Bookings & Leads',
                title: 'Manage Bookings, Quotes & Buyer Leads',
                body: 'Switch tabs to accept scheduled bookings, send itemized Labor + Materials custom quotes, or pitch your services to open Buyer Leads.'
            }
        ]
    };

    function isElementVisible(el) {
        if (!el) return false;
        const rect = el.getBoundingClientRect();
        const style = window.getComputedStyle(el);
        return style.display !== 'none' && style.visibility !== 'hidden' && rect.width > 0 && rect.height > 0;
    }

    function pickVisibleElement(selectorList) {
        if (!selectorList) return null;
        const parts = selectorList.split(',').map(s => s.trim()).filter(Boolean);
        for (let i = 0; i < parts.length; i++) {
            const candidate = document.querySelector(parts[i]);
            if (isElementVisible(candidate)) {
                return candidate;
            }
        }
        return null;
    }

    function resolveActiveSteps(roleKey) {
        const rawSteps = TOUR_SETS[roleKey] || TOUR_SETS.customer;
        const isMobile = window.innerWidth <= 768;
        const resolved = [];

        rawSteps.forEach(step => {
            let targetEl = null;
            if (isMobile && step.mobileSelector) {
                targetEl = pickVisibleElement(step.mobileSelector);
            }
            if (!targetEl) {
                targetEl = pickVisibleElement(step.selector);
            }
            if (targetEl) {
                resolved.push({ ...step, element: targetEl });
            }
        });
        return resolved;
    }

    function detectCurrentTourRole() {
        const dashWrapper = document.getElementById('providerDashboardRoot');
        if (dashWrapper) {
            const pType = (dashWrapper.getAttribute('data-provider-type') || 'VENDOR').toUpperCase();
            if (pType === 'SERVICE') return 'service';
            return 'vendor';
        }
        return 'customer';
    }

    // === 2. Fixed Viewport Spotlight Runner (Mobile & Desktop Safe) ===
    let activeTargetEl = null;
    let spotlightRingEl = null;
    let tooltipEl = null;
    let BoundRepositionHandler = null;

    function updateSpotlightPosition() {
        if (!activeTargetEl || !spotlightRingEl) return;

        const rect = activeTargetEl.getBoundingClientRect();
        const isMobile = window.innerWidth <= 768;
        const pad = isMobile ? 5 : 8;
        const maxWinW = document.documentElement.clientWidth || window.innerWidth;
        const maxWinH = window.innerHeight;

        const left = Math.max(6, Math.round(rect.left - pad));
        const top = Math.max(6, Math.round(rect.top - pad));
        const width = Math.max(40, Math.min(maxWinW - left - 6, Math.round(rect.width + pad * 2)));
        // Clamp spotlight height on mobile if an element is taller than 40% of the screen
        const maxAllowedHeight = isMobile ? Math.round(maxWinH * 0.40) : maxWinH - 20;
        const height = Math.max(28, Math.min(maxAllowedHeight, Math.round(rect.height + pad * 2)));

        spotlightRingEl.style.left = `${left}px`;
        spotlightRingEl.style.top = `${top}px`;
        spotlightRingEl.style.width = `${width}px`;
        spotlightRingEl.style.height = `${height}px`;

        if (tooltipEl) {
            const tooltipHeight = tooltipEl.offsetHeight || 195;
            const bottomSafeBoundary = maxWinH - tooltipHeight - 24;
            // Dock tooltip near the top only if the highlighted target overlaps the bottom tooltip zone
            if ((top + height) > bottomSafeBoundary && top > (tooltipHeight + 36)) {
                tooltipEl.classList.add('dock-top');
            } else {
                tooltipEl.classList.remove('dock-top');
            }
        }
    }

    function scrollTargetIntoMobileSafeZone(targetEl) {
        if (!targetEl) return;

        const navbar = document.querySelector('.navbar');
        const isInsideNavbar = navbar && navbar.contains(targetEl);

        if (isInsideNavbar) {
            window.scrollTo({ top: 0, behavior: 'smooth' });
            return;
        }

        const navHeight = navbar ? navbar.offsetHeight : 72;
        const rect = targetEl.getBoundingClientRect();
        const absoluteElementTop = window.pageYOffset + rect.top;
        // Position the target comfortably below the sticky navbar and well above the bottom tooltip card
        const topClearance = navHeight + 18;
        const targetScrollY = Math.max(0, absoluteElementTop - topClearance);

        window.scrollTo({
            top: targetScrollY,
            behavior: 'smooth'
        });
    }

    function cleanupTourDOM() {
        document.body.classList.remove('tour-running');

        if (BoundRepositionHandler) {
            window.removeEventListener('scroll', BoundRepositionHandler, { passive: true });
            window.removeEventListener('resize', BoundRepositionHandler);
            BoundRepositionHandler = null;
        }
        if (spotlightRingEl) {
            spotlightRingEl.remove();
            spotlightRingEl = null;
        }
        if (tooltipEl) {
            tooltipEl.remove();
            tooltipEl = null;
        }
        activeTargetEl = null;
    }

    function startGuidedTour(forceRole) {
        cleanupTourDOM();
        const banner = document.getElementById('tourWelcomeBanner');
        if (banner) banner.classList.add('hidden-initial');

        const role = forceRole || detectCurrentTourRole();
        const storageKey = role === 'customer' ? CUSTOMER_TOUR_KEY : PROVIDER_TOUR_KEY;
        const steps = resolveActiveSteps(role);

        if (steps.length === 0) return;

        document.body.classList.add('tour-running');

        spotlightRingEl = document.createElement('div');
        spotlightRingEl.id = 'tourSpotlightRing';
        spotlightRingEl.className = 'tour-spotlight-ring';
        document.body.appendChild(spotlightRingEl);

        tooltipEl = document.createElement('aside');
        // Do NOT add animate-fade-in here because global.css sets transform: none !important on mobile
        tooltipEl.className = 'tour-tooltip-card';
        tooltipEl.setAttribute('role', 'dialog');
        tooltipEl.setAttribute('aria-live', 'polite');
        document.body.appendChild(tooltipEl);

        BoundRepositionHandler = function () {
            window.requestAnimationFrame(updateSpotlightPosition);
        };
        window.addEventListener('scroll', BoundRepositionHandler, { passive: true });
        window.addEventListener('resize', BoundRepositionHandler);

        let currentIndex = 0;

        function renderStep(idx) {
            const step = steps[idx];
            activeTargetEl = step.element;

            const isFirst = idx === 0;
            const isLast = idx === steps.length - 1;

            tooltipEl.innerHTML = `
                <div class="tour-tooltip-top">
                    <span class="tour-step-badge">
                        <i class="fa-solid fa-compass"></i> ${step.badge} &bull; ${idx + 1} of ${steps.length}
                    </span>
                    <button type="button" class="tour-skip-btn" id="tourSkipBtn">Skip Tour</button>
                </div>
                <h4 class="tour-tooltip-title">${step.title}</h4>
                <p class="tour-tooltip-body">${step.body}</p>
                <div class="tour-tooltip-footer">
                    <button type="button" class="action-btn btn-outline action-sm ${isFirst ? 'hidden-initial' : ''}" id="tourPrevBtn">
                        &larr; Back
                    </button>
                    <div class="tour-nav-btns">
                        <button type="button" class="action-btn btn-primary action-sm" id="tourNextBtn">
                            ${isLast ? '<i class="fa-solid fa-check"></i> Finish' : 'Next &rarr;'}
                        </button>
                    </div>
                </div>
            `;

            scrollTargetIntoMobileSafeZone(activeTargetEl);
            updateSpotlightPosition();
            // Recalculate after smooth scroll settles on mobile devices
            setTimeout(updateSpotlightPosition, 160);
            setTimeout(updateSpotlightPosition, 340);
            setTimeout(updateSpotlightPosition, 520);

            const skipBtn = document.getElementById('tourSkipBtn');
            const prevBtn = document.getElementById('tourPrevBtn');
            const nextBtn = document.getElementById('tourNextBtn');

            if (skipBtn) {
                skipBtn.addEventListener('click', () => {
                    try { localStorage.setItem(storageKey, 'true'); } catch (e) {}
                    cleanupTourDOM();
                });
            }

            if (prevBtn) {
                prevBtn.addEventListener('click', () => {
                    if (currentIndex > 0) {
                        currentIndex -= 1;
                        renderStep(currentIndex);
                    }
                });
            }

            if (nextBtn) {
                nextBtn.addEventListener('click', () => {
                    if (currentIndex < steps.length - 1) {
                        currentIndex += 1;
                        renderStep(currentIndex);
                    } else {
                        try { localStorage.setItem(storageKey, 'true'); } catch (e) {}
                        cleanupTourDOM();
                    }
                });
            }
        }

        renderStep(0);
    }

    // === 3. Auto-Inject or Show Non-Intrusive Welcome Banner on First Visit ===
    const role = detectCurrentTourRole();
    const storageKey = role === 'customer' ? CUSTOMER_TOUR_KEY : PROVIDER_TOUR_KEY;
    const isHomePage = window.location.pathname === '/' && !window.location.search;
    const isProviderDashboard = Boolean(document.getElementById('providerDashboardRoot'));

    let alreadySeen = false;
    try {
        alreadySeen = localStorage.getItem(storageKey) === 'true';
    } catch (e) {}

    let welcomeBanner = document.getElementById('tourWelcomeBanner');

    if (!alreadySeen && !welcomeBanner && (isHomePage || isProviderDashboard)) {
        const mainContainer = document.querySelector('.main-container');
        if (mainContainer) {
            welcomeBanner = document.createElement('div');
            welcomeBanner.id = 'tourWelcomeBanner';
            welcomeBanner.className = 'tour-welcome-card';
            const titleText = isProviderDashboard
                ? 'Welcome to Your Provider Command Center! 🚀'
                : 'Welcome to AllThings! 👋 Everything you need, all in one place.';
            const subText = isProviderDashboard
                ? 'Take a quick 30-second tour to see how escrow payouts, order PINs, custom service quotes, and buyer leads work.'
                : 'Discover quality products, book KYC-verified service professionals, or request hard-to-find items—100% protected by AllThings Escrow.';

            welcomeBanner.innerHTML = `
                <div class="tour-welcome-left">
                    <span class="tour-welcome-icon"><i class="fa-solid fa-compass"></i></span>
                    <div>
                        <h3 class="tour-welcome-title">${titleText}</h3>
                        <p class="tour-welcome-text">${subText}</p>
                    </div>
                </div>
                <div class="tour-welcome-actions">
                    <button type="button" id="startWelcomeTourBtn" class="action-btn btn-primary action-sm">
                        <i class="fa-solid fa-wand-magic-sparkles"></i> Take a Quick Tour
                    </button>
                    <button type="button" id="dismissWelcomeTourBtn" class="action-btn btn-outline action-sm">
                        ${isProviderDashboard ? 'Dismiss' : 'Explore AllThings'}
                    </button>
                </div>
            `;
            mainContainer.insertBefore(welcomeBanner, mainContainer.firstChild);
        }
    } else if (welcomeBanner && !alreadySeen) {
        welcomeBanner.classList.remove('hidden-initial');
    }

    const startWelcomeTourBtn = document.getElementById('startWelcomeTourBtn');
    const dismissWelcomeTourBtn = document.getElementById('dismissWelcomeTourBtn');

    if (startWelcomeTourBtn) {
        startWelcomeTourBtn.addEventListener('click', () => startGuidedTour(role));
    }

    if (dismissWelcomeTourBtn) {
        dismissWelcomeTourBtn.addEventListener('click', () => {
            try { localStorage.setItem(storageKey, 'true'); } catch (e) {}
            if (welcomeBanner) welcomeBanner.classList.add('hidden-initial');
        });
    }

    // Manual "Take a Guided Tour" / "Portal Tour" Triggers
    const manualTourTriggers = document.querySelectorAll('.js-start-guided-tour');
    manualTourTriggers.forEach(btn => {
        btn.addEventListener('click', function (e) {
            e.preventDefault();
            const mobileDrawer = document.getElementById('mobileDrawer');
            const mobileOverlay = document.getElementById('mobileOverlay');
            if (mobileDrawer) mobileDrawer.classList.remove('active');
            if (mobileOverlay) mobileOverlay.classList.remove('active');
            document.body.style.overflow = '';

            document.querySelectorAll('.nav-dropdown-menu').forEach(m => m.classList.remove('active'));
            startGuidedTour();
        });
    });

    // === 4. Provider Setup Checklist Progress Bar & Dismissal ===
    const checklistCard = document.getElementById('providerSetupChecklist');
    const progressFill = document.getElementById('setupProgressFill');
    const progressText = document.getElementById('setupProgressText');
    const dismissChecklistBtn = document.getElementById('dismissSetupChecklistBtn');

    if (checklistCard) {
        const allSteps = checklistCard.querySelectorAll('.setup-step-item');
        const completedSteps = checklistCard.querySelectorAll('.setup-step-item.is-completed');
        const total = allSteps.length || 5;
        const done = completedSteps.length;
        const pct = Math.round((done / total) * 100);

        if (progressText) {
            progressText.textContent = `${done}/${total} Completed (${pct}%)`;
        }

        if (progressFill) {
            progressFill.className = `setup-progress-fill progress-w-${pct}`;
        }

        let isChecklistHidden = false;
        try {
            isChecklistHidden = localStorage.getItem(CHECKLIST_DISMISSED_KEY) === 'true';
        } catch (e) {}

        if (done === total && isChecklistHidden) {
            checklistCard.classList.add('hidden-initial');
        } else {
            checklistCard.classList.remove('hidden-initial');
        }

        if (dismissChecklistBtn) {
            dismissChecklistBtn.addEventListener('click', () => {
                try { localStorage.setItem(CHECKLIST_DISMISSED_KEY, 'true'); } catch (e) {}
                checklistCard.classList.add('hidden-initial');
            });
        }
    }
});