// static/js/pages/chat.js
document.addEventListener("DOMContentLoaded", function () {
    const chatHistory = document.getElementById("chatHistory");
    const chatForm = document.getElementById("chatForm");
    const chatInput = document.getElementById("chatInput");
    const fileInput = document.getElementById("chat-file");
    const previewBox = document.getElementById("chatAttachmentPreview");
    const previewName = document.getElementById("chatAttachmentName");
    const clearBtn = document.getElementById("clearChatAttachment");
    const errorBanner = document.getElementById("chatErrorBanner");
    const errorText = document.getElementById("chatErrorText");
    const closeErrorBtn = document.getElementById("closeChatErrorBtn");

    function scrollToBottom() {
        if (chatHistory) {
            chatHistory.scrollTop = chatHistory.scrollHeight;
        }
    }

    function hideAttachmentPreview() {
        if (previewBox) {
            previewBox.classList.add("hidden-initial");
        }
        if (previewName) {
            previewName.textContent = "";
        }
    }

    function showChatError(message) {
        if (!errorBanner || !errorText) return;
        errorText.textContent = message || "Unable to send message. Please keep all contact and payment details inside AllThings Escrow.";
        errorBanner.classList.remove("hidden-initial");
    }

    function hideChatError() {
        if (!errorBanner) return;
        errorBanner.classList.add("hidden-initial");
        if (errorText) errorText.textContent = "";
    }

    function escapeHtml(str) {
        const div = document.createElement("div");
        div.textContent = str;
        return div.innerHTML;
    }

    // 1. Scroll to bottom on initial load
    scrollToBottom();

    if (closeErrorBtn) {
        closeErrorBtn.addEventListener("click", hideChatError);
    }

    if (chatInput) {
        chatInput.addEventListener("input", function () {
            if (errorBanner && !errorBanner.classList.contains("hidden-initial")) {
                hideChatError();
            }
        });
    }

    // 2. Attachment file selection & clear controls (Zero inline styles)
    if (fileInput && previewBox) {
        fileInput.addEventListener("change", function () {
            if (this.files && this.files[0]) {
                previewName.textContent = "Attached: " + this.files[0].name;
                previewBox.classList.remove("hidden-initial");
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

    // 3. AJAX Message Submission with Anti-Leakage Error Handling
    if (chatForm) {
        chatForm.addEventListener("submit", function (e) {
            e.preventDefault();

            const hasText = chatInput && chatInput.value.trim() !== "";
            const hasFile = fileInput && fileInput.files && fileInput.files.length > 0;

            if (!hasText && !hasFile) return;

            hideChatError();
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

                    const lastImg = chatHistory.querySelector(".message-bubble:last-child .chat-attachment");
                    if (lastImg) {
                        lastImg.addEventListener("load", scrollToBottom);
                    }

                    chatForm.reset();
                    hideAttachmentPreview();
                    scrollToBottom();
                    if (chatInput) chatInput.focus();
                } else {
                    showChatError(data.error);
                }
            })
            .catch(() => {
                showChatError("Network error while sending message. Please check your connection and try again.");
            })
            .finally(() => {
                if (submitBtn) submitBtn.disabled = false;
            });
        });
    }
});