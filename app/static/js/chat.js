// Chat refinement for plan sections
(function() {
    const csrfToken = document.querySelector('meta[name="csrf-token"]').content;

    // Toggle chat visibility
    document.querySelectorAll('.toggle-chat-btn').forEach(btn => {
        btn.addEventListener('click', function() {
            const section = this.dataset.section;
            const chatContainer = document.getElementById(`chat-${section}`);
            chatContainer.classList.toggle('d-none');
            if (!chatContainer.classList.contains('d-none')) {
                chatContainer.querySelector('.chat-input').focus();
            }
        });
    });

    // Send chat message
    document.querySelectorAll('.send-chat-btn').forEach(btn => {
        btn.addEventListener('click', function() {
            sendMessage(this.dataset.section);
        });
    });

    // Enter key to send
    document.querySelectorAll('.chat-input').forEach(input => {
        input.addEventListener('keypress', function(e) {
            if (e.key === 'Enter') {
                sendMessage(this.dataset.section);
            }
        });
    });

    function sendMessage(section) {
        const input = document.querySelector(`.chat-input[data-section="${section}"]`);
        const message = input.value.trim();
        if (!message) return;

        const chatArea = document.getElementById(`chat-messages-${section}`);
        const sendBtn = document.querySelector(`.send-chat-btn[data-section="${section}"]`);

        // Add user message to chat
        const userMsg = document.createElement('div');
        userMsg.className = 'chat-message user';
        userMsg.textContent = message;
        chatArea.appendChild(userMsg);
        chatArea.scrollTop = chatArea.scrollHeight;

        // Clear input and disable
        input.value = '';
        input.disabled = true;
        sendBtn.disabled = true;
        sendBtn.innerHTML = '<span class="spinner-border spinner-border-sm"></span>';

        // Get event ID from URL
        const eventId = window.location.pathname.split('/')[2];

        fetch(`/api/event/${eventId}/chat`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'X-CSRFToken': csrfToken,
            },
            body: JSON.stringify({ section, message }),
        })
        .then(resp => resp.json())
        .then(data => {
            if (data.status === 'success') {
                // Add AI response
                const aiMsg = document.createElement('div');
                aiMsg.className = 'chat-message assistant';
                aiMsg.textContent = data.ai_message;
                chatArea.appendChild(aiMsg);

                // Reload the page to refresh the section content
                // (simpler than rendering JSON client-side)
                window.location.reload();
            } else {
                const errMsg = document.createElement('div');
                errMsg.className = 'chat-message assistant text-danger';
                errMsg.textContent = data.error || 'Something went wrong.';
                chatArea.appendChild(errMsg);
            }
        })
        .catch(() => {
            const errMsg = document.createElement('div');
            errMsg.className = 'chat-message assistant text-danger';
            errMsg.textContent = 'Network error. Please try again.';
            chatArea.appendChild(errMsg);
        })
        .finally(() => {
            input.disabled = false;
            sendBtn.disabled = false;
            sendBtn.innerHTML = '<i class="bi bi-send"></i>';
            chatArea.scrollTop = chatArea.scrollHeight;
        });
    }
})();
