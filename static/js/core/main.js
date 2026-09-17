document.addEventListener("DOMContentLoaded", function() {
    const searchInput = document.getElementById('globalSearchInput');
    const searchDropdown = document.getElementById('searchDropdown');
    const searchForm = document.getElementById('globalSearchForm');
    const recentContainer = document.getElementById('recentSearchesContainer');
    const clearBtn = document.getElementById('clearSearchesBtn');

    if (!searchInput || !searchDropdown) return;

    // 1. UI Toggle Logic
    searchInput.addEventListener('focus', () => {
        searchDropdown.classList.add('active');
        renderRecentSearches();
    });

    document.addEventListener('click', (e) => {
        if (!searchInput.contains(e.target) && !searchDropdown.contains(e.target)) {
            searchDropdown.classList.remove('active');
        }
    });

    // 2. LocalStorage Logic for Recent Searches
    function renderRecentSearches() {
        // Grab searches from browser storage, or start an empty array
        const searches = JSON.parse(localStorage.getItem('recentSearches') || '[]');
        recentContainer.innerHTML = ''; // Clear container

        if (searches.length === 0) {
            recentContainer.innerHTML = '<span style="color: #9ca3af; font-size: 13px;">No recent searches</span>';
            clearBtn.style.display = 'none';
            return;
        }

        clearBtn.style.display = 'block';
        
        // Build the pills
        searches.forEach(term => {
            const pill = document.createElement('a');
            pill.href = `/?q=${encodeURIComponent(term)}`; // Link back to home search
            pill.className = 'search-pill';
            pill.textContent = term;
            recentContainer.appendChild(pill);
        });
    }

    // Save search term on form submission
    searchForm.addEventListener('submit', (e) => {
        const term = searchInput.value.trim();
        if (term) {
            let searches = JSON.parse(localStorage.getItem('recentSearches') || '[]');
            // Remove it if it already exists to avoid duplicates
            searches = searches.filter(t => t.toLowerCase() !== term.toLowerCase());
            // Add to the front of the line
            searches.unshift(term);
            // Keep only the top 8 recent searches
            searches = searches.slice(0, 8);
            localStorage.setItem('recentSearches', JSON.stringify(searches));
        }
    });

    // Clear all recent searches
    if (clearBtn) {
        clearBtn.addEventListener('click', () => {
            localStorage.removeItem('recentSearches');
            renderRecentSearches();
        });
    }
});

// === Mobile Drawer Logic ===
document.addEventListener("DOMContentLoaded", function() {
    const mobileMenuBtn = document.getElementById('mobileMenuBtn');
    const closeDrawerBtn = document.getElementById('closeDrawerBtn');
    const mobileDrawer = document.getElementById('mobileDrawer');
    const mobileOverlay = document.getElementById('mobileOverlay');

    if (mobileMenuBtn && mobileDrawer) {
        function toggleDrawer() {
            mobileDrawer.classList.toggle('active');
            mobileOverlay.classList.toggle('active');
            // Prevent background scrolling when menu is open
            document.body.style.overflow = mobileDrawer.classList.contains('active') ? 'hidden' : '';
        }
        
        mobileMenuBtn.addEventListener('click', toggleDrawer);
        closeDrawerBtn.addEventListener('click', toggleDrawer);
        mobileOverlay.addEventListener('click', toggleDrawer);
    }
});

document.addEventListener('DOMContentLoaded', function() {
    const seeMoreBtn = document.getElementById('seeMoreCategoriesBtn');
    
    if (seeMoreBtn) {
        seeMoreBtn.addEventListener('click', function() {
            // FIX: Select items that actually have the 'hidden-initial' class
            const hiddenItems = document.querySelectorAll('.mobile-cat-item.hidden-initial');
            
            if (hiddenItems.length > 0) {
                // Reveal them by removing the class and enforcing display block
                hiddenItems.forEach(item => {
                    item.classList.remove('hidden-initial');
                    item.style.display = 'block';
                });
                
                // Update the button text to show it is fully expanded
                this.innerHTML = 'All Categories Loaded <i class="fa-solid fa-check" style="margin-left: 5px;"></i>';
                this.style.color = '#10b981'; // Turn green to indicate success
                this.disabled = true; // Prevent further clicks
            }
        });
    }
});