document.addEventListener('DOMContentLoaded', () => {
    // --- Tab Switching Logic ---
    const tabBtns = document.querySelectorAll('.tab-btn');
    tabBtns.forEach(btn => {
        btn.addEventListener('click', () => {
            // Remove active states from all tabs and contents
            document.querySelectorAll('.tab-btn').forEach(b => b.classList.remove('active'));
            document.querySelectorAll('.tab-content').forEach(c => c.classList.remove('active'));
            
            // Add active state to the clicked tab
            btn.classList.add('active');
            const targetId = btn.getAttribute('data-target');
            document.getElementById(targetId).classList.add('active');
        });
    });

    // --- Inquiry Reader Logic ---
    const inquiryItems = document.querySelectorAll('.inquiry-item');
    const readerEmpty = document.getElementById('readerEmpty');
    const readerContent = document.getElementById('readerContent');
    
    // Reader Content Nodes
    const readerName = document.getElementById('readerName');
    const readerEmail = document.getElementById('readerEmail');
    const readerDate = document.getElementById('readerDate');
    const readerMessage = document.getElementById('readerMessage');
    const replyBtn = document.getElementById('replyBtn');
    
    // Get CSRF Token securely from the hidden input
    const csrfToken = document.getElementById('csrfToken')?.value;

    inquiryItems.forEach(item => {
        item.addEventListener('click', async () => {
            // 1. Extract data securely from the DOM attributes
            const id = item.getAttribute('data-id');
            const name = item.getAttribute('data-name');
            const email = item.getAttribute('data-email');
            const date = item.getAttribute('data-date');
            const message = item.getAttribute('data-message');

            // 2. Toggle UI States
            readerEmpty.style.display = 'none';
            readerContent.classList.add('active');
            
            // 3. Populate Data
            readerName.textContent = name;
            readerEmail.textContent = email;
            readerDate.textContent = date;
            readerMessage.textContent = message;
            replyBtn.href = `mailto:${email}?subject=Reply to your AllThings inquiry`;

            // 4. Handle Active Highlighting
            inquiryItems.forEach(el => el.classList.remove('active'));
            item.classList.add('active');

            // 5. Fire Read Status to Backend if Unread
            if (item.classList.contains('unread')) {
                item.classList.remove('unread'); // Optimistic UI update
                
                try {
                    await fetch(`/api/inquiry/${id}/read/`, {
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
});