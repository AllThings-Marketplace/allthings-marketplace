document.addEventListener('DOMContentLoaded', function () {
    const COOKIE_NAME = 'allthings_cookie_consent';
    const COOKIE_MAX_AGE = 60 * 60 * 24 * 180; // 180 days

    const banner = document.getElementById('cookieConsentBanner');
    const modal = document.getElementById('cookiePreferencesModal');

    const acceptAllBtn = document.getElementById('cookieAcceptAllBtn');
    const rejectBtn = document.getElementById('cookieRejectBtn');
    const customizeBtn = document.getElementById('cookieCustomizeBtn');
    const closeModalBtn = document.getElementById('closeCookieModalBtn');
    const modalRejectBtn = document.getElementById('cookieModalRejectBtn');
    const savePrefsBtn = document.getElementById('cookieSavePrefsBtn');
    const openSettingsTriggers = document.querySelectorAll('.js-open-cookie-settings');

    const functionalToggle = document.getElementById('consentFunctionalToggle');
    const analyticsToggle = document.getElementById('consentAnalyticsToggle');
    const marketingToggle = document.getElementById('consentMarketingToggle');

    function getSavedConsent() {
        const match = document.cookie
            .split('; ')
            .find(row => row.startsWith(COOKIE_NAME + '='));
        if (!match) return null;
        try {
            return JSON.parse(decodeURIComponent(match.split('=')[1]));
        } catch (e) {
            return null;
        }
    }

    function applyConsentSideEffects(prefs) {
        // Expose globally so main.js or analytics scripts can check consent
        window.AllThingsCookieConsent = prefs;

        // If Functional storage is rejected, clear non-essential recentSearches from localStorage
        if (!prefs.functional) {
            try {
                localStorage.removeItem('recentSearches');
            } catch (e) {
                // Ignore storage errors in private browsing
            }
        }
    }

    function saveConsent(prefs) {
        const payload = {
            necessary: true,
            functional: Boolean(prefs.functional),
            analytics: Boolean(prefs.analytics),
            marketing: Boolean(prefs.marketing),
            updatedAt: new Date().toISOString()
        };

        const encoded = encodeURIComponent(JSON.stringify(payload));
        const secureFlag = window.location.protocol === 'https:' ? '; Secure' : '';
        document.cookie = `${COOKIE_NAME}=${encoded}; max-age=${COOKIE_MAX_AGE}; path=/; SameSite=Lax${secureFlag}`;

        applyConsentSideEffects(payload);

        if (banner) banner.classList.add('hidden-initial');
        if (modal) modal.classList.remove('active');
        document.body.style.overflow = '';
    }

    function openPreferencesModal() {
        const current = getSavedConsent() || {
            functional: true,
            analytics: true,
            marketing: false
        };
        if (functionalToggle) functionalToggle.checked = Boolean(current.functional);
        if (analyticsToggle) analyticsToggle.checked = Boolean(current.analytics);
        if (marketingToggle) marketingToggle.checked = Boolean(current.marketing);

        if (modal) {
            modal.classList.add('active');
            document.body.style.overflow = 'hidden';
        }
    }

    // 1. Check initial consent on page load
    const existingConsent = getSavedConsent();
    if (!existingConsent) {
        if (banner) banner.classList.remove('hidden-initial');
    } else {
        applyConsentSideEffects(existingConsent);
    }

    // 2. Wire Banner & Modal Buttons
    if (acceptAllBtn) {
        acceptAllBtn.addEventListener('click', () => {
            saveConsent({ functional: true, analytics: true, marketing: true });
        });
    }

    if (rejectBtn) {
        rejectBtn.addEventListener('click', () => {
            saveConsent({ functional: false, analytics: false, marketing: false });
        });
    }

    if (modalRejectBtn) {
        modalRejectBtn.addEventListener('click', () => {
            saveConsent({ functional: false, analytics: false, marketing: false });
        });
    }

    if (customizeBtn) {
        customizeBtn.addEventListener('click', openPreferencesModal);
    }

    openSettingsTriggers.forEach(trigger => {
        trigger.addEventListener('click', (e) => {
            e.preventDefault();
            openPreferencesModal();
        });
    });

    if (closeModalBtn && modal) {
        closeModalBtn.addEventListener('click', () => {
            modal.classList.remove('active');
            document.body.style.overflow = '';
        });
    }

    if (savePrefsBtn) {
        savePrefsBtn.addEventListener('click', () => {
            saveConsent({
                functional: functionalToggle ? functionalToggle.checked : false,
                analytics: analyticsToggle ? analyticsToggle.checked : false,
                marketing: marketingToggle ? marketingToggle.checked : false
            });
        });
    }
});