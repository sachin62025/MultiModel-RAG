async function sendMessage() {
    const inputField = document.getElementById('user-input');
    const chatWindow = document.getElementById('chat-window');
    const query = inputField.value.trim();

    if (!query) return;

    // 1. Add User Message
    appendMessage(query, 'user-message');
    inputField.value = '';

    // 2. Show Loading Indicator
    const loadingId = 'loading-' + Date.now();
    const loadingDiv = document.createElement('div');
    loadingDiv.id = loadingId;
    loadingDiv.className = 'message bot-message loading';
    loadingDiv.textContent = '🔍 Scanning document visuals...';
    chatWindow.appendChild(loadingDiv);
    chatWindow.scrollTop = chatWindow.scrollHeight;

    try {
        // 3. Call FastAPI Backend
        const response = await fetch('/api/chat', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ query: query })
        });

        const data = await response.json();

        // 4. Remove Loading & Add Bot Response
        document.getElementById(loadingId).remove();
        appendMessage(data.answer, 'bot-message', data.retrieved_image, data.page_number);

    } catch (error) {
        console.error("Error:", error);
        document.getElementById(loadingId).textContent = "⚠️ Error connecting to server.";
    }
}

function appendMessage(text, className, imageB64 = null, pageNum = null) {
    const chatWindow = document.getElementById('chat-window');
    const div = document.createElement('div');
    div.className = `message ${className}`;
    
    // Add text content
    let contentHtml = `<p>${text}</p>`;
    
    // Add Image Evidence if available
    if (imageB64) {
        contentHtml += `
            <div style="margin-top: 10px; font-size: 0.9em; color: #aaa;">
                📄 Retrieved from Page ${pageNum}:
            </div>
            <img src="data:image/jpeg;base64,${imageB64}" class="evidence-image" alt="Retrieved Document Page">
        `;
    }

    div.innerHTML = contentHtml;
    chatWindow.appendChild(div);
    chatWindow.scrollTop = chatWindow.scrollHeight;
}

function handleKeyPress(event) {
    if (event.key === 'Enter') {
        sendMessage();
    }
}