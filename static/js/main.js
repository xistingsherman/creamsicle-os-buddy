document.addEventListener('DOMContentLoaded', () => {
    // App State
    let selectedBoard = null;
    let selectedImage = null; // Object containing download_url, distro, variant, etc.
    let selectedLocalFile = null; // Object containing name, path
    
    let selectedDisk = null; // Object containing number, name, size
    
    // Customization config
    let configData = {
        hostname: 'orangepi',
        username: 'pi',
        password: 'orangepi',
        wifi_ssid: '',
        wifi_password: '',
        ssh_key: '',
        enable_ssh: false,
        preload_apps: []
    };
    let configApplied = false;

    // Elements
    const btnSelectOS = document.getElementById('btn-select-os');
    const btnOpenCustomize = document.getElementById('btn-open-customize');
    const btnSelectStorage = document.getElementById('btn-select-storage');
    const btnFlash = document.getElementById('btn-flash');
    
    // Cards
    const cardOS = document.getElementById('card-os');
    
    // Labels
    const selectedOSLabel = document.getElementById('selected-os-label');
    const selectedStorageLabel = document.getElementById('selected-storage-label');
    const configStatusBadge = document.getElementById('config-status-badge');
    const headerStatus = document.getElementById('header-status');
    
    // Modals
    const modalOS = document.getElementById('modal-os');
    const modalCustomize = document.getElementById('modal-customize');
    const modalStorage = document.getElementById('modal-storage');
    
    // Modal Selectors
    const selectBoard = document.getElementById('select-board');
    const selectImage = document.getElementById('select-image');
    const groupSelectImage = document.getElementById('group-select-image');
    const localFileInput = document.getElementById('local-file-input');
    const localFileDisplay = document.getElementById('local-file-display');
    const localFilePathInput = document.getElementById('local-file-path-input');
    const diskListContainer = document.getElementById('disk-list-container');
    
    // Confirm Buttons
    const btnConfirmOS = document.getElementById('btn-confirm-os');
    const btnConfirmStorage = document.getElementById('btn-confirm-storage');
    const btnSaveCustomize = document.getElementById('btn-save-customize');
    const btnRefreshDisks = document.getElementById('btn-refresh-disks');
    
    // Progress Elements
    const progressView = document.getElementById('progress-view');
    const progressHeader = document.getElementById('progress-header');
    const progressMessage = document.getElementById('progress-message');
    const progressPercentText = document.getElementById('progress-percent');
    const progressCircle = document.querySelector('.progress-ring__circle');
    const btnCancelFlash = document.getElementById('btn-cancel-flash');
    
    // Success Elements
    const successView = document.getElementById('success-view');
    const btnSuccessReset = document.getElementById('btn-success-reset');
    const mainDashboard = document.getElementById('main-dashboard');

    // Circular Progress Ring Setup
    let circumference = 565.48; // Default fallback for r=90
    try {
        if (progressCircle && progressCircle.r && progressCircle.r.baseVal) {
            const radius = progressCircle.r.baseVal.value;
            circumference = radius * 2 * Math.PI;
            progressCircle.style.strokeDasharray = `${circumference} ${circumference}`;
            progressCircle.style.strokeDashoffset = circumference;
        }
    } catch (e) {
        console.warn("SVG progress ring initialization failed:", e);
    }

    function setProgress(percent) {
        const offset = circumference - (percent / 100) * circumference;
        if (progressCircle) {
            progressCircle.style.strokeDashoffset = offset;
        }
        if (progressPercentText) {
            progressPercentText.textContent = `${percent}%`;
        }
    }

    // Modal helpers
    function openModal(modal) {
        modal.classList.add('active');
    }

    function closeModal(modal) {
        modal.classList.remove('active');
    }

    // App Space Counter Config
    const appSizes = {
        'firefox': 200,
        'vscode': 350,
        'kiwix': 60,
        'dictionary': 100,
        'sudoku': 15,
        'stardew': 250
    };

    function updateAppSpaceCounter() {
        let total = 0;
        const appIds = ['firefox', 'vscode', 'kiwix', 'dictionary', 'sudoku', 'stardew'];
        appIds.forEach(app => {
            const cb = document.getElementById('checkbox-app-' + app);
            if (cb && cb.checked) {
                total += appSizes[app];
            }
        });

        const modalCounter = document.getElementById('app-space-counter-modal');
        const mainCounter = document.getElementById('app-space-counter-main');
        const mainBadge = document.getElementById('main-app-space-badge');

        if (modalCounter) {
            modalCounter.textContent = `${total} MB`;
        }
        if (mainCounter) {
            mainCounter.textContent = `${total} MB`;
        }
        if (mainBadge) {
            if (total > 0) {
                mainBadge.style.display = 'inline-flex';
            } else {
                mainBadge.style.display = 'none';
            }
        }
    }

    // Close buttons binding
    document.querySelectorAll('.close-modal-btn').forEach(btn => {
        btn.addEventListener('click', (e) => {
            closeModal(e.target.closest('.modal-overlay'));
        });
    });
    document.querySelectorAll('.cancel-modal-btn').forEach(btn => {
        btn.addEventListener('click', (e) => {
            closeModal(e.target.closest('.modal-overlay'));
        });
    });

    // --- STEP 1: BOARD SELECTION ---
    function initBoardsList() {
        fetch('/api/boards')
            .then(res => res.json())
            .then(data => {
                selectBoard.innerHTML = '<option value="">Choose Board</option>';
                data.boards.forEach(b => {
                    const opt = document.createElement('option');
                    opt.value = b.id;
                    opt.textContent = b.name;
                    selectBoard.appendChild(opt);
                });
            })
            .catch(err => {
                console.error("Error loading boards:", err);
                selectBoard.innerHTML = '<option value="">Choose Board (Offline Mode)</option>';
                const fallbackBoards = [
                    { id: "orangepizero3", name: "Orange Pi Zero 3" },
                    { id: "orangepi5", name: "Orange Pi 5" },
                    { id: "orangepi5-plus", name: "Orange Pi 5 Plus" },
                    { id: "orangepizero2", name: "Orange Pi Zero 2" },
                    { id: "orangepi3-lts", name: "Orange Pi 3 LTS" },
                    { id: "orangepi4-lts", name: "Orange Pi 4 LTS" },
                    { id: "orangepi4pro", name: "Orange Pi 4 Pro" },
                    { id: "orangepione", name: "Orange Pi One" },
                    { id: "orangepizero", name: "Orange Pi Zero" },
                    { id: "orangepipc2", name: "Orange Pi PC 2" }
                ];
                fallbackBoards.forEach(b => {
                    const opt = document.createElement('option');
                    opt.value = b.id;
                    opt.textContent = b.name;
                    selectBoard.appendChild(opt);
                });
                
                const errorMsg = document.createElement('div');
                errorMsg.style.color = '#ef4444';
                errorMsg.style.fontSize = '12px';
                errorMsg.style.marginTop = '5px';
                errorMsg.id = 'boards-fetch-error';
                errorMsg.innerHTML = '<i class="fa-solid fa-triangle-exclamation"></i> Server connection failed. Using local list.';
                
                if (!document.getElementById('boards-fetch-error')) {
                    selectBoard.parentNode.appendChild(errorMsg);
                }
            });
    }

    // Load boards list automatically on page load
    initBoardsList();

    selectBoard.addEventListener('change', () => {
        const newBoard = selectBoard.value;
        if (newBoard !== selectedBoard) {
            selectedBoard = newBoard;
            
            // Reset OS Selection since board changed
            selectedImage = null;
            selectedLocalFile = null;
            selectedOSLabel.textContent = 'Choose OS';
            
            // Clear files display
            localFileDisplay.textContent = 'No file selected';
            localFileInput.value = '';
            localFilePathInput.value = '';
            btnConfirmOS.classList.add('disabled');
            btnConfirmOS.disabled = true;

            const cardCustomize = document.getElementById('card-customize');
            
            if (selectedBoard) {
                // Enable OS Selection Card (Step 2)
                cardOS.classList.remove('disabled');
                btnSelectOS.disabled = false;
                
                // Pre-fetch images list for this board
                selectImage.innerHTML = '<option value="" disabled selected>Loading images...</option>';
                fetch(`/api/images/${selectedBoard}`)
                    .then(res => res.json())
                    .then(data => {
                        selectImage.innerHTML = '<option value="" disabled selected>Choose distribution...</option>';
                        if (data.images.length === 0) {
                            if (selectedBoard === "orangepi4pro") {
                                selectImage.innerHTML = '<option value="" disabled>No official Armbian builds for Orange Pi 4 Pro. Use Custom File below.</option>';
                            } else {
                                selectImage.innerHTML = '<option value="" disabled>No recent distributions found in archive.</option>';
                            }
                            return;
                        }
                        data.images.forEach((img, idx) => {
                            const opt = document.createElement('option');
                            opt.value = idx;
                            opt.textContent = `${img.distro} - ${img.variant} (${img.kernel})`;
                            opt.dataset.img = JSON.stringify(img);
                            selectImage.appendChild(opt);
                        });
                    })
                    .catch(err => {
                        console.error("Error loading images:", err);
                        selectImage.innerHTML = '<option value="" disabled>Error: Failed to fetch image list from server.</option>';
                    });
            } else {
                // Disable OS Selection Card (Step 2)
                cardOS.classList.add('disabled');
                btnSelectOS.disabled = true;
                
                // Disable Customize Card (Step 3)
                cardCustomize.classList.add('disabled');
                btnOpenCustomize.disabled = true;
            }
        }
        validateInputs();
    });

    // --- STEP 2: OS SELECTION ---
    btnSelectOS.addEventListener('click', () => {
        openModal(modalOS);
    });

    selectImage.addEventListener('change', () => {
        const selectedOpt = selectImage.options[selectImage.selectedIndex];
        selectedImage = JSON.parse(selectedOpt.dataset.img);
        selectedLocalFile = null; // Clear local file if choosing remote OS
        
        btnConfirmOS.classList.remove('disabled');
        btnConfirmOS.disabled = false;
    });

    localFileInput.addEventListener('change', (e) => {
        const file = e.target.files[0];
        if (file) {
            localFileDisplay.innerHTML = `<i class="fa-solid fa-circle-notch fa-spin"></i> Checking ${file.name}...`;
            localFilePathInput.value = '';
            localFilePathInput.disabled = true;
            localFileInput.disabled = true;
            selectedLocalFile = null;
            selectedImage = null;
            selectImage.selectedIndex = 0;
            btnConfirmOS.classList.add('disabled');
            btnConfirmOS.disabled = true;

            function onUploadComplete(data) {
                localFileDisplay.textContent = file.name;
                localFilePathInput.value = data.path;
                localFilePathInput.disabled = false;
                localFileInput.disabled = false;
                selectedLocalFile = {
                    name: file.name,
                    path: data.path
                };
                btnConfirmOS.classList.remove('disabled');
                btnConfirmOS.disabled = false;
            }

            function onUploadError(msg) {
                localFileDisplay.innerHTML = `<i class="fa-solid fa-circle-xmark" style="color: var(--error);"></i> ${msg}`;
                localFilePathInput.disabled = false;
                localFileInput.disabled = false;
            }

            // Check if the file already exists on the server
            fetch('/api/check_upload', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ filename: file.name, size: file.size })
            })
            .then(res => res.json())
            .then(checkData => {
                if (checkData.exists) {
                    localFileDisplay.innerHTML = `<i class="fa-solid fa-circle-check" style="color: #22c55e;"></i> ${file.name} (cached)`;
                    onUploadComplete(checkData);
                    return;
                }

                // Upload with progress via XMLHttpRequest
                const formData = new FormData();
                formData.append('file', file);

                const xhr = new XMLHttpRequest();
                xhr.open('POST', '/api/upload');

                xhr.upload.addEventListener('progress', (evt) => {
                    if (evt.lengthComputable) {
                        const pct = Math.round((evt.loaded / evt.total) * 100);
                        const loadedMB = (evt.loaded / (1024 * 1024)).toFixed(1);
                        const totalMB = (evt.total / (1024 * 1024)).toFixed(1);
                        localFileDisplay.innerHTML = `<i class="fa-solid fa-circle-notch fa-spin"></i> Uploading ${file.name} — ${pct}% (${loadedMB} / ${totalMB} MB)`;
                    }
                });

                xhr.addEventListener('load', () => {
                    if (xhr.status === 200) {
                        const data = JSON.parse(xhr.responseText);
                        if (data.error) {
                            onUploadError(data.error);
                            return;
                        }
                        onUploadComplete(data);
                    } else {
                        onUploadError('Upload failed. Try pasting the path manually.');
                    }
                });

                xhr.addEventListener('error', () => {
                    onUploadError('Upload failed. Try pasting the path manually.');
                });

                xhr.send(formData);
            })
            .catch(err => {
                console.error("Error uploading file:", err);
                onUploadError('Upload failed. Try pasting the path manually.');
            });
        }
    });

    localFilePathInput.addEventListener('input', () => {
        const fullPath = localFilePathInput.value.trim();
        if (fullPath) {
            const fileName = fullPath.split('\\').pop().split('/').pop();
            selectedLocalFile = {
                name: fileName,
                path: fullPath
            };
            selectedImage = null; // Clear remote OS
            
            localFileDisplay.textContent = fileName;
            
            // Reset dropdown select
            selectImage.selectedIndex = 0;
            
            btnConfirmOS.classList.remove('disabled');
            btnConfirmOS.disabled = false;
        } else {
            selectedLocalFile = null;
            if (selectImage.selectedIndex <= 0) {
                btnConfirmOS.classList.add('disabled');
                btnConfirmOS.disabled = true;
            }
        }
    });

    btnConfirmOS.addEventListener('click', () => {
        if (selectedLocalFile) {
            selectedOSLabel.textContent = `Custom: ${selectedLocalFile.name}`;
        } else if (selectedImage) {
            selectedOSLabel.textContent = `${BOARDS_MAP[selectedBoard]} - ${selectedImage.distro}`;
        }
        
        // Enable Customize Step (Step 3)
        const cardCustomize = document.getElementById('card-customize');
        cardCustomize.classList.remove('disabled');
        btnOpenCustomize.disabled = false;
        
        closeModal(modalOS);
        validateInputs();
    });

    const BOARDS_MAP = {
        "orangepizero3": "Orange Pi Zero 3",
        "orangepi5": "Orange Pi 5",
        "orangepi5-plus": "Orange Pi 5 Plus",
        "orangepizero2": "Orange Pi Zero 2",
        "orangepi3-lts": "Orange Pi 3 LTS",
        "orangepi4-lts": "Orange Pi 4 LTS",
        "orangepi4pro": "Orange Pi 4 Pro",
        "orangepione": "Orange Pi One",
        "orangepizero": "Orange Pi Zero",
        "orangepipc2": "Orange Pi PC 2",
        "custom": "Custom File"
    };

    // --- STEP 2: CUSTOMIZATION MODAL ---
    btnOpenCustomize.addEventListener('click', () => {
        // Populate inputs from configData
        document.getElementById('input-hostname').value = configData.hostname;
        document.getElementById('input-username').value = configData.username;
        document.getElementById('input-password').value = configData.password;
        document.getElementById('input-wifi-ssid').value = configData.wifi_ssid;
        document.getElementById('input-wifi-password').value = configData.wifi_password;
        document.getElementById('input-ssh-key').value = configData.ssh_key;
        
        const checkboxEnableSSH = document.getElementById('checkbox-enable-ssh');
        if (checkboxEnableSSH) {
            checkboxEnableSSH.checked = configData.enable_ssh;
            checkboxEnableSSH.dispatchEvent(new Event('change'));
        }
        
        // Populate checkboxes
        document.getElementById('checkbox-app-firefox').checked = configData.preload_apps.includes('firefox');
        document.getElementById('checkbox-app-vscode').checked = configData.preload_apps.includes('vscode');
        document.getElementById('checkbox-app-kiwix').checked = configData.preload_apps.includes('kiwix');
        document.getElementById('checkbox-app-dictionary').checked = configData.preload_apps.includes('dictionary');
        document.getElementById('checkbox-app-sudoku').checked = configData.preload_apps.includes('sudoku');
        document.getElementById('checkbox-app-stardew').checked = configData.preload_apps.includes('stardew');
        
        updateAppSpaceCounter();
        openModal(modalCustomize);
    });

    function revertCustomizeForm() {
        document.getElementById('input-hostname').value = configData.hostname;
        document.getElementById('input-username').value = configData.username;
        document.getElementById('input-password').value = configData.password;
        document.getElementById('input-wifi-ssid').value = configData.wifi_ssid;
        document.getElementById('input-wifi-password').value = configData.wifi_password;
        document.getElementById('input-ssh-key').value = configData.ssh_key;
        
        const checkboxEnableSSH = document.getElementById('checkbox-enable-ssh');
        if (checkboxEnableSSH) {
            checkboxEnableSSH.checked = configData.enable_ssh;
            checkboxEnableSSH.dispatchEvent(new Event('change'));
        }
        
        document.getElementById('checkbox-app-firefox').checked = configData.preload_apps.includes('firefox');
        document.getElementById('checkbox-app-vscode').checked = configData.preload_apps.includes('vscode');
        document.getElementById('checkbox-app-kiwix').checked = configData.preload_apps.includes('kiwix');
        document.getElementById('checkbox-app-dictionary').checked = configData.preload_apps.includes('dictionary');
        document.getElementById('checkbox-app-sudoku').checked = configData.preload_apps.includes('sudoku');
        document.getElementById('checkbox-app-stardew').checked = configData.preload_apps.includes('stardew');
        
        updateAppSpaceCounter();
    }

    modalCustomize.querySelectorAll('.close-modal-btn').forEach(btn => {
        btn.addEventListener('click', revertCustomizeForm);
    });

    modalCustomize.querySelectorAll('.cancel-modal-btn').forEach(btn => {
        btn.addEventListener('click', revertCustomizeForm);
    });

    // Tabs inside Customization
    document.querySelectorAll('.tab-btn').forEach(btn => {
        btn.addEventListener('click', () => {
            document.querySelectorAll('.tab-btn').forEach(b => b.classList.remove('active'));
            document.querySelectorAll('.tab-content').forEach(c => c.classList.remove('active'));
            
            btn.classList.add('active');
            document.getElementById(btn.dataset.tab).classList.add('active');
        });
    });

    // Password visibility toggle
    document.querySelectorAll('.toggle-password-btn').forEach(btn => {
        btn.addEventListener('click', (e) => {
            const input = btn.previousElementSibling;
            const icon = btn.querySelector('i');
            if (input.type === 'password') {
                input.type = 'text';
                icon.className = 'fa-solid fa-eye-slash';
            } else {
                input.type = 'password';
                icon.className = 'fa-solid fa-eye';
            }
        });
    });

    // Fetch keys from GitHub
    const btnFetchGithub = document.getElementById('btn-fetch-github-keys');
    if (btnFetchGithub) {
        btnFetchGithub.addEventListener('click', () => {
            const username = document.getElementById('input-github-username').value.trim();
            if (!username) {
                alert("Please enter a GitHub username first.");
                return;
            }
            btnFetchGithub.disabled = true;
            btnFetchGithub.innerHTML = '<i class="fa-solid fa-spinner fa-spin"></i> Fetching...';
            
            fetch(`/api/github_keys?username=${username}`)
                .then(res => res.json())
                .then(data => {
                    if (data.keys) {
                        const textarea = document.getElementById('input-ssh-key');
                        if (textarea.value.trim()) {
                            textarea.value = textarea.value.trim() + '\n' + data.keys.trim();
                        } else {
                            textarea.value = data.keys.trim();
                        }
                        alert(`Successfully fetched keys for ${username}!`);
                    } else {
                        alert("Error: " + (data.error || "No keys found."));
                    }
                })
                .catch(err => {
                    console.error("Error fetching keys:", err);
                    alert("Network error fetching keys from GitHub.");
                })
                .finally(() => {
                    btnFetchGithub.disabled = !checkboxEnableSSH.checked;
                    btnFetchGithub.innerHTML = '<i class="fa-solid fa-cloud-arrow-down"></i> Fetch Keys';
                });
        });
    }

    // Toggle SSH Fields based on checkbox
    const checkboxEnableSSH = document.getElementById('checkbox-enable-ssh');
    const sshFieldsWrapper = document.getElementById('ssh-fields-wrapper');
    const inputGithubUsername = document.getElementById('input-github-username');
    const inputSSHKey = document.getElementById('input-ssh-key');

    if (checkboxEnableSSH) {
        checkboxEnableSSH.addEventListener('change', () => {
            const enabled = checkboxEnableSSH.checked;
            if (enabled) {
                sshFieldsWrapper.classList.remove('disabled-group');
                inputGithubUsername.disabled = false;
                btnFetchGithub.disabled = false;
                inputSSHKey.disabled = false;
            } else {
                sshFieldsWrapper.classList.add('disabled-group');
                inputGithubUsername.disabled = true;
                btnFetchGithub.disabled = true;
                inputSSHKey.disabled = true;
            }
        });
    }

    btnSaveCustomize.addEventListener('click', () => {
        configData.hostname = document.getElementById('input-hostname').value;
        configData.username = document.getElementById('input-username').value;
        configData.password = document.getElementById('input-password').value;
        configData.wifi_ssid = document.getElementById('input-wifi-ssid').value;
        configData.wifi_password = document.getElementById('input-wifi-password').value;
        configData.ssh_key = document.getElementById('input-ssh-key').value;
        configData.enable_ssh = checkboxEnableSSH ? checkboxEnableSSH.checked : false;
        
        const selectedApps = [];
        if (document.getElementById('checkbox-app-firefox').checked) selectedApps.push('firefox');
        if (document.getElementById('checkbox-app-vscode').checked) selectedApps.push('vscode');
        if (document.getElementById('checkbox-app-kiwix').checked) selectedApps.push('kiwix');
        if (document.getElementById('checkbox-app-dictionary').checked) selectedApps.push('dictionary');
        if (document.getElementById('checkbox-app-sudoku').checked) selectedApps.push('sudoku');
        if (document.getElementById('checkbox-app-stardew').checked) selectedApps.push('stardew');
        configData.preload_apps = selectedApps;
        
        configApplied = true;
        configStatusBadge.style.display = 'inline-flex';
        
        closeModal(modalCustomize);
        validateInputs();
    });

    // App checkbox listeners for live space counter updates
    const appIds = ['firefox', 'vscode', 'kiwix', 'dictionary', 'sudoku', 'stardew'];
    appIds.forEach(app => {
        const cb = document.getElementById('checkbox-app-' + app);
        if (cb) {
            cb.addEventListener('change', updateAppSpaceCounter);
        }
    });

    // Deselect all apps button binding
    const btnDeselectAllApps = document.getElementById('btn-deselect-all-apps');
    if (btnDeselectAllApps) {
        btnDeselectAllApps.addEventListener('click', () => {
            appIds.forEach(app => {
                const cb = document.getElementById('checkbox-app-' + app);
                if (cb) {
                    cb.checked = false;
                }
            });
            updateAppSpaceCounter();
        });
    }

    // Select all apps button binding
    const btnSelectAllApps = document.getElementById('btn-select-all-apps');
    if (btnSelectAllApps) {
        btnSelectAllApps.addEventListener('click', () => {
            appIds.forEach(app => {
                const cb = document.getElementById('checkbox-app-' + app);
                if (cb) {
                    cb.checked = true;
                }
            });
            updateAppSpaceCounter();
        });
    }

    // --- STEP 3: STORAGE SELECTION ---
    btnSelectStorage.addEventListener('click', () => {
        openModal(modalStorage);
        loadDisks();
    });

    btnRefreshDisks.addEventListener('click', () => {
        const icon = btnRefreshDisks.querySelector('i');
        icon.classList.add('fa-spin');
        loadDisks(() => {
            icon.classList.remove('fa-spin');
        });
    });

    function loadDisks(callback = null) {
        diskListContainer.innerHTML = '<div class="loading-spinner"><i class="fa-solid fa-circle-notch fa-spin"></i> Detecting storage devices...</div>';
        btnConfirmStorage.classList.add('disabled');
        btnConfirmStorage.disabled = true;

        fetch('/api/disks')
            .then(res => res.json())
            .then(data => {
                diskListContainer.innerHTML = '';
                if (data.disks.length === 0) {
                    diskListContainer.innerHTML = '<div class="loading-spinner"><i class="fa-solid fa-triangle-exclamation"></i> No removable drives found.</div>';
                    return;
                }
                
                data.disks.forEach(d => {
                    const item = document.createElement('div');
                    item.className = 'disk-item';
                    
                    const isProtected = d.is_system || d.bus_type.toLowerCase() === 'sata' || !d.is_removable;
                    if (isProtected) {
                        item.classList.add('protected');
                    }
                    
                    item.dataset.disk = JSON.stringify(d);
                    
                    let badge = '';
                    if (d.is_system) {
                        badge = '<span class="protected-badge">System Boot Disk (Protected)</span>';
                    } else if (d.bus_type.toLowerCase() === 'sata') {
                        badge = '<span class="protected-badge">SATA Drive (Protected)</span>';
                    } else if (!d.is_removable) {
                        badge = '<span class="protected-badge">Internal Drive (Protected)</span>';
                    }
                    
                    const iconClass = d.is_system ? 'fa-laptop' : (isProtected ? 'fa-hard-drive' : 'fa-sd-card');
                    
                    item.innerHTML = `
                        <div class="disk-info">
                            <i class="fa-solid ${iconClass}"></i>
                            <div class="disk-meta">
                                <h4>${d.display_name}: ${d.name} ${badge}</h4>
                                <span>Bus: ${d.bus_type} | Removable: ${d.is_removable ? 'Yes' : 'No'}</span>
                            </div>
                        </div>
                        <div class="disk-size">${d.size_gb} GB</div>
                    `;
                    
                    if (!isProtected) {
                        item.addEventListener('click', () => {
                            document.querySelectorAll('.disk-item').forEach(i => i.classList.remove('selected'));
                            item.classList.add('selected');
                            selectedDisk = d;
                            
                            btnConfirmStorage.classList.remove('disabled');
                            btnConfirmStorage.disabled = false;
                        });
                    }
                    
                    diskListContainer.appendChild(item);
                });
            })
            .catch(err => {
                console.error("Error loading disks:", err);
                diskListContainer.innerHTML = '<div class="loading-spinner"><i class="fa-solid fa-circle-xmark"></i> Failed to query physical drives.</div>';
            })
            .finally(() => {
                if (callback) callback();
            });
    }

    btnConfirmStorage.addEventListener('click', () => {
        if (selectedDisk) {
            selectedStorageLabel.textContent = `${selectedDisk.display_name}: ${selectedDisk.name} (${selectedDisk.size_gb} GB)`;
        }
        closeModal(modalStorage);
        validateInputs();
    });

    // Validation
    function validateInputs() {
        const osSelected = (selectedBoard && (selectedImage || selectedLocalFile));
        const storageSelected = (selectedDisk !== null);
        
        if (osSelected && storageSelected) {
            btnFlash.classList.remove('disabled');
            btnFlash.disabled = false;
        } else {
            btnFlash.classList.add('disabled');
            btnFlash.disabled = true;
        }
    }

    // --- ACTIONS: FLASHING ---
    btnFlash.addEventListener('click', () => {
        if (!selectedDisk) return;
        
        const confirmMsg = `WARNING: Are you sure you want to write to ${selectedDisk.display_name} (${selectedDisk.name})?\n\nALL EXISTING DATA ON THIS DRIVE WILL BE PERMANENTLY DELETED.`;
        if (!confirm(confirmMsg)) return;

        const payload = {
            board_id: selectedLocalFile ? 'custom' : selectedBoard,
            download_url: selectedImage ? selectedImage.download_url : null,
            local_image_path: selectedLocalFile ? selectedLocalFile.path : null,
            device: selectedDisk.device,
            hostname: configApplied ? configData.hostname : '',
            username: configApplied ? configData.username : '',
            password: configApplied ? configData.password : '',
            wifi_ssid: configApplied ? configData.wifi_ssid : '',
            wifi_password: configApplied ? configData.wifi_password : '',
            ssh_key: configApplied ? configData.ssh_key : '',
            enable_ssh: configApplied ? configData.enable_ssh : false,
            preload_apps: configApplied ? configData.preload_apps : []
        };

        btnFlash.classList.add('disabled');
        btnFlash.disabled = true;

        fetch('/api/flash', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(payload)
        })
        .then(res => res.json())
        .then(data => {
            if (data.status === 'started') {
                // Shift views
                mainDashboard.classList.add('hidden');
                progressView.classList.remove('hidden');
                headerStatus.textContent = 'Writing...';
                startStatusPolling();
            } else {
                alert("Error starting flash: " + data.error);
                validateInputs();
            }
        })
        .catch(err => {
            console.error("Error starting flash:", err);
            alert("Network error starting flash task.");
            validateInputs();
        });
    });

    let pollingInterval = null;

    function startStatusPolling() {
        if (pollingInterval) clearInterval(pollingInterval);
        
        // Reset steps
        document.querySelectorAll('.p-step').forEach(step => {
            step.className = 'p-step';
        });

        pollingInterval = setInterval(() => {
            fetch('/api/status')
                .then(res => res.json())
                .then(state => {
                    const status = state.status;
                    const progress = state.progress;
                    const message = state.message;
                    
                    setProgress(progress);
                    progressMessage.textContent = message;

                    // Update UI states based on active status
                    if (status === 'downloading') {
                        progressHeader.textContent = "Downloading Operating System Image";
                        setStepActive('p-step-download');
                    } else if (status === 'decompressing') {
                        progressHeader.textContent = "Decompressing Image Archive";
                        setStepCompleted('p-step-download');
                        setStepActive('p-step-decompress');
                    } else if (status === 'cleaning' || status === 'writing') {
                        progressHeader.textContent = "Writing Image Sectors to SD Card";
                        setStepCompleted('p-step-download');
                        setStepCompleted('p-step-decompress');
                        setStepCompleted('p-step-customize');
                        setStepActive('p-step-flash');
                    } else if (status === 'success') {
                        clearInterval(pollingInterval);
                        progressView.classList.add('hidden');
                        successView.classList.remove('hidden');
                        headerStatus.textContent = 'Completed';

                        // Check if post-boot setup script was generated
                        const instrAuto = document.getElementById('instructions-auto');
                        const instrManual = document.getElementById('instructions-manual');
                        if (message && message.startsWith('SETUP_SCRIPTS:')) {
                            const paths = message.substring('SETUP_SCRIPTS:'.length).split('|');
                            const userScriptPath = paths[0];
                            const configScriptPath = paths[1];
                            instrAuto.classList.add('hidden');
                            instrManual.classList.remove('hidden');
                            document.getElementById('setup-script-path').textContent = userScriptPath;
                            document.getElementById('setup-script-command').textContent =
                                '# Step 1 — Copy both scripts to your Pi:\n' +
                                'scp "' + userScriptPath + '" user@<PI_IP>:/tmp/setup_user.sh\n' +
                                'scp "' + configScriptPath + '" user@<PI_IP>:/tmp/setup_config.sh\n\n' +
                                '# Step 2 — SSH in and create the new user:\n' +
                                'ssh user@<PI_IP>\n' +
                                'sudo bash /tmp/setup_user.sh\n\n' +
                                '# Step 3 — Log out, log back in as your new user, then finish setup:\n' +
                                'sudo bash /tmp/setup_config.sh';
                        } else {
                            instrAuto.classList.remove('hidden');
                            instrManual.classList.add('hidden');
                        }
                    } else if (status === 'error') {
                        clearInterval(pollingInterval);
                        alert(`Flashing Error:\n\n${message}`);
                        resetToDashboard();
                    }
                })
                .catch(err => console.error("Error fetching status:", err));
        }, 500);
    }

    function setStepActive(stepId) {
        document.getElementById(stepId).className = 'p-step active';
    }

    function setStepCompleted(stepId) {
        document.getElementById(stepId).className = 'p-step completed';
    }

    btnCancelFlash.addEventListener('click', () => {
        if (confirm("Are you sure you want to cancel the writing process?")) {
            fetch('/api/cancel', { method: 'POST' })
                .then(res => res.json())
                .then(() => {
                    clearInterval(pollingInterval);
                    resetToDashboard();
                })
                .catch(err => console.error("Error cancelling:", err));
        }
    });

    function resetToDashboard() {
        progressView.classList.add('hidden');
        successView.classList.add('hidden');
        mainDashboard.classList.remove('hidden');
        headerStatus.textContent = 'Ready';
        validateInputs();
    }

    btnSuccessReset.addEventListener('click', () => {
        // Clear variables
        selectedDisk = null;
        selectedStorageLabel.textContent = 'Select Drive';
        
        resetToDashboard();
    });

    // Initial counter sync
    updateAppSpaceCounter();
});
