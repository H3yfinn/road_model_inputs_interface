/**
 * app.js
 * Main UI Logic and State Management for the Multinode Energy Modeler.
 * Enforces strict 'en-US' locale parameters and fully dynamic dictionary-based macro driver allocation.
 */

// ==========================================
// 1. GLOBAL STATE & DOM CACHE
// ==========================================
const State = {
    economy: null,
    year: null,
    sector_flow: null,
    total_energy: 0,
    macro_targets: {}, 
    treeState: {},     
    balancedTree: null,
    // NEW: Open and extensible dictionary configuration for variable socio-economic drivers
    macroDrivers: {
        households: 132400000,
        floor_area_sqm: 26470.5,
        occupancy_rate: 0.8
    },
    // INTERACTIVE CANVAS ZOOM & PAN STATE
    zoomScale: 1.0,
    panX: 40,
    panY: 100,
    isDragging: false,
    startX: 0,
    startY: 0,
    isCompactMode: false,
    activeNodePathStr: null
};

const DOM = {
    selectEconomy: document.getElementById('select-economy'),
    selectYear: document.getElementById('select-year'),
    selectSector: document.getElementById('select-sector'),
    
    // Dynamic macro drivers lifecycle element cache
    selectMacroDriverType: document.getElementById('select-macro-driver-type'),
    containerCustomDriverName: document.getElementById('container-custom-driver-name'),
    inputCustomDriverName: document.getElementById('input-custom-driver-name'),
    btnAddMacroDriver: document.getElementById('btn-add-macro-driver'),
    globalDriversContainer: document.getElementById('global-drivers-container'),
    
    btnStart: document.getElementById('btn-start'),
    targetDashboard: document.getElementById('target-dashboard'),
    displayTotalEnergy: document.getElementById('display-total-energy'),
    fuelTargetsContainer: document.getElementById('fuel-targets-container'),
    canvasEmptyState: document.getElementById('canvas-empty-state'),
    treeRootContainer: document.getElementById('tree-root-container'),
    treeNodesList: document.getElementById('tree-nodes-list'),
    btnAddRoot: document.getElementById('btn-add-root-branch'),
    
    // Multi-screen screen compaction toolbar buttons
    btnCollapseAll: document.getElementById('btn-collapse-all'),
    btnExpandAll: document.getElementById('btn-expand-all'),
    
    loadingOverlay: document.getElementById('loading-overlay'),
    loadingText: document.getElementById('loading-text'),
    actionConsole: document.getElementById('action-console'),
    
    // Actions
    btnValidate: document.getElementById('btn-validate'),
    btnOptimize: document.getElementById('btn-optimize'),
    btnExport: document.getElementById('btn-export'),
    statusMessage: document.getElementById('status-message'),

    // Canvas Interactive Float Elements
    treeCanvas: document.getElementById('tree-canvas'),
    treeTransformContainer: document.getElementById('tree-transform-container'),
    btnZoomIn: document.getElementById('btn-zoom-in'),
    btnZoomOut: document.getElementById('btn-zoom-out'),
    btnFitScreen: document.getElementById('btn-fit-screen'),
    btnToggleCompact: document.getElementById('btn-toggle-compact'),
    displayZoom: document.getElementById('display-zoom'),
    compactIcon: document.getElementById('compact-icon'),
    // Collapsible Results Panel elements
    resultsSidebar: document.getElementById('results-sidebar'),
    btnToggleResults: document.getElementById('btn-toggle-results'),
    selectResultsUnit: document.getElementById('select-results-unit'),
    inputSearchResults: document.getElementById('input-search-results'),
    btnExportResultsCsv: document.getElementById('btn-export-results-csv'),
    resultsTableContainer: document.getElementById('results-table-container'),
    resultsCount: document.getElementById('results-count')
};

// ==========================================
// CUSTOM CONFIRMATION MODAL & TOAST MANAGERS
// ==========================================
let currentConfirmResolve = null;

function showCustomConfirm(title, message, options = {}) {
    const modal = document.getElementById('custom-confirm-modal');
    const titleEl = document.getElementById('confirm-modal-title');
    const msgEl = document.getElementById('confirm-modal-message');
    const btnConfirm = document.getElementById('confirm-modal-confirm');
    const btnCancel = document.getElementById('confirm-modal-cancel');
    
    titleEl.innerText = title;
    msgEl.innerText = message;
    
    btnConfirm.innerText = options.confirmText || 'Confirm';
    btnCancel.innerText = options.cancelText || 'Cancel';
    
    if (options.isDanger) {
        btnConfirm.className = "px-4 py-2 bg-red-600 hover:bg-red-700 text-white rounded-md text-xs font-bold active:scale-95 transition-all";
    } else {
        btnConfirm.className = "px-4 py-2 bg-blue-600 hover:bg-blue-700 text-white rounded-md text-xs font-bold active:scale-95 transition-all";
    }

    modal.classList.remove('hidden');
    modal.classList.add('flex-display');
    
    setTimeout(() => {
        modal.style.opacity = '1';
        modal.querySelector('.bg-white').style.transform = 'scale(1)';
    }, 20);

    return new Promise((resolve) => {
        currentConfirmResolve = resolve;
    });
}

function closeConfirmModal(result) {
    const modal = document.getElementById('custom-confirm-modal');
    modal.style.opacity = '0';
    modal.querySelector('.bg-white').style.transform = 'scale(0.95)';
    
    setTimeout(() => {
        modal.classList.add('hidden');
        modal.classList.remove('flex-display');
        if (currentConfirmResolve) {
            currentConfirmResolve(result);
            currentConfirmResolve = null;
        }
    }, 200);
}

document.getElementById('confirm-modal-confirm').addEventListener('click', () => closeConfirmModal(true));
document.getElementById('confirm-modal-cancel').addEventListener('click', () => closeConfirmModal(false));
document.getElementById('custom-confirm-modal').addEventListener('click', (e) => {
    if (e.target === document.getElementById('custom-confirm-modal')) {
        closeConfirmModal(false);
    }
});

function showCustomToast(message, type = 'info', duration = 3500) {
    const container = document.getElementById('toast-container');
    if (!container) return;

    const toast = document.createElement('div');
    toast.className = `custom-toast toast-${type}`;
    
    let icon = '';
    if (type === 'success') {
        icon = `<svg class="w-4 h-4 text-emerald-500 flex-shrink-0" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2.5" d="M9 12l2 2 4-4m6 2a9 9 0 11-18 0 9 9 0 0118 0z"></path></svg>`;
    } else if (type === 'error') {
        icon = `<svg class="w-4 h-4 text-red-500 flex-shrink-0" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2.5" d="M10 14l2-2m0 0l2-2m-2 2l-2-2m2 2l2 2m7-2a9 9 0 11-18 0 9 9 0 0118 0z"></path></svg>`;
    } else {
        icon = `<svg class="w-4 h-4 text-amber-500 flex-shrink-0" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2.5" d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z"></path></svg>`;
    }

    toast.innerHTML = `
        ${icon}
        <span class="text-xs font-semibold text-slate-700">${message}</span>
    `;
    
    container.appendChild(toast);

    setTimeout(() => {
        toast.classList.add('toast-fade-out');
        toast.addEventListener('animationend', () => {
            toast.remove();
        });
    }, duration);
}

// ==========================================
// 2. INITIALIZATION & SETUP
// ==========================================

function initApp() {
    setupDropdowns();
    renderGlobalMacroDriversPanel(); // Initial execution pass to append default drivers
    DOM.btnStart.addEventListener('click', handleStartModeling);
    
    // Setup global layout compaction events
    DOM.btnCollapseAll.addEventListener('click', () => handleGlobalCollapse(true));
    DOM.btnExpandAll.addEventListener('click', () => handleGlobalCollapse(false));

    // Listeners for customizable macro driver additions
    DOM.selectMacroDriverType.addEventListener('change', handleMacroDriverTemplateToggle);
    DOM.btnAddMacroDriver.addEventListener('click', handleAddMacroDriverItem);

    // Setup Panning, Zooming, and Float UI bindings
    setupInteractiveCanvas();

    // Setup collapsible results panel events
    setupResultsPanelToggle();
    if (DOM.btnExportResultsCsv) {
        DOM.btnExportResultsCsv.addEventListener('click', handleCSVExport);
    }
    if (DOM.selectResultsUnit) {
        DOM.selectResultsUnit.addEventListener('change', renderResultsSummary);
    }
    if (DOM.inputSearchResults) {
        DOM.inputSearchResults.addEventListener('input', renderResultsSummary);
    }
}

function setupDropdowns() {
    const economies = [
        { code: "01AUS", text: "01AUS (Australia)" },
        { code: "02BD", text: "02BD (Brunei Darussalam)" },
        { code: "03CDA", text: "03CDA (Canada)" },
        { code: "04CHL", text: "04CHL (Chile)" },
        { code: "05PRC", text: "05PRC (China)" },
        { code: "06HKC", text: "06HKC (Hong Kong, China)" },
        { code: "07INA", text: "07INA (Indonesia)" },
        { code: "08JPN", text: "08JPN (Japan)" },
        { code: "09ROK", text: "09ROK (Korea)" },
        { code: "10MAS", text: "10MAS (Malaysia)" },
        { code: "11MEX", text: "11MEX (Mexico)" },
        { code: "12NZ", text: "12NZ (New Zealand)" },
        { code: "13PNG", text: "13PNG (Papua New Guinea)" },
        { code: "14PE", text: "14PE (Peru)" },
        { code: "15PHL", text: "15PHL (Philippines)" },
        { code: "16RUS", text: "16RUS (Russia)" },
        { code: "17SGP", text: "17SGP (Singapore)" },
        { code: "18CT", text: "18CT (Chinese Taipei)" },
        { code: "19THA", text: "19THA (Thailand)" },
        { code: "20USA", text: "20USA (United States)" },
        { code: "21VN", text: "21VN (Viet Nam)" }
    ];
    economies.forEach(eco => DOM.selectEconomy.add(new Option(eco.text, eco.code)));

    for (let y = 2022; y >= 2000; y--) {
        DOM.selectYear.add(new Option(y.toString(), y));
    }

    const sectors = [
        "14 Industry sector",
        "15 Transport sector",
        "16 Other sector",
        "16.01 Commercial and public services",
        "16.02 Residential"
    ];
    sectors.forEach(sec => DOM.selectSector.add(new Option(sec, sec))); 
    DOM.selectSector.value = "16.02 Residential";
    DOM.selectEconomy.value = "20USA"; // Default
}

function handleMacroDriverTemplateToggle() {
    if (DOM.selectMacroDriverType.value === 'custom') {
        DOM.containerCustomDriverName.classList.remove('hidden');
    } else {
        DOM.containerCustomDriverName.classList.add('hidden');
    }
}

function handleAddMacroDriverItem() {
    const selectedTemplate = DOM.selectMacroDriverType.value;
    let targetKey = '';

    if (selectedTemplate === 'custom') {
        const rawInputName = DOM.inputCustomDriverName.value.trim();
        if (!rawInputName) {
            showCustomToast("Please input a non-empty key identifier for custom allocation.", "warning");
            return;
        }
        // Normalize custom textual input into clean snake_case parameters
        targetKey = rawInputName.toLowerCase().replace(/[^a-z0-9_]/g, '_');
    } else {
        targetKey = selectedTemplate;
    }

    if (State.macroDrivers[targetKey] !== undefined) {
        showCustomToast(`Macro driver identifier reference '${targetKey}' already exists.`, "warning");
        return;
    }

    // Add entry with baseline allocation
    State.macroDrivers[targetKey] = 1.0;
    
    // Clear textual input buffer and re-collapse name container if custom template path was used
    DOM.inputCustomDriverName.value = '';
    if (selectedTemplate === 'custom') {
        DOM.selectMacroDriverType.value = 'households';
        DOM.containerCustomDriverName.classList.add('hidden');
    }

    renderGlobalMacroDriversPanel();
    // Forces recursive tree redraw to instantly propagate newly registered key down to node selection dropdowns
    refreshTree();
    showCustomToast(`Macro driver '${targetKey}' added.`, "success");
}

function renderGlobalMacroDriversPanel() {
    DOM.globalDriversContainer.innerHTML = '';
    
    const hardcodedLabels = {
        households: 'Households',
        floor_area_sqm: 'Floor Area (sqm)',
        occupancy_rate: 'Occupancy Rate'
    };

    for (const [driverKey, driverValue] of Object.entries(State.macroDrivers)) {
        const descriptiveLabel = hardcodedLabels[driverKey] || driverKey;
        const html = `
            <div class="flex items-center gap-2 bg-white border border-slate-200 rounded p-1.5 shadow-sm fade-in">
                <div class="flex-1 min-w-0">
                    <label class="block text-[9px] font-bold text-slate-400 uppercase tracking-tight truncate" title="${driverKey}">${descriptiveLabel}</label>
                    <input type="number" step="any" value="${driverValue}" class="w-full text-xs bg-transparent border-none outline-none focus:ring-0 p-0 text-slate-700 font-medium input-global-driver-val" data-key="${driverKey}">
                </div>
                <button type="button" class="text-slate-300 hover:text-red-500 font-bold px-1.5 text-sm transition-colors btn-remove-global-driver" data-key="${driverKey}" title="Remove driver parameters">&times;</button>
            </div>
        `;
        DOM.globalDriversContainer.insertAdjacentHTML('beforeend', html);
    }

    // Real-time local macro driver storage updates
    DOM.globalDriversContainer.querySelectorAll('.input-global-driver-val').forEach(input => {
        input.addEventListener('input', (e) => {
            const key = e.target.dataset.key;
            State.macroDrivers[key] = parseFloat(e.target.value) || 0;
        });
    });

    // Handle removal lifecycle and cascading tree disconnect cleanups
    DOM.globalDriversContainer.querySelectorAll('.btn-remove-global-driver').forEach(btn => {
        btn.addEventListener('click', (e) => {
            const associatedKey = e.target.dataset.key;
            showCustomConfirm(
                "Delete Macro Driver",
                `Are you sure you want to remove the macro driver '${associatedKey}'?\nThis will disconnect all matched tree nodes.`,
                { confirmText: "Delete", isDanger: true }
            ).then(accepted => {
                if (accepted) {
                    delete State.macroDrivers[associatedKey];
                    
                    // Recursive closure traversal execution pass to clean out severed links
                    function pruneReferences(nodes) {
                        for (const k in nodes) {
                            if (nodes[k].macro_driver === associatedKey) {
                                nodes[k].macro_driver = null;
                            }
                            if (nodes[k].children) pruneReferences(nodes[k].children);
                        }
                    }
                    pruneReferences(State.treeState);
                    
                    renderGlobalMacroDriversPanel();
                    refreshTree();
                    showCustomToast(`Macro driver '${associatedKey}' deleted successfully.`, "info");
                }
            });
        });
    });
}

async function handleStartModeling() {
    State.economy = DOM.selectEconomy.value;
    State.year = parseInt(DOM.selectYear.value);
    State.sector_flow = DOM.selectSector.value;

    showLoading("Fetching Macro Targets...");
    try {
        const metadataResponse = await EnergyModelAPI.getActiveFuels(State.economy, State.year, State.sector_flow);
        State.macro_targets = metadataResponse.active_fuels;
        State.total_energy = Object.values(State.macro_targets).reduce((sum, val) => sum + val, 0);

        renderTargetDashboard();
        
        DOM.canvasEmptyState.classList.add('hidden');
        DOM.targetDashboard.classList.remove('hidden');
        DOM.treeRootContainer.classList.remove('hidden');
        DOM.actionConsole.classList.remove('hidden'); // Action Console is persistent and shown immediately
        
        setTimeout(() => fitToScreen(), 150);
        
        DOM.selectEconomy.disabled = true;
        DOM.selectYear.disabled = true;
        DOM.selectSector.disabled = true;
        DOM.btnStart.innerText = "Environment Locked";
        DOM.btnStart.classList.replace('bg-blue-600', 'bg-slate-400');
        DOM.btnStart.classList.replace('hover:bg-blue-700', 'hover:bg-slate-400');
        DOM.btnStart.disabled = true;
        
        renderResultsSummary();
        showCustomToast("Model environment initialized successfully.", "success");
    } catch (error) {
        showCustomToast("Failed to initialize: " + error.message, "error");
    } finally {
        hideLoading();
    }
}

function renderTargetDashboard() {
    // Explicit 'en-US' locale parameters forced to comply with strict number styling
    DOM.displayTotalEnergy.innerText = State.total_energy.toLocaleString('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 2 });
    DOM.fuelTargetsContainer.innerHTML = ''; 

    for (const [fuelName, targetValue] of Object.entries(State.macro_targets)) {
        const safeFuelId = fuelName.replace(/[^a-zA-Z0-9]/g, '-');
        const formattedTarget = targetValue.toLocaleString('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 2 });

        const html = `
            <div class="mb-3">
                <div class="flex justify-between items-end mb-1">
                    <span class="text-xs font-bold text-slate-600">${fuelName}</span>
                    <span class="text-xs font-medium text-slate-500">
                        <span id="calc-${safeFuelId}">0.00</span> / ${formattedTarget}
                    </span>
                </div>
                <div class="w-full bg-slate-100 rounded-full h-2 overflow-hidden border border-slate-200">
                    <div id="bar-${safeFuelId}" class="progress-bar-fill h-2 rounded-full bg-blue-500" style="width: 0%"></div>
                </div>
            </div>
        `;
        DOM.fuelTargetsContainer.insertAdjacentHTML('beforeend', html);
    }
}

// ==========================================
// INTERACTIVE CANVAS (PAN & ZOOM) LOGIC
// ==========================================

function applyTransform() {
    if (!DOM.treeTransformContainer) return;
    DOM.treeTransformContainer.style.transform = `translate(${State.panX}px, ${State.panY}px) scale(${State.zoomScale})`;
    if (DOM.displayZoom) {
        DOM.displayZoom.innerText = `${Math.round(State.zoomScale * 100)}%`;
    }
}

function setupInteractiveCanvas() {
    if (!DOM.treeCanvas || !DOM.treeTransformContainer) return;

    // Mouse Panning
    DOM.treeCanvas.addEventListener('mousedown', (e) => {
        // Only pan if clicking direct on canvas or elements that are not inputs/buttons/dropdowns
        const tag = e.target.tagName;
        if (tag === 'INPUT' || tag === 'SELECT' || tag === 'BUTTON' || e.target.closest('.node-card')) {
            return;
        }
        State.isDragging = true;
        DOM.treeCanvas.classList.add('is-grabbing');
        DOM.treeTransformContainer.classList.add('is-dragging');
        State.startX = e.clientX - State.panX;
        State.startY = e.clientY - State.panY;
    });

    window.addEventListener('mousemove', (e) => {
        if (!State.isDragging) return;
        State.panX = e.clientX - State.startX;
        State.panY = e.clientY - State.startY;
        applyTransform();
    });

    window.addEventListener('mouseup', () => {
        if (State.isDragging) {
            State.isDragging = false;
            DOM.treeCanvas.classList.remove('is-grabbing');
            DOM.treeTransformContainer.classList.remove('is-dragging');
        }
    });

    DOM.treeCanvas.addEventListener('mouseleave', () => {
        if (State.isDragging) {
            State.isDragging = false;
            DOM.treeCanvas.classList.remove('is-grabbing');
            DOM.treeTransformContainer.classList.remove('is-dragging');
        }
    });

    // Mouse Wheel Zoom (Figma Style: Ctrl + Wheel)
    DOM.treeCanvas.addEventListener('wheel', (e) => {
        if (e.ctrlKey) {
            e.preventDefault();
            const rect = DOM.treeCanvas.getBoundingClientRect();
            const mouseX = e.clientX - rect.left;
            const mouseY = e.clientY - rect.top;

            const zoomFactor = 0.08;
            const delta = -e.deltaY * zoomFactor > 0 ? zoomFactor : -zoomFactor;
            const newScale = Math.min(Math.max(State.zoomScale + delta, 0.25), 2.0);

            // Zoom centered under cursor
            State.panX = mouseX - (mouseX - State.panX) * (newScale / State.zoomScale);
            State.panY = mouseY - (mouseY - State.panY) * (newScale / State.zoomScale);
            State.zoomScale = newScale;

            applyTransform();
        } else {
            // Standard scroll pans vertically
            State.panY -= e.deltaY * 0.5;
            applyTransform();
        }
    }, { passive: false });

    // Floating Zoom Buttons
    if (DOM.btnZoomIn) {
        DOM.btnZoomIn.addEventListener('click', () => {
            adjustZoom(0.1);
        });
    }
    if (DOM.btnZoomOut) {
        DOM.btnZoomOut.addEventListener('click', () => {
            adjustZoom(-0.1);
        });
    }
    if (DOM.btnFitScreen) {
        DOM.btnFitScreen.addEventListener('click', fitToScreen);
    }
    if (DOM.btnToggleCompact) {
        DOM.btnToggleCompact.addEventListener('click', toggleCompactMode);
    }

    // Touchpad / Gesture support
    DOM.treeCanvas.addEventListener('gesturestart', (e) => e.preventDefault());
    DOM.treeCanvas.addEventListener('gesturechange', (e) => e.preventDefault());

    // Apply initial transform coordinate values
    applyTransform();
}

function adjustZoom(delta) {
    const rect = DOM.treeCanvas.getBoundingClientRect();
    const centerX = rect.width / 2;
    const centerY = rect.height / 2;

    const newScale = Math.min(Math.max(State.zoomScale + delta, 0.25), 2.0);

    // Zoom centered in viewport
    State.panX = centerX - (centerX - State.panX) * (newScale / State.zoomScale);
    State.panY = centerY - (centerY - State.panY) * (newScale / State.zoomScale);
    State.zoomScale = newScale;

    applyTransform();
}

function fitToScreen() {
    if (!DOM.treeTransformContainer || !DOM.treeCanvas) return;
    
    // Find bounds of the nodes list container relative to treeTransformContainer
    const bounds = DOM.treeNodesList.getBoundingClientRect();
    const canvasBounds = DOM.treeCanvas.getBoundingClientRect();

    if (bounds.width === 0 || bounds.height === 0) {
        // Reset to default if empty
        State.zoomScale = 1.0;
        State.panX = 40;
        State.panY = 100;
        applyTransform();
        return;
    }

    // Unscale bounds to find physical size
    const physicalWidth = bounds.width / State.zoomScale;
    const physicalHeight = bounds.height / State.zoomScale;

    const padding = 60;
    const availWidth = canvasBounds.width - padding * 2;
    const availHeight = canvasBounds.height - padding * 2;

    // Calculate optimal scale factor
    const scaleX = availWidth / physicalWidth;
    const scaleY = availHeight / physicalHeight;
    let newScale = Math.min(scaleX, scaleY);
    newScale = Math.min(Math.max(newScale, 0.3), 1.2); // keep fit scale sensible

    // Center the element
    State.zoomScale = newScale;
    State.panX = padding + (availWidth - physicalWidth * newScale) / 2;
    State.panY = padding + (availHeight - physicalHeight * newScale) / 2;

    applyTransform();
}

function toggleCompactMode() {
    State.isCompactMode = !State.isCompactMode;
    if (State.isCompactMode) {
        DOM.treeCanvas.classList.add('canvas-compact-mode');
        DOM.compactIcon.innerText = '🕶️';
    } else {
        DOM.treeCanvas.classList.remove('canvas-compact-mode');
        DOM.compactIcon.innerText = '👁️';
    }
    // Refresh to update heights and run fit if needed
    refreshTree();
}

// Smart Auto-Collapse logic
function autoPruneExpandedBranches(nodes, activePath, currentPath = []) {
    for (const key in nodes) {
        const node = nodes[key];
        const nodePath = [...currentPath, key];
        
        let isAncestorOrSelf = true;
        for (let i = 0; i < nodePath.length; i++) {
            if (activePath[i] !== nodePath[i]) {
                isAncestorOrSelf = false;
                break;
            }
        }
        
        if (node.children && Object.keys(node.children).length > 0) {
            if (!isAncestorOrSelf) {
                node._ui_collapsed = true;
            }
            autoPruneExpandedBranches(node.children, activePath, [...nodePath, 'children']);
        }
    }
}

// ==========================================
// 3. MATH ENGINE
// ==========================================

function recalculateTreeEnergy() {
    function distributeEnergy(nodes, parentEnergy) {
        const keys = Object.keys(nodes);
        if (keys.length === 0) return;

        let totalWeight = 0;
        keys.forEach(k => totalWeight += (parseFloat(nodes[k].weight) || 0));

        keys.forEach(k => {
            const node = nodes[k];
            node._ui_normalized = totalWeight > 0 ? (parseFloat(node.weight) / totalWeight) : 0;
            node._ui_energy = parentEnergy * node._ui_normalized;

            if (node.children && Object.keys(node.children).length > 0) {
                distributeEnergy(node.children, node._ui_energy);
            } else if (node.fuels && node.fuels.length > 0) {
                let totalFuelW = 0;
                node.fuels.forEach(f => totalFuelW += (parseFloat(f.weight) || 0));
                
                node.fuels.forEach(f => {
                    f._ui_normalized = totalFuelW > 0 ? (parseFloat(f.weight) / totalFuelW) : 0;
                    f._ui_energy = node._ui_energy * f._ui_normalized;
                });
            }
        });
    }

    distributeEnergy(State.treeState, State.total_energy);
    updateDashboardBars();
}

function updateDashboardBars() {
    let calculatedTotals = {};
    Object.keys(State.macro_targets).forEach(fuel => calculatedTotals[fuel] = 0);

    function traverseAndSum(nodes) {
        Object.values(nodes).forEach(node => {
            if (node.children && Object.keys(node.children).length > 0) {
                traverseAndSum(node.children);
            } else if (node.fuels && node.fuels.length > 0) {
                node.fuels.forEach(f => {
                    if (calculatedTotals[f.name] !== undefined) calculatedTotals[f.name] += f._ui_energy;
                });
            }
        });
    }
    traverseAndSum(State.treeState);

    for (const [fuelName, targetVal] of Object.entries(State.macro_targets)) {
        const calcVal = calculatedTotals[fuelName];
        const safeFuelId = fuelName.replace(/[^a-zA-Z0-9]/g, '-');
        const label = document.getElementById(`calc-${safeFuelId}`);
        const bar = document.getElementById(`bar-${safeFuelId}`);
        
        if (label && bar) {
            label.innerText = calcVal.toLocaleString('en-US', { minimumFractionDigits: 1, maximumFractionDigits: 1 });
            let pct = (calcVal / targetVal) * 100;
            if (isNaN(pct) || !isFinite(pct)) pct = 0;
            bar.style.width = `${Math.min(pct, 100)}%`;
            
            const diff = Math.abs(calcVal - targetVal);
            if (diff <= 0.1) bar.className = "progress-bar-fill h-2 rounded-full bg-emerald-500";
            else if (calcVal > targetVal) bar.className = "progress-bar-fill h-2 rounded-full bg-red-500";
            else bar.className = "progress-bar-fill h-2 rounded-full bg-blue-500";
        }
    }
}

// ==========================================
// 4. TREE UI RENDERER
// ==========================================

function refreshTree() {
    recalculateTreeEnergy();
    DOM.treeNodesList.innerHTML = '';
    
    if (Object.keys(State.treeState).length === 0) {
        DOM.treeNodesList.innerHTML = `<p class="text-slate-400 italic text-sm">No branches yet. Click "+ Add Root Branch" above.</p>`;
        DOM.statusMessage.innerText = "Model initialized. Click '+ Add Root Branch' to begin.";
        DOM.statusMessage.className = "text-sm font-semibold text-slate-500";
        DOM.actionConsole.classList.remove('hidden');
        renderResultsSummary();
        return;
    }
    
    DOM.actionConsole.classList.remove('hidden');
    DOM.statusMessage.innerText = "Tree ready. Ensure all mass is distributed.";
    DOM.statusMessage.className = "text-sm font-semibold text-slate-500";
    buildTreeHTML(State.treeState, DOM.treeNodesList, []);
    renderResultsSummary();
}

function buildTreeHTML(nodesObj, parentContainer, pathArray) {
    for (const [nodeName, nodeData] of Object.entries(nodesObj)) {
        const currentPath = [...pathArray, nodeName];
        const isLeaf = !nodeData.children || Object.keys(nodeData.children).length === 0;
        const isCollapsed = nodeData._ui_collapsed === true;
        
        const li = document.createElement('li');
        li.className = 'tree-node-group fade-in';
        
        const isHighImbalance = nodeData.tags && nodeData.tags.includes('balancing_node') && (nodeData._ui_normalized || 0) > 0.10;
        let tagsHtml = nodeData.tags && nodeData.tags.includes('balancing_node') 
            ? `<span class="tag-balancing ${isHighImbalance ? 'tag-balancing-high' : ''}" title="${isHighImbalance ? 'Warning: High energy imbalance detected!' : ''}">Balancing Node</span>` 
            : '';

        const collapseBtnHtml = !isLeaf ? `
            <button class="text-slate-400 hover:text-slate-600 font-bold text-xs mr-1 p-1 btn-toggle-collapse ${isCollapsed ? 'is-rotated' : ''}" data-path='${JSON.stringify(currentPath)}' title="Toggle Group visibility">
                ▼
            </button>
        ` : '<span class="w-4 inline-block"></span>';

        // Loop execution matrix to fetch active registered runtime macro driver options dynamically
        let driverOptionsHtml = `<option value="" ${!nodeData.macro_driver ? 'selected' : ''}>None (Unindexed)</option>`;
        const structuralLabels = {
            households: 'Households',
            floor_area_sqm: 'Floor Area (sqm)',
            occupancy_rate: 'Occupancy Rate'
        };

        for (const driverKey of Object.keys(State.macroDrivers)) {
            const visualText = structuralLabels[driverKey] || driverKey;
            driverOptionsHtml += `<option value="${driverKey}" ${nodeData.macro_driver === driverKey ? 'selected' : ''}>${visualText}</option>`;
        }

        const isActive = State.activeNodePathStr === JSON.stringify(currentPath);

        li.innerHTML = `
            <div class="tree-node-wrapper">
                <div class="node-card ${isCollapsed ? 'is-collapsed-card' : ''} ${isActive ? 'is-active-card' : ''}" data-path-str='${JSON.stringify(currentPath)}'>
                    ${tagsHtml}
                    <div class="p-3 border-b border-slate-100 flex justify-between items-center bg-slate-50/50 rounded-t-lg">
                        <div class="flex items-center w-full mr-2 overflow-hidden">
                            ${collapseBtnHtml}
                            <input type="text" class="font-bold text-slate-700 text-sm truncate bg-transparent border border-transparent hover:border-slate-300 focus:border-blue-500 focus:bg-white rounded px-1 outline-none w-full input-node-name" value="${nodeName}" data-path='${JSON.stringify(currentPath)}' title="Edit Branch Name">
                        </div>
                        <button class="text-red-400 hover:text-red-600 font-bold px-2 py-1 text-xs flex-shrink-0 btn-remove" data-path='${JSON.stringify(currentPath)}' title="Delete Branch">&times;</button>
                    </div>
                    
                    <div class="p-3 space-y-3">
                        <div class="flex items-center justify-between gap-3">
                            <label class="text-xs font-semibold text-slate-500 w-16 input-weight-label">Weight</label>
                            <input type="number" step="0.01" min="0" value="${nodeData.weight}" class="flex-1 border border-slate-300 rounded p-1 text-sm text-right focus:ring-1 focus:ring-blue-500 outline-none input-weight" data-path='${JSON.stringify(currentPath)}'>
                            <span class="text-xs font-bold text-blue-600 w-12 text-right pct-label">${((nodeData._ui_normalized || 0) * 100).toFixed(1)}%</span>
                        </div>

                        <div class="pt-1.5 node-slider-container">
                            <input type="range" min="0" max="2.0" step="0.01" value="${nodeData.weight}" class="input-weight-slider" data-path='${JSON.stringify(currentPath)}'>
                        </div>

                        <div class="grid grid-cols-2 gap-2 pt-1 border-t border-dashed border-slate-100 node-bounds-container">
                            <div class="flex items-center gap-1.5">
                                <label class="text-[10px] font-bold text-slate-400 uppercase tracking-tight">Min W</label>
                                <input type="number" step="0.01" min="0" max="1" placeholder="None" value="${nodeData.min_weight !== undefined && nodeData.min_weight !== null ? nodeData.min_weight : ''}" class="w-full border border-slate-200 rounded px-1.5 py-0.5 text-xs text-right outline-none focus:border-purple-400 input-min-weight input-boundary-box" data-path='${JSON.stringify(currentPath)}'>
                            </div>
                            <div class="flex items-center gap-1.5">
                                <label class="text-[10px] font-bold text-slate-400 uppercase tracking-tight">Max W</label>
                                <input type="number" step="0.01" min="0" max="1" placeholder="None" value="${nodeData.max_weight !== undefined && nodeData.max_weight !== null ? nodeData.max_weight : ''}" class="w-full border border-slate-200 rounded px-1.5 py-0.5 text-xs text-right outline-none focus:border-purple-400 input-max-weight input-boundary-box" data-path='${JSON.stringify(currentPath)}'>
                            </div>
                        </div>

                        <div class="flex items-center gap-1.5 pt-1 border-t border-slate-100 node-driver-container">
                            <label class="text-[10px] font-bold text-slate-400 uppercase tracking-tight w-16">Driver</label>
                            <select class="w-full border border-slate-200 rounded px-1.5 py-1 text-xs bg-white focus:border-blue-400 outline-none  input-macro-driver" data-path='${JSON.stringify(currentPath)}'>
                                ${driverOptionsHtml}
                            </select>
                        </div>
                        
                        <div class="flex items-center justify-between bg-slate-100 p-2 rounded border border-slate-200">
                            <span class="text-xs font-semibold text-slate-500">Energy Drop</span>
                            <span class="text-sm font-black text-slate-700 energy-drop-value">${(nodeData._ui_energy || 0).toLocaleString('en-US', {maximumFractionDigits:1})}</span>
                        </div>
                    </div>

                    <div class="p-3 bg-slate-50 border-t border-slate-100 rounded-b-lg flex gap-2 node-actions-footer">
                        ${isLeaf ? `
                            <button class="flex-1 bg-white border border-slate-300 hover:border-blue-500 hover:text-blue-600 text-slate-600 text-xs font-bold py-1.5 rounded transition-colors btn-add-child" data-path='${JSON.stringify(currentPath)}'>+ Sub-Branch</button>
                            <button class="flex-1 bg-blue-50 border border-blue-200 hover:bg-blue-100 text-blue-700 text-xs font-bold py-1.5 rounded transition-colors btn-add-fuel" data-path='${JSON.stringify(currentPath)}'>+ Fuel</button>
                        ` : `
                            <button class="w-full bg-white border border-slate-300 hover:border-blue-500 hover:text-blue-600 text-slate-600 text-xs font-bold py-1.5 rounded transition-colors btn-add-child" data-path='${JSON.stringify(currentPath)}'>+ Sub-Branch</button>
                        `}
                    </div>
                </div>

                ${isLeaf && nodeData.fuels && nodeData.fuels.length > 0 ? buildFuelsHTML(nodeData.fuels, currentPath) : ''}
            </div>
            <ul class="tree-children-list ${isCollapsed ? 'is-collapsed' : ''}"></ul>
        `;

        if (!isLeaf) {
            const ul = li.querySelector('.tree-children-list');
            buildTreeHTML(nodeData.children, ul, [...currentPath, 'children']);
        }
        parentContainer.appendChild(li);
    }
}

function buildFuelsHTML(fuels, currentPath) {
    let html = `<div class="mt-2 ml-4 pl-4 border-l-2 border-dashed border-blue-200 space-y-2">`;
    const activeFuelKeys = Object.keys(State.macro_targets);

    fuels.forEach((f, idx) => {
        const optionsHtml = activeFuelKeys.map(k => `<option value="${k}" ${k === f.name ? 'selected' : ''}>${k}</option>`).join('');
        
        html += `
            <div class="bg-blue-50 border border-blue-100 p-2 rounded-md shadow-sm flex items-center gap-2 relative fuel-item-container">
                <button class="absolute -left-2 -top-2 bg-red-100 text-red-600 rounded-full w-5 h-5 flex items-center justify-center text-xs font-bold hover:bg-red-200 btn-remove-fuel" data-path='${JSON.stringify(currentPath)}' data-idx="${idx}">&times;</button>
                
                <select class="flex-1 w-24 text-xs font-bold text-blue-900 bg-white border border-blue-200 rounded p-1 outline-none focus:ring-1 focus:ring-blue-500 input-fuel-name" data-path='${JSON.stringify(currentPath)}' data-idx="${idx}" title="Select Fuel">
                    ${optionsHtml}
                </select>
                
                <div class="flex items-center gap-1" title="Efficiency (η)">
                    <span class="text-[10px] font-bold text-slate-400">η</span>
                    <input type="number" step="0.01" min="0.01" value="${f.efficiency}" class="w-14 text-xs p-1 border rounded text-right input-fuel-eff" data-path='${JSON.stringify(currentPath)}' data-idx="${idx}">
                </div>
                
                <div class="flex items-center gap-1" title="Weight (W)">
                    <span class="text-[10px] font-bold text-slate-400">W</span>
                    <input type="number" step="0.01" min="0" value="${f.weight}" class="w-14 text-xs p-1 border rounded text-right input-fuel-weight" data-path='${JSON.stringify(currentPath)}' data-idx="${idx}">
                </div>
                
                <div class="text-xs font-bold text-blue-600 w-10 text-right fuel-pct-label">${((f._ui_normalized || 0)*100).toFixed(0)}%</div>
            </div>
        `;
    });
    html += `</div>`;
    return html;
}

function updateDOMWeightsAndEnergy() {
    const cards = DOM.treeCanvas.querySelectorAll('.node-card');
    cards.forEach(card => {
        if (!card.dataset.pathStr) return;
        const path = JSON.parse(card.dataset.pathStr);
        const node = getNestedObj(State.treeState, path);
        if (!node) return;

        // Update percentage label
        const pctLabel = card.querySelector('.pct-label');
        if (pctLabel) {
            pctLabel.innerText = `${((node._ui_normalized || 0) * 100).toFixed(1)}%`;
        }

        // Update balancing node warning badge status in real-time
        const balancingTag = card.querySelector('.tag-balancing');
        if (balancingTag) {
            const isHighImbalance = node.tags && node.tags.includes('balancing_node') && (node._ui_normalized || 0) > 0.10;
            if (isHighImbalance) {
                balancingTag.classList.add('tag-balancing-high');
                balancingTag.title = 'Warning: High energy imbalance detected!';
            } else {
                balancingTag.classList.remove('tag-balancing-high');
                balancingTag.title = '';
            }
        }

        // Update energy drop
        const energyDrop = card.querySelector('.energy-drop-value');
        if (energyDrop) {
            energyDrop.innerText = (node._ui_energy || 0).toLocaleString('en-US', {maximumFractionDigits: 1});
        }
        
        // Synchronize inputs if they are out of focus
        const weightInput = card.querySelector('.input-weight');
        const sliderInput = card.querySelector('.input-weight-slider');
        if (weightInput && document.activeElement !== weightInput) {
            weightInput.value = node.weight;
        }
        if (sliderInput && document.activeElement !== sliderInput) {
            sliderInput.value = node.weight;
        }

        // Update fuel item percentages if this is a leaf node with fuels
        if (node.fuels && node.fuels.length > 0) {
            const fuelContainers = card.querySelectorAll('.fuel-item-container');
            fuelContainers.forEach((fuelEl, idx) => {
                const f = node.fuels[idx];
                if (f) {
                    const fuelPctLabel = fuelEl.querySelector('.fuel-pct-label');
                    if (fuelPctLabel) {
                        fuelPctLabel.innerText = `${((f._ui_normalized || 0) * 100).toFixed(0)}%`;
                    }
                    const fuelWeightInput = fuelEl.querySelector('.input-fuel-weight');
                    if (fuelWeightInput && document.activeElement !== fuelWeightInput) {
                        fuelWeightInput.value = f.weight;
                    }
                }
            });
        }
    });

    // Update fuel target bars in left dashboard
    updateDashboardBars();
    
    // Update collapsible results panel summary in real-time
    renderResultsSummary();
}

// ==========================================
// 5. EVENT DELEGATION
// ==========================================

function getUniqueName(parentObj, baseName) {
    let counter = 1;
    let newName = `${baseName} ${counter}`;
    while (parentObj[newName]) { counter++; newName = `${baseName} ${counter}`; }
    return newName;
}

function handleGlobalCollapse(status) {
    function recurseCollapse(nodes) {
        for (const k in nodes) {
            if (nodes[k].children && Object.keys(nodes[k].children).length > 0) {
                nodes[k]._ui_collapsed = status;
                recurseCollapse(nodes[k].children);
            }
        }
    }
    recurseCollapse(State.treeState);
    refreshTree();
}

DOM.treeCanvas = document.getElementById('tree-canvas');
DOM.treeCanvas.addEventListener('click', async (e) => {
    const target = e.target;
    
    // Active Card Focus & Smart Collapse Selection
    const card = target.closest('.node-card');
    if (card && !target.classList.contains('btn-remove') && !target.classList.contains('btn-add-child') && !target.classList.contains('btn-add-fuel') && !target.classList.contains('btn-toggle-collapse')) {
        const path = JSON.parse(card.dataset.pathStr);
        const pathStr = JSON.stringify(path);
        if (State.activeNodePathStr !== pathStr) {
            State.activeNodePathStr = pathStr;
            
            // Highlight the active card in the DOM immediately without full re-render
            DOM.treeCanvas.querySelectorAll('.node-card').forEach(c => {
                c.classList.remove('is-active-card');
            });
            card.classList.add('is-active-card');
            
            // If they clicked an input/select, don't prune parallel branches immediately (which triggers a full refresh and loses focus),
            // but if they clicked the card background/header, do prune and refresh to tidy up the tree!
            if (target.tagName !== 'INPUT' && target.tagName !== 'SELECT') {
                autoPruneExpandedBranches(State.treeState, path);
                refreshTree();
                return;
            }
        }
    }
    
    if (target.classList.contains('btn-toggle-collapse')) {
        const path = JSON.parse(target.dataset.path);
        let node = getNestedObj(State.treeState, path);
        node._ui_collapsed = !node._ui_collapsed;
        refreshTree();
        return;
    }

    if (target.classList.contains('btn-add-child')) {
        const path = JSON.parse(target.dataset.path);
        let node = getNestedObj(State.treeState, path);
        if (node.fuels && node.fuels.length > 0) {
            const accepted = await showCustomConfirm(
                "Adding Sub-Branch",
                "Adding a branch will remove all assigned fuels from this node.\nDo you want to continue?",
                { confirmText: "Yes, Remove Fuels", isDanger: true }
            );
            if (!accepted) return;
            node.fuels = [];
        }
        if (!node.children) node.children = {};
        const newName = getUniqueName(node.children, "New Branch");
        node.children[newName] = { weight: 1.0, children: {}, fuels: [] };
        refreshTree();
    }

    if (target.classList.contains('btn-add-fuel')) {
        const path = JSON.parse(target.dataset.path);
        let node = getNestedObj(State.treeState, path);
        if (!node.fuels) node.fuels = [];
        
        let avail = Object.keys(State.macro_targets);
        let choice = avail.find(f => !node.fuels.some(existing => existing.name === f));
        if (!choice) return showCustomToast("All available fuels are already assigned here.", "warning");
        
        node.fuels.push({ name: choice, weight: 1.0, efficiency: 1.0 });
        refreshTree();
    }

    if (target.classList.contains('btn-remove')) {
        const path = JSON.parse(target.dataset.path);
        const nodeName = path[path.length - 1];
        const accepted = await showCustomConfirm(
            "Delete Branch",
            `Are you sure you want to delete "${nodeName}" and all of its sub-branches?\nThis action cannot be undone.`,
            { confirmText: "Delete", isDanger: true }
        );
        if (!accepted) return;
        const key = path.pop(); 
        const parent = path.length === 0 ? State.treeState : getNestedObj(State.treeState, path);
        delete parent[key];
        refreshTree();
    }

    if (target.classList.contains('btn-remove-fuel')) {
        const path = JSON.parse(target.dataset.path);
        const idx = parseInt(target.dataset.idx);
        let node = getNestedObj(State.treeState, path);
        node.fuels.splice(idx, 1);
        refreshTree();
    }
});

DOM.treeCanvas.addEventListener('keydown', (e) => {
    if (e.key === 'Enter' && e.target.tagName === 'INPUT') e.target.blur();
});

// Keyboard Shortcuts for Advanced Productivity
window.addEventListener('keydown', async (e) => {
    // Ignore keyboard shortcuts if the user is typing in an input or select element
    if (document.activeElement.tagName === 'INPUT' || document.activeElement.tagName === 'SELECT' || document.activeElement.tagName === 'TEXTAREA') {
        return;
    }

    if (!State.activeNodePathStr) return;
    const path = JSON.parse(State.activeNodePathStr);
    const node = getNestedObj(State.treeState, path);
    if (!node) return;

    // 'n' or 'N': Add a sub-branch to the active node
    if (e.key === 'n' || e.key === 'N') {
        e.preventDefault();
        if (node.fuels && node.fuels.length > 0) {
            const accepted = await showCustomConfirm(
                "Adding Sub-Branch",
                "Adding a branch will remove all assigned fuels from this node.\nDo you want to continue?",
                { confirmText: "Yes, Remove Fuels", isDanger: true }
            );
            if (!accepted) return;
            node.fuels = [];
        }
        if (!node.children) node.children = {};
        const newName = getUniqueName(node.children, "New Branch");
        node.children[newName] = { weight: 1.0, children: {}, fuels: [] };
        
        // Auto-focus the new branch
        const newPath = [...path, 'children', newName];
        State.activeNodePathStr = JSON.stringify(newPath);
        
        refreshTree();
        
        // Find the input element of the new node and focus it
        setTimeout(() => {
            const inputs = DOM.treeCanvas.querySelectorAll('.input-node-name');
            for (const input of inputs) {
                if (input.dataset.path && JSON.stringify(JSON.parse(input.dataset.path)) === JSON.stringify(newPath)) {
                    input.focus();
                    input.select();
                    break;
                }
            }
        }, 100);
    }

    // 'f' or 'F': Add a fuel to the active node
    if (e.key === 'f' || e.key === 'F') {
        e.preventDefault();
        // Fuels can only be added to leaf nodes (no children)
        if (node.children && Object.keys(node.children).length > 0) {
            showCustomToast("Fuels can only be added to leaf nodes (branches without sub-branches).", "warning");
            return;
        }
        if (!node.fuels) node.fuels = [];
        let avail = Object.keys(State.macro_targets);
        let choice = avail.find(fl => !node.fuels.some(existing => existing.name === fl));
        if (!choice) return showCustomToast("All available fuels are already assigned here.", "warning");
        
        node.fuels.push({ name: choice, weight: 1.0, efficiency: 1.0 });
        refreshTree();
    }

    // 'Delete': Delete the active node
    if (e.key === 'Delete') {
        e.preventDefault();
        const nodeName = path[path.length - 1];
        const accepted = await showCustomConfirm(
            "Delete Active Branch",
            `Are you sure you want to delete the active node "${nodeName}" and all of its sub-branches?`,
            { confirmText: "Delete", isDanger: true }
        );
        if (!accepted) return;
        const key = path.pop(); 
        const parent = path.length === 0 ? State.treeState : getNestedObj(State.treeState, path);
        delete parent[key];
        State.activeNodePathStr = null;
        refreshTree();
    }

    // 'c' or 'C': Toggle collapse of the active node
    if (e.key === 'c' || e.key === 'C') {
        e.preventDefault();
        if (node.children && Object.keys(node.children).length > 0) {
            node._ui_collapsed = !node._ui_collapsed;
            refreshTree();
        }
    }
    
    // 'Space': Center/fit screen
    if (e.key === ' ') {
        e.preventDefault();
        fitToScreen();
    }
});

// Real-Time Math Update
DOM.treeCanvas.addEventListener('input', (e) => {
    const target = e.target;
    const path = target.dataset.path ? JSON.parse(target.dataset.path) : null;
    
    if (target.classList.contains('input-weight') || target.classList.contains('input-weight-slider')) {
        let node = getNestedObj(State.treeState, path);
        const val = parseFloat(target.value) || 0;
        node.weight = val;
        
        const card = target.closest('.node-card');
        if (card) {
            const textInput = card.querySelector('.input-weight');
            const sliderInput = card.querySelector('.input-weight-slider');
            if (target === textInput && sliderInput) {
                sliderInput.value = val;
            } else if (target === sliderInput && textInput) {
                textInput.value = val;
            }
        }
        
        recalculateTreeEnergy();
        updateDOMWeightsAndEnergy();
    }
    
    if (target.classList.contains('input-min-weight')) {
        let node = getNestedObj(State.treeState, path);
        node.min_weight = target.value.trim() === "" ? null : parseFloat(target.value);
    }
    if (target.classList.contains('input-max-weight')) {
        let node = getNestedObj(State.treeState, path);
        node.max_weight = target.value.trim() === "" ? null : parseFloat(target.value);
    }
    
    if (target.classList.contains('input-fuel-weight')) {
        let node = getNestedObj(State.treeState, path);
        node.fuels[parseInt(target.dataset.idx)].weight = parseFloat(target.value) || 0;
        recalculateTreeEnergy();
        updateDOMWeightsAndEnergy();
    }
    if (target.classList.contains('input-fuel-eff')) {
        let node = getNestedObj(State.treeState, path);
        node.fuels[parseInt(target.dataset.idx)].efficiency = parseFloat(target.value) || 1.0;
    }
});

// Structural Update (Name Changes / Fuel Selection / Macro Driver Allocation)
DOM.treeCanvas.addEventListener('change', (e) => {
    const target = e.target;
    const path = target.dataset.path ? JSON.parse(target.dataset.path) : null;

    if (target.classList.contains('input-node-name')) {
        const oldKey = path.pop();
        const newKey = target.value.trim();
        if(!newKey || newKey === oldKey) return; 

        const parent = path.length === 0 ? State.treeState : getNestedObj(State.treeState, path);
        if (parent[newKey]) {
            showCustomToast("A branch with this name already exists here.", "error");
            target.value = oldKey; 
            return;
        }
        
        parent[newKey] = parent[oldKey];
        delete parent[oldKey];
        refreshTree(); 
    }

    // Dynamic runtime mapping for node-specific macro indices
    if (target.classList.contains('input-macro-driver')) {
        let node = getNestedObj(State.treeState, path);
        node.macro_driver = target.value === "" ? null : target.value;
    }

    if (target.classList.contains('input-fuel-name')) {
        const idx = parseInt(target.dataset.idx);
        let node = getNestedObj(State.treeState, path);
        const newName = target.value;
        
        if (node.fuels.some((f, i) => i !== idx && f.name === newName)) {
            showCustomToast("Fuel already assigned to this node.", "error");
            target.value = node.fuels[idx].name; 
            return;
        }
        node.fuels[idx].name = newName;
        recalculateTreeEnergy(); 
    }

    if (target.classList.contains('input-weight') || target.classList.contains('input-weight-slider') || target.classList.contains('input-fuel-weight')) {
        refreshTree(); 
    }
});

DOM.btnAddRoot.addEventListener('click', () => {
    const newName = getUniqueName(State.treeState, "New Root Branch");
    State.treeState[newName] = { weight: 1.0, children: {}, fuels: [] };
    refreshTree();
});

function getNestedObj(obj, pathArr) {
    return pathArr.reduce((acc, key) => (acc && acc[key] !== 'undefined') ? acc[key] : undefined, obj);
}

// ==========================================
// 6. VALIDATION, OPTIMIZATION & EXPORT
// ==========================================

function buildApiPayload() {
    return {
        economy: State.economy,
        year: State.year,
        sector_flow: State.sector_flow,
        total_energy: State.total_energy,
        target_layer: "full_tree",
        tree_state: State.treeState
    };
}

DOM.btnValidate.addEventListener('click', async () => {
    showLoading("Validating Mass Balance...");
    try {
        const res = await EnergyModelAPI.validateTree(buildApiPayload());
        const details = res.validation_details;

        if (details.is_valid) {
            DOM.statusMessage.innerText = "Perfectly Balanced! Ready for export.";
            DOM.statusMessage.className = "text-sm font-bold text-emerald-600";
            DOM.btnExport.classList.remove('hidden');
            showCustomToast("Success: " + res.message, "success");
        } else {
            DOM.statusMessage.innerText = "Imbalances Detected.";
            DOM.statusMessage.className = "text-sm font-bold text-red-600";
            DOM.btnExport.classList.add('hidden');

            let errorMsg = "Mass imbalances detected against ESTO targets:\n\n";
            details.messages.forEach(msg => errorMsg += `• ${msg}\n`);
            errorMsg += "\nGenerate a 'Balancing Node' to catch missing fuels?";

            const accepted = await showCustomConfirm(
                "Imbalances Detected",
                errorMsg,
                { confirmText: "Generate Balancing Node", cancelText: "Close" }
            );
            if (accepted) injectBalancingNode();
        }
    } catch (e) {
        showCustomToast("Validation failed: " + e.message, "error");
    } finally {
        hideLoading();
    }
});

function injectBalancingNode() {
    if (State.treeState["Other Demand"]) {
        showCustomToast("Balancing node already exists. Please run the optimizer.", "warning");
        return;
    }

    State.treeState["Other Demand"] = {
        weight: 0.1,
        tags: ["balancing_node", "auto_generated"],
        children: {
            "Unspecified Uses": {
                weight: 1.0, children: {}, fuels: []
            }
        }, fuels: []
    };

    const targetLeaf = State.treeState["Other Demand"].children["Unspecified Uses"];
    Object.keys(State.macro_targets).forEach(fuelName => {
        targetLeaf.fuels.push({ name: fuelName, weight: 0.1, efficiency: 1.0 });
    });

    refreshTree();
    showCustomToast("Balancing node injected! Click 'Optimize Weights'.", "success");
}

DOM.btnOptimize.addEventListener('click', async () => {
    showLoading("Running SLSQP Optimizer...");
    try {
        const res = await EnergyModelAPI.optimizeTree(buildApiPayload());
        updateWeightsFromBackend(State.treeState, res.balanced_tree);
        refreshTree(); 
        
        DOM.statusMessage.innerText = "Mathematically Optimized!";
        DOM.statusMessage.className = "text-sm font-bold text-purple-600";
        DOM.btnExport.classList.remove('hidden');
        showCustomToast(res.message, "success");
    } catch (e) {
        showCustomToast("Optimization failed: " + e.message, "error");
    } finally {
        hideLoading();
    }
});

function updateWeightsFromBackend(localTree, backendTree) {
    for (const key in localTree) {
        if (backendTree[key]) {
            localTree[key].weight = backendTree[key].normalized_weight;
            
            if (backendTree[key].min_weight !== undefined) localTree[key].min_weight = backendTree[key].min_weight;
            if (backendTree[key].max_weight !== undefined) localTree[key].max_weight = backendTree[key].max_weight;
            if (backendTree[key].macro_driver !== undefined) localTree[key].macro_driver = backendTree[key].macro_driver;

            if (localTree[key].children && backendTree[key].children) {
                updateWeightsFromBackend(localTree[key].children, backendTree[key].children);
            }
            if (localTree[key].fuels && backendTree[key].fuels) {
                localTree[key].fuels.forEach(localFuel => {
                    const backFuel = backendTree[key].fuels.find(f => f.name === localFuel.name);
                    if (backFuel) localFuel.weight = backFuel.normalized_weight;
                });
            }
        }
    }
}

// Refactored Export Method: Transmits the real-time customizable macro drivers dictionary context directly
DOM.btnExport.addEventListener('click', async () => {
    showLoading("Generating LEAP Export...");
    try {
        const payload = {
            economy: State.economy, 
            year: State.year, 
            sector_flow: State.sector_flow,
            macro_drivers: State.macroDrivers, 
            balanced_tree: State.treeState 
        };
        const res = await EnergyModelAPI.exportToLeap(payload);
        await showCustomConfirm(
            "Export Successful",
            `Success! ${res.message}\n\nExport File Path:\n${res.leap_export_path}`,
            { confirmText: "OK", cancelText: "" }
        );
    } catch(e) {
        showCustomToast("Export failed: " + e.message, "error");
    } finally {
        hideLoading();
    }
});

function showLoading(text) {
    DOM.loadingText.innerText = text;
    DOM.loadingOverlay.classList.remove('hidden');
    DOM.loadingOverlay.classList.add('flex');
}
function hideLoading() {
    DOM.loadingOverlay.classList.add('hidden');
    DOM.loadingOverlay.classList.remove('flex');
}

// ==========================================
// 7. COLLAPSIBLE RESULTS PANEL LOGIC
// ==========================================

function getLeafNodes(nodes, pathArray = [], parentWeightsProduct = 1.0) {
    if (!nodes) return [];
    let leaves = [];
    for (const [nodeName, nodeData] of Object.entries(nodes)) {
        const normWeight = nodeData._ui_normalized !== undefined ? nodeData._ui_normalized : 0;
        const currentWeightsProduct = parentWeightsProduct * normWeight;
        const newPathArray = [...pathArray, nodeName];
        const isLeaf = !nodeData.children || Object.keys(nodeData.children).length === 0;
        
        if (isLeaf) {
            leaves.push({
                name: nodeName,
                path: newPathArray,
                activityLevel: currentWeightsProduct,
                energy: nodeData._ui_energy !== undefined ? nodeData._ui_energy : 0,
                macroDriver: nodeData.macro_driver,
                fuels: nodeData.fuels || []
            });
        } else {
            leaves = leaves.concat(getLeafNodes(nodeData.children, newPathArray, currentWeightsProduct));
        }
    }
    return leaves;
}

function formatModelNumber(val) {
    const absVal = Math.abs(val);
    if (val === 0) return "0.00";
    if (absVal >= 1000000) {
        return val.toExponential(3);
    } else if (absVal < 0.001) {
        return val.toExponential(3);
    } else {
        return val.toLocaleString('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 4 });
    }
}

function setupResultsPanelToggle() {
    if (!DOM.btnToggleResults || !DOM.resultsSidebar) return;
    DOM.btnToggleResults.addEventListener('click', () => {
        const isCollapsed = DOM.resultsSidebar.classList.toggle('is-collapsed');
        if (isCollapsed) {
            DOM.btnToggleResults.innerText = '‹';
            DOM.btnToggleResults.title = 'Expand Results Panel';
        } else {
            DOM.btnToggleResults.innerText = '›';
            DOM.btnToggleResults.title = 'Collapse Results Panel';
        }
    });
}

function renderResultsSummary() {
    if (!DOM.resultsTableContainer) return;
    
    // Handle early state when treeState has no roots
    if (Object.keys(State.treeState).length === 0) {
        DOM.resultsTableContainer.innerHTML = `
            <div class="flex flex-col items-center justify-center text-slate-400 h-full text-center py-20 italic">
                <svg class="w-10 h-10 mb-2 text-slate-300" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="1.5" d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z"></path></svg>
                No branches available. Initialize the model to view results.
            </div>
        `;
        if (DOM.resultsCount) {
            DOM.resultsCount.innerText = "0 branches";
        }
        return;
    }
    
    // 1. Determine scaling based on unit select dropdown
    const unitVal = DOM.selectResultsUnit ? DOM.selectResultsUnit.value : "PJ";
    let unitFactor = 1.0;
    let unitLabel = "PJ";
    if (unitVal === "GJ") {
        unitFactor = 1e6;
        unitLabel = "GJ";
    } else if (unitVal === "MJ") {
        unitFactor = 1e9;
        unitLabel = "MJ";
    }
    
    // 2. Fetch all leaf nodes recursively
    const leaves = getLeafNodes(State.treeState);
    
    // 3. Filter leaf nodes based on search value
    const searchQuery = DOM.inputSearchResults ? DOM.inputSearchResults.value.trim().toLowerCase() : "";
    const filteredLeaves = leaves.filter(leaf => {
        const pathStr = leaf.path.join(" › ").toLowerCase();
        return pathStr.includes(searchQuery);
    });
    
    // 4. Update count badge
    if (DOM.resultsCount) {
        DOM.resultsCount.innerText = `${filteredLeaves.length} branch${filteredLeaves.length === 1 ? '' : 'es'}`;
    }
    
    // 5. Build and render rows
    if (filteredLeaves.length === 0) {
        DOM.resultsTableContainer.innerHTML = `
            <div class="flex flex-col items-center justify-center text-slate-400 h-full text-center py-20 italic">
                <svg class="w-10 h-10 mb-2 text-slate-300" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="1.5" d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z"></path></svg>
                No matching branches found.
            </div>
        `;
        return;
    }
    
    // Find the first driver key in global macroDrivers to use as fallback if unassigned
    const activeDriverKeys = Object.keys(State.macroDrivers);
    const fallbackDriverKey = activeDriverKeys.length > 0 ? activeDriverKeys[0] : null;
    
    const hardcodedLabels = {
        households: 'Households',
        floor_area_sqm: 'Floor Area (sqm)',
        occupancy_rate: 'Occupancy Rate'
    };
    
    let cardsHtml = '';
    filteredLeaves.forEach(leaf => {
        const scaledEnergy = leaf.energy * unitFactor;
        const activityPercent = State.total_energy > 0 ? ((leaf.energy / State.total_energy) * 100).toFixed(4) : "0.0000";
        
        // Fallback logic
        const finalDriverKey = leaf.macroDriver || fallbackDriverKey;
        const finalDriverVal = finalDriverKey ? (State.macroDrivers[finalDriverKey] || 0) : 0;
        const driverLabel = finalDriverKey ? (hardcodedLabels[finalDriverKey] || finalDriverKey) : 'None';
        
        // Intensity math
        const intensity = finalDriverVal > 0 ? (scaledEnergy / finalDriverVal) : 0;
        
        // Breadcrumb presentation
        const pathHtml = leaf.path.map((p, i) => {
            if (i === leaf.path.length - 1) {
                return `<span class="font-extrabold text-slate-800">${p}</span>`;
            }
            return `<span>${p}</span>`;
        }).join(' <span class="text-slate-300">›</span> ');
        
        // Fuels associated
        const fuelsHtml = leaf.fuels.length > 0 
            ? leaf.fuels.map(f => `<span class="fuel-badge" title="Weight: ${f.weight}, Eff: ${f.efficiency}">${f.name}</span>`).join(' ')
            : `<span class="text-xs text-slate-400 italic">No fuels</span>`;
            
        cardsHtml += `
            <div class="result-card fade-in flex flex-col gap-2">
                <!-- Breadcrumb Path -->
                <div class="result-breadcrumb flex items-center gap-1 flex-wrap min-w-0">
                    ${pathHtml}
                </div>
                
                <!-- Energy & Activity Level Grid -->
                <div class="grid grid-cols-2 gap-3 pt-1 border-t border-slate-100">
                    <div>
                        <span class="block text-[9px] font-bold text-slate-400 uppercase tracking-tight">Energy Drop</span>
                        <span class="text-sm font-black text-slate-800">${formatModelNumber(scaledEnergy)} <span class="text-[10px] font-bold text-blue-600">${unitLabel}</span></span>
                    </div>
                    <div>
                        <span class="block text-[9px] font-bold text-slate-400 uppercase tracking-tight">Activity Level</span>
                        <span class="text-sm font-black text-purple-600">${activityPercent}%</span>
                    </div>
                </div>
                
                <!-- Driver & Intensity Grid -->
                <div class="grid grid-cols-2 gap-3 pt-1">
                    <div>
                        <span class="block text-[9px] font-bold text-slate-400 uppercase tracking-tight">Macro Driver</span>
                        <span class="text-xs font-semibold text-slate-700 truncate block" title="${driverLabel}: ${finalDriverVal.toLocaleString('en-US')}">
                            ${driverLabel} (${finalDriverVal.toLocaleString('en-US')})
                        </span>
                    </div>
                    <div>
                        <span class="block text-[9px] font-bold text-slate-400 uppercase tracking-tight">Intensity</span>
                        <span class="text-xs font-bold text-emerald-600 truncate block" title="Energy / Driver">
                            ${formatModelNumber(intensity)} <span class="text-[9px] font-medium text-slate-400">${unitLabel}/Unit</span>
                        </span>
                    </div>
                </div>
                
                <!-- Associated Fuels -->
                <div class="pt-2 border-t border-dashed border-slate-100 flex items-center justify-between gap-2 flex-wrap">
                    <span class="text-[9px] font-bold text-slate-400 uppercase tracking-tight">Associated Fuels</span>
                    <div class="flex items-center gap-1.5 flex-wrap">
                        ${fuelsHtml}
                    </div>
                </div>
            </div>
        `;
    });
    
    DOM.resultsTableContainer.innerHTML = cardsHtml;
}

function handleCSVExport() {
    const leaves = getLeafNodes(State.treeState);
    if (leaves.length === 0) {
        showCustomToast("No branches available to export.", "warning");
        return;
    }
    
    const unitVal = DOM.selectResultsUnit ? DOM.selectResultsUnit.value : "PJ";
    let unitFactor = 1.0;
    if (unitVal === "GJ") {
        unitFactor = 1e6;
    } else if (unitVal === "MJ") {
        unitFactor = 1e9;
    }
    
    const activeDriverKeys = Object.keys(State.macroDrivers);
    const fallbackDriverKey = activeDriverKeys.length > 0 ? activeDriverKeys[0] : null;
    
    let csvContent = `Branch Path,Energy (${unitVal}),Activity Level,Macro Driver,Driver Value,Energy Intensity (${unitVal}/driver),Associated Fuels\n`;
    
    leaves.forEach(leaf => {
        const pathStr = `"${leaf.path.join(' > ')}"`;
        const scaledEnergy = leaf.energy * unitFactor;
        const activityPercent = State.total_energy > 0 ? (leaf.energy / State.total_energy) : 0;
        
        const finalDriverKey = leaf.macroDriver || fallbackDriverKey;
        const finalDriverVal = finalDriverKey ? (State.macroDrivers[finalDriverKey] || 0) : 0;
        const intensity = finalDriverVal > 0 ? (scaledEnergy / finalDriverVal) : 0;
        
        const fuelsStr = `"${leaf.fuels.map(f => f.name).join('; ')}"`;
        const driverLabel = finalDriverKey || 'None';
        
        csvContent += `${pathStr},${scaledEnergy},${activityPercent},"${driverLabel}",${finalDriverVal},${intensity},${fuelsStr}\n`;
    });
    
    const blob = new Blob([csvContent], { type: 'text/csv;charset=utf-8;' });
    const url = URL.createObjectURL(blob);
    const link = document.createElement("a");
    link.setAttribute("href", url);
    link.setAttribute("download", `energy_modeler_results_${unitVal.toLowerCase()}_${new Date().toISOString().slice(0,10)}.csv`);
    link.style.visibility = 'hidden';
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
    
    showCustomToast("Results CSV exported successfully.", "success");
}

document.addEventListener('DOMContentLoaded', initApp);