document.addEventListener('DOMContentLoaded', function () {
    const checkoutForm = document.getElementById('checkoutForm');
    if (!checkoutForm) return;

    const quotesUrl = checkoutForm.dataset.quotesUrl;
    const baseSubtotal = parseFloat(checkoutForm.dataset.subtotal || '0');

    const addressRadios = document.querySelectorAll('.address-radio');
    const newAddressForm = document.getElementById('new-address-form');
    const newAddressInputs = document.querySelectorAll('.new-address-input');
    const stateSelect = document.getElementById('newAddressState');
    const cityInput = document.getElementById('newAddressCity');

    const courierContainer = document.getElementById('courierOptionsContainer');
    const quoteTokenInput = document.getElementById('quoteTokenInput');
    const loadingBadge = document.getElementById('quoteLoadingBadge');

    const summaryShipping = document.getElementById('summaryShipping');
    const summaryCourierName = document.getElementById('summaryCourierName');
    const summaryTotal = document.getElementById('summaryTotal');

    function formatNGN(amount) {
        return 'NGN ' + Math.round(amount).toLocaleString('en-US');
    }

    function updateSummaryTotals(shippingFee, courierName, quoteToken) {
        const fee = parseFloat(shippingFee || '0');
        const grandTotal = baseSubtotal + fee;

        if (summaryShipping) summaryShipping.textContent = formatNGN(fee);
        if (summaryCourierName && courierName) summaryCourierName.textContent = courierName;
        if (summaryTotal) summaryTotal.textContent = formatNGN(grandTotal);
        if (quoteTokenInput && quoteToken) quoteTokenInput.value = quoteToken;
    }

    function bindCourierRadioEvents() {
        const courierRadios = courierContainer.querySelectorAll('.courier-radio');
        courierRadios.forEach(radio => {
            radio.addEventListener('change', function () {
                courierContainer.querySelectorAll('.courier-card').forEach(c => c.classList.remove('selected'));
                const parentCard = this.closest('.courier-card');
                if (parentCard) parentCard.classList.add('selected');

                updateSummaryTotals(
                    this.dataset.amount,
                    this.dataset.name,
                    this.dataset.token
                );
            });
        });
    }

    function renderCourierQuotes(quotes) {
        if (!courierContainer || !quotes || !quotes.length) return;

        // Preserve currently selected courier code if still available
        const currentSelected = courierContainer.querySelector('.courier-radio:checked');
        const preferredCode = currentSelected ? currentSelected.value : quotes[0].courier_code;

        let matchedQuote = quotes.find(q => q.courier_code === preferredCode) || quotes[0];

        courierContainer.innerHTML = quotes.map(q => {
            const isChecked = q.courier_code === matchedQuote.courier_code;
            const badgeHtml = q.badge ? `<span class="courier-badge">${q.badge}</span>` : '';
            return `
                <label class="courier-card ${isChecked ? 'selected' : ''}">
                    <input type="radio"
                           name="selected_courier"
                           value="${q.courier_code}"
                           class="courier-radio"
                           data-amount="${q.amount}"
                           data-token="${q.quote_token}"
                           data-name="${q.courier_name}"
                           ${isChecked ? 'checked' : ''}>
                    <div class="courier-card-body">
                        <div class="courier-top-row">
                            <span class="courier-title">
                                <i class="fa-solid ${q.icon} text-primary"></i> ${q.courier_name}
                            </span>
                            ${badgeHtml}
                        </div>
                        <p class="courier-desc">${q.description}</p>
                        <div class="courier-bottom-row">
                            <span class="courier-eta"><i class="fa-regular fa-clock"></i> Est: ${q.estimated_delivery}</span>
                            <strong class="courier-price">${formatNGN(q.amount)}</strong>
                        </div>
                    </div>
                </label>
            `;
        }).join('');

        bindCourierRadioEvents();
        updateSummaryTotals(matchedQuote.amount, matchedQuote.courier_name, matchedQuote.quote_token);
    }

    function fetchLiveQuotes() {
        const selectedAddrRadio = document.querySelector('.address-radio:checked');
        const addressId = selectedAddrRadio ? selectedAddrRadio.value : 'new';

        const params = new URLSearchParams();
        document.querySelectorAll('.selected-product-input').forEach(input => {
            params.append('selected_products', input.value);
        });

        params.append('address_id', addressId);
        if (addressId === 'new') {
            params.append('region', stateSelect ? stateSelect.value : 'Rivers State');
            params.append('city', cityInput ? cityInput.value : '');
        }

        if (loadingBadge) loadingBadge.style.display = 'inline-block';

        fetch(`${quotesUrl}?${params.toString()}`, {
            headers: { 'X-Requested-With': 'XMLHttpRequest' }
        })
            .then(res => res.json())
            .then(data => {
                if (data.status === 'success' && data.quotes) {
                    renderCourierQuotes(data.quotes);
                }
            })
            .catch(err => console.error('Failed to update shipping quotes:', err))
            .finally(() => {
                if (loadingBadge) loadingBadge.style.display = 'none';
            });
    }

    // 1. Handle Switching Saved Addresses vs. New Address Form
    function toggleAddressMode() {
        const selected = document.querySelector('.address-radio:checked');
        const isNew = !selected || selected.value === 'new';

        document.querySelectorAll('.address-card').forEach(card => card.classList.remove('selected'));
        if (selected && selected.closest('.address-card')) {
            selected.closest('.address-card').classList.add('selected');
        }

        if (newAddressForm) {
            if (isNew) {
                newAddressForm.classList.add('force-show-form');
                newAddressForm.style.display = 'block';
                newAddressInputs.forEach(inp => inp.setAttribute('required', 'required'));
            } else {
                newAddressForm.classList.remove('force-show-form');
                newAddressForm.style.display = 'none';
                newAddressInputs.forEach(inp => inp.removeAttribute('required'));
            }
        }

        fetchLiveQuotes();
    }

    addressRadios.forEach(radio => {
        radio.addEventListener('change', toggleAddressMode);
    });

    // 2. Recalculate Quotes When State or City Changes in New Address Form
    if (stateSelect) {
        stateSelect.addEventListener('change', fetchLiveQuotes);
    }

    let cityDebounce = null;
    if (cityInput) {
        cityInput.addEventListener('input', function () {
            clearTimeout(cityDebounce);
            cityDebounce = setTimeout(fetchLiveQuotes, 450);
        });
    }

    // Initialize radio bindings on first load
    bindCourierRadioEvents();
    if (addressRadios.length === 0 && newAddressInputs.length > 0) {
        newAddressInputs.forEach(inp => inp.setAttribute('required', 'required'));
    }
});