document.addEventListener("DOMContentLoaded", function () {

    // --- 1. UNIVERSAL NAVBAR CART BADGE UPDATER ---
    function updateNavbarCartBadge(cartCount) {
        if (typeof cartCount === "undefined" || cartCount === null) return;

        const count = parseInt(cartCount, 10) || 0;
        const badges = document.querySelectorAll("#navCartBadge, .nav-cart-badge, .nav-cart-wrapper .cart-badge");

        badges.forEach(badge => {
            badge.textContent = count;
            if (count > 0) {
                badge.style.display = "inline-flex";
                badge.classList.remove("hidden-initial");
            } else {
                badge.style.display = "none";
                badge.classList.add("hidden-initial");
            }
        });
    }

    function formatNGN(amount) {
        return "NGN " + Math.round(parseFloat(amount || 0)).toLocaleString("en-US");
    }

    // --- 2. CART PAGE: DYNAMIC TOTALS & INSTANT +/- QUANTITY CONTROLS ---
    const selectAllCheckbox = document.getElementById("selectAllItems");
    const cartTotalDisplay = document.getElementById("cartTotalDisplay");
    const proceedCheckoutBtn = document.getElementById("proceedCheckoutBtn");

    function getActiveCheckboxes() {
        return Array.from(document.querySelectorAll(".item-checkbox"));
    }

    function calculateTotal() {
        if (!cartTotalDisplay) return;
        const boxes = getActiveCheckboxes();
        let total = 0;
        let checkedCount = 0;

        boxes.forEach(box => {
            if (box.checked) {
                total += parseFloat(box.getAttribute("data-price") || "0");
                checkedCount += 1;
            }
        });

        cartTotalDisplay.textContent = formatNGN(total);

        if (proceedCheckoutBtn) {
            proceedCheckoutBtn.disabled = checkedCount === 0;
        }

        if (selectAllCheckbox) {
            selectAllCheckbox.checked = boxes.length > 0 && checkedCount === boxes.length;
            const labelSpan = selectAllCheckbox.parentElement.querySelector("span");
            if (labelSpan) {
                labelSpan.textContent = `Select All (${boxes.length} Item${boxes.length === 1 ? "" : "s"})`;
            }
        }
    }

    if (selectAllCheckbox && cartTotalDisplay) {
        selectAllCheckbox.addEventListener("change", function () {
            getActiveCheckboxes().forEach(box => {
                box.checked = this.checked;
            });
            calculateTotal();
        });

        getActiveCheckboxes().forEach(box => {
            box.addEventListener("change", calculateTotal);
        });

        // Instant AJAX for +, -, and Remove buttons on cart.html
        document.querySelectorAll(".cart-item-row").forEach(row => {
            const qtyBtns = row.querySelectorAll(".qty-btn");
            const deleteBtn = row.querySelector(".btn-delete");
            const qtyDisplay = row.querySelector(".qty-display");
            const lineTotalEl = row.querySelector(".cart-line-total") || row.querySelector(".cart-item-actions strong");
            const checkbox = row.querySelector(".item-checkbox");

            qtyBtns.forEach(btn => {
                btn.addEventListener("click", function (e) {
                    e.preventDefault();
                    if (row.dataset.updating === "true") return;
                    row.dataset.updating = "true";

                    fetch(this.href, {
                        headers: {
                            "X-Requested-With": "XMLHttpRequest",
                            "Accept": "application/json"
                        }
                    })
                        .then(res => res.json().then(data => ({ ok: res.ok, data })))
                        .then(({ ok, data }) => {
                            if (!ok || data.status === "error") {
                                alert(data.message || "Maximum available stock reached.");
                                return;
                            }

                            updateNavbarCartBadge(data.cart_count);

                            if (data.item_quantity === 0) {
                                row.remove();
                                if (getActiveCheckboxes().length === 0) {
                                    window.location.reload();
                                    return;
                                }
                            } else {
                                if (qtyDisplay) qtyDisplay.textContent = data.item_quantity;
                                if (lineTotalEl) lineTotalEl.textContent = formatNGN(data.item_total);
                                if (checkbox) checkbox.setAttribute("data-price", data.item_total);
                            }
                            calculateTotal();
                        })
                        .catch(() => window.location.assign(this.href))
                        .finally(() => {
                            row.dataset.updating = "false";
                        });
                });
            });

            if (deleteBtn) {
                deleteBtn.addEventListener("click", function (e) {
                    e.preventDefault();
                    fetch(this.href, {
                        headers: {
                            "X-Requested-With": "XMLHttpRequest",
                            "Accept": "application/json"
                        }
                    })
                        .then(res => res.json())
                        .then(data => {
                            updateNavbarCartBadge(data.cart_count);
                            row.remove();
                            if (getActiveCheckboxes().length === 0) {
                                window.location.reload();
                                return;
                            }
                            calculateTotal();
                        })
                        .catch(() => window.location.assign(this.href));
                });
            }
        });
    }

    // --- 3. CATALOG & HOMEPAGE: AJAX ADD-TO-CART BUTTONS ---
    const cartButtons = document.querySelectorAll(".ajax-cart-btn");

    cartButtons.forEach(button => {
        button.addEventListener("click", function (e) {
            e.preventDefault();

            // 1. Strict Lock: Ignore extra clicks while request is in flight
            if (this.dataset.loading === "true") return;
            this.dataset.loading = "true";

            // 2. Capture original button HTML once
            if (!this.dataset.originalText) {
                this.dataset.originalText = this.innerHTML;
            }

            const url = this.href;

            this.innerHTML = '<i class="fa-solid fa-spinner fa-spin"></i> Adding...';
            this.classList.add("btn-loading");

            const serverRequest = fetch(url, {
                headers: {
                    "X-Requested-With": "XMLHttpRequest",
                    "Accept": "application/json"
                }
            }).then(res => res.json().then(data => ({ ok: res.ok, data })));

            const minimumDelay = new Promise(resolve => setTimeout(resolve, 650));

            Promise.all([serverRequest, minimumDelay])
                .then(([{ ok, data }]) => {
                    this.classList.remove("btn-loading");

                    if (ok && data.status === "success") {
                        updateNavbarCartBadge(data.cart_count);
                        this.classList.add("btn-added");
                        this.innerHTML = '<i class="fa-solid fa-check"></i> Added!';
                    } else {
                        this.innerHTML = '<i class="fa-solid fa-circle-exclamation"></i> Max Stock';
                    }

                    setTimeout(() => {
                        this.innerHTML = this.dataset.originalText;
                        this.classList.remove("btn-added");
                        this.dataset.loading = "false";
                    }, 1500);
                })
                .catch(() => {
                    this.classList.remove("btn-loading");
                    this.innerHTML = "Error";

                    setTimeout(() => {
                        this.innerHTML = this.dataset.originalText;
                        this.dataset.loading = "false";
                    }, 1500);
                });
        });
    });
});