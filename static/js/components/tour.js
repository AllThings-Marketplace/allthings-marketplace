document.addEventListener('DOMContentLoaded', function () {
    const CUSTOMER_TOUR_KEY = 'allthings_customer_tour_done_v1';
    const PROVIDER_TOUR_KEY = 'allthings_provider_tour_done_v1';
    const CHECKLIST_DISMISSED_KEY = 'allthings_setup_checklist_hidden_v1';

    const welcomeBanner = document.getElementById('tourWelcomeBanner');
    const startWelcomeTourBtn = document.getElementById('startWelcomeTourBtn');
    const dismissWelcomeTourBtn = document.getElementById('dismissWelcomeTourBtn');
    const manualTourTriggers = document.querySelectorAll('.js-start-guided-tour');

    // === 1. Role-Aware Tour Step Definitions (With Mobile Fallbacks) ===
    const TOUR_SETS = {
        customer: [
            {
                selector: '#globalSearchForm',
                badge: 'Customer Tour',
                title: 'Find Products & Professionals Fast',
                body: 'Search by product name, brand, budget (e.g. "solar inverter under 250k"), or service specialty across Nigeria.'
            },
            {
                selector: '.trust-strip',
                badge: 'Escrow Protection',
                title: '100% Escrow-Protected Shopping',
                body: 'Your money is held safely in AllThings Escrow and released to the vendor only after you inspect your delivery and share your 6-digit PIN.'
            },
            {
                selector: '#marketplaceSidebar',
                mobileSelector: '#mobileFilterToggleBtn',
                badge: 'Departments & Filters',
                title: 'Browse Products & Service Categories',
                body: 'Filter by Physical Products or Professional Services, set your NGN budget, or drill down into specific departments.'
            },
            {
                selector: '.sourcing-home-callout',
                badge: 'Custom Sourcing',
                title: "Can't Find an Item? Request It",
                body: 'Post what you need and verified AllThings vendors and service professionals will pitch matching offers to you.'
            },
            {
                selector: '.nav-cart-wrapper',
                badge: 'Checkout & PINs',
                title: 'Compare Live Courier Rates at Checkout',
                body: 'Add items to your cart to compare live delivery rates from AllThings Express, GIG Logistics, and Inter-State Waybill.'
            }
        ],
        vendor: [
            {
                selector: '.kpi-grid',
                badge: 'Vendor Tour',
                title: 'Track Escrow & Cleared Earnings',
                body: 'Paid customer orders appear in "Locked in Escrow" first and move to "Available for Withdrawal" as soon as the buyer confirms their 6-digit Delivery PIN.'
            },
            {
                selector: '#tourStoreOrdersBtn',
                mobileSelector: '.dashboard-actions',
                badge: 'Order Fulfillment',
                title: 'Accept Orders & Dispatch with Pickup PINs',
                body: 'Open Store Orders to accept paid items, mark packages Ready for Pickup, and hand them to the courier using your 6-digit Pickup PIN.'
            },
            {
                selector: '#tourAddProductBtn',
                mobileSelector: '.dashboard-actions',
                badge: 'Add Inventory',
                title: 'Publish Products with Studio Photo AI',
                body: 'Upload up to 6 photos per product. Our smart category guesser and background processor prepare your listing automatically.'
            },
            {
                selector: '#dashboardTabsBar',
                badge: 'Workspace Tabs',
                title: 'Switch Between Catalog, Buyer Leads & Payouts',
                body: 'Use these workspace tabs to filter your product catalog, pitch products to open Buyer Leads, or withdraw cleared funds to your Nigerian bank.'
            }
        ],
        service: [
            {
                selector: '.kpi-grid',
                badge: 'Service Pro Tour',
                title: 'Escrow-Backed Service Earnings',
                body: 'Clients fund escrow before you begin work. Once the job is confirmed completed, your earnings unlock for instant bank withdrawal.'
            },
            {
                selector: '#tourAddServiceBtn',
                mobileSelector: '.dashboard-actions',
                badge: 'Service Listings',
                title: 'List Fixed, Package, or Custom Quote Services',
                body: 'Publish your service packages, travel radius, included scope of work, and portfolio photos.'
            },
            {
                selector: '[data-section="services"]',
                badge: 'Bookings & Quotes',
                title: 'Manage Bookings & Send Custom Quotes',
                body: 'Accept scheduled bookings, chat securely with clients in-app, or send itemized Labor + Materials custom quotes.'
            },
            {
                selector: '[data-section="leads"]',
                badge: 'Buyer Leads',
                title: 'Win New Clients from Buyer Requests',
                body: 'Browse open customer requests in your region and pitch your approved service listing directly.'
            }
        ]
    };

    function isElementVisible(el) {
        if (!el) return false;
        const rect = el.getBoundingClientRect();
        const style = window.getComputedStyle(el);
        return style.display !== 'none' && style.visibility !== 'hidden' && rect.width > 0 && rect.height > 0;
    }

    function resolveActiveSteps(roleKey) {
        const rawSteps = TOUR_SETS[roleKey] || TOUR_SETS.customer;
        const resolved = [];

        rawSteps.forEach(step => {
            let targetEl = document.querySelector(step.selector);
            if (!isElementVisible(targetEl) && step.mobileSelector) {
                targetEl = document.querySelector(step.mobileSelector);
            }
            if (isElementVisible(targetEl)) {
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

    // === 2. Interactive Spotlight Runner ===
    let activeTargetEl = null;
    let tooltipEl = null;

    function cleanupTourDOM() {
        if (activeTargetEl) {
            activeTargetEl.classList.remove('tour-active-target');
            activeTargetEl = null;
        }
        if (tooltipEl) {
            tooltipEl.remove();
            tooltipEl = null;
        }
    }

    function startGuidedTour(forceRole) {
        cleanupTourDOM();
        if (welcomeBanner) welcomeBanner.classList.add('hidden-initial');

        const role = forceRole || detectCurrentTourRole();
        const storageKey = role === 'customer' ? CUSTOMER_TOUR_KEY : PROVIDER_TOUR_KEY;
        const steps = resolveActiveSteps(role);

        if (steps.length === 0) return;

        let currentIndex = 0;

        tooltipEl = document.createElement('aside');
        tooltipEl.className = 'tour-tooltip-card animate-fade-in';
        tooltipEl.setAttribute('role', 'dialog');
        tooltipEl.setAttribute('aria-live', 'polite');
        document.body.appendChild(tooltipEl);

        function renderStep(idx) {
            if (activeTargetEl) {
                activeTargetEl.classList.remove('tour-active-target');
            }

            const step = steps[idx];
            activeTargetEl = step.element;
            activeTargetEl.classList.add('tour-active-target');
            activeTargetEl.scrollIntoView({ behavior: 'smooth', block: 'center' });

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
                        &larr; Previous
                    </button>
                    <div class="tour-nav-btns">
                        <button type="button" class="action-btn btn-primary action-sm" id="tourNextBtn">
                            ${isLast ? '<i class="fa-solid fa-check"></i> Finish' : 'Next &rarr;'}
                        </button>
                    </div>
                </div>
            `;

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

    // === 3. Show Non-Intrusive Welcome Banner on First Visit ===
    if (welcomeBanner) {
        const role = detectCurrentTourRole();
        const storageKey = role === 'customer' ? CUSTOMER_TOUR_KEY : PROVIDER_TOUR_KEY;
        let alreadySeen = false;
        try {
            alreadySeen = localStorage.getItem(storageKey) === 'true';
        } catch (e) {}

        if (!alreadySeen) {
            welcomeBanner.classList.remove('hidden-initial');
        }

        if (startWelcomeTourBtn) {
            startWelcomeTourBtn.addEventListener('click', () => startGuidedTour(role));
        }

        if (dismissWelcomeTourBtn) {
            dismissWelcomeTourBtn.addEventListener('click', () => {
                try { localStorage.setItem(storageKey, 'true'); } catch (e) {}
                welcomeBanner.classList.add('hidden-initial');
            });
        }
    }

    // Manual "Take a Quick Tour" Triggers in Navbar, Mobile Drawer & Footer
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