const form = document.getElementById("upload-form");
const imageInput = document.getElementById("image-input");
const selectedFileName = document.getElementById("selected-file-name");
const errorBanner = document.getElementById("error-banner");

const welcomeState = document.getElementById("welcome-state");
const documentView = document.getElementById("document-view");
const previewImage = document.getElementById("preview-image");
const docFilename = document.getElementById("doc-filename");
const docFiletype = document.getElementById("doc-filetype");
const docStatus = document.getElementById("doc-status");

const newDocumentBtn = document.getElementById("new-document-btn");
const attachBtn = document.getElementById("attach-btn");
const sidebar = document.getElementById("sidebar");
const sidebarToggle = document.getElementById("sidebar-toggle");

const extractTextBtn = document.getElementById("extract-text-btn");
const extractedTextView = document.getElementById("extracted-text-view");
const extractedTextLoading = document.getElementById("extracted-text-loading");
const extractedTextError = document.getElementById("extracted-text-error");
const extractedTextContent = document.getElementById("extracted-text-content");

let currentDocumentId = null;

imageInput.addEventListener("change", () => {
    const file = imageInput.files[0];
    selectedFileName.textContent = file ? file.name : "";
});

function showError(message) {
    errorBanner.textContent = message;
    errorBanner.classList.remove("d-none");
}

function clearError() {
    errorBanner.classList.add("d-none");
    errorBanner.textContent = "";
}

function showWelcomeState() {
    documentView.classList.add("d-none");
    extractedTextView.classList.add("d-none");
    welcomeState.classList.remove("d-none");
    form.reset();
    selectedFileName.textContent = "";
    currentDocumentId = null;
    extractedTextContent.textContent = "";
    clearError();
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

        previewImage.src = URL.createObjectURL(file);
        docFilename.textContent = data.original_filename;
        docFiletype.textContent = data.content_type;
        docStatus.textContent = data.status;
        currentDocumentId = data.document_id;

        extractedTextView.classList.add("d-none");
        extractedTextContent.textContent = "";
        extractedTextError.classList.add("d-none");

        welcomeState.classList.add("d-none");
        documentView.classList.remove("d-none");
    } catch (error) {
        showError("Something went wrong. Please try again.");
    }
});

extractTextBtn.addEventListener("click", async () => {
    if (!currentDocumentId) {
        return;
    }

    extractedTextView.classList.remove("d-none");
    extractedTextError.classList.add("d-none");
    extractedTextContent.textContent = "";
    extractedTextLoading.classList.remove("d-none");
    extractTextBtn.disabled = true;

    try {
        const response = await fetch(`/api/documents/${currentDocumentId}/ocr`, {
            method: "POST",
        });

        const data = await response.json();

        if (!response.ok || data.status !== "success") {
            extractedTextError.textContent = data.error || data.detail || "Could not extract text from this document.";
            extractedTextError.classList.remove("d-none");
            return;
        }

        extractedTextContent.textContent = data.extracted_text;
    } catch (error) {
        extractedTextError.textContent = "Something went wrong while extracting text. Please try again.";
        extractedTextError.classList.remove("d-none");
    } finally {
        extractedTextLoading.classList.add("d-none");
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