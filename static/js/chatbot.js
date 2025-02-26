import { InferenceSession } from "https://ai.google.dev/edge/mediapipe/solutions/genai/llm_inference";

let session;

async function setupLLM() {
    session = await InferenceSession.create("gemini-1.5-flash"); // Load Gemini model
}

async function getLLMResponse(prompt) {
    if (!session) {
        return "Error: LLM session not initialized.";
    }
    const response = await session.generateContent(prompt);
    return response.text();
}

document.addEventListener("DOMContentLoaded", function () {
    setupLLM(); // Initialize the AI model

    const chatBox = document.getElementById("chat-box");
    const userInput = document.getElementById("user-input");
    const sendBtn = document.getElementById("send-btn");

    function appendMessage(sender, message) {
        const msgDiv = document.createElement("div");
        msgDiv.classList.add("chat-message", sender);
        msgDiv.innerText = message;
        chatBox.appendChild(msgDiv);
        chatBox.scrollTop = chatBox.scrollHeight;
    }

    sendBtn.addEventListener("click", async function () {
        const question = userInput.value.trim();
        if (!question) return;

        appendMessage("user", question);
        userInput.value = "";

        const response = await getLLMResponse(question);
        appendMessage("bot", response);
    });
});

document.addEventListener("DOMContentLoaded", function () {
    var animation = bodymovin.loadAnimation({
        container: document.getElementById("json-animation"), // JSON animation container
        renderer: "svg",
        loop: true,
        autoplay: true,
        path: "static/img/bot.json" // ✅ Update this path to your JSON file
    });
});
