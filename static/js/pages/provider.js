// static/js/pages/provider.js
document.addEventListener('DOMContentLoaded', () => {
    // --- 1. Premium Tab Logic ---
    const tabButtons = document.querySelectorAll('.tab-btn');
    const tabContents = document.querySelectorAll('.tab-content');

    tabButtons.forEach(button => {
        button.addEventListener('click', () => {
            const targetId = button.getAttribute('data-tab');

            tabButtons.forEach(btn => btn.classList.remove('active'));
            tabContents.forEach(content => content.classList.remove('active'));

            button.classList.add('active');
            const targetPanel = document.getElementById(`${targetId}-tab`);
            if (targetPanel) {
                targetPanel.classList.add('active');
            }
        });
    });

    // --- 2. Follow Button Logic ---
    const followBtn = document.getElementById('followBtn');
    if (followBtn) {
        followBtn.addEventListener('click', async function () {
            const providerId = this.getAttribute('data-provider-id');
            const isFollowing = this.classList.contains('following');

            if (isFollowing) {
                this.classList.remove('following');
                this.classList.replace('btn-success', 'btn-outline');
                this.innerHTML = '<i class="fa-solid fa-user-plus icon-spaced"></i> Follow Store';
            } else {
                this.classList.add('following');
                this.classList.replace('btn-outline', 'btn-success');
                this.innerHTML = '<i class="fa-solid fa-user-check icon-spaced"></i> Following';
            }

            try {
                const csrfEl = document.querySelector('[name=csrfmiddlewaretoken]');
                const response = await fetch(`/api/toggle-follow/${providerId}/`, {
                    method: 'POST',
                    headers: {
                        'X-CSRFToken': csrfEl ? csrfEl.value : '',
                        'Content-Type': 'application/json'
                    }
                });

                if (!response.ok) {
                    console.error("Failed to update follow status.");
                }
            } catch (error) {
                console.error("Network error:", error);
            }
        });
    }

    // --- 3. Copy Profile Link Button (In-Place Feedback, No Browser Alert) ---
    const copyBtn = document.getElementById('copyProfileLinkBtn');
    if (copyBtn) {
        const originalCopyHtml = copyBtn.innerHTML;
        copyBtn.addEventListener('click', async () => {
            try {
                await navigator.clipboard.writeText(window.location.href);
                copyBtn.innerHTML = '<i class="fa-solid fa-check icon-spaced"></i> Link Copied!';
                setTimeout(() => {
                    copyBtn.innerHTML = originalCopyHtml;
                }, 2000);
            } catch (err) {
                console.error("Clipboard copy failed:", err);
            }
        });
    }

    // --- 4. Inquiry Modal Open / Close / Submit (Zero Inline Styles) ---
    const inquiryModal = document.getElementById('inquiryModal');
    const openModalBtn = document.getElementById('openInquiryModalBtn');
    const closeModalBtn = document.getElementById('closeInquiryModalBtn');
    const inquiryForm = document.getElementById('inquiryForm');
    const messageInput = document.getElementById('inquiryMessage');
    const errorMsg = document.getElementById('inquiryErrorMsg');

    function closeInquiryModal() {
        if (inquiryModal) {
            inquiryModal.classList.remove('active');
            document.body.classList.remove('lightbox-open');
        }
    }

    if (openModalBtn && inquiryModal) {
        openModalBtn.addEventListener('click', () => {
            inquiryModal.classList.add('active');
            document.body.classList.add('lightbox-open');
            if (messageInput) messageInput.focus();
        });
    }

    if (closeModalBtn) {
        closeModalBtn.addEventListener('click', closeInquiryModal);
    }

    if (inquiryModal) {
        inquiryModal.addEventListener('click', (e) => {
            if (e.target === inquiryModal) closeInquiryModal();
        });
    }

    if (messageInput && errorMsg) {
        messageInput.addEventListener('input', () => {
            if (!errorMsg.classList.contains('hidden-initial')) {
                errorMsg.classList.add('hidden-initial');
                errorMsg.textContent = '';
            }
        });
    }

    if (inquiryForm) {
        inquiryForm.addEventListener('submit', async (event) => {
            event.preventDefault();

            const providerId = inquiryForm.getAttribute('data-provider-id');
            const btn = document.getElementById('sendInquiryBtn');
            const csrfEl = inquiryForm.querySelector('[name=csrfmiddlewaretoken]');
            const cleanedMessage = messageInput ? messageInput.value.trim() : '';

            if (!cleanedMessage) {
                if (errorMsg) {
                    errorMsg.textContent = 'Please write your question before sending.';
                    errorMsg.classList.remove('hidden-initial');
                }
                return;
            }

            if (errorMsg) errorMsg.classList.add('hidden-initial');
            btn.innerHTML = '<i class="fa-solid fa-spinner fa-spin icon-spaced"></i> Sending...';
            btn.disabled = true;

            try {
                const response = await fetch(`/api/provider/${providerId}/inquiry/`, {
                    method: 'POST',
                    headers: {
                        'X-CSRFToken': csrfEl ? csrfEl.value : '',
                        'Content-Type': 'application/json'
                    },
                    body: JSON.stringify({ message: cleanedMessage })
                });
                const data = await response.json();

                if (response.ok && data.success) {
                    btn.innerHTML = '<i class="fa-solid fa-check icon-spaced"></i> Sent!';
                    btn.classList.replace('btn-primary', 'btn-success');

                    setTimeout(() => {
                        closeInquiryModal();
                        btn.innerHTML = '<i class="fa-solid fa-paper-plane icon-spaced"></i> Send Secure Inquiry';
                        btn.classList.replace('btn-success', 'btn-primary');
                        btn.disabled = false;
                        if (messageInput) messageInput.value = '';
                    }, 1200);
                } else {
                    if (errorMsg) {
                        errorMsg.textContent = data.error || 'Could not send message. Please keep contact details inside AllThings Escrow.';
                        errorMsg.classList.remove('hidden-initial');
                    }
                    btn.innerHTML = '<i class="fa-solid fa-paper-plane icon-spaced"></i> Send Secure Inquiry';
                    btn.disabled = false;
                }
            } catch (error) {
                if (errorMsg) {
                    errorMsg.textContent = 'Network error while sending inquiry. Please check your connection and try again.';
                    errorMsg.classList.remove('hidden-initial');
                }
                btn.innerHTML = '<i class="fa-solid fa-paper-plane icon-spaced"></i> Send Secure Inquiry';
                btn.disabled = false;
            }
        });
    }
});