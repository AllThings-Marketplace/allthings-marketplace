document.addEventListener("DOMContentLoaded", function () {

    // === 1. Global Search Dropdown & Recent Searches (LocalStorage + Consent Guard) ===
    const searchInput = document.getElementById('globalSearchInput');
    const searchDropdown = document.getElementById('searchDropdown');
    const searchForm = document.getElementById('globalSearchForm');
    const recentContainer = document.getElementById('recentSearchesContainer');
    const clearBtn = document.getElementById('clearSearchesBtn');

    function isFunctionalStorageAllowed() {
        if (window.AllThingsCookieConsent && typeof window.AllThingsCookieConsent.functional === 'boolean') {
            return window.AllThingsCookieConsent.functional;
        }
        const match = document.cookie
            .split('; ')
            .find(row => row.startsWith('allthings_cookie_consent='));
        if (!match) {
            return true;
        }
        try {
            const parsed = JSON.parse(decodeURIComponent(match.split('=')[1]));
            return parsed.functional !== false;
        } catch (e) {
            return true;
        }
    }

    function renderRecentSearches() {
        if (!recentContainer) return;
        recentContainer.innerHTML = '';

        if (!isFunctionalStorageAllowed()) {
            const pausedSpan = document.createElement('span');
            pausedSpan.className = 'text-12-muted';
            pausedSpan.textContent = 'Recent search memory is paused by your cookie preferences.';
            recentContainer.appendChild(pausedSpan);
            if (clearBtn) clearBtn.classList.add('hidden-initial');
            return;
        }

        let searches = [];
        try {
            searches = JSON.parse(localStorage.getItem('recentSearches') || '[]');
        } catch (e) {
            searches = [];
        }

        if (searches.length === 0) {
            const emptySpan = document.createElement('span');
            emptySpan.className = 'text-12-muted';
            emptySpan.textContent = 'No recent searches';
            recentContainer.appendChild(emptySpan);
            if (clearBtn) clearBtn.classList.add('hidden-initial');
            return;
        }

        if (clearBtn) clearBtn.classList.remove('hidden-initial');

        searches.forEach(term => {
            const pill = document.createElement('a');
            pill.href = `/?q=${encodeURIComponent(term)}`;
            pill.className = 'search-pill';
            pill.textContent = term;
            recentContainer.appendChild(pill);
        });
    }

    if (searchInput && searchDropdown) {
        searchInput.addEventListener('focus', () => {
            searchDropdown.classList.add('active');
            renderRecentSearches();
        });

        document.addEventListener('click', (e) => {
            if (!searchInput.contains(e.target) && !searchDropdown.contains(e.target)) {
                searchDropdown.classList.remove('active');
            }
        });
    }

    if (searchForm && searchInput) {
        searchForm.addEventListener('submit', () => {
            if (!isFunctionalStorageAllowed()) {
                return;
            }
            const term = searchInput.value.trim();
            if (term) {
                try {
                    let searches = JSON.parse(localStorage.getItem('recentSearches') || '[]');
                    searches = searches.filter(t => t.toLowerCase() !== term.toLowerCase());
                    searches.unshift(term);
                    searches = searches.slice(0, 8);
                    localStorage.setItem('recentSearches', JSON.stringify(searches));
                } catch (e) {
                    // Ignore storage quota or private-mode errors
                }
            }
        });
    }

    if (clearBtn) {
        clearBtn.addEventListener('click', () => {
            try {
                localStorage.removeItem('recentSearches');
            } catch (e) {
                // Ignore storage errors
            }
            renderRecentSearches();
        });
    }

    // === 2. Mobile Drawer Toggle Logic ===
    const mobileMenuBtn = document.getElementById('mobileMenuBtn');
    const closeDrawerBtn = document.getElementById('closeDrawerBtn');
    const mobileDrawer = document.getElementById('mobileDrawer');
    const mobileOverlay = document.getElementById('mobileOverlay');

    if (mobileMenuBtn && mobileDrawer && mobileOverlay) {
        function toggleDrawer() {
            mobileDrawer.classList.toggle('active');
            mobileOverlay.classList.toggle('active');
            document.body.style.overflow = mobileDrawer.classList.contains('active') ? 'hidden' : '';
        }

        mobileMenuBtn.addEventListener('click', toggleDrawer);
        if (closeDrawerBtn) closeDrawerBtn.addEventListener('click', toggleDrawer);
        mobileOverlay.addEventListener('click', toggleDrawer);
    }

    // === 3. Smart Mobile Department "See All / Show Less" Toggle ===
    const seeMoreBtn = document.getElementById('seeMoreCategoriesBtn');
    const mobileProductList = document.getElementById('mobileCategoryList');
    const VISIBLE_DEPT_LIMIT = 6;

    if (seeMoreBtn && mobileProductList) {
        const deptItems = Array.from(mobileProductList.querySelectorAll(':scope > li.mobile-cat-item'));
        const extraItems = deptItems.slice(VISIBLE_DEPT_LIMIT);

        if (extraItems.length === 0) {
            deptItems.forEach(item => item.classList.remove('hidden-initial'));
            seeMoreBtn.classList.add('hidden-initial');
        } else {
            deptItems.slice(0, VISIBLE_DEPT_LIMIT).forEach(item => item.classList.remove('hidden-initial'));
            extraItems.forEach(item => item.classList.add('hidden-initial'));

            let isExpanded = false;

            function updateSeeMoreUI() {
                if (isExpanded) {
                    extraItems.forEach(item => item.classList.remove('hidden-initial'));
                    seeMoreBtn.innerHTML = 'Show Fewer Departments <i class="fa-solid fa-angle-up see-more-icon"></i>';
                } else {
                    extraItems.forEach(item => item.classList.add('hidden-initial'));
                    seeMoreBtn.innerHTML = `See All Departments (${deptItems.length}) <i class="fa-solid fa-angle-down see-more-icon"></i>`;
                }
            }

            updateSeeMoreUI();

            seeMoreBtn.addEventListener('click', function () {
                isExpanded = !isExpanded;
                updateSeeMoreUI();
            });
        }
    }

    // === 4. Navbar Dropdowns (Notification Bell & User Account Menu) ===
    const dropdownTriggers = document.querySelectorAll('.nav-dropdown-trigger');

    dropdownTriggers.forEach(trigger => {
        trigger.addEventListener('click', (e) => {
            e.preventDefault();
            e.stopPropagation();

            const container = trigger.closest('.nav-dropdown-container');
            if (!container) return;
            const menu = container.querySelector('.nav-dropdown-menu');
            if (!menu) return;

            const isCurrentlyOpen = menu.classList.contains('active');

            document.querySelectorAll('.nav-dropdown-menu').forEach(m => m.classList.remove('active'));

            if (!isCurrentlyOpen) {
                menu.classList.add('active');
            }
        });
    });

    document.addEventListener('click', (e) => {
        if (!e.target.closest('.nav-dropdown-container')) {
            document.querySelectorAll('.nav-dropdown-menu').forEach(menu => {
                menu.classList.remove('active');
            });
        }
    });
});