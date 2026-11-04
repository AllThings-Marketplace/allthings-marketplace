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

    // --- 3. Copy Profile Link Button ---
    const copyBtn = document.getElementById('copyProfileLinkBtn');
    if (copyBtn) {
        copyBtn.addEventListener('click', () => {
            navigator.clipboard.writeText(window.location.href);
            alert('Store link copied to clipboard!');
        });
    }

    // --- 4. Inquiry Modal Open / Close / Submit ---
    const inquiryModal = document.getElementById('inquiryModal');
    const openModalBtn = document.getElementById('openInquiryModalBtn');
    const closeModalBtn = document.getElementById('closeInquiryModalBtn');
    const inquiryForm = document.getElementById('inquiryForm');
    const errorMsg = document.getElementById('inquiryErrorMsg');

    function closeInquiryModal() {
        if (inquiryModal) {
            inquiryModal.classList.remove('active');
            document.body.style.overflow = '';
        }
    }

    if (openModalBtn && inquiryModal) {
        openModalBtn.addEventListener('click', () => {
            inquiryModal.classList.add('active');
            document.body.style.overflow = 'hidden';
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

    if (inquiryForm) {
        inquiryForm.addEventListener('submit', async (event) => {
            event.preventDefault();

            const providerId = inquiryForm.getAttribute('data-provider-id');
            const messageInput = document.getElementById('inquiryMessage');
            const btn = document.getElementById('sendInquiryBtn');
            const csrfEl = inquiryForm.querySelector('[name=csrfmiddlewaretoken]');

            if (errorMsg) errorMsg.classList.add('hidden-initial');
            btn.innerHTML = '<i class="fa-solid fa-spinner fa-spin"></i> Sending...';
            btn.disabled = true;

            try {
                const response = await fetch(`/api/provider/${providerId}/inquiry/`, {
                    method: 'POST',
                    headers: {
                        'X-CSRFToken': csrfEl ? csrfEl.value : '',
                        'Content-Type': 'application/json'
                    },
                    body: JSON.stringify({ message: messageInput.value })
                });
                const data = await response.json();

                if (response.ok && data.success) {
                    btn.innerHTML = '<i class="fa-solid fa-check"></i> Sent!';
                    btn.classList.replace('btn-primary', 'btn-success');

                    setTimeout(() => {
                        closeInquiryModal();
                        btn.innerHTML = '<i class="fa-solid fa-paper-plane icon-spaced"></i> Send Secure Inquiry';
                        btn.classList.replace('btn-success', 'btn-primary');
                        btn.disabled = false;
                        messageInput.value = '';
                    }, 1200);
                } else {
                    if (errorMsg) {
                        errorMsg.textContent = data.error || 'Could not send message.';
                        errorMsg.classList.remove('hidden-initial');
                    }
                    btn.innerHTML = '<i class="fa-solid fa-paper-plane icon-spaced"></i> Send Secure Inquiry';
                    btn.disabled = false;
                }
            } catch (error) {
                console.error("Error sending inquiry:", error);
                btn.innerHTML = 'Error. Try Again';
                btn.disabled = false;
            }
        });
    }
});