document.addEventListener('DOMContentLoaded', () => {
    // --- 1. Tab Switching Logic ---
    const tabBtns = document.querySelectorAll('.tab-btn');
    tabBtns.forEach(btn => {
        btn.addEventListener('click', () => {
            document.querySelectorAll('.tab-btn').forEach(b => b.classList.remove('active'));
            document.querySelectorAll('.tab-content').forEach(c => c.classList.remove('active'));

            btn.classList.add('active');
            const targetId = btn.getAttribute('data-target');
            const targetEl = document.getElementById(targetId);
            if (targetEl) targetEl.classList.add('active');
        });
    });

    // --- 2. Inquiry Reader & In-App Reply Logic ---
    const inquiryItems = document.querySelectorAll('.inquiry-item');
    const readerEmpty = document.getElementById('readerEmpty');
    const readerContent = document.getElementById('readerContent');

    const readerName = document.getElementById('readerName');
    const readerDate = document.getElementById('readerDate');
    const readerMessage = document.getElementById('readerMessage');

    const replyForm = document.getElementById('providerInquiryReplyForm');
    const replyInput = document.getElementById('providerReplyInput');
    const replyFeedback = document.getElementById('providerReplyFeedback');
    const sendReplyBtn = document.getElementById('sendReplyBtn');
    const csrfToken = document.getElementById('csrfToken')?.value;

    let activeInquiryItem = null;
    let activeInquiryId = null;

    inquiryItems.forEach(item => {
        item.addEventListener('click', async () => {
            activeInquiryItem = item;
            activeInquiryId = item.getAttribute('data-id');
            const name = item.getAttribute('data-name');
            const date = item.getAttribute('data-date');
            const message = item.getAttribute('data-message');

            if (readerEmpty) readerEmpty.classList.add('hidden-initial');
            if (readerContent) readerContent.classList.add('active');

            if (readerName) readerName.textContent = name;
            if (readerDate) readerDate.textContent = date;
            if (readerMessage) readerMessage.textContent = message;
            if (replyFeedback) replyFeedback.classList.add('hidden-initial');

            inquiryItems.forEach(el => el.classList.remove('active'));
            item.classList.add('active');

            if (item.classList.contains('unread')) {
                item.classList.remove('unread');
                try {
                    await fetch(`/api/inquiry/${activeInquiryId}/read/`, {
                        method: 'POST',
                        headers: {
                            'X-CSRFToken': csrfToken,
                            'Content-Type': 'application/json'
                        }
                    });
                } catch (error) {
                    console.error("Failed to mark inquiry as read:", error);
                }
            }
        });
    });

    if (replyForm && replyInput && sendReplyBtn) {
        replyForm.addEventListener('submit', async (e) => {
            e.preventDefault();
            if (!activeInquiryId) return;

            const replyText = replyInput.value.trim();
            if (!replyText) return;

            sendReplyBtn.disabled = true;
            sendReplyBtn.innerHTML = '<i class="fa-solid fa-spinner fa-spin icon-spaced"></i> Sending...';
            if (replyFeedback) replyFeedback.classList.add('hidden-initial');

            try {
                const response = await fetch(`/api/inquiry/${activeInquiryId}/reply/`, {
                    method: 'POST',
                    headers: {
                        'X-CSRFToken': csrfToken,
                        'Content-Type': 'application/json'
                    },
                    body: JSON.stringify({ reply: replyText })
                });
                const data = await response.json();

                if (response.ok && data.success) {
                    replyInput.value = '';
                    if (readerMessage && data.updated_message) {
                        readerMessage.textContent = data.updated_message;
                    }
                    if (activeInquiryItem && data.updated_message) {
                        activeInquiryItem.setAttribute('data-message', data.updated_message);
                    }
                    if (replyFeedback) {
                        replyFeedback.className = 'text-12-muted text-success font-600 mb-10';
                        replyFeedback.textContent = data.message || 'Reply sent securely!';
                        replyFeedback.classList.remove('hidden-initial');
                    }
                } else if (replyFeedback) {
                    replyFeedback.className = 'text-12-muted text-danger font-600 mb-10';
                    replyFeedback.textContent = data.error || 'Could not send reply.';
                    replyFeedback.classList.remove('hidden-initial');
                }
            } catch (error) {
                console.error("Error sending inquiry reply:", error);
            } finally {
                sendReplyBtn.disabled = false;
                sendReplyBtn.innerHTML = '<i class="fa-solid fa-paper-plane icon-spaced"></i> Send Secure In-App Reply';
            }
        });
    }
});