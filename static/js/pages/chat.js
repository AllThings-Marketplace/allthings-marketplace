// static/js/pages/chat.js
document.addEventListener("DOMContentLoaded", function() {
    const chatHistory = document.getElementById("chatHistory");
    const chatForm = document.getElementById("chatForm");
    const chatInput = document.getElementById("chatInput");
    const fileInput = document.getElementById("chat-file");

    function scrollToBottom() {
        if (chatHistory) {
            chatHistory.scrollTop = chatHistory.scrollHeight;
        }
    }

    // Scroll to bottom on initial load
    scrollToBottom();

    if (chatForm) {
        chatForm.addEventListener("submit", function(e) {
            e.preventDefault(); // Stop the page from reloading

            // Prevent sending empty messages
            if (chatInput.value.trim() === "" && fileInput.files.length === 0) return;

            const formData = new FormData(chatForm);
            const submitBtn = chatForm.querySelector('button[type="submit"]');
            
            // Briefly disable button to prevent double-clicks
            submitBtn.disabled = true;

            fetch(chatForm.action, {
                method: 'POST',
                body: formData,
                headers: {
                    'X-Requested-With': 'XMLHttpRequest' // Tells Django this is an AJAX request
                }
            })
            .then(response => response.json())
            .then(data => {
                if (data.status === 'success') {
                    // Create the new message bubble
                    let newMessage = `
                        <div class="message-bubble message-sent">
                            ${data.body ? `<p class="m-0">${data.body}</p>` : ''}
                            ${data.attachment_url ? `<a href="${data.attachment_url}" target="_blank"><img src="${data.attachment_url}" class="chat-attachment" alt="Attachment"></a>` : ''}
                            <span class="message-meta">${data.time}</span>
                        </div>
                    `;
                    
                    // Inject into the DOM
                    chatHistory.insertAdjacentHTML('beforeend', newMessage);
                    
                    // Reset form and scroll
                    chatForm.reset();
                    scrollToBottom();
                } else {
                    console.error("Message failed to send:", data.error);
                }
            })
            .catch(error => {
                console.error('Error:', error);
            })
            .finally(() => {
                submitBtn.disabled = false;
            });
        });
    }
});