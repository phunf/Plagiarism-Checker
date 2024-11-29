function toggleInputFields() {
    const option = document.getElementById("input-option").value;
    document.getElementById("text-input").style.display = option === "text" ? "block" : "none";
    document.getElementById("file-input").style.display = option === "upload" ? "block" : "none";
    document.getElementById("compare-input").style.display = option === "compare" ? "block" : "none";
}

async function checkPlagiarism() {
    const option = document.getElementById("input-option").value;
    const formData = new FormData();

    // Prepare the form data based on user input type
    if (option === "text") {
        const text = document.getElementById("text-area").value.trim();
        if (!text) {
            alert("No text provided for plagiarism check.");
            return;
        }
        formData.append("option", "Enter text");
        formData.append("text_input", text);

    } else if (option === "upload") {
        const file = document.getElementById("upload-file").files[0];
        if (!file) {
            alert("No file uploaded.");
            return;
        }
        formData.append("option", "Upload file");
        formData.append("uploaded_file", file);

    } else if (option === "compare") {
        const files = document.getElementById("upload-multiple-files").files;
        if (files.length < 2) {
            alert("Please upload at least two files for comparison.");
            return;
        }
        formData.append("option", "Find similarities");
        for (const file of files) {
            formData.append("uploaded_files", file);
        }
    }

    // Send data to the backend
    try {
        const response = await fetch("/", {
            method: "POST",
            body: formData,
        });

        if (response.redirected) {
            window.location.href = response.url; // Redirect to results page
        } else {
            const resultText = await response.text();
            document.getElementById("results").innerHTML = resultText;
        }
    } catch (error) {
        alert(`Error: ${error.message}`);
    }
}
