const form = document.getElementById("upload-form");
const imageInput = document.getElementById("image-input");
const selectedFileName = document.getElementById("selected-file-name");
const errorBanner = document.getElementById("error-banner");

const welcomeState = document.getElementById("welcome-state");
const documentView = document.getElementById("document-view");
const previewImage = document.getElementById("preview-image");
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
const extractedTextView = document.getElementById("extracted-text-view");
const extractedTextLoading = document.getElementById("extracted-text-loading");
const extractedTextError = document.getElementById("extracted-text-error");
const extractedTextEmpty = document.getElementById("extracted-text-empty");
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

function showWelcomeState() {
    documentView.classList.add("d-none");
    extractedTextView.classList.add("d-none");
    welcomeState.classList.remove("d-none");
    form.reset();
    selectedFileName.textContent = "";
    currentDocumentId = null;
    extractedTextContent.textContent = "";
    extractedTextEmpty.classList.add("d-none");
    docUploadDate.textContent = "";
    docLanguage.textContent = "";
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
        renderMetadata(data.metadata);

        extractedTextView.classList.add("d-none");
        extractedTextContent.textContent = "";
        extractedTextError.classList.add("d-none");
        extractedTextEmpty.classList.add("d-none");

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
    extractedTextEmpty.classList.add("d-none");
    extractedTextContent.textContent = "";
    extractedTextLoading.classList.remove("d-none");
    extractTextBtn.disabled = true;

    try {
        const response = await fetch(`/api/documents/${currentDocumentId}/ocr`, {
            method: "POST",
        });

        const data = await response.json();

        if (!response.ok) {
            extractedTextError.textContent = data.detail || "Could not extract text from this document.";
            extractedTextError.classList.remove("d-none");
            return;
        }

        if (data.status === "success") {
            extractedTextContent.textContent = data.extracted_text;
        } else if (data.status === "empty") {
            extractedTextEmpty.classList.remove("d-none");
        } else {
            extractedTextError.textContent = data.error || "Could not extract text from this document.";
            extractedTextError.classList.remove("d-none");
        }

        renderMetadata(data.metadata);
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