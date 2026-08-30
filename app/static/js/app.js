const form = document.getElementById("upload-form");
const imageInput = document.getElementById("image-input");
const selectedFileName = document.getElementById("selected-file-name");
const errorBanner = document.getElementById("error-banner");

const welcomeState = document.getElementById("welcome-state");
const documentView = document.getElementById("document-view");
const previewImage = document.getElementById("preview-image");
const previewImageError = document.getElementById("preview-image-error");
const docFilename = document.getElementById("doc-filename");
const docFiletype = document.getElementById("doc-filetype");
const docUploadDate = document.getElementById("doc-upload-date");
const docStatus = document.getElementById("doc-status");
const docLanguage = document.getElementById("doc-language");

const newDocumentBtn = document.getElementById("new-document-btn");
const attachBtn = document.getElementById("attach-btn");
const sidebar = document.getElementById("sidebar");
const sidebarToggle = document.getElementById("sidebar-toggle");

const extractTextBtn = document.getElementById("extract-text-btn");
const extractedTextLoading = document.getElementById("extracted-text-loading");
const extractedTextError = document.getElementById("extracted-text-error");
const extractedTextEmpty = document.getElementById("extracted-text-empty");
const extractedTextPending = document.getElementById("extracted-text-pending");
const extractedTextUncertainNotice = document.getElementById("extracted-text-uncertain-notice");
const extractedTextContent = document.getElementById("extracted-text-content");

const docList = document.getElementById("doc-list");
const docListEmpty = document.getElementById("doc-list-empty");

const chatMessages = document.getElementById("chat-messages");
const chatInput = document.getElementById("chat-input");
const chatSendBtn = document.getElementById("chat-send-btn");

let currentDocumentId = null;
let currentExtractedText = null;
let selectedLibraryDocumentId = null;

imageInput.addEventListener("change", () => {
    const file = imageInput.files[0];
    selectedFileName.textContent = file ? file.name : "";
});

previewImage.addEventListener("error", () => {
    if (!previewImage.getAttribute("src")) {
        return;
    }
    previewImage.classList.add("d-none");
    previewImageError.classList.remove("d-none");
});

function showError(message) {
    errorBanner.textContent = message;
    errorBanner.classList.remove("d-none");
}

function clearError() {
    errorBanner.classList.add("d-none");
    errorBanner.textContent = "";
}

function renderMetadata(metadata) {
    if (!metadata) {
        return;
    }
    if (metadata.upload_timestamp) {
        docUploadDate.textContent = new Date(metadata.upload_timestamp).toLocaleDateString();
    }
    if (metadata.processing_status) {
        docStatus.textContent = metadata.processing_status;
    }
    if (metadata.language) {
        docLanguage.textContent = metadata.language;
    }
}

function setExtractedTextState(state, options = {}) {
    extractedTextLoading.classList.add("d-none");
    extractedTextError.classList.add("d-none");
    extractedTextEmpty.classList.add("d-none");
    extractedTextPending.classList.add("d-none");
    extractedTextUncertainNotice.classList.add("d-none");
    extractedTextContent.textContent = "";

    if (state === "loading") {
        extractedTextLoading.classList.remove("d-none");
    } else if (state === "error") {
        extractedTextError.textContent = options.message || "Could not extract text from this document.";
        extractedTextError.classList.remove("d-none");
    } else if (state === "empty") {
        extractedTextEmpty.classList.remove("d-none");
    } else if (state === "pending") {
        extractedTextPending.classList.remove("d-none");
    } else if (state === "content") {
        extractedTextContent.textContent = options.text || "";
        if (options.uncertain) {
            extractedTextUncertainNotice.classList.remove("d-none");
        }
    }
}

function updateChatAvailability() {
    const ready = Boolean(currentDocumentId && currentExtractedText && currentExtractedText.trim() !== "");
    chatInput.disabled = !ready;
    chatSendBtn.disabled = !ready;
    chatInput.placeholder = ready
        ? "Ask anything about your document..."
        : "Select a processed document to ask questions...";
}

function resetChatMessages() {
    const placeholderText = currentDocumentId
        ? "Ask a question about this document."
        : "Select or upload a document, then ask a question about it.";
    chatMessages.innerHTML = `<div class="chat-placeholder" id="chat-placeholder">${placeholderText}</div>`;
}

async function loadConversation(documentId) {
    resetChatMessages();
    try {
        const response = await fetch(`/api/documents/${documentId}/conversation`);
        if (!response.ok) {
            return;
        }
        const data = await response.json();
        if (data.messages && data.messages.length) {
            data.messages.forEach((message) => {
                appendChatMessage(message.role, message.content);
            });
        }
    } catch (error) {
        // Keep the placeholder if the conversation can't be loaded.
    }
}

function appendChatMessage(role, text) {
    const placeholder = chatMessages.querySelector(".chat-placeholder");
    if (placeholder) {
        placeholder.remove();
    }

    const message = document.createElement("div");
    message.className = `chat-message chat-message-${role}`;
    message.innerHTML = `
        <div class="chat-message-sender">${role === "user" ? "You" : "UrduDoc AI"}</div>
        <div class="chat-message-bubble" dir="auto"></div>
    `;
    message.querySelector(".chat-message-bubble").textContent = text;

    chatMessages.appendChild(message);
    chatMessages.scrollTop = chatMessages.scrollHeight;
    return message;
}

async function sendChatQuestion() {
    const question = chatInput.value.trim();
    if (!question || !currentDocumentId) {
        return;
    }

    appendChatMessage("user", question);
    chatInput.value = "";
    chatInput.disabled = true;
    chatSendBtn.disabled = true;

    const loadingMessage = appendChatMessage("assistant", "Thinking...");
    loadingMessage.classList.add("chat-message-loading");

    try {
        const response = await fetch(`/api/documents/${currentDocumentId}/ask`, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ question }),
        });

        const data = await response.json();

        loadingMessage.remove();

        if (!response.ok) {
            appendChatMessage("assistant", data.detail || "Something went wrong. Please try again.");
        } else if (data.status === "success") {
            appendChatMessage("assistant", data.answer);
        } else {
            appendChatMessage("assistant", data.error || "Could not answer that question. Please try again.");
        }
    } catch (error) {
        loadingMessage.remove();
        appendChatMessage("assistant", "Something went wrong. Please try again.");
    } finally {
        updateChatAvailability();
    }
}

chatSendBtn.addEventListener("click", sendChatQuestion);
chatInput.addEventListener("keydown", (event) => {
    if (event.key === "Enter") {
        event.preventDefault();
        sendChatQuestion();
    }
});

function highlightActiveDocument(documentId) {
    selectedLibraryDocumentId = documentId;
    const items = docList.querySelectorAll(".doc-list-item");
    items.forEach((item) => {
        item.classList.toggle("active", item.dataset.id === documentId);
    });
}

function renderDocumentDetail(detail) {
    currentDocumentId = detail.document_id;

    docFilename.textContent = detail.filename;
    docFiletype.textContent = detail.file_type;
    docUploadDate.textContent = detail.upload_timestamp
        ? new Date(detail.upload_timestamp).toLocaleDateString()
        : "";
    docStatus.textContent = detail.processing_status;
    docLanguage.textContent = detail.language;

    previewImageError.classList.add("d-none");
    previewImage.classList.remove("d-none");
    previewImage.src = detail.image_url ? `${detail.image_url}?t=${Date.now()}` : "";

    currentExtractedText = detail.extracted_text || null;

    if (detail.processing_status === "completed" && detail.extracted_text) {
        setExtractedTextState("content", { text: detail.extracted_text, uncertain: detail.has_uncertain_text });
    } else if (detail.processing_status === "completed") {
        setExtractedTextState("empty");
    } else if (detail.processing_status === "failed") {
        setExtractedTextState("error", { message: "Text extraction failed for this document. Try Extract text again." });
    } else {
        setExtractedTextState("pending");
    }

    clearError();
    welcomeState.classList.add("d-none");
    documentView.classList.remove("d-none");
    highlightActiveDocument(detail.document_id);
    loadConversation(detail.document_id);
    updateChatAvailability();
}

async function selectLibraryDocument(documentId) {
    clearError();
    try {
        const response = await fetch(`/api/documents/${documentId}`);
        const data = await response.json();

        if (!response.ok) {
            showError(data.detail || "Could not load that document.");
            return;
        }

        renderDocumentDetail(data);
    } catch (error) {
        showError("Could not load that document. Please try again.");
    }
}

async function loadDocumentLibrary() {
    try {
        const response = await fetch("/api/documents");
        const documents = await response.json();

        docList.innerHTML = "";

        if (!documents.length) {
            docListEmpty.classList.remove("d-none");
            return;
        }

        docListEmpty.classList.add("d-none");

        documents.forEach((doc) => {
            const item = document.createElement("li");
            item.className = "doc-list-item";
            item.dataset.id = doc.document_id;
            if (doc.document_id === selectedLibraryDocumentId) {
                item.classList.add("active");
            }

            const uploadDate = doc.upload_timestamp
                ? new Date(doc.upload_timestamp).toLocaleDateString()
                : "";

            item.innerHTML = `
                <i class="bi bi-file-earmark-text doc-item-icon"></i>
                <div class="doc-item-text">
                    <div class="doc-item-name">${doc.filename}</div>
                    <div class="doc-item-subtitle">${doc.language} · ${doc.processing_status} · ${uploadDate}</div>
                </div>
                <button class="doc-item-delete" type="button" title="Delete document">
                    <i class="bi bi-trash"></i>
                </button>
            `;

            docList.appendChild(item);
        });
    } catch (error) {
        docListEmpty.classList.remove("d-none");
    }
}

docList.addEventListener("click", async (event) => {
    const deleteBtn = event.target.closest(".doc-item-delete");
    const item = event.target.closest(".doc-list-item");
    if (!item) {
        return;
    }

    const documentId = item.dataset.id;

    if (deleteBtn) {
        event.stopPropagation();
        try {
            await fetch(`/api/documents/${documentId}`, { method: "DELETE" });
        } catch (error) {
            showError("Could not delete that document. Please try again.");
        }
        if (documentId === currentDocumentId) {
            showWelcomeState();
        }
        if (documentId === selectedLibraryDocumentId) {
            selectedLibraryDocumentId = null;
        }
        loadDocumentLibrary();
        return;
    }

    selectLibraryDocument(documentId);
});

function showWelcomeState() {
    documentView.classList.add("d-none");
    welcomeState.classList.remove("d-none");
    form.reset();
    selectedFileName.textContent = "";
    currentDocumentId = null;
    currentExtractedText = null;
    previewImage.src = "";
    previewImage.classList.remove("d-none");
    previewImageError.classList.add("d-none");
    setExtractedTextState("pending");
    docUploadDate.textContent = "";
    docLanguage.textContent = "";
    clearError();
    highlightActiveDocument(null);
    resetChatMessages();
    updateChatAvailability();
}

form.addEventListener("submit", async (event) => {
    event.preventDefault();

    const file = imageInput.files[0];
    if (!file) {
        return;
    }

    clearError();

    const formData = new FormData();
    formData.append("file", file);

    try {
        const response = await fetch("/upload", {
            method: "POST",
            body: formData,
        });

        const data = await response.json();

        if (!response.ok) {
            showError(data.detail);
            return;
        }

        await loadDocumentLibrary();
        await selectLibraryDocument(data.document_id);
    } catch (error) {
        showError("Something went wrong. Please try again.");
    }
});

extractTextBtn.addEventListener("click", async () => {
    if (!currentDocumentId) {
        return;
    }

    setExtractedTextState("loading");
    extractTextBtn.disabled = true;

    try {
        const response = await fetch(`/api/documents/${currentDocumentId}/ocr`, {
            method: "POST",
        });

        const data = await response.json();

        if (!response.ok) {
            setExtractedTextState("error", { message: data.detail || "Could not extract text from this document." });
            return;
        }

        if (data.status === "success") {
            setExtractedTextState("content", {
                text: data.extracted_text,
                uncertain: data.metadata && data.metadata.has_uncertain_text,
            });
            currentExtractedText = data.extracted_text;
        } else if (data.status === "empty") {
            setExtractedTextState("empty");
            currentExtractedText = null;
        } else {
            setExtractedTextState("error", { message: data.error || "Could not extract text from this document." });
            currentExtractedText = null;
        }

        renderMetadata(data.metadata);
        loadDocumentLibrary();
        updateChatAvailability();
    } catch (error) {
        setExtractedTextState("error", { message: "Something went wrong while extracting text. Please try again." });
    } finally {
        extractTextBtn.disabled = false;
    }
});

newDocumentBtn.addEventListener("click", showWelcomeState);
attachBtn.addEventListener("click", () => imageInput.click());

if (sidebarToggle) {
    sidebarToggle.addEventListener("click", () => {
        sidebar.classList.toggle("open");
    });
}

loadDocumentLibrary();
resetChatMessages();
updateChatAvailability();