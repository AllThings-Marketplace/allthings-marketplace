// static/js/pages/chat.js
document.addEventListener("DOMContentLoaded", function () {
    const chatHistory = document.getElementById("chatHistory");
    const chatForm = document.getElementById("chatForm");
    const chatInput = document.getElementById("chatInput");
    const fileInput = document.getElementById("chat-file");
    const previewBox = document.getElementById("chatAttachmentPreview");
    const previewName = document.getElementById("chatAttachmentName");
    const clearBtn = document.getElementById("clearChatAttachment");

    function scrollToBottom() {
        if (chatHistory) {
            chatHistory.scrollTop = chatHistory.scrollHeight;
        }
    }

    function hideAttachmentPreview() {
        if (previewBox) {
            previewBox.style.display = "none";
            previewBox.classList.add("hidden-initial");
        }
        if (previewName) {
            previewName.textContent = "";
        }
    }

    function escapeHtml(str) {
        const div = document.createElement("div");
        div.textContent = str;
        return div.innerHTML;
    }

    // 1. Scroll to bottom on initial load
    scrollToBottom();

    // 2. Attachment file selection & clear controls
    if (fileInput && previewBox) {
        fileInput.addEventListener("change", function () {
            if (this.files && this.files[0]) {
                previewName.textContent = "Attached: " + this.files[0].name;
                previewBox.classList.remove("hidden-initial");
                previewBox.style.display = "flex";
            } else {
                hideAttachmentPreview();
            }
        });
    }

    if (clearBtn && fileInput) {
        clearBtn.addEventListener("click", function () {
            fileInput.value = "";
            hideAttachmentPreview();
        });
    }

    // 3. AJAX Message Submission
    if (chatForm) {
        chatForm.addEventListener("submit", function (e) {
            e.preventDefault();

            const hasText = chatInput && chatInput.value.trim() !== "";
            const hasFile = fileInput && fileInput.files && fileInput.files.length > 0;

            if (!hasText && !hasFile) return;

            const formData = new FormData(chatForm);
            const submitBtn = chatForm.querySelector('button[type="submit"]');
            if (submitBtn) submitBtn.disabled = true;

            fetch(chatForm.action, {
                method: "POST",
                body: formData,
                headers: {
                    "X-Requested-With": "XMLHttpRequest"
                }
            })
            .then(response => response.json())
            .then(data => {
                if (data.status === "success") {
                    // Remove empty-state placeholder if this is the very first message
                    const emptyBox = chatHistory.querySelector(".chat-empty-box");
                    if (emptyBox) emptyBox.remove();

                    const safeBody = data.body ? `<p class="m-0">${escapeHtml(data.body)}</p>` : "";
                    const attachmentHtml = data.attachment_url
                        ? `<a href="${data.attachment_url}" target="_blank">
                               <img src="${data.attachment_url}" class="chat-attachment" alt="Attachment">
                           </a>`
                        : "";

                    const newMessage = `
                        <div class="message-bubble message-sent">
                            ${safeBody}
                            ${attachmentHtml}
                            <span class="message-meta">${data.time}</span>
                        </div>
                    `;

                    chatHistory.insertAdjacentHTML("beforeend", newMessage);

                    // If an image was attached, scroll again once the image finishes rendering
                    const lastImg = chatHistory.querySelector(".message-bubble:last-child .chat-attachment");
                    if (lastImg) {
                        lastImg.addEventListener("load", scrollToBottom);
                    }

                    // Reset form, hide attachment preview banner, and refocus input
                    chatForm.reset();
                    hideAttachmentPreview();
                    scrollToBottom();
                    if (chatInput) chatInput.focus();
                } else {
                    console.error("Message failed to send:", data.error);
                }
            })
            .catch(error => {
                console.error("Error:", error);
            })
            .finally(() => {
                if (submitBtn) submitBtn.disabled = false;
            });
        });
    }
});