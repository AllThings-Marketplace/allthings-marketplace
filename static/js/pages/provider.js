document.addEventListener('DOMContentLoaded', () => {
    // --- 1. Premium Tab Logic ---
    const tabButtons = document.querySelectorAll('.tab-btn');
    const tabContents = document.querySelectorAll('.tab-content');

    tabButtons.forEach(button => {
        button.addEventListener('click', () => {
            const targetId = button.getAttribute('data-tab');

            // Reset all buttons and panels
            tabButtons.forEach(btn => btn.classList.remove('active'));
            tabContents.forEach(content => content.classList.remove('active'));

            // Activate clicked button and corresponding panel
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
        followBtn.addEventListener('click', async function() {
            const providerId = this.getAttribute('data-provider-id');
            
            // Optimistic UI update (Instant visual feedback)
            const isFollowing = this.classList.contains('following');
            
            if (isFollowing) {
                this.classList.remove('following');
                this.classList.replace('btn-success', 'btn-outline');
                this.innerHTML = '<i class="fa-solid fa-user-plus icon-spaced"></i> Follow';
            } else {
                this.classList.add('following');
                this.classList.replace('btn-outline', 'btn-success');
                this.innerHTML = '<i class="fa-solid fa-user-check icon-spaced"></i> Following';
            }
            
            // Background Database Update
            try {
                const response = await fetch(`/api/toggle-follow/${providerId}/`, {
                    method: 'POST',
                    headers: {
                        'X-CSRFToken': document.querySelector('[name=csrfmiddlewaretoken]').value,
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
});

// --- Modal & Utility Functions ---
function copyProfileLink() {
    navigator.clipboard.writeText(window.location.href);
    alert('Profile link copied to clipboard!');
}

function openInquiryModal() {
    document.getElementById('inquiryModal').classList.add('active');
    document.body.style.overflow = 'hidden'; // Prevent background scrolling
}

function closeInquiryModal() {
    document.getElementById('inquiryModal').classList.remove('active');
    document.body.style.overflow = '';
}

async function submitInquiry(event) {
    event.preventDefault();
    
    const form = event.target;
    const providerId = form.getAttribute('data-provider-id');
    const messageInput = document.getElementById('inquiryMessage');
    const btn = document.getElementById('sendInquiryBtn');
    
    const message = messageInput.value;
    
    // UI Loading State
    btn.innerHTML = '<i class="fa-solid fa-spinner fa-spin"></i> Sending...';
    btn.disabled = true;

    try {
        const response = await fetch(`/api/provider/${providerId}/inquiry/`, {
            method: 'POST',
            headers: {
                'X-CSRFToken': document.querySelector('[name=csrfmiddlewaretoken]').value,
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({ message: message })
        });

        if (response.ok) {
            // Success State
            btn.innerHTML = '<i class="fa-solid fa-check"></i> Sent!';
            btn.classList.replace('btn-primary', 'btn-success');
            
            setTimeout(() => {
                closeInquiryModal();
                // Reset form to default state for next time
                btn.innerHTML = 'Send Message';
                btn.classList.replace('btn-success', 'btn-primary');
                btn.disabled = false;
                messageInput.value = '';
            }, 1500);
        } else {
            throw new Error('Failed to send message');
        }
    } catch (error) {
        console.error("Error sending inquiry:", error);
        btn.innerHTML = 'Error. Try Again';
        btn.disabled = false;
    }
}