const fileInput = document.getElementById("fileInput");
const fileName = document.getElementById("fileName");
const dropzone = document.getElementById("dropzone");
const uploadForm = document.getElementById("uploadForm");
const submitBtn = document.getElementById("submitBtn");
const processingText = document.getElementById("processingText");

if (fileInput && fileName) {
  fileInput.addEventListener("change", () => {
    if (fileInput.files.length > 0) {
      fileName.textContent = fileInput.files[0].name;
      dropzone.classList.add("file-ready");
    } else {
      fileName.textContent = "No file selected";
      dropzone.classList.remove("file-ready");
    }
  });
}

if (dropzone) {
  ["dragenter", "dragover"].forEach((eventName) => {
    dropzone.addEventListener(eventName, (event) => {
      event.preventDefault();
      event.stopPropagation();
      dropzone.classList.add("active");
    });
  });

  ["dragleave", "drop"].forEach((eventName) => {
    dropzone.addEventListener(eventName, (event) => {
      event.preventDefault();
      event.stopPropagation();
      dropzone.classList.remove("active");
    });
  });

  dropzone.addEventListener("drop", (event) => {
    const files = event.dataTransfer.files;

    if (files.length > 0) {
      fileInput.files = files;
      fileName.textContent = files[0].name;
      dropzone.classList.add("file-ready");
    }
  });
}

if (uploadForm) {
  uploadForm.addEventListener("submit", () => {
    if (submitBtn) {
      submitBtn.disabled = true;
      submitBtn.textContent = "Processing...";
    }

    if (processingText) {
      processingText.classList.remove("hidden");
    }
  });
}