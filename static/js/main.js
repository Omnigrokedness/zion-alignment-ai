// Main JavaScript file for Zion's Steward

document.addEventListener('DOMContentLoaded', function() {
    // Initialize tooltips
    var tooltipTriggerList = [].slice.call(document.querySelectorAll('[data-bs-toggle="tooltip"]'));
    var tooltipList = tooltipTriggerList.map(function (tooltipTriggerEl) {
        return new bootstrap.Tooltip(tooltipTriggerEl);
    });

    // Handle adding new truths
    const addTruthForm = document.getElementById('add-truth-form');
    if (addTruthForm) {
        addTruthForm.addEventListener('submit', function(e) {
            e.preventDefault();
            
            const content = document.getElementById('truth-content').value;
            const source = document.getElementById('truth-source').value;
            
            if (!content) {
                showAlert('Please enter truth content', 'danger');
                return;
            }
            
            fetch('/api/truth/add', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify({
                    content: content,
                    source: source
                })
            })
            .then(response => response.json())
            .then(data => {
                if (data.error) {
                    showAlert(data.error, 'danger');
                } else {
                    showAlert('Truth added successfully', 'success');
                    addTruthForm.reset();
                    
                    // Reload truths if we're on the truths page
                    if (window.location.pathname === '/truths') {
                        setTimeout(() => {
                            window.location.reload();
                        }, 1000);
                    }
                }
            })
            .catch(error => {
                console.error('Error adding truth:', error);
                showAlert('An error occurred while adding the truth', 'danger');
            });
        });
    }

    // Handle truth search
    const searchForm = document.getElementById('search-form');
    if (searchForm) {
        searchForm.addEventListener('submit', function(e) {
            e.preventDefault();
            
            const query = document.getElementById('search-query').value;
            const searchType = document.querySelector('input[name="search-type"]:checked').value;
            
            if (!query) {
                showAlert('Please enter a search query', 'danger');
                return;
            }
            
            fetch(`/api/truth/search?query=${encodeURIComponent(query)}&type=${searchType}`)
            .then(response => response.json())
            .then(data => {
                if (data.error) {
                    showAlert(data.error, 'danger');
                } else {
                    displaySearchResults(data.results);
                }
            })
            .catch(error => {
                console.error('Error searching truths:', error);
                showAlert('An error occurred while searching', 'danger');
            });
        });
    }

    // Handle model update from settings
    const updateModelForm = document.getElementById('update-model-form');
    if (updateModelForm) {
        updateModelForm.addEventListener('submit', function(e) {
            e.preventDefault();
            
            const modelPath = document.getElementById('model-path').value;
            const quantization = document.getElementById('quantization').value;
            
            if (!modelPath) {
                showAlert('Please enter a model path', 'danger');
                return;
            }
            
            showAlert('Starting model update. This may take several minutes...', 'info');
            
            fetch('/api/upgrader/load-model', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify({
                    model_path: modelPath,
                    quantization: quantization
                })
            })
            .then(response => response.json())
            .then(data => {
                if (data.error) {
                    showAlert(data.error, 'danger');
                } else {
                    showAlert(data.message, 'success');
                }
            })
            .catch(error => {
                console.error('Error updating model:', error);
                showAlert('An error occurred while updating the model', 'danger');
            });
        });
    }

    // Handle replication node management
    const addNodeForm = document.getElementById('add-node-form');
    if (addNodeForm) {
        addNodeForm.addEventListener('submit', function(e) {
            e.preventDefault();
            
            const nodeName = document.getElementById('node-name').value;
            const nodeEndpoint = document.getElementById('node-endpoint').value;
            const nodeApiKey = document.getElementById('node-api-key').value;
            
            if (!nodeName || !nodeEndpoint) {
                showAlert('Please enter node name and endpoint', 'danger');
                return;
            }
            
            fetch('/api/replication/nodes', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify({
                    name: nodeName,
                    endpoint: nodeEndpoint,
                    api_key: nodeApiKey
                })
            })
            .then(response => response.json())
            .then(data => {
                if (data.error) {
                    showAlert(data.error, 'danger');
                } else {
                    showAlert('Node added successfully', 'success');
                    addNodeForm.reset();
                    loadReplicationNodes();
                }
            })
            .catch(error => {
                console.error('Error adding node:', error);
                showAlert('An error occurred while adding the node', 'danger');
            });
        });
    }

    // Load initial data
    loadModelInfo();
    loadReplicationNodes();
    loadStats();
});

// Display search results
function displaySearchResults(results) {
    const resultsContainer = document.getElementById('search-results');
    if (!resultsContainer) return;
    
    if (results.length === 0) {
        resultsContainer.innerHTML = '<div class="alert alert-info">No results found</div>';
        return;
    }
    
    let html = '<div class="list-group">';
    results.forEach(result => {
        let topicsHtml = '';
        if (result.topics && result.topics.length > 0) {
            topicsHtml = '<div class="mt-2">';
            result.topics.forEach(topic => {
                topicsHtml += `<span class="badge bg-info me-1">${topic}</span>`;
            });
            topicsHtml += '</div>';
        }
        
        html += `
            <div class="list-group-item">
                <div class="d-flex justify-content-between align-items-start">
                    <div>
                        <p>${result.content}</p>
                        <small class="text-muted">Source: ${result.source || 'Unknown'}</small>
                        ${topicsHtml}
                    </div>
                    <div class="ms-2">
                        <button class="btn btn-sm btn-outline-danger" onclick="deleteTruth(${result.id})">
                            <i class="bi bi-trash"></i>
                        </button>
                    </div>
                </div>
            </div>
        `;
    });
    html += '</div>';
    
    resultsContainer.innerHTML = html;
}

// Load model information
function loadModelInfo() {
    const modelInfoContainer = document.getElementById('model-info');
    if (!modelInfoContainer) return;
    
    fetch('/api/llm/model-info')
    .then(response => response.json())
    .then(data => {
        if (data.error) {
            modelInfoContainer.innerHTML = `<div class="alert alert-warning">${data.error}</div>`;
        } else {
            modelInfoContainer.innerHTML = `
                <div class="card">
                    <div class="card-body">
                        <h5 class="card-title">Current Model</h5>
                        <p><strong>Name:</strong> ${data.model_name}</p>
                        <p><strong>Version:</strong> ${data.model_version}</p>
                        <p><strong>Path:</strong> ${data.model_path}</p>
                        <p><strong>Quantization:</strong> ${data.quantization}</p>
                        <p><strong>Last Used:</strong> ${data.last_used ? new Date(data.last_used).toLocaleString() : 'Never'}</p>
                    </div>
                </div>
            `;
        }
    })
    .catch(error => {
        console.error('Error loading model info:', error);
        modelInfoContainer.innerHTML = '<div class="alert alert-danger">Failed to load model information</div>';
    });
}

// Load replication nodes
function loadReplicationNodes() {
    const nodesContainer = document.getElementById('replication-nodes');
    if (!nodesContainer) return;
    
    fetch('/api/replication/nodes')
    .then(response => response.json())
    .then(data => {
        if (data.error) {
            nodesContainer.innerHTML = `<div class="alert alert-warning">${data.error}</div>`;
        } else if (data.nodes.length === 0) {
            nodesContainer.innerHTML = '<div class="alert alert-info">No replication nodes configured</div>';
        } else {
            let html = '<div class="list-group">';
            data.nodes.forEach(node => {
                const statusClass = node.status === 'active' ? 'status-active' : 
                                    node.status === 'error' ? 'status-error' : 'status-inactive';
                
                html += `
                    <div class="list-group-item">
                        <div class="d-flex justify-content-between align-items-center">
                            <div>
                                <div class="d-flex align-items-center">
                                    <span class="status-indicator ${statusClass}"></span>
                                    <h5 class="mb-1">${node.name}</h5>
                                </div>
                                <p class="mb-1">${node.endpoint}</p>
                                <small class="text-muted">Last sync: ${node.last_sync ? new Date(node.last_sync).toLocaleString() : 'Never'}</small>
                            </div>
                            <div>
                                <button class="btn btn-sm btn-primary me-2" onclick="syncNode(${node.id})">Sync</button>
                                <button class="btn btn-sm btn-danger" onclick="deleteNode(${node.id})">Delete</button>
                            </div>
                        </div>
                    </div>
                `;
            });
            html += '</div>';
            
            nodesContainer.innerHTML = html;
        }
    })
    .catch(error => {
        console.error('Error loading replication nodes:', error);
        nodesContainer.innerHTML = '<div class="alert alert-danger">Failed to load replication nodes</div>';
    });
}

// Load dashboard stats
function loadStats() {
    const statsContainer = document.getElementById('dashboard-stats');
    if (!statsContainer) return;
    
    // Load truth count
    fetch('/api/truth/all')
    .then(response => response.json())
    .then(data => {
        if (!data.error) {
            document.getElementById('truth-count').textContent = data.truths.length;
        }
    })
    .catch(error => console.error('Error loading truth count:', error));
    
    // Load topic count
    fetch('/api/truth/topics')
    .then(response => response.json())
    .then(data => {
        if (!data.error) {
            document.getElementById('topic-count').textContent = data.topics.length;
        }
    })
    .catch(error => console.error('Error loading topic count:', error));
    
    // Load call logs
    fetch('/api/twilio/logs')
    .then(response => response.json())
    .then(data => {
        if (!data.error) {
            document.getElementById('call-count').textContent = data.logs.length;
        }
    })
    .catch(error => console.error('Error loading call count:', error));
}

// Delete a truth
function deleteTruth(id) {
    if (!confirm('Are you sure you want to delete this truth?')) return;
    
    fetch(`/api/truth/delete/${id}`, {
        method: 'DELETE'
    })
    .then(response => response.json())
    .then(data => {
        if (data.error) {
            showAlert(data.error, 'danger');
        } else {
            showAlert('Truth deleted successfully', 'success');
            
            // Reload truths if we're on the truths page
            if (window.location.pathname === '/truths') {
                setTimeout(() => {
                    window.location.reload();
                }, 1000);
            } else {
                // Otherwise just refresh the search results
                document.getElementById('search-form').dispatchEvent(new Event('submit'));
            }
        }
    })
    .catch(error => {
        console.error('Error deleting truth:', error);
        showAlert('An error occurred while deleting the truth', 'danger');
    });
}

// Sync with a replication node
function syncNode(id) {
    fetch(`/api/replication/sync/${id}`, {
        method: 'POST'
    })
    .then(response => response.json())
    .then(data => {
        if (data.error) {
            showAlert(data.error, 'danger');
        } else {
            showAlert(`Sync successful. Synced ${data.synced_truths} truths.`, 'success');
            loadReplicationNodes();
        }
    })
    .catch(error => {
        console.error('Error syncing node:', error);
        showAlert('An error occurred while syncing with the node', 'danger');
    });
}

// Delete a replication node
function deleteNode(id) {
    if (!confirm('Are you sure you want to delete this replication node?')) return;
    
    fetch(`/api/replication/nodes/${id}`, {
        method: 'DELETE'
    })
    .then(response => response.json())
    .then(data => {
        if (data.error) {
            showAlert(data.error, 'danger');
        } else {
            showAlert('Node deleted successfully', 'success');
            loadReplicationNodes();
        }
    })
    .catch(error => {
        console.error('Error deleting node:', error);
        showAlert('An error occurred while deleting the node', 'danger');
    });
}

// Show alert
function showAlert(message, type) {
    const alertsContainer = document.getElementById('alerts-container');
    if (!alertsContainer) return;
    
    const alert = document.createElement('div');
    alert.className = `alert alert-${type} alert-dismissible fade show`;
    alert.role = 'alert';
    
    alert.innerHTML = `
        ${message}
        <button type="button" class="btn-close" data-bs-dismiss="alert" aria-label="Close"></button>
    `;
    
    alertsContainer.appendChild(alert);
    
    // Auto dismiss after 5 seconds
    setTimeout(() => {
        alert.classList.remove('show');
        setTimeout(() => {
            alert.remove();
        }, 150);
    }, 5000);
}
