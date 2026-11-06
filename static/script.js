document.addEventListener("DOMContentLoaded", () => {
    const showMessage = (message, type = "success") => {
        let alert = document.querySelector(".alert");

        if (!alert) {
            alert = document.createElement("div");
            document.body.prepend(alert);
        }

        alert.textContent = message;
        alert.className = `alert alert-${type}`;

        setTimeout(() => alert.remove(), 4000);
    };

    const apiRequest = async (url, options = {}) => {
        const response = await fetch(url, {
            credentials: "same-origin",
            ...options
        });

        const contentType = response.headers.get("content-type");

        if (!contentType || !contentType.includes("application/json")) {
            const text = await response.text();
            console.error("Expected JSON but received:", text);
            throw new Error("API returned HTML instead of JSON. Check API URL and Flask route.");
        }

        const data = await response.json();

        if (!response.ok) {
            throw new Error(data.message || "Something went wrong");
        }

        return data;
    };

    const getRole = () => {
        return new URLSearchParams(location.search).get("role") || "student";
    };

    const loginTitle = document.querySelector("#loginTitle");

    if (loginTitle) {
        loginTitle.textContent = getRole() === "teacher" ? "Teacher Login" : "Student Login";
    }

    const loginLink = document.querySelector("#loginLink");

    if (loginLink) {
        loginLink.href = `/pages/login.html?role=${getRole()}`;
    }

    const signupTitle = document.querySelector("#signupTitle");

    if (signupTitle) {
        signupTitle.textContent = getRole() === "teacher" ? "Teacher Registration" : "Student Registration";
    }

    const signupLink = document.querySelector("#signupLink");

    if (signupLink) {
        signupLink.href = `/pages/signup.html?role=${getRole()}`;
    }

    document.querySelectorAll("[data-toggle-password]").forEach(button => {
        button.addEventListener("click", () => {
            const input = document.querySelector(button.dataset.togglePassword);

            if (input) {
                input.type = input.type === "password" ? "text" : "password";
            }
        });
    });

    document.querySelectorAll("[data-logout]").forEach(button => {
        button.addEventListener("click", async event => {
            event.preventDefault();

            try {
                await apiRequest("/api/logout", {
                    method: "POST"
                });

                window.location.href = "/";
            } catch (error) {
                showMessage(error.message, "danger");
            }
        });
    });

    const loginForm = document.querySelector("#loginForm");

    if (loginForm) {
        loginForm.addEventListener("submit", async event => {
            event.preventDefault();

            if (!loginForm.checkValidity()) {
                loginForm.classList.add("was-validated");
                return;
            }

            try {
                const data = await apiRequest(`/api/login/${getRole()}`, {
                    method: "POST",
                    headers: {
                        "Content-Type": "application/json"
                    },
                    body: JSON.stringify(Object.fromEntries(new FormData(loginForm)))
                });

                window.location.href = data.redirect;
            } catch (error) {
                showMessage(error.message, "danger");
            }
        });
    }

    const signupForm = document.querySelector("#signupForm");

    if (signupForm) {
        signupForm.addEventListener("submit", async event => {
            event.preventDefault();

            if (!signupForm.checkValidity()) {
                signupForm.classList.add("was-validated");
                return;
            }

            const formData = new FormData(signupForm);

            if (formData.get("password") !== formData.get("confirm_password")) {
                showMessage("Passwords do not match", "danger");
                return;
            }

            try {
                await apiRequest(`/api/signup/${getRole()}`, {
                    method: "POST",
                    headers: {
                        "Content-Type": "application/json"
                    },
                    body: JSON.stringify(Object.fromEntries(formData))
                });

                showMessage("Registration successful");

                setTimeout(() => {
                    window.location.href = `/pages/login.html?role=${getRole()}`;
                }, 1000);
            } catch (error) {
                showMessage(error.message, "danger");
            }
        });
    }

    const profileForm = document.querySelector("#profileForm");

    if (profileForm) {
        apiRequest("/api/student/profile")
            .then(data => {
                const user = data.user || data;

                Object.keys(user).forEach(key => {
                    const input = profileForm.elements[key];

                    if (input) {
                        input.value = user[key] || "";
                    }
                });

                const displayName = document.getElementById("profileDisplayName");

                if (displayName) {
                    displayName.textContent = user.name || "Student";
                }
            })
            .catch(error => showMessage(error.message, "danger"));

        profileForm.addEventListener("submit", async event => {
            event.preventDefault();

            if (!profileForm.checkValidity()) {
                profileForm.classList.add("was-validated");
                return;
            }

            try {
                const data = Object.fromEntries(new FormData(profileForm));

                await apiRequest("/api/student/profile", {
                    method: "PUT",
                    headers: {
                        "Content-Type": "application/json"
                    },
                    body: JSON.stringify(data)
                });

                showMessage("Profile updated successfully");

                const displayName = document.getElementById("profileDisplayName");

                if (displayName) {
                    displayName.textContent = data.name || "Student";
                }
            } catch (error) {
                showMessage(error.message, "danger");
            }
        });
    }

    const getFileUrl = filePath => {
        if (!filePath) return "";

        if (filePath.startsWith("http://") || filePath.startsWith("https://")) {
            return filePath;
        }

        return "/" + filePath.replace(/^\/+/, "");
    };

    const displayRecords = (records, table, count, type) => {
        count.textContent = records.length;
        table.innerHTML = "";

        if (records.length === 0) {
            table.innerHTML = `
                <tr>
                    <td colspan="6" class="text-center">
                        No ${type} submitted yet.
                    </td>
                </tr>`;
            return;
        }

        records.forEach((record, index) => {
            const row = document.createElement("tr");

            const values = [
                index + 1,
                record.title || "Untitled",
                record.filename || "No File",
                record.submitted_at || "Not Available",
                record.status || "Pending",
                record.feedback || "No feedback yet"
            ];

            values.forEach((value, i) => {
                const cell = document.createElement("td");

                if (i === 2 && record.file_path) {
                    const link = document.createElement("a");
                    link.href = getFileUrl(record.file_path);
                    link.textContent = value;
                    link.target = "_blank";
                    link.rel = "noopener noreferrer";
                    cell.appendChild(link);
                } else {
                    cell.textContent = value;
                }

                row.appendChild(cell);
            });

            table.appendChild(row);
        });
    };

    const loadAssignments = async () => {
        const table = document.getElementById("assignmentsTable");
        const count = document.getElementById("assignmentCount");

        if (!table || !count) return;

        try {
            const data = await apiRequest("/api/student/assignments");
            displayRecords(data.assignments || [], table, count, "assignments");
        } catch (error) {
            console.error("Assignment loading error:", error);

            table.innerHTML = `
                <tr>
                    <td colspan="6" class="text-center text-danger">
                        Failed to load assignments.
                    </td>
                </tr>`;
        }
    };

    const loadProjects = async () => {
        const table = document.getElementById("projectsTableBody");
        const count = document.getElementById("projectCount");

        if (!table || !count) return;

        try {
            const data = await apiRequest("/api/student/projects");
            displayRecords(data.projects || [], table, count, "projects");
        } catch (error) {
            console.error("Project loading error:", error);

            table.innerHTML = `
                <tr>
                    <td colspan="6" class="text-center text-danger">
                        Failed to load projects.
                    </td>
                </tr>`;
        }
    };

    const assignmentForm = document.querySelector("#assignmentForm");

    if (assignmentForm) {
        assignmentForm.addEventListener("submit", async event => {
            event.preventDefault();

            if (!assignmentForm.checkValidity()) {
                assignmentForm.classList.add("was-validated");
                return;
            }

            try {
                const data = await apiRequest("/api/student/assignments", {
                    method: "POST",
                    body: new FormData(assignmentForm)
                });

                showMessage(data.message || "Assignment uploaded successfully");

                assignmentForm.reset();
                assignmentForm.classList.remove("was-validated");

                assignmentForm.querySelectorAll(".is-valid, .is-invalid").forEach(element => {
                    element.classList.remove("is-valid", "is-invalid");
                });

                const fileName = document.getElementById("assignmentFileName");

                if (fileName) {
                    fileName.textContent = "";
                }

                await loadAssignments();
            } catch (error) {
                showMessage(error.message, "danger");
            }
        });
    }

    const projectForm = document.querySelector("#projectForm");

    if (projectForm) {
        projectForm.addEventListener("submit", async event => {
            event.preventDefault();

            if (!projectForm.checkValidity()) {
                projectForm.classList.add("was-validated");
                return;
            }

            try {
                const data = await apiRequest("/api/student/projects", {
                    method: "POST",
                    body: new FormData(projectForm)
                });

                showMessage(data.message || "Project submitted successfully");

                projectForm.reset();
                projectForm.classList.remove("was-validated");

                projectForm.querySelectorAll(".is-valid, .is-invalid").forEach(element => {
                    element.classList.remove("is-valid", "is-invalid");
                });

                const fileName = document.getElementById("projectFileName");

                if (fileName) {
                    fileName.textContent = "";
                }

                await loadProjects();
            } catch (error) {
                showMessage(error.message, "danger");
            }
        });
    }

    if (document.getElementById("assignmentsTable")) {
        loadAssignments();
    }

    if (document.getElementById("projectsTableBody")) {
        loadProjects();
    }

    document.querySelectorAll('input[type="file"]').forEach(input => {
        input.addEventListener("change", () => {
            const file = input.files[0];

            if (!file) return;

            const allowed = [
                "pdf", "doc", "docx", "ppt", "pptx",
                "zip", "jpg", "jpeg", "png"
            ];

            const extension = file.name.split(".").pop().toLowerCase();

            if (!allowed.includes(extension)) {
                showMessage("Invalid file type", "danger");
                input.value = "";
                return;
            }

            if (file.size > 16 * 1024 * 1024) {
                showMessage("File size must be less than 16 MB", "danger");
                input.value = "";
                return;
            }

            const label = input.dataset.fileName
                ? document.querySelector(input.dataset.fileName)
                : null;

            if (label) {
                label.textContent = file.name;
            }
        });
    });

    document.querySelectorAll("[data-confirm]").forEach(button => {
        button.addEventListener("click", event => {
            if (!confirm(button.dataset.confirm)) {
                event.preventDefault();
            }
        });
    });

    document.querySelectorAll("[data-confirm-delete]").forEach(button => {
        button.addEventListener("click", event => {
            if (!confirm("Are you sure you want to delete this?")) {
                event.preventDefault();
            }
        });
    });

    document.querySelectorAll('a[href^="#"]').forEach(link => {
        link.addEventListener("click", event => {
            const target = document.querySelector(link.getAttribute("href"));

            if (target) {
                event.preventDefault();
                target.scrollIntoView({
                    behavior: "smooth"
                });
            }
        });
    });

    document.querySelectorAll(".needs-validation").forEach(form => {
        form.addEventListener("submit", event => {
            if (!form.checkValidity()) {
                event.preventDefault();
                event.stopPropagation();
            }

            form.classList.add("was-validated");
        });
    });
});