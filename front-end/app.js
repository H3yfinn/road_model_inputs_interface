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
    roadModule1: {
        version: null,
        economy: null,
        scenario: 'Target',
        scenarios: ['Current Accounts', 'Target'],
        configuredScenarios: ['Current Accounts', 'Reference', 'Target'],
        keyColumns: [],
        rows: [],
        hiddenRows: [],
        overrides: new Map(),
        sharedMileageOverrides: new Map(),
        sharedFuelEconomyOverrides: new Map(),
        sharedUtilisationOverrides: new Map(),
        turnoverConfig: {
            passenger: { lower: '', upper: '', fitMode: 'auto' },
            freight:   { lower: '', upper: '', fitMode: 'auto' }
        },
        activeFilter: '',
        structuredFilters: {
            scenario: '',
            vehicle: '',
            drive: '',
            measure: ''
        },
        sortBy: 'energy-rank',
        sortDirection: 'desc',
        viewMode: 'list',
        dataDensity: 'less',
        lastDraftSavedAt: null
    },
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
    activeNodePathStr: null,
    // Researcher-defined variables exported to the User_Variables sheet
    userVariables: []  // Array of { id, name, key, value, unit, category, description }
};

const ROAD_MODULE1_BASE_YEAR = 2022;
const ROAD_MODULE1_CURRENT_ACCOUNTS = 'Current Accounts';
const ROAD_MODULE1_DEFAULT_PROJECTION_SCENARIO = 'Target';
const ROAD_MODULE1_CONFIGURED_SCENARIOS = ['Current Accounts', 'Reference', 'Target'];
const ROAD_MODULE1_STATIC_BASE_PATH = './road-module1-static';
const ROAD_MODULE1_STATIC_INDEX_PATH = `${ROAD_MODULE1_STATIC_BASE_PATH}/index.json`;
const ROAD_MODULE1_REQUIRED_KEY_COLUMNS = ['Branch Path', 'Variable', 'Scenario', 'Region'];
const ROAD_MODULE1_LONG_KEY_COLUMNS = ['Economy', 'Scenario', 'Branch Path', 'Variable', 'Year'];
const ROAD_MODULE1_LONG_COLUMNS = ['Economy', 'Scenario', 'Branch Path', 'Variable', 'Year', 'Value', 'Scale', 'Units', 'Source', 'Comment', 'Input Status', 'Shown In Interface'];
const ROAD_MODULE1_STOCK_SHARE_TARGET_YEARS = [2040, 2060];
const ROAD_SERIES_RECOMMENDATION = 'For a full path to 2060, it is often easiest to prepare the values in Excel or ask an AI tool to draft a year-by-year series, then paste it here.';
const ROAD_MODULE1_STOCK_SHARE_BRANCHES = {
    passenger: [
        'Demand\\Passenger road\\Motorcycles',
        'Demand\\Passenger road\\Buses',
        'Demand\\Passenger road\\LPVs'
    ],
    freight: [
        'Demand\\Freight road\\Trucks',
        'Demand\\Freight road\\LCVs'
    ]
};
const ROAD_MODULE1_TRANSPORT_PARAM_GROUPS_ENABLED = {
    ownership: true,
    fleetWeighting: true,
    freightProjection: true
};
const ROAD_MODULE1_VALUE_RULES = {
    'Stock': { min: 0 },
    'Sales Share': { min: 0, max: 100 },
    'Stock Share': { min: 0, max: 100 },
    'Final On-Road Fuel Economy': { min: 0 },
    'Fuel Economy': { min: 0 },
    'Mileage Correction Factor': { min: 0 },
    'Fuel Economy Correction Factor': { min: 0 },
    'Mileage': { min: 0 },
    'Passenger Vehicle Saturation': { min: 0 },
    'Passenger Stock Growth Rate Adjustment': { min: 0, max: 2 },
    'PHEV Electric Driving Share': { min: 0, max: 100 },
    'Freight GDP Elasticity Adjustment': { min: 0, max: 2 },
    'Reconciliation Bound Lower': { min: 0 },
    'Reconciliation Bound Upper': { min: 0 },
    'Reconciliation Weight': { min: 0 },
    'Gasoline/Diesel Share Tolerance': { min: 0, max: 100 },
    'Survival Rate': { min: 0, max: 100 },
    'Turnover Rate Bound Lower': { min: 0, max: 1 },
    'Turnover Rate Bound Upper': { min: 0, max: 1 },
    'Vehicle Equivalent Weight': { min: 0 },
    'Vintage Profile Share': { min: 0, max: 100 }
};
const RoadModule1StaticBundleState = {
    indexLoaded: false,
    indexData: null
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
    
    // User Variables panel
    btnToggleUserVars: document.getElementById('btn-toggle-user-vars'),
    userVarsForm: document.getElementById('user-vars-form'),
    inputUvarName: document.getElementById('input-uvar-name'),
    inputUvarValue: document.getElementById('input-uvar-value'),
    inputUvarUnit: document.getElementById('input-uvar-unit'),
    inputUvarCategory: document.getElementById('input-uvar-category'),
    inputUvarDescription: document.getElementById('input-uvar-description'),
    btnAddUserVar: document.getElementById('btn-add-user-var'),
    userVarsContainer: document.getElementById('user-vars-container'),

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
    roadModule1Main: document.getElementById('road-module1-main'),
    roadVersionSelect: document.getElementById('road-version-select'),
    roadEconomySelect: document.getElementById('road-economy-select'),
    roadLoadDefaults: document.getElementById('road-load-defaults'),
    roadUseBuiltinProvidedValues: document.getElementById('road-use-builtin-provided-values'),
    roadDownloadProvidedTemplate: document.getElementById('road-download-provided-template'),
    roadProvidedFileInput: document.getElementById('road-provided-file-input'),
    roadUploadProvidedValues: document.getElementById('road-upload-provided-values'),
    roadLeftPanel: document.getElementById('road-left-panel'),
    roadLeftResizer: document.getElementById('road-left-resizer'),
    roadFilterInput: document.getElementById('road-filter-input'),
    roadFilterScenario: document.getElementById('road-filter-scenario'),
    roadFilterVehicle: document.getElementById('road-filter-vehicle'),
    roadFilterDrive: document.getElementById('road-filter-drive'),
    roadFilterMeasure: document.getElementById('road-filter-measure'),
    roadSortBy: document.getElementById('road-sort-by'),
    roadSortDirection: document.getElementById('road-sort-direction'),
    roadListView: document.getElementById('road-list-view'),
    roadTreeView: document.getElementById('road-tree-view'),
    roadDensityLess: document.getElementById('road-density-less'),
    roadSaveOutput: document.getElementById('road-save-output'),
    roadRunModel: document.getElementById('road-run-model'),
    roadClearDraft: document.getElementById('road-clear-draft'),
    roadSaveStatus: document.getElementById('road-save-status'),
    roadRunLogModal: document.getElementById('road-run-log-modal'),
    roadRunLogTitle: document.getElementById('road-run-log-title'),
    roadRunLogSpinner: document.getElementById('road-run-log-spinner'),
    roadRunLogOutput: document.getElementById('road-run-log-output'),
    roadRunLogClose: document.getElementById('road-run-log-close'),
    roadRunLogDashboard: document.getElementById('road-run-log-dashboard'),
    roadRunLogWorkbook: document.getElementById('road-run-log-workbook'),
    roadRunLogLifecycleProfiles: document.getElementById('road-run-log-lifecycle-profiles'),
    roadRunLogReimportCsv: document.getElementById('road-run-log-reimport-csv'),
    roadDensityMore: document.getElementById('road-density-more'),
    roadDensityUltra: document.getElementById('road-density-ultra'),
    roadRowStats: document.getElementById('road-row-stats'),
    roadValidationSummary: document.getElementById('road-validation-summary'),
    roadInputContainer: document.getElementById('road-input-container'),
    roadVariableMapBtn: document.getElementById('road-variable-map-btn'),
    roadVariableMapModal: document.getElementById('road-variable-map-modal'),
    roadVariableMapClose: document.getElementById('road-variable-map-close'),
    roadVariableMapDiagram: document.getElementById('road-variable-map-diagram'),
    roadUploadSummaryModal: document.getElementById('road-upload-summary-modal'),
    roadUploadSummaryTitle: document.getElementById('road-upload-summary-title'),
    roadUploadSummaryText: document.getElementById('road-upload-summary-text'),
    roadUploadSummaryClose: document.getElementById('road-upload-summary-close'),
    roadUploadSummaryDismiss: document.getElementById('road-upload-summary-dismiss'),
    roadUploadSummaryConfirm: document.getElementById('road-upload-summary-confirm'),
    roadUploadSummaryCancel: document.getElementById('road-upload-summary-cancel'),
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
let roadModule1DraftSaveTimer = null;
let pendingRoadModule1Upload = null;
let roadModule1AutoLoadInFlight = false;
let roadModule1SuppressAutoLoad = false;

function getSelectedRoadModule1Version() {
    return DOM.roadVersionSelect?.value || State.roadModule1.version || '';
}

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

function showRoadUploadSummaryModal(title, summaryText, { confirmMode = false } = {}) {
    if (!DOM.roadUploadSummaryModal || !DOM.roadUploadSummaryText || !DOM.roadUploadSummaryTitle) return;
    DOM.roadUploadSummaryTitle.innerText = title || 'Upload Change Summary';
    DOM.roadUploadSummaryText.value = summaryText || '';

    const showConfirm = confirmMode;
    DOM.roadUploadSummaryConfirm?.classList.toggle('hidden', !showConfirm);
    DOM.roadUploadSummaryCancel?.classList.toggle('hidden', !showConfirm);
    DOM.roadUploadSummaryDismiss?.classList.toggle('hidden', showConfirm);

    DOM.roadUploadSummaryModal.classList.remove('hidden');
    DOM.roadUploadSummaryModal.classList.add('flex-display');

    setTimeout(() => {
        DOM.roadUploadSummaryModal.style.opacity = '1';
        DOM.roadUploadSummaryModal.querySelector('.road-upload-summary-card')?.classList.add('is-open');
    }, 20);
}

function closeRoadUploadSummaryModal() {
    if (!DOM.roadUploadSummaryModal) return;
    DOM.roadUploadSummaryModal.style.opacity = '0';
    DOM.roadUploadSummaryModal.querySelector('.road-upload-summary-card')?.classList.remove('is-open');
    setTimeout(() => {
        DOM.roadUploadSummaryModal.classList.add('hidden');
        DOM.roadUploadSummaryModal.classList.remove('flex-display');
    }, 200);
}

if (DOM.roadUploadSummaryClose) {
    DOM.roadUploadSummaryClose.addEventListener('click', () => {
        pendingRoadModule1Upload = null;
        closeRoadUploadSummaryModal();
    });
}
if (DOM.roadUploadSummaryDismiss) {
    DOM.roadUploadSummaryDismiss.addEventListener('click', closeRoadUploadSummaryModal);
}
if (DOM.roadUploadSummaryCancel) {
    DOM.roadUploadSummaryCancel.addEventListener('click', () => {
        pendingRoadModule1Upload = null;
        closeRoadUploadSummaryModal();
        showCustomToast('Upload cancelled — no changes applied.', 'info');
    });
}
if (DOM.roadUploadSummaryConfirm) {
    DOM.roadUploadSummaryConfirm.addEventListener('click', () => {
        if (!pendingRoadModule1Upload) { closeRoadUploadSummaryModal(); return; }
        const { preview, version, economy, fileName } = pendingRoadModule1Upload;
        pendingRoadModule1Upload = null;
        commitRoadModule1UploadPreview(preview, version, economy, fileName);
        closeRoadUploadSummaryModal();
    });
}
if (DOM.roadUploadSummaryModal) {
    DOM.roadUploadSummaryModal.addEventListener('click', (event) => {
        if (event.target === DOM.roadUploadSummaryModal) {
            pendingRoadModule1Upload = null;
            closeRoadUploadSummaryModal();
        }
    });
}

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
    setupRoadModule1();

    if (DOM.btnStart) {
        renderGlobalMacroDriversPanel();
        renderUserVariablesPanel();
        DOM.btnStart.addEventListener('click', handleStartModeling);
    }

    if (DOM.btnCollapseAll) DOM.btnCollapseAll.addEventListener('click', () => handleGlobalCollapse(true));
    if (DOM.btnExpandAll) DOM.btnExpandAll.addEventListener('click', () => handleGlobalCollapse(false));
    if (DOM.selectMacroDriverType) DOM.selectMacroDriverType.addEventListener('change', handleMacroDriverTemplateToggle);
    if (DOM.btnAddMacroDriver) DOM.btnAddMacroDriver.addEventListener('click', handleAddMacroDriverItem);
    if (DOM.btnToggleUserVars) {
        DOM.btnToggleUserVars.addEventListener('click', () => {
            DOM.userVarsForm.classList.toggle('hidden');
            DOM.btnToggleUserVars.textContent = DOM.userVarsForm.classList.contains('hidden') ? '+ Add' : '− Hide';
        });
    }
    if (DOM.btnAddUserVar) DOM.btnAddUserVar.addEventListener('click', handleAddUserVariable);

    setupInteractiveCanvas();
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
    if (DOM.selectEconomy) {
        economies.forEach(eco => DOM.selectEconomy.add(new Option(eco.text, eco.code)));
        DOM.selectEconomy.value = "20USA";
    }

    if (DOM.selectYear) {
        for (let y = 2022; y >= 2000; y--) {
            DOM.selectYear.add(new Option(y.toString(), y));
        }
    }

    if (DOM.selectSector) {
        const sectors = [
            "14 Industry sector",
            "15 Transport sector",
            "16 Other sector",
            "16.01 Commercial and public services",
            "16.02 Residential"
        ];
        sectors.forEach(sec => DOM.selectSector.add(new Option(sec, sec)));
        DOM.selectSector.value = "16.02 Residential";
    }
}

function setupInfoTipPopup() {
    const popup = document.createElement('div');
    popup.id = 'road-info-tip-popup';
    document.body.appendChild(popup);

    document.addEventListener('mouseover', (e) => {
        const tip = e.target.closest('.road-info-tip');
        if (!tip) return;
        const text = tip.dataset.tip;
        if (!text) return;
        popup.textContent = text;
        popup.style.display = 'block';
        const rect = tip.getBoundingClientRect();
        const pr = popup.getBoundingClientRect();
        const gap = 6;
        let top = rect.top - pr.height - gap;
        let left = rect.left + rect.width / 2 - pr.width / 2;
        if (top < gap) top = rect.bottom + gap;
        if (left < gap) left = gap;
        if (left + pr.width > window.innerWidth - gap) left = window.innerWidth - pr.width - gap;
        popup.style.top = `${top}px`;
        popup.style.left = `${left}px`;
    });

    document.addEventListener('mouseout', (e) => {
        if (e.target.closest('.road-info-tip')) popup.style.display = 'none';
    });
}

function setupRoadModule1() {
    if (!DOM.roadModule1Main) return;

    seedRoadModule1FallbackSelectors();
    setupRoadHelpTooltips();
    setupInfoTipPopup();

    if (DOM.roadLoadDefaults) {
        DOM.roadLoadDefaults.addEventListener('click', loadRoadModule1Defaults);
    }
    if (DOM.roadUseBuiltinProvidedValues) {
        DOM.roadUseBuiltinProvidedValues.addEventListener('click', loadRoadModule1BuiltinProvidedValues);
    }
    if (DOM.roadDownloadProvidedTemplate) {
        DOM.roadDownloadProvidedTemplate.addEventListener('click', downloadRoadModule1ProvidedValuesTemplate);
    }
    if (DOM.roadUploadProvidedValues && DOM.roadProvidedFileInput) {
        DOM.roadUploadProvidedValues.addEventListener('click', () => DOM.roadProvidedFileInput.click());
        DOM.roadProvidedFileInput.addEventListener('change', handleRoadModule1ProvidedFileSelected);
    }
    DOM.roadSaveOutput.addEventListener('click', saveRoadModule1ResearcherOutput);
    if (DOM.roadRunModel) {
        DOM.roadRunModel.addEventListener('click', runRoadModel);
    }
    if (DOM.roadRunLogClose) {
        DOM.roadRunLogClose.addEventListener('click', hideRoadRunLogModal);
    }
    if (DOM.roadVariableMapBtn) {
        DOM.roadVariableMapBtn.addEventListener('click', showRoadVariableMapModal);
    }
    if (DOM.roadVariableMapClose) {
        DOM.roadVariableMapClose.addEventListener('click', hideRoadVariableMapModal);
    }
    if (DOM.roadClearDraft) {
        DOM.roadClearDraft.addEventListener('click', clearRoadModule1DraftForCurrentSelection);
    }
    setupRoadLeftPanelResizer();
    if (DOM.roadFilterInput) {
        DOM.roadFilterInput.addEventListener('input', (event) => {
            State.roadModule1.activeFilter = event.target.value.trim().toLowerCase();
            renderRoadModule1Inputs();
            scheduleRoadModule1DraftSave();
        });
    }
    setupRoadModule1FilterControls();
    setupRoadModule1ViewControls();
    if (DOM.roadVersionSelect) {
        DOM.roadVersionSelect.addEventListener('change', async () => {
            if (roadModule1SuppressAutoLoad) return;
            await populateRoadModule1Economies(getSelectedRoadModule1Version());
            await autoLoadRoadModule1OnSelectionChange();
        });
    }
    DOM.roadEconomySelect.addEventListener('change', async () => {
        if (roadModule1SuppressAutoLoad) return;
        await autoLoadRoadModule1OnSelectionChange();
    });

    updateRoadModule1OptionalBackendUiState();
    populateRoadModule1Selectors();
    if (typeof setupRoadModelHelper === 'function') setupRoadModelHelper();
}

function updateRoadModule1OptionalBackendUiState() {
    if (DOM.roadUseBuiltinProvidedValues) {
        DOM.roadUseBuiltinProvidedValues.disabled = false;
        DOM.roadUseBuiltinProvidedValues.title = '';
    }
    if (DOM.roadDownloadProvidedTemplate) {
        DOM.roadDownloadProvidedTemplate.disabled = false;
        DOM.roadDownloadProvidedTemplate.title = '';
    }
}

function setupRoadLeftPanelResizer() {
    if (!DOM.roadLeftPanel || !DOM.roadLeftResizer) return;

    const storageKey = 'roadModule1:leftPanelWidth';
    const computedStyle = window.getComputedStyle(DOM.roadLeftPanel);
    const minWidth = Number.parseFloat(computedStyle.minWidth) || 60;
    const maxWidth = Number.parseFloat(computedStyle.maxWidth) || 560;

    const clampWidth = (width) => Math.max(minWidth, Math.min(maxWidth, width));

    const savedWidth = Number.parseFloat(localStorage.getItem(storageKey) || '');
    if (Number.isFinite(savedWidth)) {
        DOM.roadLeftPanel.style.width = `${clampWidth(savedWidth)}px`;
    }

    const onMouseDown = (event) => {
        event.preventDefault();

        const startX = event.clientX;
        const startWidth = DOM.roadLeftPanel.getBoundingClientRect().width;

        DOM.roadLeftPanel.classList.add('is-resizing');
        document.body.classList.add('road-panel-resizing');

        const onMouseMove = (moveEvent) => {
            const deltaX = moveEvent.clientX - startX;
            const nextWidth = clampWidth(startWidth + deltaX);
            DOM.roadLeftPanel.style.width = `${nextWidth}px`;
        };

        const onMouseUp = () => {
            const finalWidth = clampWidth(DOM.roadLeftPanel.getBoundingClientRect().width);
            DOM.roadLeftPanel.style.width = `${finalWidth}px`;
            localStorage.setItem(storageKey, String(finalWidth));

            DOM.roadLeftPanel.classList.remove('is-resizing');
            document.body.classList.remove('road-panel-resizing');
            document.removeEventListener('mousemove', onMouseMove);
            document.removeEventListener('mouseup', onMouseUp);
        };

        document.addEventListener('mousemove', onMouseMove);
        document.addEventListener('mouseup', onMouseUp);
    };

    DOM.roadLeftResizer.addEventListener('mousedown', onMouseDown);
}

function getRoadStaticIndexVersions(indexData) {
    const versions = Array.isArray(indexData?.versions)
        ? indexData.versions
        : [];
    return versions
        .map(item => {
            if (typeof item === 'string') return item;
            if (item && typeof item.version === 'string') return item.version;
            return '';
        })
        .filter(Boolean);
}

function getRoadStaticIndexDefaultVersion(indexData, versions) {
    const defaultVersion = String(indexData?.default_version || '').trim();
    if (defaultVersion && versions.includes(defaultVersion)) return defaultVersion;
    if (versions.length > 0) return versions[versions.length - 1];
    return '';
}

function getRoadStaticEconomies(indexData, version) {
    const versions = Array.isArray(indexData?.versions)
        ? indexData.versions
        : [];
    const versionRecord = versions.find(item => item && typeof item === 'object' && item.version === version);
    const economies = Array.isArray(versionRecord?.economies)
        ? versionRecord.economies
        : [];

    return economies
        .map(item => {
            if (!item || typeof item !== 'object') return null;
            const economy = String(item.economy || '').trim();
            const economyName = String(item.economy_name || '').trim();
            if (!economy || !economyName) return null;
            return { economy, economy_name: economyName };
        })
        .filter(Boolean);
}

function sanitizeRoadStaticSegment(value) {
    return String(value || '')
        .trim()
        .replace(/[^a-zA-Z0-9_-]+/g, '_');
}

async function fetchRoadModule1StaticIndex() {
    if (RoadModule1StaticBundleState.indexLoaded) {
        return RoadModule1StaticBundleState.indexData;
    }

    const response = await fetch(ROAD_MODULE1_STATIC_INDEX_PATH, { cache: 'no-store' });
    if (!response.ok) {
        throw new Error(`Static selector index was not found at ${ROAD_MODULE1_STATIC_INDEX_PATH}.`);
    }

    const data = await response.json();
    if (!data || typeof data !== 'object') {
        throw new Error('Static selector index is malformed.');
    }

    RoadModule1StaticBundleState.indexLoaded = true;
    RoadModule1StaticBundleState.indexData = data;
    if (Array.isArray(data.configured_scenarios) && data.configured_scenarios.length > 0) {
        State.roadModule1.configuredScenarios = data.configured_scenarios
            .map(normaliseRoadScenarioLabel)
            .filter(Boolean);
    }
    return data;
}

async function loadRoadModule1DefaultsFromStaticBundle(version, economy) {
    const safeVersion = sanitizeRoadStaticSegment(version);
    const safeEconomy = sanitizeRoadStaticSegment(economy);
    const path = `${ROAD_MODULE1_STATIC_BASE_PATH}/${safeVersion}/${safeEconomy}.csv`;

    const response = await fetch(path, { cache: 'no-store' });
    if (!response.ok) {
        throw new Error(
            `No packaged defaults file found for ${version}/${economy}. Expected: ${path}`
        );
    }

    const text = await response.text();
    const rows = parseCsvText(text).map(row => ({
        ...row,
        Year: row.Year === '' ? row.Year : Number(row.Year),
        Value: row.Value === '' ? row.Value : Number(row.Value),
        Scenario: row.Scenario || 'Current Accounts'
    }));

    if (rows.length === 0) {
        throw new Error(`Static defaults file is empty: ${path}`);
    }

    return {
        key_columns: ROAD_MODULE1_LONG_KEY_COLUMNS,
        rows
    };
}

function normalizeRoadModule1RowsForUi(rows) {
    const rawRows = Array.isArray(rows) ? rows : [];
    const looksLong = rawRows.length > 0
        && ROAD_MODULE1_LONG_KEY_COLUMNS.every(column => Object.prototype.hasOwnProperty.call(rawRows[0], column))
        && Object.prototype.hasOwnProperty.call(rawRows[0], 'Value');
    const uiRows = looksLong ? convertRoadLongRowsToWideUiRows(rawRows) : rawRows.map(row => ({ ...row }));
    return ensureRoadStockShareTargetYearColumns(uiRows).map(row => ({
        ...row,
        researcher_review_recommended: false
    }));
}

function normaliseRoadScenarioLabel(value) {
    return String(value || '').trim();
}

function getRoadModule1ConfiguredScenarios() {
    return Array.from(new Set([
        ...ROAD_MODULE1_CONFIGURED_SCENARIOS,
        ...(State.roadModule1.configuredScenarios || [])
    ].map(normaliseRoadScenarioLabel).filter(Boolean)));
}

function isRoadConfiguredProjectionScenario(label) {
    const scenario = normaliseRoadScenarioLabel(label);
    return scenario !== ROAD_MODULE1_CURRENT_ACCOUNTS
        && getRoadModule1ConfiguredScenarios().includes(scenario);
}

function getRoadModule1ScenariosFromRows(rows) {
    const labels = new Set([ROAD_MODULE1_CURRENT_ACCOUNTS]);
    (rows || []).forEach(row => {
        const scenario = normaliseRoadScenarioLabel(row?.Scenario) || ROAD_MODULE1_CURRENT_ACCOUNTS;
        labels.add(scenario);
    });
    return [
        ROAD_MODULE1_CURRENT_ACCOUNTS,
        ...Array.from(labels)
            .filter(label => label !== ROAD_MODULE1_CURRENT_ACCOUNTS)
            .sort((a, b) => {
                if (a === ROAD_MODULE1_DEFAULT_PROJECTION_SCENARIO) return -1;
                if (b === ROAD_MODULE1_DEFAULT_PROJECTION_SCENARIO) return 1;
                return a.localeCompare(b, 'en-US', { numeric: true });
            })
    ];
}

function syncRoadModule1ScenarioState(preferredScenario = '') {
    const scenarios = getRoadModule1ScenariosFromRows([
        ...(State.roadModule1.rows || []),
        ...(State.roadModule1.hiddenRows || [])
    ]);
    State.roadModule1.scenarios = scenarios;

    const preferred = normaliseRoadScenarioLabel(preferredScenario || State.roadModule1.scenario);
    const fallback = scenarios.find(scenario => scenario !== ROAD_MODULE1_CURRENT_ACCOUNTS)
        || ROAD_MODULE1_CURRENT_ACCOUNTS;
    State.roadModule1.scenario = scenarios.includes(preferred) ? preferred : fallback;
}

function isRoadCurrentAccountsRow(row) {
    return normaliseRoadScenarioLabel(row?.Scenario) === ROAD_MODULE1_CURRENT_ACCOUNTS;
}

function isRoadProjectionRow(row) {
    return !isRoadCurrentAccountsRow(row);
}

function getRoadRowsForCurrentView(rows = State.roadModule1.rows) {
    return rows || [];
}

function getRoadProjectionScenarioLabels() {
    return (State.roadModule1.scenarios || [])
        .filter(scenario => scenario && scenario !== ROAD_MODULE1_CURRENT_ACCOUNTS);
}

function getRoadRunScenarioLabels() {
    return getRoadProjectionScenarioLabels();
}

function cloneRoadProjectionRowsForScenario(rows, sourceScenario, targetScenario) {
    return (rows || [])
        .filter(row => normaliseRoadScenarioLabel(row?.Scenario) === sourceScenario)
        .filter(isRoadProjectionRow)
        .map(row => {
            const clone = { ...row, Scenario: targetScenario, _inputStatus: row._inputStatus || 'default' };
            Object.keys(clone).forEach(column => {
                if (/^\d{4}$/.test(column) && Number(column) <= ROAD_MODULE1_BASE_YEAR) {
                    delete clone[column];
                }
            });
            return clone;
        });
}

function ensureRoadModule1ProjectionScenarioRows(scenarioLabel, rows = State.roadModule1.rows) {
    const scenario = normaliseRoadScenarioLabel(scenarioLabel);
    if (!scenario || scenario === ROAD_MODULE1_CURRENT_ACCOUNTS) return rows || [];
    if (!isRoadConfiguredProjectionScenario(scenario)) {
        throw new Error(`Scenario "${scenario}" is not configured. Add it to the road model scenario config before using it.`);
    }
    const existing = (rows || []).some(row => normaliseRoadScenarioLabel(row?.Scenario) === scenario);
    if (existing) return rows || [];

    const sourceScenario = (rows || []).some(row => normaliseRoadScenarioLabel(row?.Scenario) === ROAD_MODULE1_DEFAULT_PROJECTION_SCENARIO)
        ? ROAD_MODULE1_DEFAULT_PROJECTION_SCENARIO
        : normaliseRoadScenarioLabel((rows || []).find(isRoadProjectionRow)?.Scenario);
    if (!sourceScenario) {
        throw new Error('No projection scenario rows are available to clone.');
    }
    const clonedRows = cloneRoadProjectionRowsForScenario(rows, sourceScenario, scenario);
    if (clonedRows.length === 0) {
        throw new Error(`No projectable rows found in source scenario "${sourceScenario}".`);
    }
    return [...(rows || []), ...clonedRows];
}

function addRoadModule1Scenario(scenarioLabel) {
    if (!Array.isArray(State.roadModule1.rows) || State.roadModule1.rows.length === 0) {
        showCustomToast('Load an economy before adding a scenario.', 'warning');
        return;
    }
    const scenario = normaliseRoadScenarioLabel(scenarioLabel);
    if (!scenario) return;
    if (scenario === ROAD_MODULE1_CURRENT_ACCOUNTS) {
        showCustomToast('Current Accounts already exists as the locked base-year scenario.', 'warning');
        return;
    }
    try {
        State.roadModule1.rows = ensureRoadModule1ProjectionScenarioRows(scenario, State.roadModule1.rows);
        syncRoadModule1ScenarioState(scenario);
        populateRoadModule1StructuredFilters(getRoadRowsForCurrentView());
        renderRoadModule1Inputs();
        scheduleRoadModule1DraftSave();
        showCustomToast(`Scenario ${scenario} added from ${ROAD_MODULE1_DEFAULT_PROJECTION_SCENARIO} projectable rows.`, 'success', 5000);
    } catch (error) {
        showCustomToast(error.message, 'error', 6000);
    }
}

function isRoadModule1ShownInInterface(row) {
    const rawValue = row?.['Shown In Interface'] ?? row?.shown_in_interface ?? row?.shownInInterface;
    if (rawValue === undefined || rawValue === null || rawValue === '') return true;
    return !['false', '0', 'no', 'n'].includes(String(rawValue).trim().toLowerCase());
}

function splitRoadModule1RowsByVisibility(rows) {
    const visibleRows = [];
    const hiddenRows = [];
    (Array.isArray(rows) ? rows : []).forEach(row => {
        if (isRoadProjectionRow(row) || isRoadModule1ShownInInterface(row) || isRoadDriveLevelSalesShareRow(row)) {
            visibleRows.push(row);
        } else {
            hiddenRows.push(row);
        }
    });
    return { visibleRows, hiddenRows };
}

function isRoadVehicleTypeStockShareRow(row) {
    if (!row || String(row.Variable || '') !== 'Stock Share') return false;
    const path = String(row['Branch Path'] || '');
    return Object.values(ROAD_MODULE1_STOCK_SHARE_BRANCHES).some(branches => branches.includes(path));
}

function getRoadStockShareTransportGroup(row) {
    const path = String(row?.['Branch Path'] || '');
    if (ROAD_MODULE1_STOCK_SHARE_BRANCHES.passenger.includes(path)) return 'passenger';
    if (ROAD_MODULE1_STOCK_SHARE_BRANCHES.freight.includes(path)) return 'freight';
    return '';
}

function convertRoadLongRowsToWideUiRows(longRows) {
    const rowsByKey = new Map();
    longRows.forEach(row => {
        const region = row.Region || row.Economy || '';
        const inputStatus = row['Input Status'] || row.input_source || 'default';
        const key = [
            row['Branch Path'] ?? '',
            row.Variable ?? '',
            row.Scenario ?? '',
            region
        ].join('||');
        const target = rowsByKey.get(key) || {
            'Branch Path': row['Branch Path'] ?? '',
            Variable: row.Variable ?? '',
            Scenario: row.Scenario ?? '',
            Region: region,
            Scale: row.Scale ?? (String(row.Variable || '').includes('Share') ? '%' : ''),
            Units: row.Units ?? '',
            'Per...': '',
            input_source: inputStatus,
            _inputStatus: inputStatus,
            'Shown In Interface': row['Shown In Interface'] ?? 'True',
            standardized_label_status: 'standardized',
            notes: row.Comment ?? '',
            source_type: 'module1_long_csv',
            source_name: row.Source ?? '',
            source_scope: row.Economy ?? '',
            source_date: '',
            default_version: State.roadModule1.version || '',
            researcher_review_recommended: false,
            review_reason: ''
        };
        const year = String(row.Year ?? '').trim();
        if (/^\d{4}$/.test(year)) target[year] = row.Value ?? '';
        rowsByKey.set(key, target);
    });
    return Array.from(rowsByKey.values());
}

function ensureRoadStockShareTargetYearColumns(rows) {
    return (rows || []).map(row => {
        if (!isRoadVehicleTypeStockShareRow(row)) return row;
        if (isRoadCurrentAccountsRow(row)) return row;
        const copy = { ...row };
        ROAD_MODULE1_STOCK_SHARE_TARGET_YEARS.forEach(year => {
            const yearKey = String(year);
            if (!Object.prototype.hasOwnProperty.call(copy, yearKey)) copy[yearKey] = '';
        });
        return copy;
    });
}

function seedRoadModule1FallbackSelectors() {
    if (DOM.roadVersionSelect && DOM.roadVersionSelect.options.length === 0) {
        DOM.roadVersionSelect.innerHTML = '';
        DOM.roadVersionSelect.add(new Option('No packaged versions found', ''));
        DOM.roadVersionSelect.value = '';
    }
    if (DOM.roadEconomySelect && DOM.roadEconomySelect.options.length === 0) {
        DOM.roadEconomySelect.innerHTML = '';
        DOM.roadEconomySelect.add(new Option('No packaged economies found', ''));
        DOM.roadEconomySelect.value = '';
    }
}

function setupRoadHelpTooltips() {
    document.querySelectorAll('.road-help-button').forEach(button => {
        const tooltip = button.parentElement?.querySelector('.road-help-tooltip');
        if (!tooltip) return;

        const showTooltip = () => {
            tooltip.classList.add('is-visible');
            tooltip.style.left = '0px';
            tooltip.style.top = '0px';
            const buttonRect = button.getBoundingClientRect();
            const tooltipRect = tooltip.getBoundingClientRect();
            const gap = 8;
            let left = buttonRect.right + gap;
            let top = buttonRect.top - 8;

            if (left + tooltipRect.width > window.innerWidth - gap) {
                left = buttonRect.left - tooltipRect.width - gap;
            }
            if (left < gap) left = gap;
            if (top + tooltipRect.height > window.innerHeight - gap) {
                top = window.innerHeight - tooltipRect.height - gap;
            }
            if (top < gap) top = gap;

            tooltip.style.left = `${left}px`;
            tooltip.style.top = `${top}px`;
        };
        const hideTooltip = () => {
            tooltip.classList.remove('is-visible');
        };

        button.addEventListener('mouseenter', showTooltip);
        button.addEventListener('focus', showTooltip);
        button.addEventListener('mouseleave', hideTooltip);
        button.addEventListener('blur', hideTooltip);
    });
}

function setupRoadModule1FilterControls() {
    const filterBindings = [
        [DOM.roadFilterScenario, 'scenario'],
        [DOM.roadFilterVehicle, 'vehicle'],
        [DOM.roadFilterDrive, 'drive'],
        [DOM.roadFilterMeasure, 'measure']
    ];

    filterBindings.forEach(([element, filterKey]) => {
        if (!element) return;
        element.addEventListener('change', (event) => {
            State.roadModule1.structuredFilters[filterKey] = event.target.value;
            renderRoadModule1Inputs();
            scheduleRoadModule1DraftSave();
        });
    });

    if (DOM.roadSortBy) {
        DOM.roadSortBy.addEventListener('change', (event) => {
            State.roadModule1.sortBy = event.target.value;
            updateRoadSortDirectionLabels();
            renderRoadModule1Inputs();
            scheduleRoadModule1DraftSave();
        });
    }
    if (DOM.roadSortDirection) {
        DOM.roadSortDirection.addEventListener('change', (event) => {
            State.roadModule1.sortDirection = event.target.value;
            renderRoadModule1Inputs();
            scheduleRoadModule1DraftSave();
        });
    }
}

function setupRoadModule1ViewControls() {
    if (DOM.roadListView) {
        DOM.roadListView.addEventListener('click', () => {
            State.roadModule1.viewMode = 'list';
            renderRoadModule1Inputs();
            scheduleRoadModule1DraftSave();
        });
    }
    if (DOM.roadTreeView) {
        DOM.roadTreeView.addEventListener('click', () => {
            State.roadModule1.viewMode = 'tree';
            renderRoadModule1Inputs();
            scheduleRoadModule1DraftSave();
        });
    }
    if (DOM.roadDensityLess) {
        DOM.roadDensityLess.addEventListener('click', () => {
            State.roadModule1.dataDensity = 'less';
            updateRoadDensityToggle();
            renderRoadModule1Inputs();
            scheduleRoadModule1DraftSave();
        });
    }
    if (DOM.roadDensityMore) {
        DOM.roadDensityMore.addEventListener('click', () => {
            State.roadModule1.dataDensity = 'more';
            updateRoadDensityToggle();
            renderRoadModule1Inputs();
            scheduleRoadModule1DraftSave();
        });
    }
    if (DOM.roadDensityUltra) {
        DOM.roadDensityUltra.addEventListener('click', () => {
            State.roadModule1.dataDensity = 'ultra';
            updateRoadDensityToggle();
            renderRoadModule1Inputs();
            scheduleRoadModule1DraftSave();
        });
    }
}

async function populateRoadModule1Selectors() {
    seedRoadModule1FallbackSelectors();

    try {
        const staticIndex = await fetchRoadModule1StaticIndex();
        const versions = getRoadStaticIndexVersions(staticIndex);
        if (versions.length > 0) {
            roadModule1SuppressAutoLoad = true;
            DOM.roadVersionSelect.innerHTML = '';
            versions.forEach(version => {
                DOM.roadVersionSelect.add(new Option(version, version));
            });
            DOM.roadVersionSelect.value = getRoadStaticIndexDefaultVersion(staticIndex, versions);
            await populateRoadModule1Economies(DOM.roadVersionSelect.value);
            roadModule1SuppressAutoLoad = false;
            await autoLoadRoadModule1OnSelectionChange();
            return;
        }
    } catch (error) {
        roadModule1SuppressAutoLoad = false;
        if (DOM.roadSaveStatus) {
            DOM.roadSaveStatus.innerText = `Static selector metadata unavailable. Populate packaged data from back-end/data/road_model and rebuild static bundle. (${error.message})`;
        }
    }

    seedRoadModule1FallbackSelectors();
    await autoLoadRoadModule1OnSelectionChange();
}

async function populateRoadModule1Economies(version) {
    try {
        const staticIndex = await fetchRoadModule1StaticIndex();
        const economies = getRoadStaticEconomies(staticIndex, version);
        if (economies.length > 0) {
            const previousEconomy = DOM.roadEconomySelect.value;
            DOM.roadEconomySelect.innerHTML = '';
            economies.forEach(item => {
                DOM.roadEconomySelect.add(new Option(`${item.economy} (${item.economy_name})`, item.economy));
            });
            if (previousEconomy && DOM.roadEconomySelect.querySelector(`option[value="${previousEconomy}"]`)) {
                DOM.roadEconomySelect.value = previousEconomy;
            } else if (DOM.roadEconomySelect.options.length > 0) {
                DOM.roadEconomySelect.value = DOM.roadEconomySelect.options[0].value;
            }
            return;
        }
    } catch {
        // If static index is unavailable, fallback economy list applies below.
    }

    seedRoadModule1FallbackSelectors();
}

async function autoLoadRoadModule1OnSelectionChange() {
    if (roadModule1SuppressAutoLoad || roadModule1AutoLoadInFlight) return;

    const version = getSelectedRoadModule1Version();
    const economy = DOM.roadEconomySelect?.value;
    if (!version || !economy) return;

    const hasLoadedRows = Array.isArray(State.roadModule1.rows) && State.roadModule1.rows.length > 0;
    const selectionChanged = (
        State.roadModule1.version !== version
        || State.roadModule1.economy !== economy
    );

    if (!selectionChanged && hasLoadedRows) return;

    roadModule1AutoLoadInFlight = true;
    try {
        await loadRoadModule1Defaults();
    } finally {
        roadModule1AutoLoadInFlight = false;
    }
}

function getRoadModule1DraftKey(version = State.roadModule1.version, economy = State.roadModule1.economy) {
    if (!version || !economy) return null;
    return `roadModule1Draft:${version}:${economy}`;
}

function buildRoadModule1OverrideMapKey(override) {
    const rowKey = State.roadModule1.keyColumns
        .map(column => `${column}=${override.key?.[column] ?? ''}`)
        .join('||');
    return `${rowKey}||Year=${override.year}`;
}

function buildRoadSharedOverrideMapKey(sharedKey, year) {
    return `${sharedKey}||Year=${year}`;
}

function serializeRoadModule1Draft() {
    return {
        savedAt: new Date().toISOString(),
        version: State.roadModule1.version,
        economy: State.roadModule1.economy,
        scenario: State.roadModule1.scenario,
        scenarios: State.roadModule1.scenarios,
        overrides: Array.from(State.roadModule1.overrides.values()),
        activeFilter: State.roadModule1.activeFilter,
        structuredFilters: { ...State.roadModule1.structuredFilters },
        sortBy: State.roadModule1.sortBy,
        sortDirection: State.roadModule1.sortDirection,
        viewMode: State.roadModule1.viewMode,
        dataDensity: State.roadModule1.dataDensity,
        sharedMileageOverrides: Array.from(State.roadModule1.sharedMileageOverrides.values()),
        sharedFuelEconomyOverrides: Array.from(State.roadModule1.sharedFuelEconomyOverrides.values()),
        sharedUtilisationOverrides: Array.from(State.roadModule1.sharedUtilisationOverrides.values()),
        turnoverConfig: State.roadModule1.turnoverConfig
    };
}

function readRoadModule1Draft(version, economy) {
    const draftKey = getRoadModule1DraftKey(version, economy);
    if (!draftKey) return null;
    if (typeof localStorage === 'undefined') return null;
    try {
        const rawDraft = localStorage.getItem(draftKey);
        return rawDraft ? JSON.parse(rawDraft) : null;
    } catch (error) {
        console.warn('Failed to read Road model draft:', error);
        return null;
    }
}

function saveRoadModule1DraftNow() {
    const draftKey = getRoadModule1DraftKey();
    if (!draftKey || !State.roadModule1.rows.length) return;
    if (typeof localStorage === 'undefined') return;

    try {
        const draft = serializeRoadModule1Draft();
        localStorage.setItem(draftKey, JSON.stringify(draft));
        State.roadModule1.lastDraftSavedAt = draft.savedAt;
        if (DOM.roadClearDraft) DOM.roadClearDraft.disabled = false;
    } catch (error) {
        console.warn('Failed to save Road model draft:', error);
    }
}

function scheduleRoadModule1DraftSave() {
    if (!State.roadModule1.version || !State.roadModule1.economy) return;
    clearTimeout(roadModule1DraftSaveTimer);
    roadModule1DraftSaveTimer = setTimeout(saveRoadModule1DraftNow, 350);
}

function clearRoadModule1Draft(version = State.roadModule1.version, economy = State.roadModule1.economy) {
    const draftKey = getRoadModule1DraftKey(version, economy);
    if (!draftKey) return;
    if (typeof localStorage !== 'undefined') {
        localStorage.removeItem(draftKey);
    }
    State.roadModule1.lastDraftSavedAt = null;
    if (DOM.roadClearDraft) DOM.roadClearDraft.disabled = true;
}

async function clearRoadModule1DraftForCurrentSelection() {
    const accepted = await showCustomConfirm(
        'Clear Saved Draft',
        'Clear the browser-saved draft for the currently loaded Road model version and economy?',
        { confirmText: 'Clear Draft', isDanger: true }
    );
    if (!accepted) return;
    clearRoadModule1Draft();
    showCustomToast('Saved draft cleared.', 'info');
}

function applyRoadModule1Draft(draft) {
    if (!draft) return;
    State.roadModule1.overrides = new Map();
    State.roadModule1.sharedMileageOverrides = new Map();
    State.roadModule1.sharedFuelEconomyOverrides = new Map();
    State.roadModule1.sharedUtilisationOverrides = new Map();
    (draft.overrides || []).forEach(override => {
        if (!override || !override.key || override.year === undefined) return;
        if (!isRoadEditableYear(override.year)) return;
        State.roadModule1.overrides.set(buildRoadModule1OverrideMapKey(override), override);
    });
    (draft.sharedMileageOverrides || []).forEach(override => {
        if (!override || !override.sharedKey || override.year === undefined) return;
        if (!isRoadEditableYear(override.year)) return;
        State.roadModule1.sharedMileageOverrides.set(buildRoadSharedOverrideMapKey(override.sharedKey, override.year), override);
    });
    (draft.sharedFuelEconomyOverrides || []).forEach(override => {
        if (!override || !override.sharedKey || override.year === undefined) return;
        if (!isRoadEditableYear(override.year)) return;
        State.roadModule1.sharedFuelEconomyOverrides.set(buildRoadSharedOverrideMapKey(override.sharedKey, override.year), override);
    });
    (draft.sharedUtilisationOverrides || []).forEach(override => {
        if (!override || !override.sharedKey || override.year === undefined) return;
        if (!isRoadEditableYear(override.year)) return;
        State.roadModule1.sharedUtilisationOverrides.set(buildRoadSharedOverrideMapKey(override.sharedKey, override.year), override);
    });

    State.roadModule1.activeFilter = draft.activeFilter || '';
    const allowedFilterKeys = Object.keys(State.roadModule1.structuredFilters);
    const restoredStructuredFilters = draft.structuredFilters || {};
    allowedFilterKeys.forEach(filterKey => {
        State.roadModule1.structuredFilters[filterKey] = restoredStructuredFilters[filterKey] || '';
    });
    State.roadModule1.sortBy = draft.sortBy || State.roadModule1.sortBy;
    State.roadModule1.sortDirection = draft.sortDirection || State.roadModule1.sortDirection;
    State.roadModule1.viewMode = draft.viewMode || State.roadModule1.viewMode;
    if (State.roadModule1.viewMode === 'graph' || State.roadModule1.viewMode === 'canvas') {
        State.roadModule1.viewMode = 'tree';
    }
    State.roadModule1.dataDensity = ['less', 'more', 'ultra'].includes(draft.dataDensity) ? draft.dataDensity : 'less';
    if (draft.turnoverConfig) {
        State.roadModule1.turnoverConfig = {
            passenger: { lower: '', upper: '', fitMode: 'auto', ...(draft.turnoverConfig.passenger || {}) },
            freight:   { lower: '', upper: '', fitMode: 'auto', ...(draft.turnoverConfig.freight   || {}) }
        };
    }
    State.roadModule1.lastDraftSavedAt = draft.savedAt || null;
    syncRoadModule1ScenarioState(draft.scenario || State.roadModule1.scenario);
    applyRoadModule1FilterControlValues();
}

function applyRoadModule1FilterControlValues() {
    if (DOM.roadFilterInput) DOM.roadFilterInput.value = State.roadModule1.activeFilter;
    const filterBindings = [
        [DOM.roadFilterScenario, 'scenario'],
        [DOM.roadFilterVehicle, 'vehicle'],
        [DOM.roadFilterDrive, 'drive'],
        [DOM.roadFilterMeasure, 'measure']
    ];

    filterBindings.forEach(([element, filterKey]) => {
        if (!element) return;
        const value = State.roadModule1.structuredFilters[filterKey] || '';
        element.value = Array.from(element.options || []).some(option => option.value === value) ? value : '';
        State.roadModule1.structuredFilters[filterKey] = element.value;
    });
    if (DOM.roadSortBy) DOM.roadSortBy.value = State.roadModule1.sortBy;
    if (DOM.roadSortDirection) DOM.roadSortDirection.value = State.roadModule1.sortDirection;
    updateRoadSortDirectionLabels();
    updateRoadDensityToggle();
    updateRoadModule1ViewToggle();
}

function updateRoadDensityToggle() {
    if (DOM.roadDensityLess) DOM.roadDensityLess.classList.toggle('is-active', State.roadModule1.dataDensity === 'less');
    if (DOM.roadDensityMore) DOM.roadDensityMore.classList.toggle('is-active', State.roadModule1.dataDensity === 'more');
    if (DOM.roadDensityUltra) DOM.roadDensityUltra.classList.toggle('is-active', State.roadModule1.dataDensity === 'ultra');
}

function updateRoadModule1ViewToggle() {
    if (DOM.roadListView) DOM.roadListView.classList.toggle('is-active', State.roadModule1.viewMode === 'list');
    if (DOM.roadTreeView) DOM.roadTreeView.classList.toggle('is-active', State.roadModule1.viewMode === 'tree');
}

function getRoadModule1OverrideCount() {
    return State.roadModule1.overrides.size + State.roadModule1.sharedMileageOverrides.size + State.roadModule1.sharedFuelEconomyOverrides.size + State.roadModule1.sharedUtilisationOverrides.size;
}

function getRoadModule1RowStats() {
    const rows = getRoadRowsForCurrentView();
    if (rows.length === 0) return null;
    const groups = groupRoadRowsForEditors(
        rows
            .filter(row => !isRoadVehicleEquivalentBoundsRow(row))
            .filter(row => isRoadRowVisibleAtCurrentDensity(row))
    );
    const total = groups.size;
    const yearSuffix = '||Year=';
    const customisedRowKeys = new Set();
    for (const key of State.roadModule1.overrides.keys()) {
        const cut = key.lastIndexOf(yearSuffix);
        customisedRowKeys.add(cut >= 0 ? key.slice(0, cut) : key);
    }
    for (const key of State.roadModule1.sharedMileageOverrides.keys()) {
        const cut = key.lastIndexOf(yearSuffix);
        customisedRowKeys.add(cut >= 0 ? key.slice(0, cut) : key);
    }
    for (const key of State.roadModule1.sharedFuelEconomyOverrides.keys()) {
        const cut = key.lastIndexOf(yearSuffix);
        customisedRowKeys.add(cut >= 0 ? key.slice(0, cut) : key);
    }
    for (const key of State.roadModule1.sharedUtilisationOverrides.keys()) {
        const cut = key.lastIndexOf(yearSuffix);
        customisedRowKeys.add(cut >= 0 ? key.slice(0, cut) : key);
    }
    return { customised: customisedRowKeys.size, total };
}

function updateRoadModule1OverrideCount() {
    if (!DOM.roadRowStats) return;
    const stats = getRoadModule1RowStats();
    if (!stats) { DOM.roadRowStats.textContent = ''; return; }
    DOM.roadRowStats.textContent = stats.customised === 0
        ? `${stats.total} values`
        : `${stats.customised} of ${stats.total} values customised`;
}

async function loadRoadModule1Defaults() {
    const version = getSelectedRoadModule1Version();
    const economy = DOM.roadEconomySelect?.value;

    if (!economy) {
        showCustomToast("Select an economy first.", "warning");
        return;
    }

    showLoading("Loading Road model Provided Values...");
    try {
        const response = await loadRoadModule1DefaultsFromStaticBundle(version, economy);
        const loadSourceLabel = 'packaged static defaults';

        State.roadModule1.version = version;
        State.roadModule1.economy = economy;
        State.roadModule1.keyColumns = ROAD_MODULE1_REQUIRED_KEY_COLUMNS;
        const splitRows = splitRoadModule1RowsByVisibility(response.rows);
        State.roadModule1.rows = normalizeRoadModule1RowsForUi(splitRows.visibleRows);
        State.roadModule1.hiddenRows = splitRows.hiddenRows;
        syncRoadModule1ScenarioState(ROAD_MODULE1_DEFAULT_PROJECTION_SCENARIO);
        State.roadModule1.overrides = new Map();
        State.roadModule1.sharedMileageOverrides = new Map();
        State.roadModule1.sharedFuelEconomyOverrides = new Map();
        State.roadModule1.sharedUtilisationOverrides = new Map();
        populateRoadModule1StructuredFilters(getRoadRowsForCurrentView());
        const draft = readRoadModule1Draft(version, economy);
        if (draft && ((draft.overrides || []).length > 0 || (draft.sharedMileageOverrides || []).length > 0 || (draft.sharedFuelEconomyOverrides || []).length > 0 || (draft.sharedUtilisationOverrides || []).length > 0 || draft.activeFilter || draft.savedAt)) {
            const savedAtLabel = draft.savedAt ? new Date(draft.savedAt).toLocaleString('en-US') : 'an earlier time';
            const accepted = await showCustomConfirm(
                'Restore Saved Draft',
                `A browser-saved draft exists for this version/economy from ${savedAtLabel}.\n\nRestore it now?`,
                { confirmText: 'Restore Draft', cancelText: 'Ignore' }
            );
            if (accepted) {
                applyRoadModule1Draft(draft);
            } else if (DOM.roadClearDraft) {
                DOM.roadClearDraft.disabled = false;
            }
        } else if (DOM.roadClearDraft) {
            DOM.roadClearDraft.disabled = true;
        }
        DOM.roadSaveOutput.disabled = false;
        if (DOM.roadRunModel) DOM.roadRunModel.disabled = false;
        renderRoadModule1Inputs();
        showCustomToast("Road defaults loaded.", "success");
    } catch (error) {
        showCustomToast("Failed to load road provided values: " + error.message, "error");
    } finally {
        hideLoading();
    }
}

async function handleRoadModule1ProvidedFileSelected(event) {
    const file = event.target.files && event.target.files[0];
    if (!file) return;

    const version = getSelectedRoadModule1Version();
    const economy = DOM.roadEconomySelect?.value;
    if (!economy) {
        showCustomToast("Select an economy first.", "warning");
        event.target.value = '';
        return;
    }

    if (!State.roadModule1.rows || State.roadModule1.rows.length === 0) {
        showCustomToast("Defaults are not loaded yet. Change economy and wait, then upload your filled template.", "warning", 5000);
        event.target.value = '';
        return;
    }

    showLoading("Validating Provided Values File...");
    try {
        const uploadResult = await readRoadModule1RowsFromUploadFile(file);
        const preview = previewRoadModule1UploadedRows(uploadResult.rows);

        pendingRoadModule1Upload = { preview, version, economy, fileName: file.name };
        showRoadUploadSummaryModal(
            'Review Upload Changes',
            buildRoadUploadSummaryText(file.name, uploadResult.summary, preview),
            { confirmMode: true }
        );
    } catch (error) {
        showCustomToast("Upload validation failed: " + error.message, "error");
    } finally {
        event.target.value = '';
        hideLoading();
    }
}

async function loadRoadModule1BuiltinProvidedValues() {
    const version = getSelectedRoadModule1Version();
    const economy = DOM.roadEconomySelect?.value;

    if (!economy) {
        showCustomToast("Select an economy first.", "warning");
        return;
    }

    showLoading("Applying Built-In Provided Values...");
    try {
        const response = await loadRoadModule1DefaultsFromStaticBundle(version, economy);
        State.roadModule1.version = version;
        State.roadModule1.economy = economy;
        State.roadModule1.keyColumns = ROAD_MODULE1_REQUIRED_KEY_COLUMNS;
        const splitRows = splitRoadModule1RowsByVisibility(response.rows);
        State.roadModule1.rows = normalizeRoadModule1RowsForUi(splitRows.visibleRows);
        State.roadModule1.hiddenRows = splitRows.hiddenRows;
        syncRoadModule1ScenarioState(ROAD_MODULE1_DEFAULT_PROJECTION_SCENARIO);
        State.roadModule1.overrides = new Map();
        State.roadModule1.sharedMileageOverrides = new Map();
        State.roadModule1.sharedFuelEconomyOverrides = new Map();
        State.roadModule1.sharedUtilisationOverrides = new Map();
        populateRoadModule1StructuredFilters(getRoadRowsForCurrentView());
        clearRoadModule1Draft(version, economy);
        DOM.roadSaveOutput.disabled = false;
        DOM.roadSaveStatus.innerText = 'Built-in provided values applied.';
        renderRoadModule1Inputs();
        showCustomToast('Built-in provided values applied from packaged static defaults.', 'success', 5000);
    } catch (error) {
        showCustomToast("Failed to apply built-in provided values: " + error.message, "error");
    } finally {
        hideLoading();
    }
}

async function downloadRoadModule1ProvidedValuesTemplate() {
    const version = getSelectedRoadModule1Version();
    const economy = DOM.roadEconomySelect?.value;

    if (!economy) {
        showCustomToast("Select an economy first.", "warning");
        return;
    }

    showLoading("Preparing Input CSV...");
    try {
        const response = await loadRoadModule1DefaultsFromStaticBundle(version, economy);
        const fileName = `road_module1_values_${economy}.csv`;
        exportRoadModule1RowsCsvClientSide(normalizeRoadModule1RowsForUi(response.rows), economy, fileName);
        DOM.roadSaveStatus.innerText = `Input CSV downloaded for ${economy}.`;
        showCustomToast('Input CSV downloaded.', 'success', 5000);
    } catch (error) {
        showCustomToast("Failed to download input CSV: " + error.message, "error");
    } finally {
        hideLoading();
    }
}

function buildRoadModule1Key(row) {
    return State.roadModule1.keyColumns.map(column => `${column}=${row[column] ?? ''}`).join('||');
}

function roadModule1KeyPayload(row) {
    const keyPayload = {};
    State.roadModule1.keyColumns.forEach(column => {
        keyPayload[column] = row[column];
    });
    return keyPayload;
}

function formatRoadDefaultValue(value) {
    const numeric = Number(value);
    if (!Number.isFinite(numeric)) return '';
    if (Math.abs(numeric) >= 1000000) return numeric.toExponential(4);
    if (Math.abs(numeric) > 0 && Math.abs(numeric) < 0.001) return numeric.toExponential(4);
    return numeric.toLocaleString('en-US', { maximumFractionDigits: 6 });
}

function formatRoadEditableInputValue(value) {
    const text = String(value ?? '').trim();
    if (!text) return '';
    const numeric = Number(text.replace(/,/g, ''));
    if (!Number.isFinite(numeric)) return text;
    return String(Number(numeric.toPrecision(15)));
}

function getRoadInputValueWithDefault(override, defaultValue) {
    return override && override.value !== null && override.value !== undefined && String(override.value).trim() !== ''
        ? formatRoadEditableInputValue(override.value)
        : formatRoadEditableInputValue(defaultValue);
}

function roadInputValueDiffersFromDefault(value, defaultValue) {
    const rawText = String(value ?? '').trim();
    const defaultText = String(defaultValue ?? '').trim();
    if (!rawText) return false;
    const rawNumber = Number(rawText.replace(/,/g, ''));
    const defaultNumber = Number(defaultText.replace(/,/g, ''));
    if (Number.isFinite(rawNumber) && Number.isFinite(defaultNumber)) {
        return Math.abs(rawNumber - defaultNumber) > 1e-9;
    }
    return rawText !== defaultText;
}

function formatRoadInputSourceLabel(source) {
    const normalized = String(source || '').trim().toLowerCase();
    if (!normalized || normalized === 'default') return 'provided';
    return source;
}

function formatRoadSeriesInputValue(value) {
    const numeric = Number(value);
    if (!Number.isFinite(numeric)) return '';
    if (Math.abs(numeric) >= 1000000) return numeric.toExponential(6);
    if (Math.abs(numeric) > 0 && Math.abs(numeric) < 0.000001) return numeric.toExponential(6);
    return String(Number(numeric.toFixed(8)));
}

function escapeHtml(value) {
    return String(value ?? '')
        .replace(/&/g, '&amp;')
        .replace(/</g, '&lt;')
        .replace(/>/g, '&gt;')
        .replace(/"/g, '&quot;')
        .replace(/'/g, '&#039;');
}

function formatRoadBranchPath(path) {
    return String(path || '')
        .split('\\')
        .filter(Boolean)
        .map((part, index) => `<span style="padding-left:${index === 0 ? 0 : 0.35}rem">${escapeHtml(part)}</span>`)
        .join('<span class="road-breadcrumb-separator">/</span>');
}

function getRoadBranchDepth(path) {
    return String(path || '').split('\\').filter(Boolean).length;
}

function getRoadAgeFromBranchPath(path) {
    const parts = String(path || '').split('\\').filter(Boolean);
    const lastPart = parts.length ? parts[parts.length - 1] : '';
    const match = lastPart.match(/^Age\s+(\d+)$/i);
    return match ? Number(match[1]) : null;
}

function getRoadParentBranchPath(path) {
    const parts = String(path || '').split('\\').filter(Boolean);
    if (getRoadAgeFromBranchPath(path) === null) return String(path || '');
    return parts.slice(0, -1).join('\\');
}

function getRoadBranchLeafLabel(path) {
    const parts = String(path || '').split('\\').filter(Boolean);
    if (parts.length === 0) return '';
    return parts[parts.length - 1];
}

function isRoadAgeSeriesRow(row) {
    return getRoadAgeFromBranchPath(row['Branch Path']) !== null;
}

function isRoadMileageRow(row) {
    return String(row.Variable || '').trim().toLowerCase() === 'mileage';
}

function isRoadCoreDensityRow(row) {
    const v = String(row.Variable || '').trim().toLowerCase();
    if (isRoadDriveLevelSalesShareRow(row)) return false;
    return v === 'stock' || v === 'stock share' || v === 'sales share' || v === 'fuel economy' || v === 'mileage';
}

function isRoadSalesShareRow(row) {
    return normalizeRoadTextToken(row?.Variable || '') === normalizeRoadTextToken('Sales Share');
}

function isRoadDriveLevelSalesShareRow(row) {
    if (!isRoadSalesShareRow(row)) return false;
    return getRoadPathParts(row).length >= 4;
}

function isRoadProjectedDriveLevelSalesShareRow(row) {
    return isRoadDriveLevelSalesShareRow(row)
        && !isRoadPairedFuelShareRow(row)
        && !isRoadCurrentAccountsRow(row);
}

function isRoadRowVisibleAtCurrentDensity(row) {
    const density = State.roadModule1.dataDensity || 'less';
    if (isRoadCorrectionFactorRow(row)) return density === 'ultra';
    if (density === 'less') return isRoadCoreDensityRow(row);
    if (density === 'more') return !isRoadDriveLevelSalesShareRow(row) || isRoadPairedFuelShareRow(row);
    return true;
}

function getRoadSalesShareVehicleBranchPath(row) {
    const parts = getRoadPathParts(row);
    return parts.slice(0, Math.min(3, parts.length)).join('\\') || row['Branch Path'] || '';
}

function getRoadSalesShareMixGroupKey(row) {
    return [
        getRoadSalesShareVehicleBranchPath(row),
        row.Scenario || '',
        row.Region || ''
    ].join('||');
}

function getRoadSalesShareNormaliseGroupKey(row) {
    return [
        getRoadSalesShareVehicleBranchPath(row),
        row.Scenario || '',
        row.Region || ''
    ].join('||');
}

function getRoadSalesShareScenarioRank(row, year) {
    const scenario = normalizeRoadTextToken(row?.Scenario || '');
    if (Number(year) === ROAD_MODULE1_BASE_YEAR && scenario === normalizeRoadTextToken('Current Accounts')) return 0;
    if (scenario === normalizeRoadTextToken(ROAD_MODULE1_DEFAULT_PROJECTION_SCENARIO)) return 1;
    return 2;
}

function getRoadMileageSharedBranchPath(row) {
    const parts = getRoadPathParts(row);
    const vehicleTypeDepth = parts.length >= 4 && !looksLikeRoadDrive(parts[3]) ? 4 : 3;
    return parts.slice(0, Math.min(vehicleTypeDepth, parts.length)).join('\\') || row['Branch Path'] || '';
}

function getRoadMileageSharedVehicleLabel(row) {
    const parts = getRoadMileageSharedBranchPath(row).split('\\').filter(Boolean);
    return parts.length ? parts[parts.length - 1] : 'vehicle type';
}

function getRoadSharedMileageKey(row) {
    return [
        getRoadMileageSharedBranchPath(row),
        row.Variable || '',
        row.Scenario || '',
        row.Region || '',
        row.Units || ''
    ].join('||');
}

function getRoadSharedMileageDriveKey(row) {
    return [
        getRoadDriveBranchPath(row),
        row.Variable || '',
        row.Scenario || '',
        row.Region || '',
        row.Units || ''
    ].join('||');
}

function isRoadFuelEconomyRow(row) {
    return String(row.Variable || '').trim().toLowerCase() === 'fuel economy';
}

function isRoadCorrectionFactorRow(row) {
    const variable = normalizeRoadTextToken(row?.Variable || '');
    return variable === normalizeRoadTextToken('Mileage Correction Factor')
        || variable === normalizeRoadTextToken('Fuel Economy Correction Factor');
}

function isRoadPhevOrErevDrive(branchPath) {
    const parts = String(branchPath || '').split('\\').filter(Boolean);
    const drive = parts[3] || '';
    return /phev|erev/i.test(drive);
}

function isRoadElectricityFuel(row) {
    const parts = getRoadPathParts(row);
    const fuel = parts[4] || '';
    return /electricity|electric/i.test(fuel);
}

function getRoadDriveBranchPath(row) {
    const parts = getRoadPathParts(row);
    return parts.slice(0, 4).join('\\') || row['Branch Path'] || '';
}

function getRoadSharedFuelEconomySubGroup(row) {
    const drivePath = getRoadDriveBranchPath(row);
    if (!isRoadPhevOrErevDrive(drivePath)) return 'all';
    return isRoadElectricityFuel(row) ? 'electric' : 'other';
}

function getRoadSharedFuelEconomyKey(row) {
    return [
        getRoadDriveBranchPath(row),
        getRoadSharedFuelEconomySubGroup(row),
        row.Variable || '',
        row.Scenario || '',
        row.Region || '',
        row.Units || ''
    ].join('||');
}

function getRoadSharedFuelEconomyOverride(row, year) {
    if (!isRoadFuelEconomyRow(row)) return null;
    return State.roadModule1.sharedFuelEconomyOverrides.get(
        buildRoadSharedOverrideMapKey(getRoadSharedFuelEconomyKey(row), year)
    ) || null;
}

function getRoadDriveLevelLabel(drivePath) {
    const parts = String(drivePath || '').split('\\').filter(Boolean);
    const drive = parts[3] || parts[parts.length - 1] || 'drive';
    return drive;
}

function getRoadTopLevelVehicleBranchPath(row) {
    const parts = getRoadPathParts(row);
    return parts.slice(0, Math.min(3, parts.length)).join('\\') || row['Branch Path'] || '';
}

function getRoadPairedFuelShareBranchPath(row) {
    return getRoadTopLevelVehicleBranchPath(row);
}

function getRoadPairedFuelShareGroupKey(row) {
    return [
        getRoadPairedFuelShareBranchPath(row),
        row.Scenario || '',
        row.Region || ''
    ].join('||');
}

function isRoadGasolineDieselShareRow(row) {
    const variable = normalizeRoadTextToken(row?.Variable || '');
    const drive = normalizeRoadTextToken(row?.drive || '');
    return variable === normalizeRoadTextToken('Sales Share') && ['ice_gasoline', 'ice_diesel'].includes(drive);
}

function isRoadFuelShareToleranceRow(row) {
    return normalizeRoadTextToken(row?.Variable || '') === normalizeRoadTextToken('Gasoline/Diesel Share Tolerance');
}

function isRoadPairedFuelShareRow(row) {
    return isRoadGasolineDieselShareRow(row) || isRoadFuelShareToleranceRow(row);
}

function getRoadPairedFuelShareRole(row) {
    if (isRoadFuelShareToleranceRow(row)) return 'tolerance';
    const drive = normalizeRoadTextToken(row?.drive || '');
    if (drive === 'ice_gasoline') return 'gasoline';
    if (drive === 'ice_diesel') return 'diesel';
    return '';
}

function getRoadPairedFuelShareRowRefs(rows) {
    return rows
        .map(row => ({
            role: getRoadPairedFuelShareRole(row),
            rowKey: buildRoadModule1Key(row),
            year: getRoadBaseYearColumn(row),
            keyPayload: roadModule1KeyPayload(row),
            row: row
        }))
        .filter(ref => ref.role);
}

function isRoadReconciliationControlRow(row) {
    const variable = normalizeRoadTextToken(row?.Variable || '');
    return [
        'reconciliation weight',
        'reconciliation weight stock',
        'reconciliation weight mileage',
        'reconciliation weight efficiency',
        'reconciliation bound lower',
        'reconciliation bound lower stock',
        'reconciliation bound lower mileage',
        'reconciliation bound upper',
        'reconciliation bound upper stock',
        'reconciliation bound upper mileage',
        'reconciliation bound lower efficiency',
        'reconciliation bound upper efficiency',
    ].includes(variable);
}

function getRoadReconciliationControlRole(row) {
    const variable = normalizeRoadTextToken(row?.Variable || '');
    const roleMap = {
        'reconciliation weight': 'weight_shared',
        'reconciliation weight stock': 'weight_stock',
        'reconciliation weight mileage': 'weight_mileage',
        'reconciliation weight efficiency': 'weight_efficiency',
        'reconciliation bound lower': 'bound_lower_shared',
        'reconciliation bound lower stock': 'bound_lower_stock',
        'reconciliation bound lower mileage': 'bound_lower_mileage',
        'reconciliation bound upper': 'bound_upper_shared',
        'reconciliation bound upper stock': 'bound_upper_stock',
        'reconciliation bound upper mileage': 'bound_upper_mileage',
        'reconciliation bound lower efficiency': 'bound_lower_efficiency',
        'reconciliation bound upper efficiency': 'bound_upper_efficiency',
    };
    return roleMap[variable] || '';
}

function getRoadReconciliationBranchPath(row) {
    const parts = getRoadPathParts(row);
    return parts.slice(0, Math.min(2, parts.length)).join('\\') || row['Branch Path'] || '';
}

function getRoadReconciliationGroupKey(row) {
    return [
        getRoadReconciliationBranchPath(row),
        row.Scenario || '',
        row.Region || ''
    ].join('||');
}

function getRoadReconciliationRowRefs(rows) {
    return rows
        .map(row => ({
            role: getRoadReconciliationControlRole(row),
            rowKey: buildRoadModule1Key(row),
            year: getRoadBaseYearColumn(row),
            keyPayload: roadModule1KeyPayload(row),
            row: row
        }))
        .filter(ref => ref.role);
}

function isRoadTurnoverCalibrationControlRow(row) {
    const variable = normalizeRoadTextToken(row?.Variable || '');
    return [
        normalizeRoadTextToken('Turnover Rate Bound Lower'),
        normalizeRoadTextToken('Turnover Rate Bound Upper')
    ].includes(variable);
}

function getRoadTurnoverCalibrationRole(row) {
    const variable = normalizeRoadTextToken(row?.Variable || '');
    if (variable === normalizeRoadTextToken('Turnover Rate Bound Lower')) return 'lower';
    if (variable === normalizeRoadTextToken('Turnover Rate Bound Upper')) return 'upper';
    return '';
}

function getRoadTurnoverCalibrationBranchPath(row) {
    const parts = getRoadPathParts(row);
    return parts.slice(0, Math.min(3, parts.length)).join('\\') || row['Branch Path'] || '';
}

function getRoadTurnoverCalibrationGroupKey(row) {
    return [
        getRoadTurnoverCalibrationBranchPath(row),
        row.Scenario || '',
        row.Region || ''
    ].join('||');
}

function getRoadTurnoverCalibrationRowRefs(rows) {
    return rows
        .map(row => ({
            role: getRoadTurnoverCalibrationRole(row),
            rowKey: buildRoadModule1Key(row),
            year: getRoadBaseYearColumn(row),
            keyPayload: roadModule1KeyPayload(row),
            row: row
        }))
        .filter(ref => ref.role);
}

function buildRoadInfoTooltip(text) {
    return `<button type="button" class="road-info-tip" data-tip="${escapeHtml(text)}" aria-label="More information" tabindex="0">?</button>`;
}

function getRoadCellScenarioLabel(row, year) {
    if (!row) return '';
    const numericYear = Number(year);
    if (
        normalizeRoadTextToken(row.Variable || '') === normalizeRoadTextToken('Stock Share')
        && Number.isFinite(numericYear)
        && numericYear === ROAD_MODULE1_BASE_YEAR
    ) {
        return '';
    }
    if (Number.isFinite(numericYear) && numericYear <= ROAD_MODULE1_BASE_YEAR) {
        return ROAD_MODULE1_CURRENT_ACCOUNTS;
    }
    return normaliseRoadScenarioLabel(row.Scenario) || ROAD_MODULE1_CURRENT_ACCOUNTS;
}

function buildRoadCellLabelHtml(label, helpText, scenarioLabel = '') {
    return `<label>${escapeHtml(label)} ${buildRoadInfoTooltip(helpText)}</label>`;
}

function isRoadTransportParamRow(row) {
    const variable = normalizeRoadTextToken(row?.Variable || '');
    return [
        normalizeRoadTextToken('Vehicle Equivalent Weight'),
        normalizeRoadTextToken('Passenger Vehicle Saturation'),
        normalizeRoadTextToken('Passenger Saturation Reached'),
        normalizeRoadTextToken('Passenger Stock Growth Rate Adjustment'),
        normalizeRoadTextToken('Freight GDP Elasticity Adjustment')
    ].includes(variable);
}

function getRoadTransportParamRole(row) {
    const variable = normalizeRoadTextToken(row?.Variable || '');
    if (variable === normalizeRoadTextToken('Vehicle Equivalent Weight')) return 'vew';
    if (variable === normalizeRoadTextToken('Passenger Vehicle Saturation')) return 'pvs';
    if (variable === normalizeRoadTextToken('Passenger Saturation Reached')) return 'pvs_reached';
    if (variable === normalizeRoadTextToken('Passenger Stock Growth Rate Adjustment')) return 'passenger_growth_adjustment';
    if (variable === normalizeRoadTextToken('Freight GDP Elasticity Adjustment')) return 'freight_elasticity_adjustment';
    return '';
}

function isRoadTransportParamRoleEnabled(role) {
    if (role === 'pvs' || role === 'pvs_reached' || role === 'passenger_growth_adjustment') {
        return ROAD_MODULE1_TRANSPORT_PARAM_GROUPS_ENABLED.ownership;
    }
    if (role === 'vew') {
        return ROAD_MODULE1_TRANSPORT_PARAM_GROUPS_ENABLED.fleetWeighting;
    }
    if (role === 'freight_elasticity_adjustment') {
        return ROAD_MODULE1_TRANSPORT_PARAM_GROUPS_ENABLED.freightProjection;
    }
    return false;
}

function getRoadTransportParamGroupTitle(group) {
    const roles = new Set((group?.rows || []).map(getRoadTransportParamRole).filter(Boolean));
    const hasOwnership = roles.has('pvs') || roles.has('pvs_reached') || roles.has('passenger_growth_adjustment');
    const hasFleetWeighting = roles.has('vew');
    const hasFreightProjection = roles.has('freight_elasticity_adjustment');
    if (hasFreightProjection && !hasOwnership && !hasFleetWeighting) return 'Freight projection assumptions';
    if (hasFreightProjection) return 'Projection assumptions';
    if (hasOwnership && hasFleetWeighting) return 'Fleet assumptions';
    if (hasOwnership) return 'Ownership assumptions';
    if (hasFleetWeighting) return 'Fleet weighting';
    return 'Model assumptions';
}

function getRoadTransportParamBranchPath(row) {
    const parts = getRoadPathParts(row);
    return parts.slice(0, Math.min(2, parts.length)).join('\\') || row['Branch Path'] || '';
}

function getRoadTransportParamGroupKey(row) {
    return [
        getRoadTransportParamBranchPath(row),
        row.Scenario || '',
        row.Region || ''
    ].join('||');
}

function getRoadVehicleWeightLabel(row) {
    const parts = getRoadPathParts(row);
    return parts[parts.length - 1] || 'Vehicle';
}

function getRoadFleetWeightCanonicalClass(row) {
    const branchPath = String(row?.['Branch Path'] || '');
    const normalized = normalizeRoadTextToken(branchPath);

    if (normalized.includes('demand\\passenger road')) {
        if (normalized.includes('\\buses')) return 'Buses';
        if (normalized.includes('\\motorcycles')) return 'Motorcycles';
        if (
            normalized.includes('\\lpvs')
            || normalized.includes('\\passenger cars')
            || normalized.includes('\\suv and light trucks')
        ) {
            return 'LPVs';
        }
    }

    return getRoadVehicleWeightLabel(row);
}

function isRoadVehicleEquivalentBoundsRow(row) {
    const variable = normalizeRoadTextToken(row?.Variable || '');
    return [
        normalizeRoadTextToken('Vehicle Equivalent Weight Lower Bound'),
        normalizeRoadTextToken('Vehicle Equivalent Weight Upper Bound')
    ].includes(variable);
}

function isRoadTransportLevelSharedRow(row) {
    const variable = normalizeRoadTextToken(row?.Variable || '');
    return variable === normalizeRoadTextToken('PHEV Electric Driving Share');
}

function getRoadTransportSharedBranchPath(row) {
    const parts = getRoadPathParts(row);
    return parts.slice(0, Math.min(2, parts.length)).join('\\') || row['Branch Path'] || '';
}

function getRoadSharedMileageOverride(row, year) {
    if (!isRoadMileageRow(row)) return null;
    return State.roadModule1.sharedMileageOverrides.get(
        buildRoadSharedOverrideMapKey(getRoadSharedMileageKey(row), year)
    ) || null;
}

function getRoadSharedUtilisationKey(row) {
    return [
        getRoadTransportSharedBranchPath(row),
        row.Variable || '',
        row.Scenario || '',
        row.Region || '',
        row.Units || ''
    ].join('||');
}

function getRoadSharedUtilisationOverride(row, year) {
    if (!isRoadTransportLevelSharedRow(row)) return null;
    return State.roadModule1.sharedUtilisationOverrides.get(
        buildRoadSharedOverrideMapKey(getRoadSharedUtilisationKey(row), year)
    ) || null;
}

function getRoadSharedUtilisationComment(sharedKey, years) {
    for (const year of years) {
        const override = State.roadModule1.sharedUtilisationOverrides.get(buildRoadSharedOverrideMapKey(sharedKey, year));
        if (override && override.comment) return override.comment;
    }
    return '';
}

function getRoadInheritedMileageValue(row, year) {
    const sharedOverride = getRoadSharedMileageOverride(row, year);
    return sharedOverride && sharedOverride.value !== null && sharedOverride.value !== ''
        ? sharedOverride.value
        : '';
}

function getRoadDisplayedPlaceholderValue(row, year) {
    const inheritedMileageValue = getRoadInheritedMileageValue(row, year);
    return inheritedMileageValue !== '' ? inheritedMileageValue : getRoadDefaultValue(row, year);
}

function normalizeRoadFilterValue(value) {
    return String(value ?? '').trim();
}

function getRoadPathParts(row) {
    return String(row['Branch Path'] || '').split('\\').filter(Boolean);
}

function looksLikeRoadDrive(value) {
    const normalized = normalizeRoadFilterValue(value).toLowerCase();
    if (!normalized) return false;
    return ['bev', 'erev', 'fcev', 'hev', 'ice', 'phev'].some(token => normalized.includes(token));
}

const ROAD_FLAGGED_VARIABLES = new Set(['Stock', 'Stock Share', 'Sales Share']);

function isRoadRowFlagged(row) {
    if (!ROAD_FLAGGED_VARIABLES.has(row.Variable)) return false;
    const stockMap = State.roadModule1.stockMap;
    if (!stockMap) return false;
    const parts = String(row['Branch Path'] || '').split('\\').filter(Boolean);
    const lookupPath = row.Variable === 'Stock'
        ? row['Branch Path']
        : parts.slice(0, -1).join('\\');
    return (stockMap.get(lookupPath) ?? 0) > 0;
}

function getRoadRowFilterMeta(row) {
    const parts = getRoadPathParts(row);
    const transport = parts[1] || '';
    // Age-series rows are intentionally stored at transport scope, e.g.
    //   Demand\Passenger road\Age 0
    //   Demand\Freight road\Age 0
    // Do not classify "Age X" as a vehicle category in filters/dropdowns.
    const isAgeSeries = isRoadAgeSeriesRow(row);
    const vehicle = isAgeSeries ? '' : (parts[2] || '');
    const detail = parts[3] || '';
    const leafFuel = parts[4] || '';
    const drive = !isAgeSeries && looksLikeRoadDrive(detail) ? detail : '';
    const fuel = !isAgeSeries ? (leafFuel || (!looksLikeRoadDrive(detail) ? detail : '')) : '';

    return {
        scenario: row.Scenario || '',
        branch: row['Branch Path'] || '',
        transport: transport,
        vehicle: vehicle,
        drive: drive,
        fuel: fuel,
        measure: row.Variable || '',
        source: row.input_source || '',
        review: isRoadRowFlagged(row) ? 'needs-review' : 'not-needed',
        units: row.Units || '',
        isAgeSeries: isAgeSeries ? 'age-series' : 'single-row'
    };
}

function addRoadSelectOptions(selectEl, values, allLabel = 'All') {
    if (!selectEl) return;
    const previousValue = selectEl.value;
    selectEl.innerHTML = '';
    selectEl.add(new Option(allLabel, ''));
    values.forEach(value => {
        selectEl.add(new Option(value, value));
    });
    selectEl.value = values.includes(previousValue) ? previousValue : '';
}

function getUniqueRoadFilterValues(rows, metaKey) {
    return [...new Set(rows
        .map(row => normalizeRoadFilterValue(getRoadRowFilterMeta(row)[metaKey]))
        .filter(Boolean))]
        .sort((a, b) => a.localeCompare(b, 'en-US', { numeric: true }));
}

function populateRoadModule1StructuredFilters(rows) {
    addRoadSelectOptions(DOM.roadFilterScenario, getUniqueRoadFilterValues(rows, 'scenario'), 'All scenarios');
    addRoadSelectOptions(DOM.roadFilterVehicle, getUniqueRoadFilterValues(rows, 'vehicle'));
    addRoadSelectOptions(DOM.roadFilterDrive, getUniqueRoadFilterValues(rows, 'drive'));
    addRoadSelectOptions(DOM.roadFilterMeasure, getUniqueRoadFilterValues(rows, 'measure'));

    Object.keys(State.roadModule1.structuredFilters).forEach(key => {
        State.roadModule1.structuredFilters[key] = '';
    });
    if (DOM.roadSortBy) DOM.roadSortBy.value = State.roadModule1.sortBy;
    if (DOM.roadSortDirection) DOM.roadSortDirection.value = State.roadModule1.sortDirection;
    updateRoadSortDirectionLabels();
    if (DOM.roadFilterInput) DOM.roadFilterInput.value = '';
}

function roadRowMatchesStructuredFilters(row) {
    const meta = getRoadRowFilterMeta(row);
    const filters = State.roadModule1.structuredFilters;
    return Object.entries(filters).every(([filterKey, filterValue]) => {
        if (!filterValue) return true;
        return normalizeRoadFilterValue(meta[filterKey]) === filterValue;
    });
}

function getRoadSortValue(row) {
    const meta = getRoadRowFilterMeta(row);
    if (State.roadModule1.sortBy === 'branch') return meta.branch;
    if (State.roadModule1.sortBy === 'measure') return meta.measure;
    if (State.roadModule1.sortBy === 'review') return meta.review;
    return meta[State.roadModule1.sortBy] || '';
}

function buildRoadStockMap(rows) {
    const map = new Map();
    const baseYear = String(ROAD_MODULE1_BASE_YEAR);
    (rows || []).forEach(row => {
        if (row.Variable === 'Stock') {
            const val = parseFloat(row[baseYear]);
            if (!isNaN(val)) map.set(row['Branch Path'], val);
        }
    });
    return map;
}

function buildRoadEnergyMap(rows) {
    const baseYear = String(ROAD_MODULE1_BASE_YEAR);

    const stockShareMap = new Map();
    const mileageMap = new Map();
    const fuelEconomyMap = new Map();

    rows.forEach(row => {
        const path = row['Branch Path'];
        if (!path) return;
        const val = parseFloat(row[baseYear]);
        if (isNaN(val)) return;
        if (row.Variable === 'Stock Share') stockShareMap.set(path, val);
        else if (row.Variable === 'Mileage') mileageMap.set(path, val);
        else if (row.Variable === 'Fuel Economy') fuelEconomyMap.set(path, val);
    });

    const stockMap = buildRoadStockMap(rows);
    const energyMap = new Map();
    const allPaths = [...new Set(rows.map(row => row['Branch Path']).filter(Boolean))];

    allPaths.forEach(path => {
        const parts = path.split('\\').filter(Boolean);
        if (parts.length !== 5) return;

        const vehiclePath = parts.slice(0, 3).join('\\');
        const drivePath = parts.slice(0, 4).join('\\');

        const vehicleStock = stockMap.get(vehiclePath);
        if (vehicleStock === undefined || vehicleStock <= 0) return;

        const stockShare = stockShareMap.get(drivePath);
        if (stockShare === undefined) return;

        const mileage = mileageMap.get(path) ?? mileageMap.get(drivePath);
        if (!mileage) return;

        const fuelEconomy = fuelEconomyMap.get(path) ?? fuelEconomyMap.get(drivePath);
        if (!fuelEconomy) return;

        const leafEnergy = vehicleStock * (stockShare / 100) * mileage * fuelEconomy;

        energyMap.set(path, (energyMap.get(path) || 0) + leafEnergy);
        for (let depth = 4; depth >= 1; depth--) {
            const ancestorPath = parts.slice(0, depth).join('\\');
            energyMap.set(ancestorPath, (energyMap.get(ancestorPath) || 0) + leafEnergy);
        }
    });

    return energyMap;
}

function formatRoadEnergy(rawEnergy) {
    // raw units: Millions veh × fraction × 1000 km/yr × MJ/100km → ×1e7 MJ/yr → ÷1e9 = PJ/yr → ×1e-2
    const pj = rawEnergy * 1e-2;
    if (pj >= 10) return `${pj.toFixed(0)} PJ`;
    if (pj >= 1) return `${pj.toFixed(1)} PJ`;
    if (pj >= 0.1) return `${(pj * 1000).toFixed(0)} TJ`;
    if (pj >= 0.001) return `${(pj * 1000).toFixed(1)} TJ`;
    return `<1 TJ`;
}

function updateRoadSortDirectionLabels() {
    if (!DOM.roadSortDirection) return;
    const isRanked = State.roadModule1.sortBy === 'energy-rank';
    const opts = DOM.roadSortDirection.options;
    if (opts[0]) opts[0].text = isRanked ? 'Least first' : 'A–Z';
    if (opts[1]) opts[1].text = isRanked ? 'Most first' : 'Z–A';
}

function sortRoadRows(rows) {
    const directionMultiplier = State.roadModule1.sortDirection === 'desc' ? -1 : 1;

    if (State.roadModule1.sortBy === 'energy-rank') {
        const energyMap = State.roadModule1.energyMap || new Map();
        return [...rows].sort((a, b) => {
            const aParts = String(a['Branch Path'] || '').split('\\').filter(Boolean);
            const bParts = String(b['Branch Path'] || '').split('\\').filter(Boolean);
            for (let depth = 2; depth <= 4; depth++) {
                const aEnergy = energyMap.get(aParts.slice(0, depth).join('\\')) ?? 0;
                const bEnergy = energyMap.get(bParts.slice(0, depth).join('\\')) ?? 0;
                const cmp = (aEnergy - bEnergy) * directionMultiplier;
                if (cmp !== 0) return cmp;
            }
            return String(a['Branch Path'] || '').localeCompare(String(b['Branch Path'] || ''), 'en-US', { numeric: true })
                || String(a.Variable || '').localeCompare(String(b.Variable || ''), 'en-US', { numeric: true });
        });
    }

    return [...rows].sort((a, b) => {
        const depthCompare = getRoadBranchDepth(a['Branch Path']) - getRoadBranchDepth(b['Branch Path']);
        if (depthCompare !== 0) return depthCompare;

        const primary = String(getRoadSortValue(a)).localeCompare(String(getRoadSortValue(b)), 'en-US', { numeric: true });
        if (primary !== 0) return primary * directionMultiplier;
        return String(a['Branch Path'] || '').localeCompare(String(b['Branch Path'] || ''), 'en-US', { numeric: true })
            || String(a.Variable || '').localeCompare(String(b.Variable || ''), 'en-US', { numeric: true });
    });
}

function getRoadBaseYearColumn(row) {
    const yearColumns = Object.keys(row)
        .filter(column => /^\d{4}$/.test(column))
        .sort();
    const eligibleYearColumns = yearColumns.filter(isRoadEditableYear);
    const baseYear = eligibleYearColumns.find(year => Number(year) === ROAD_MODULE1_BASE_YEAR);
    if (baseYear) return baseYear;

    const populatedYear = eligibleYearColumns.find(year => {
        const value = row[year];
        return value !== null && value !== undefined && String(value).trim() !== '';
    });
    if (populatedYear) return populatedYear;
    if (eligibleYearColumns.length > 0) return eligibleYearColumns[0];
    if (row.Year !== undefined && isRoadEditableYear(row.Year)) return String(row.Year);
    return '';
}

function getRoadRowTitle(row) {
    if (row['Key Detail']) return row['Key Detail'];

    const keyParts = [
        row.transport_type,
        row.vehicle_type,
        row.drive,
        row.fuel,
        row.parameter_detail
    ].filter(value => value !== undefined && value !== null && value !== '');

    if (keyParts.length > 0) return keyParts.join(' | ');
    const branchLeaf = getRoadBranchLeafLabel(row['Branch Path']);
    if (branchLeaf) return branchLeaf;
    if (row.Scenario || row.Region) {
        return [row.Scenario, row.Region].filter(Boolean).join(' | ');
    }
    return row.Variable || row.parameter || 'Input row';
}

function getRoadRowMeta(row, yearLabels) {
    const normalizedYears = (yearLabels || []).filter(Boolean);
    const showYears = normalizedYears.length > 1;
    const metaParts = [
        showYears ? normalizedYears.join(', ') : '',
        row.Units
    ].filter(value => value !== undefined && value !== null && value !== '');

    return metaParts.join(' | ');
}

function getRoadYearColumns(row) {
    const wideYearColumns = Object.keys(row)
        .filter(column => /^\d{4}$/.test(column) && isRoadEditableYear(column))
        .sort();
    if (wideYearColumns.length > 0) {
        if (isRoadCorrectionFactorRow(row)) {
            return wideYearColumns.filter(column => Number(column) > ROAD_MODULE1_BASE_YEAR);
        }
        if (isRoadVehicleTypeStockShareRow(row)) return wideYearColumns;
        const populatedColumns = wideYearColumns.filter(column => {
            const value = row[column];
            return value !== null && value !== undefined && String(value).trim() !== '';
        });
        return populatedColumns.length > 0 ? populatedColumns : [wideYearColumns[0]];
    }
    if (row.Year !== undefined && row.Value !== undefined && isRoadEditableYear(row.Year)) return [String(row.Year)];
    return [];
}

function isRoadEditableYear(year) {
    const parsedYear = Number(String(year).trim());
    return Number.isInteger(parsedYear) && parsedYear >= ROAD_MODULE1_BASE_YEAR && parsedYear <= 2060;
}

function getRoadDefaultValue(row, year) {
    if (Object.prototype.hasOwnProperty.call(row, year)) return row[year];
    if (String(row.Year) === String(year)) return row.Value;
    return '';
}

function getRoadCommentForKeys(rowKeys, years) {
    for (const rowKey of rowKeys) {
        for (const year of years) {
            const override = State.roadModule1.overrides.get(`${rowKey}||Year=${year}`);
            if (override && override.comment) return override.comment;
        }
    }
    return '';
}

function getRoadSharedMileageComment(sharedKey, years) {
    for (const year of years) {
        const override = State.roadModule1.sharedMileageOverrides.get(buildRoadSharedOverrideMapKey(sharedKey, year));
        if (override && override.comment) return override.comment;
    }
    return '';
}

function buildRoadSeriesSvg(defaultPoints, providedPoints) {
    const width = 230;
    const height = 82;
    const padding = 10;
    const numericDefaultPoints = defaultPoints
        .filter(point => point.value !== null && point.value !== undefined && String(point.value).trim() !== '' && Number.isFinite(Number(point.value)));
    const numericProvidedPoints = providedPoints
        .filter(point => point.value !== null && point.value !== undefined && String(point.value).trim() !== '' && Number.isFinite(Number(point.value)));
    const allPoints = [...numericDefaultPoints, ...numericProvidedPoints];
    const allValues = allPoints
        .map(point => Number(point.value))
        .filter(value => Number.isFinite(value));

    if (allValues.length === 0) {
        return '<div class="road-series-chart-empty">No numeric values</div>';
    }

    const minValue = Math.min(...allValues);
    const maxValue = Math.max(...allValues);
    const valueRange = maxValue - minValue || 1;
    const maxAge = Math.max(...allPoints.map(point => point.age));
    const minAge = Math.min(...allPoints.map(point => point.age));
    const ageRange = maxAge - minAge || 1;

    const toXY = (point) => {
        const x = padding + ((point.age - minAge) / ageRange) * (width - padding * 2);
        const y = height - padding - ((Number(point.value) - minValue) / valueRange) * (height - padding * 2);
        return `${x.toFixed(1)},${y.toFixed(1)}`;
    };

    const defaultLine = numericDefaultPoints.length > 1
        ? `<polyline class="road-series-default-line" points="${numericDefaultPoints.map(toXY).join(' ')}"></polyline>`
        : '';
    const providedLine = numericProvidedPoints.length > 1
        ? `<polyline class="road-series-provided-line" points="${numericProvidedPoints.map(toXY).join(' ')}"></polyline>`
        : '';
    const providedDots = numericProvidedPoints
        .map(point => {
            const [x, y] = toXY(point).split(',');
            return `<circle class="road-series-provided-dot" cx="${x}" cy="${y}" r="2.6"></circle>`;
        })
        .join('');

    return `
        <svg class="road-series-chart" viewBox="0 0 ${width} ${height}" role="img" aria-label="Loaded and entered series chart">
            <line class="road-series-axis" x1="${padding}" y1="${height - padding}" x2="${width - padding}" y2="${height - padding}"></line>
            ${defaultLine}
            ${providedLine}
            ${providedDots}
        </svg>
    `;
}

function parseRoadSeriesValues(rawText) {
    return String(rawText || '')
        .trim()
        .split(/[,\t\r\n ;]+/)
        .map(value => value.trim())
        .filter(Boolean)
        .filter(value => Number.isFinite(Number(value)));
}

function parseRoadSalesShareSeriesValues(rawText) {
    return String(rawText || '')
        .trim()
        .split(/[,\t\r\n ;]+/)
        .map(value => value.trim())
        .filter(Boolean)
        .filter(value => Number.isFinite(Number(value)) || isRoadRemainderToken(value));
}

function isRoadRemainderToken(value) {
    return /^REMAINDER\s*\(\s*100\s*\)$/i.test(String(value || '').trim());
}

function getRoadSeriesRowRefs(seriesEl) {
    return JSON.parse(decodeURIComponent(seriesEl.dataset.rowRefs || '%5B%5D'));
}

function getRoadSeriesProvidedPoints(seriesEl) {
    const rowRefs = getRoadSeriesRowRefs(seriesEl);
    const values = parseRoadSeriesValues(seriesEl.querySelector('.road-series-input')?.value || '');
    return values.slice(0, rowRefs.length).map((value, index) => ({
        age: rowRefs[index].age,
        value: value
    }));
}

function updateRoadSeriesChart(seriesEl) {
    const defaultPoints = JSON.parse(decodeURIComponent(seriesEl.dataset.defaultPoints));
    const chartEl = seriesEl.querySelector('.road-series-chart-wrap');
    if (!chartEl) return;
    chartEl.innerHTML = buildRoadSeriesSvg(defaultPoints, getRoadSeriesProvidedPoints(seriesEl));
}

function getRoadSalesShareSeriesProvidedPoints(seriesEl) {
    const yearRefs = JSON.parse(decodeURIComponent(seriesEl.dataset.yearRefs || '%5B%5D'));
    const values = parseRoadSalesShareSeriesValues(seriesEl.querySelector('.road-sales-share-series-input')?.value || '');
    return values.slice(0, yearRefs.length)
        .filter(value => Number.isFinite(Number(value)))
        .map((value, index) => ({
            age: Number(yearRefs[index]?.year),
            value: value
        }));
}

function updateRoadSalesShareSeriesCharts(rowEl) {
    const seriesEls = [...rowEl.querySelectorAll('.road-sales-share-series')];
    const chartEls = [...rowEl.querySelectorAll('.road-paired-series-row .road-series-chart-wrap')];
    seriesEls.forEach((seriesEl, index) => {
        const defaultPoints = JSON.parse(decodeURIComponent(seriesEl.dataset.defaultPoints || '%5B%5D'));
        const chartEl = chartEls[index];
        if (!chartEl) return;
        chartEl.innerHTML = buildRoadSeriesSvg(defaultPoints, getRoadSalesShareSeriesProvidedPoints(seriesEl));
    });
}

function bindRoadModule1InputEvents() {
    DOM.roadInputContainer.querySelectorAll('.road-value-input, .road-series-input, .road-comment-input').forEach(input => {
        input.addEventListener('input', handleRoadModule1InputChange);
    });
    DOM.roadInputContainer.querySelectorAll('.road-turnover-fitmode-select').forEach(sel => {
        sel.addEventListener('change', handleRoadModule1InputChange);
    });
    DOM.roadInputContainer.querySelectorAll('.road-reset-button').forEach(button => {
        button.addEventListener('click', handleRoadModule1ResetClick);
    });
    DOM.roadInputContainer.querySelectorAll('.road-boolean-btn').forEach(btn => {
        btn.addEventListener('click', e => {
            const toggle = e.currentTarget.closest('.road-boolean-toggle');
            if (!toggle) return;
            toggle.querySelectorAll('.road-boolean-btn').forEach(b => b.classList.remove('is-active'));
            e.currentTarget.classList.add('is-active');
            const rowEl = e.currentTarget.closest('.road-input-row');
            if (rowEl) handleRoadModule1TransportParamsInputChange(rowEl);
        });
    });
}

function groupRoadRowsForEditors(filteredRows) {
    const groupedRows = new Map();

    filteredRows
        .filter(isRoadTransportLevelSharedRow)
        .forEach(row => {
            const branchPath = getRoadTransportSharedBranchPath(row);
            const sharedKey = getRoadSharedUtilisationKey(row);
            const groupKey = `shared-utilisation|${sharedKey}`;
            if (!groupedRows.has(groupKey)) {
                groupedRows.set(groupKey, {
                    groupType: 'shared-utilisation',
                    branchPath: branchPath,
                    sharedKey: sharedKey,
                    rows: []
                });
            }
            groupedRows.get(groupKey).rows.push(row);
        });

    filteredRows
        .filter(isRoadProjectedDriveLevelSalesShareRow)
        .forEach(row => {
            const branchPath = getRoadSalesShareVehicleBranchPath(row);
            const groupKey = `sales-share-mix|${getRoadSalesShareMixGroupKey(row)}`;
            if (!groupedRows.has(groupKey)) {
                groupedRows.set(groupKey, {
                    groupType: 'sales-share-mix',
                    branchPath: branchPath,
                    sharedKey: '',
                    rows: []
                });
            }
            groupedRows.get(groupKey).rows.push(row);
        });

    filteredRows
        .filter(isRoadCorrectionFactorRow)
        .forEach(row => {
            const branchPath = row['Branch Path'] || '';
            const groupKey = [
                'time-series',
                branchPath,
                row.Variable || '',
                row.Scenario || '',
                row.Region || ''
            ].join('|');
            if (!groupedRows.has(groupKey)) {
                groupedRows.set(groupKey, {
                    groupType: 'time-series',
                    branchPath: branchPath,
                    sharedKey: '',
                    rows: []
                });
            }
            groupedRows.get(groupKey).rows.push(row);
        });

    filteredRows
        .filter(row => isRoadSalesShareRow(row) && !isRoadDriveLevelSalesShareRow(row))
        .forEach(row => {
            const branchPath = row['Branch Path'] || '';
            const groupKey = [
                'time-series',
                branchPath,
                row.Variable || '',
                row.Scenario || '',
                row.Region || ''
            ].join('|');
            if (!groupedRows.has(groupKey)) {
                groupedRows.set(groupKey, {
                    groupType: 'time-series',
                    branchPath: branchPath,
                    sharedKey: '',
                    rows: []
                });
            }
            groupedRows.get(groupKey).rows.push(row);
        });

    filteredRows
        .filter(isRoadPairedFuelShareRow)
        .forEach(row => {
            const branchPath = getRoadPairedFuelShareBranchPath(row);
            const groupKey = `paired-fuel-share|${getRoadPairedFuelShareGroupKey(row)}`;
            if (!groupedRows.has(groupKey)) {
                groupedRows.set(groupKey, {
                    groupType: 'paired-fuel-share',
                    branchPath: branchPath,
                    sharedKey: '',
                    rows: []
                });
            }
            groupedRows.get(groupKey).rows.push(row);
        });

    filteredRows
        .filter(isRoadReconciliationControlRow)
        .forEach(row => {
            const branchPath = getRoadReconciliationBranchPath(row);
            const groupKey = `reconciliation-controls|${getRoadReconciliationGroupKey(row)}`;
            if (!groupedRows.has(groupKey)) {
                groupedRows.set(groupKey, {
                    groupType: 'reconciliation-controls',
                    branchPath: branchPath,
                    sharedKey: '',
                    rows: []
                });
            }
            groupedRows.get(groupKey).rows.push(row);
        });

    filteredRows
        .filter(isRoadTurnoverCalibrationControlRow)
        .forEach(row => {
            const branchPath = getRoadTurnoverCalibrationBranchPath(row);
            const groupKey = `turnover-calibration|${getRoadTurnoverCalibrationGroupKey(row)}`;
            if (!groupedRows.has(groupKey)) {
                groupedRows.set(groupKey, {
                    groupType: 'turnover-calibration',
                    branchPath: branchPath,
                    sharedKey: '',
                    rows: []
                });
            }
            groupedRows.get(groupKey).rows.push(row);
        });

    filteredRows
        .filter(isRoadTransportParamRow)
        .filter(row => isRoadTransportParamRoleEnabled(getRoadTransportParamRole(row)))
        .forEach(row => {
            const branchPath = getRoadTransportParamBranchPath(row);
            const groupKey = `transport-params|${getRoadTransportParamGroupKey(row)}`;
            if (!groupedRows.has(groupKey)) {
                groupedRows.set(groupKey, {
                    groupType: 'transport-params',
                    branchPath: branchPath,
                    sharedKey: '',
                    rows: []
                });
            }
            groupedRows.get(groupKey).rows.push(row);
        });

    filteredRows
        .filter(row => !(isRoadSalesShareRow(row) && !isRoadDriveLevelSalesShareRow(row)) && !isRoadProjectedDriveLevelSalesShareRow(row) && !isRoadCorrectionFactorRow(row) && !isRoadTransportLevelSharedRow(row) && !isRoadPairedFuelShareRow(row) && !isRoadReconciliationControlRow(row) && !isRoadTurnoverCalibrationControlRow(row) && !isRoadTransportParamRow(row))
        .forEach(row => {
            const detailed = State.roadModule1.dataDensity !== 'less';
            const useSharedMileage = isRoadMileageRow(row) && !detailed;
            const useDetailedMileage = isRoadMileageRow(row) && detailed;
            const useSharedFuelEconomy = isRoadFuelEconomyRow(row) && !detailed;
            const branchPath = useSharedMileage
                ? getRoadMileageSharedBranchPath(row)
                : useDetailedMileage
                    ? getRoadDriveBranchPath(row)
                    : useSharedFuelEconomy
                        ? getRoadDriveBranchPath(row)
                        : (isRoadAgeSeriesRow(row) ? getRoadParentBranchPath(row['Branch Path']) : row['Branch Path']);
            const groupType = (useSharedMileage || useDetailedMileage) ? 'shared-mileage'
                : useSharedFuelEconomy ? 'shared-fuel-economy'
                : (isRoadAgeSeriesRow(row) ? 'age-series' : 'rows');
            const sharedKey = useSharedMileage ? getRoadSharedMileageKey(row)
                : useDetailedMileage ? getRoadSharedMileageDriveKey(row)
                : useSharedFuelEconomy ? getRoadSharedFuelEconomyKey(row)
                : '';
            const groupKey = (useSharedMileage || useDetailedMileage || useSharedFuelEconomy)
                ? `${groupType}|${sharedKey}`
                : `${groupType}|${branchPath}|${row.Variable}|${row.Scenario || ''}|${row.Region || ''}`;
            if (!groupedRows.has(groupKey)) {
                groupedRows.set(groupKey, {
                    groupType: groupType,
                    branchPath: branchPath,
                    sharedKey: sharedKey,
                    rows: []
                });
            }
            groupedRows.get(groupKey).rows.push(row);
        });
    return groupedRows;
}

function buildRoadTreeNode() {
    return {
        children: new Map(),
        groups: []
    };
}

function buildRoadModule1TreeGroups(groupedRows) {
    const root = buildRoadTreeNode();
    groupedRows.forEach(group => {
        const pathParts = String(group.branchPath || '').split('\\').filter(Boolean);
        let node = root;
        pathParts.forEach(part => {
            if (!node.children.has(part)) node.children.set(part, buildRoadTreeNode());
            node = node.children.get(part);
        });
        node.groups.push(group);
    });
    return root;
}

function renderRoadModule1TreeNode(node, depth = 0, label = '') {
    const childEntries = [...node.children.entries()]
        .sort((a, b) => a[0].localeCompare(b[0], 'en-US', { numeric: true }));
    const groupHtml = node.groups
        .map(group => buildRoadModule1TreeEditorHtml(group, depth))
        .join('');
    const childrenHtml = childEntries
        .map(([childLabel, childNode]) => renderRoadModule1TreeNode(childNode, depth + 1, childLabel))
        .join('');

    if (!label) return `${groupHtml}${childrenHtml}`;

    const descendantCount = countRoadTreeRows(node);
    return `
        <details class="road-tree-node" open>
            <summary class="road-tree-summary" style="--road-tree-depth:${depth}">
                <span class="road-tree-label">${escapeHtml(label)}</span>
                <span class="road-tree-count">${descendantCount} row${descendantCount === 1 ? '' : 's'}</span>
            </summary>
            <div class="road-tree-children">
                ${groupHtml}
                ${childrenHtml}
            </div>
        </details>
    `;
}

function countRoadTreeRows(node) {
    const ownRows = node.groups.reduce((sum, group) => sum + group.rows.length, 0);
    return ownRows + [...node.children.values()].reduce((sum, child) => sum + countRoadTreeRows(child), 0);
}

function renderRoadModule1GraphChildren(node, depth = 0, parentPath = '') {
    let childEntries = [...node.children.entries()];

    if (State.roadModule1.sortBy === 'energy-rank') {
        const energyMap = State.roadModule1.energyMap || new Map();
        const dir = State.roadModule1.sortDirection === 'desc' ? -1 : 1;
        childEntries.sort((a, b) => {
            const aEnergy = energyMap.get(parentPath ? `${parentPath}\\${a[0]}` : a[0]) ?? 0;
            const bEnergy = energyMap.get(parentPath ? `${parentPath}\\${b[0]}` : b[0]) ?? 0;
            return (aEnergy - bEnergy) * dir;
        });
    } else {
        childEntries.sort((a, b) => a[0].localeCompare(b[0], 'en-US', { numeric: true }));
    }

    if (childEntries.length === 0) return '';

    return `
        <ul class="road-graph-list ${depth === 0 ? 'road-graph-root-list' : ''}">
            ${childEntries.map(([childLabel, childNode]) => renderRoadModule1GraphNode(childLabel, childNode, depth + 1, parentPath)).join('')}
        </ul>
    `;
}

function renderRoadModule1GraphNode(label, node, depth, parentPath = '') {
    const fullPath = parentPath ? `${parentPath}\\${label}` : label;
    const childHtml = renderRoadModule1GraphChildren(node, depth, fullPath);
    const groupHtml = node.groups
        .map(group => buildRoadModule1GraphEditorHtml(group, depth))
        .join('');
    const rowCount = countRoadTreeRows(node);
    const measureCount = new Set(node.groups.map(group => group.rows[0]?.Variable).filter(Boolean)).size;
    const isLeaf = node.children.size === 0;
    const nodeHasFlaggedRows = node.groups.some(group => group.rows.some(isRoadRowFlagged));
    const nodeFlagIcon = nodeHasFlaggedRows
        ? `<svg class="road-flag-icon" viewBox="0 0 10 13" width="10" height="13" aria-label="Key input"><path d="M1.5 1v11M1.5 1.5h7L5.5 5.5l3 4H1.5" stroke="currentColor" stroke-width="1.5" fill="none" stroke-linecap="round" stroke-linejoin="round"/></svg>`
        : '';
    return `
        <li class="road-graph-node-group ${isLeaf ? 'is-leaf' : ''}">
            <div class="road-graph-node-wrapper">
                <article class="road-graph-card ${node.groups.length ? 'has-editors' : ''}">
                    <div class="road-graph-card-header">
                        <div class="min-w-0">
                            <div class="road-graph-level">Level ${depth}</div>
                            <div class="road-graph-title" title="${escapeHtml(label)}">${nodeFlagIcon}${escapeHtml(label)}</div>
                        </div>
                        <div class="road-graph-card-meta">
                            <span>${rowCount} row${rowCount === 1 ? '' : 's'}</span>
                            ${measureCount ? `<span>${measureCount} measure${measureCount === 1 ? '' : 's'}</span>` : ''}
                        </div>
                    </div>
                    ${groupHtml ? `<div class="road-graph-editors">${groupHtml}</div>` : ''}
                </article>
            </div>
            ${childHtml}
        </li>
    `;
}

function buildRoadModule1GraphEditorHtml(group, depth) {
    const first = group.rows[0];
    const groupUnits = [...new Set(group.rows.map(row => row.Units).filter(Boolean))];
    const groupTitle = group.groupType === 'paired-fuel-share'
        ? 'Gasoline / diesel mix'
        : (group.groupType === 'reconciliation-controls'
            ? 'Reconciliation controls'
            : (group.groupType === 'turnover-calibration'
                ? 'Turnover calibration'
                : (group.groupType === 'transport-params'
                    ? getRoadTransportParamGroupTitle(group)
                    : (group.groupType === 'sales-share-mix'
                        ? 'Sales share by drive type'
                        : (first.Variable || 'Measure')))));
    return `
        <section class="road-graph-editor">
            <div class="road-graph-editor-header">
                <span class="road-graph-editor-title">${escapeHtml(groupTitle)}</span>
                ${groupUnits.length ? `<span class="road-unit-pill">${escapeHtml(groupUnits.join(', '))}</span>` : ''}
            </div>
            ${buildRoadModule1EditorRowsHtml(group, depth)}
        </section>
    `;
}

function buildRoadModule1TreeEditorHtml(group, depth) {
    const groupRows = group.rows;
    const first = groupRows[0];
    const isCompactGroup = group.groupType !== 'age-series' && groupRows.length === 1;
    const groupUnits = [...new Set(groupRows.map(row => row.Units).filter(Boolean))];
    const groupCountLabel = group.groupType === 'age-series'
        ? `${groupRows.length} point series`
        : `${groupRows.length} row${groupRows.length === 1 ? '' : 's'}`;
    const groupTitle = group.groupType === 'paired-fuel-share'
        ? 'Gasoline / diesel mix'
        : (group.groupType === 'reconciliation-controls'
            ? 'Fuel reconciliation'
            : (group.groupType === 'turnover-calibration'
                ? 'Turnover calibration'
                : (group.groupType === 'transport-params'
                    ? getRoadTransportParamGroupTitle(group)
                    : (group.groupType === 'sales-share-mix'
                        ? 'Sales share by drive type'
                        : first.Variable))));
    return `
        <section class="road-group-card road-tree-editor ${isCompactGroup ? 'is-compact' : ''}" style="--road-indent:${Math.max(0, depth - 1) * 0.45}rem">
            <div class="road-group-header">
                <div class="min-w-0">
                    <div class="road-breadcrumbs" title="${escapeHtml(group.branchPath)}">${formatRoadBranchPath(group.branchPath)}</div>
                    <div class="road-group-title-row">
                        <div class="road-group-title">${escapeHtml(groupTitle)}</div>
                        ${groupUnits.length ? `<div class="road-unit-pill">${escapeHtml(groupUnits.join(', '))}</div>` : ''}
                    </div>
                </div>
            </div>
            <div class="road-group-rows">
                ${buildRoadModule1EditorRowsHtml(group, depth)}
            </div>
        </section>
    `;
}

function getRoadPairedFuelShareBoundsAttrs() {
    return 'min="0" max="1"';
}

function buildRoadModule1PairedFuelShareEditorHtml(group, depth = 0) {
    const rowsByRole = new Map();
    group.rows.forEach(row => {
        const role = getRoadPairedFuelShareRole(row);
        if (role) rowsByRole.set(role, row);
    });

    const gasolineRow = rowsByRole.get('gasoline') || null;
    const dieselRow = rowsByRole.get('diesel') || null;
    const toleranceRow = rowsByRole.get('tolerance') || null;
    const referenceRow = gasolineRow || dieselRow || toleranceRow || group.rows[0];
    const rowRefs = getRoadPairedFuelShareRowRefs([gasolineRow, dieselRow, toleranceRow].filter(Boolean));
    const serializableRowRefs = rowRefs.map(({ role, rowKey, year, keyPayload }) => ({ role, rowKey, year, keyPayload }));
    const comment = getRoadCommentForKeys(rowRefs.map(ref => ref.rowKey), rowRefs.map(ref => ref.year));

    const lookupRef = (role) => rowRefs.find(ref => ref.role === role) || null;
    const getValue = (role) => {
        const ref = lookupRef(role);
        if (!ref) return '';
        const override = State.roadModule1.overrides.get(`${ref.rowKey}||Year=${ref.year}`);
        return override && override.value !== null && override.value !== undefined && String(override.value).trim() !== ''
            ? override.value
            : getRoadDefaultValue(ref.row, ref.year);
    };

    const gasolineValue = Number(getValue('gasoline'));
    const dieselValue = Number(getValue('diesel'));
    const toleranceValue = Number(getValue('tolerance'));
    const currentTotal = Number.isFinite(gasolineValue) && Number.isFinite(dieselValue) ? gasolineValue + dieselValue : null;
    const shareHint = Number.isFinite(currentTotal)
        ? `Current sum: ${currentTotal.toFixed(4)} (shares should sum to 1.0000)`
        : 'Shares are linked so updating one updates the other.';

    const shareInput = (role, label) => {
        const ref = lookupRef(role);
        if (!ref) return '';
        const defaultValue = getRoadDefaultValue(ref.row, ref.year);
        const override = State.roadModule1.overrides.get(`${ref.rowKey}||Year=${ref.year}`);
            const inputValue = getRoadInputValueWithDefault(override, defaultValue);
        return `
            <div class="road-year-input road-paired-share-input" data-share-role="${role}" data-row-key="${encodeURIComponent(ref.rowKey)}" data-year="${ref.year}">
                ${buildRoadCellLabelHtml(label, ROAD_VARIABLE_HELP.pairedFuelShare[role] || `${label}: enter a fraction between 0 and 1 for this transport type.`, getRoadCellScenarioLabel(ref.row, ref.year))}
                <input type="number" step="any" ${getRoadPairedFuelShareBoundsAttrs()} class="road-value-input road-paired-share-value-input" data-default-value="${escapeHtml(formatRoadEditableInputValue(defaultValue))}" value="${escapeHtml(inputValue)}">
            </div>
        `;
    };

    const pairedTitle = `Gasoline / diesel mix — ${escapeHtml(getRoadMileageSharedVehicleLabel(referenceRow))}`;
    return `
        <div class="road-input-row road-paired-share-row" style="--road-indent:${Math.max(0, getRoadBranchDepth(group.branchPath) - 2 + depth * 0.25) * 0.75}rem" data-row-refs="${encodeURIComponent(JSON.stringify(serializableRowRefs))}">
            <div class="road-row-label">
                <div class="road-row-title" title="Conventional gasoline/diesel split at the top-level vehicle type">${pairedTitle} ${buildRoadInfoTooltip(ROAD_VARIABLE_HELP.pairedFuelShare.rowTitle)}</div>
            </div>
            <div class="road-year-grid road-paired-share-grid">
                ${shareInput('gasoline', 'Gasoline share')}
                ${shareInput('diesel', 'Diesel share')}
                ${shareInput('tolerance', 'Tolerance')}
                <div class="road-paired-share-sum-badge">${escapeHtml(shareHint)}</div>
            </div>
            <div class="road-row-actions road-paired-share-actions">
                <button type="button" class="road-reset-button" title="Reset paired gasoline/diesel shares" aria-label="Reset paired fuel shares">&#8634;</button>
                <input type="text" class="road-comment-input" placeholder="Comment" value="${escapeHtml(comment)}">
            </div>
        </div>
    `;
}

function buildRoadModule1ReconciliationEditorHtml(group, depth = 0) {
    const rowsByRole = new Map();
    group.rows.forEach(row => {
        const role = getRoadReconciliationControlRole(row);
        if (role) rowsByRole.set(role, row);
    });

    const referenceRow = group.rows[0];
    const rowRefs = getRoadReconciliationRowRefs(group.rows);
    const serializableRowRefs = rowRefs.map(({ role, rowKey, year, keyPayload }) => ({ role, rowKey, year, keyPayload }));
    const comment = getRoadCommentForKeys(rowRefs.map(ref => ref.rowKey), rowRefs.map(ref => ref.year));

    const valueInput = (bindRole, label, helpText) => {
        const row = rowsByRole.get(bindRole) || null;
        if (!row) return '';
        const ref = rowRefs.find(r => r.role === bindRole);
        if (!ref) return '';
        const defaultValue = getRoadDefaultValue(row, ref.year);
        const override = State.roadModule1.overrides.get(`${ref.rowKey}||Year=${ref.year}`);
        const inputValue = getRoadInputValueWithDefault(override, defaultValue);
        const boundsAttrs = getRoadModule1InputBoundsAttrs(row.Variable);
        return `
            <div class="road-year-input road-reconciliation-input" data-reconciliation-role="${bindRole}" data-row-key="${encodeURIComponent(ref.rowKey)}" data-year="${ref.year}">
                ${buildRoadCellLabelHtml(label, helpText, getRoadCellScenarioLabel(row, ref.year))}
                <input type="number" step="any" ${boundsAttrs} class="road-value-input" data-default-value="${escapeHtml(formatRoadEditableInputValue(defaultValue))}" value="${escapeHtml(inputValue)}">
            </div>
        `;
    };

    const componentSection = (label, weightRole, lowerRole, upperRole, helpWeight, helpLower, helpUpper) => {
        const weightHtml = valueInput(weightRole, 'Weight', helpWeight);
        const lowerHtml = lowerRole ? valueInput(lowerRole, 'Min adjustment', helpLower) : '';
        const upperHtml = upperRole ? valueInput(upperRole, 'Max adjustment', helpUpper) : '';
        if (!weightHtml && !lowerHtml && !upperHtml) return '';
        return `
            <div class="road-reconciliation-component">
                <div class="road-reconciliation-component-label">${escapeHtml(label)}</div>
                <div class="road-year-grid">
                    ${weightHtml}${lowerHtml}${upperHtml}
                </div>
            </div>
        `;
    };

    const hasSharedWeight = rowsByRole.has('weight_shared');
    const hasSharedLower = rowsByRole.has('bound_lower_shared');
    const hasSharedUpper = rowsByRole.has('bound_upper_shared');

    const pickWeightRole = (specificRole) => rowsByRole.has(specificRole)
        ? specificRole
        : (hasSharedWeight ? 'weight_shared' : '');
    const pickLowerRole = (specificRole) => rowsByRole.has(specificRole)
        ? specificRole
        : (hasSharedLower ? 'bound_lower_shared' : '');
    const pickUpperRole = (specificRole) => rowsByRole.has(specificRole)
        ? specificRole
        : (hasSharedUpper ? 'bound_upper_shared' : '');

    const stockSection = componentSection(
        'Stock',
        pickWeightRole('weight_stock'),
        pickLowerRole('bound_lower_stock'),
        pickUpperRole('bound_upper_stock'),
        ROAD_VARIABLE_HELP.reconciliation.stockWeight,
        ROAD_VARIABLE_HELP.reconciliation.stockLower,
        ROAD_VARIABLE_HELP.reconciliation.stockUpper
    );
    const mileageSection = componentSection(
        'Mileage',
        pickWeightRole('weight_mileage'),
        pickLowerRole('bound_lower_mileage'),
        pickUpperRole('bound_upper_mileage'),
        ROAD_VARIABLE_HELP.reconciliation.mileageWeight,
        ROAD_VARIABLE_HELP.reconciliation.mileageLower,
        ROAD_VARIABLE_HELP.reconciliation.mileageUpper
    );
    const efficiencySection = componentSection(
        'Efficiency',
        pickWeightRole('weight_efficiency'),
        pickLowerRole('bound_lower_efficiency'),
        pickUpperRole('bound_upper_efficiency'),
        ROAD_VARIABLE_HELP.reconciliation.efficiencyWeight,
        ROAD_VARIABLE_HELP.reconciliation.efficiencyLower,
        ROAD_VARIABLE_HELP.reconciliation.efficiencyUpper
    );

    const sectionCount = [stockSection, mileageSection, efficiencySection]
        .filter(Boolean)
        .length;
    const reconciliationDescription = 'Aligned to Module 6 defaults: weights 0.50 / 0.25 / 0.25, stock bounds 0–10, mileage 0.85–1.15, efficiency 0.90–1.10.';

    return `
        <div class="road-input-row road-reconciliation-row" style="--road-indent:${Math.max(0, getRoadBranchDepth(group.branchPath) - 2 + depth * 0.25) * 0.75}rem" data-row-refs="${encodeURIComponent(JSON.stringify(serializableRowRefs))}" data-key-payload="${encodeURIComponent(JSON.stringify(roadModule1KeyPayload(referenceRow)))}">
            <div class="road-row-label">
                <div class="road-row-title">Fuel reconciliation controls ${buildRoadInfoTooltip(ROAD_VARIABLE_HELP.reconciliation.rowTitle)}</div>
                <div class="road-row-meta">${escapeHtml(reconciliationDescription)} ${sectionCount > 1 ? `(${sectionCount} control groups)` : ''}</div>
            </div>
            <div class="road-reconciliation-components">
                ${stockSection}
                ${mileageSection}
                ${efficiencySection}
            </div>
            <div class="road-row-actions">
                <button type="button" class="road-reset-button" title="Reset fuel reconciliation" aria-label="Reset fuel reconciliation">&#8634;</button>
                <input type="text" class="road-comment-input" placeholder="Comment" value="${escapeHtml(comment)}">
            </div>
        </div>
    `;
}

function buildRoadModule1TransportParamsEditorHtml(group, depth = 0) {
    const enabledRows = group.rows.filter(row => isRoadTransportParamRoleEnabled(getRoadTransportParamRole(row)));
    const pvsRows = enabledRows.filter(row => getRoadTransportParamRole(row) === 'pvs');
    const pvsReachedRows = enabledRows.filter(row => getRoadTransportParamRole(row) === 'pvs_reached');
    const passengerGrowthRows = enabledRows.filter(row => getRoadTransportParamRole(row) === 'passenger_growth_adjustment');
    const freightElasticityRows = enabledRows.filter(row => getRoadTransportParamRole(row) === 'freight_elasticity_adjustment');
    const vewRows = group.rows
        .filter(row => isRoadTransportParamRoleEnabled(getRoadTransportParamRole(row)))
        .filter(row => getRoadTransportParamRole(row) === 'vew')
        .sort((a, b) => getRoadFleetWeightCanonicalClass(a).localeCompare(getRoadFleetWeightCanonicalClass(b), 'en-US', { numeric: true }));

    const paramSection = (row, role, labelText) => {
        if (!row || !labelText) return '';
        const rowKey = buildRoadModule1Key(row);
        const keyPayload = encodeURIComponent(JSON.stringify(roadModule1KeyPayload(row)));
        const yearColumns = getRoadYearColumns(row);
        const boundsAttrs = getRoadModule1InputBoundsAttrs(row.Variable);
        const _paramVarName = ROAD_VARIABLE_HELP.paramRoles[role];
        const _paramHelpText = _paramVarName ? (ROAD_VARIABLE_HELP.variables[_paramVarName] || '') : '';
        const _paramHelpTip = _paramHelpText ? ` ${buildRoadInfoTooltip(_paramHelpText)}` : '';
        const yearInputs = yearColumns.map(year => {
            const key = `${rowKey}||Year=${year}`;
            const override = State.roadModule1.overrides.get(key);
            const defaultValueRaw = getRoadDefaultValue(row, year);
            const defaultValue = formatRoadDefaultValue(defaultValueRaw);
            const inputValue = getRoadInputValueWithDefault(override, defaultValueRaw);
            const isBooleanToggle = role === 'pvs_reached';
            const defaultChecked = normalizeRoadBooleanish(defaultValueRaw);
            const currentChecked = override
                ? normalizeRoadBooleanish(override.value)
                : defaultChecked;
            return `
                <div class="road-year-input road-transport-param-input" data-param-role="${role}" data-row-key="${encodeURIComponent(rowKey)}" data-key-payload="${keyPayload}" data-year="${year}">
                    ${buildRoadCellLabelHtml(year, _paramHelpText || `${labelText} for ${year}.`, getRoadCellScenarioLabel(row, year))}
                    ${isBooleanToggle
                        ? `
                        <div class="road-view-toggle road-boolean-toggle" data-default-bool="${defaultChecked ? '1' : '0'}">
                            <button type="button" class="road-boolean-btn${!currentChecked ? ' is-active' : ''}" data-value="0">False</button>
                            <button type="button" class="road-boolean-btn${currentChecked ? ' is-active' : ''}" data-value="1">True</button>
                        </div>
                        `
                        : `<input type="number" step="any" ${boundsAttrs} class="road-value-input" data-default-value="${escapeHtml(formatRoadEditableInputValue(defaultValueRaw))}" value="${escapeHtml(inputValue)}">`
                    }
                </div>
            `;
        }).join('');
        const unitPill = row.Units ? `<span class="road-unit-pill">${escapeHtml(row.Units)}</span>` : '';
        return `
            <div class="road-transport-param-measure" data-param-role="${role}">
                <div class="road-transport-param-label">${escapeHtml(labelText)}${_paramHelpTip}${unitPill}</div>
                <div class="road-year-grid">${yearInputs}</div>
            </div>
        `;
    };

    const ownershipHtml = [
        ...pvsRows.map(row => paramSection(row, 'pvs', 'Ownership saturation')),
        ...pvsReachedRows.map(row => paramSection(row, 'pvs_reached', 'Passenger saturation reached')),
        ...passengerGrowthRows.map(row => paramSection(row, 'passenger_growth_adjustment', 'Passenger stock growth adjustment'))
    ]
        .filter(Boolean)
        .join('');

    const freightProjectionHtml = freightElasticityRows
        .map(row => paramSection(row, 'freight_elasticity_adjustment', 'Freight elasticity adjustment'))
        .join('');

    const canonicalFleetRows = (() => {
        const byClass = new Map();
        vewRows.forEach(row => {
            const className = getRoadFleetWeightCanonicalClass(row);
            if (!byClass.has(className)) {
                byClass.set(className, row);
                return;
            }
            const existing = byClass.get(className);
            const existingLeaf = normalizeRoadTextToken(getRoadVehicleWeightLabel(existing));
            const nextLeaf = normalizeRoadTextToken(getRoadVehicleWeightLabel(row));
            const prefersCanonicalLeaf = normalizeRoadTextToken(className);
            if (nextLeaf === prefersCanonicalLeaf && existingLeaf !== prefersCanonicalLeaf) {
                byClass.set(className, row);
            }
        });
        return [...byClass.entries()]
            .sort((a, b) => a[0].localeCompare(b[0], 'en-US', { numeric: true }))
            .map(([, row]) => row);
    })();

    const fleetRowsHtml = canonicalFleetRows
        .map(row => paramSection(row, 'vew', `Vehicle equivalence weight — ${getRoadFleetWeightCanonicalClass(row)}`))
        .join('');

    const allRows = [...pvsRows, ...pvsReachedRows, ...passengerGrowthRows, ...freightElasticityRows, ...canonicalFleetRows];

    const allRowKeys = allRows.map(row => buildRoadModule1Key(row));
    const allYears = allRows.flatMap(row => getRoadYearColumns(row));
    const comment = getRoadCommentForKeys(allRowKeys, allYears);

    const rowRefs = allRows.map(row => ({
        role: getRoadTransportParamRole(row),
        rowKey: buildRoadModule1Key(row),
        year: getRoadBaseYearColumn(row),
        keyPayload: roadModule1KeyPayload(row)
    }));

    return `
        <div class="road-input-row road-transport-params-row" style="--road-indent:${Math.max(0, getRoadBranchDepth(group.branchPath) - 2 + depth * 0.25) * 0.75}rem" data-row-refs="${encodeURIComponent(JSON.stringify(rowRefs))}" data-key-payload="${encodeURIComponent(JSON.stringify(roadModule1KeyPayload(group.rows[0])))}">
            <div class="road-transport-params-measures">
                ${ownershipHtml ? `
                <div class="road-transport-param-group">
                    <div class="road-transport-param-group-title">Ownership</div>
                    ${ownershipHtml}
                </div>
                ` : ''}
                ${fleetRowsHtml ? `
                <div class="road-transport-param-group">
                    <div class="road-transport-param-group-title">Fleet weighting</div>
                    ${fleetRowsHtml}
                </div>
                ` : ''}
                ${freightProjectionHtml ? `
                <div class="road-transport-param-group">
                    <div class="road-transport-param-group-title">Freight projection</div>
                    ${freightProjectionHtml}
                </div>
                ` : ''}
            </div>
            <div class="road-row-actions">
                <button type="button" class="road-reset-button" title="Reset transport parameters" aria-label="Reset transport parameters">&#8634;</button>
                <input type="text" class="road-comment-input" placeholder="Comment" value="${escapeHtml(comment)}">
            </div>
        </div>
    `;
}

// ---------------------------------------------------------------------------
// Turnover calibration controls (detailed mode, backed by Module 1 rows)
// ---------------------------------------------------------------------------

function buildRoadTurnoverConfigPayload(rows = null) {
    const sourceRows = Array.isArray(rows) ? rows : buildRoadModule1CompletedRowsForCheckpoint();
    const result = {};
    sourceRows
        .filter(isRoadTurnoverCalibrationControlRow)
        .forEach(row => {
            const parts = getRoadPathParts(row);
            const transportRaw = normalizeRoadTextToken(parts[1] || '');
            const transportType = transportRaw.includes('passenger') ? 'passenger'
                : transportRaw.includes('freight') ? 'freight'
                : '';
            const role = getRoadTurnoverCalibrationRole(row);
            if (!transportType || !role) return;
            const rawValue = getRoadDefaultValue(row, getRoadBaseYearColumn(row));
            const numeric = Number(rawValue);
            if (!Number.isFinite(numeric)) return;
            if (!result[transportType]) result[transportType] = { fit_mode: 'auto' };
            result[transportType][role] = numeric * 100.0;
        });
    if (Object.keys(result).length) return result;

    const cfg = State.roadModule1.turnoverConfig || {};
    const defaults = { passenger: { lower: 5, upper: 8 }, freight: { lower: 6, upper: 10 } };
    const fallback = {};
    ['passenger', 'freight'].forEach(tt => {
        const ttCfg = cfg[tt] || {};
        const d = defaults[tt];
        const lower = ttCfg.lower !== '' && ttCfg.lower != null ? parseFloat(ttCfg.lower) : d.lower;
        const upper = ttCfg.upper !== '' && ttCfg.upper != null ? parseFloat(ttCfg.upper) : d.upper;
        fallback[tt] = { lower, upper, fit_mode: ttCfg.fitMode || 'auto' };
    });
    return fallback;
}

function buildRoadModule1TurnoverCalibrationEditorHtml(group, depth = 0) {
    const rowsByRole = new Map();
    group.rows.forEach(row => {
        const role = getRoadTurnoverCalibrationRole(row);
        if (role) rowsByRole.set(role, row);
    });

    const referenceRow = group.rows[0];
    const rowRefs = getRoadTurnoverCalibrationRowRefs(group.rows);
    const serializableRowRefs = rowRefs.map(({ role, rowKey, year, keyPayload }) => ({ role, rowKey, year, keyPayload }));
    const comment = getRoadCommentForKeys(rowRefs.map(ref => ref.rowKey), rowRefs.map(ref => ref.year));

    const valueInput = (bindRole, label, helpText) => {
        const row = rowsByRole.get(bindRole) || null;
        if (!row) return '';
        const ref = rowRefs.find(r => r.role === bindRole);
        if (!ref) return '';
        const defaultValue = getRoadDefaultValue(row, ref.year);
        const override = State.roadModule1.overrides.get(`${ref.rowKey}||Year=${ref.year}`);
        const inputValue = getRoadInputValueWithDefault(override, defaultValue);
        const boundsAttrs = getRoadModule1InputBoundsAttrs(row.Variable);
        return `
            <div class="road-year-input road-turnover-calibration-input" data-turnover-role="${bindRole}" data-row-key="${encodeURIComponent(ref.rowKey)}" data-year="${ref.year}">
                ${buildRoadCellLabelHtml(label, helpText, getRoadCellScenarioLabel(row, ref.year))}
                <input type="number" step="any" ${boundsAttrs} class="road-value-input" data-default-value="${escapeHtml(formatRoadEditableInputValue(defaultValue))}" value="${escapeHtml(inputValue)}">
            </div>
        `;
    };

    return `
        <div class="road-input-row road-turnover-calibration-row" style="--road-indent:${Math.max(0, getRoadBranchDepth(group.branchPath) - 2 + depth * 0.25) * 0.75}rem" data-row-refs="${encodeURIComponent(JSON.stringify(serializableRowRefs))}" data-key-payload="${encodeURIComponent(JSON.stringify(roadModule1KeyPayload(referenceRow)))}">
            <div class="road-row-label">
                <div class="road-row-title">Turnover calibration ${buildRoadInfoTooltip(ROAD_VARIABLE_HELP.turnoverCalibration.rowTitle)}</div>
                <div class="road-row-meta">Reshapes survival curves so fleet replacement rate stays within range. Defaults: passenger 0.05-0.08/yr, freight 0.06-0.10/yr.</div>
            </div>
            <div class="road-reconciliation-components">
                <div class="road-reconciliation-component">
                    <div class="road-reconciliation-component-label">Bounds</div>
                    <div class="road-year-grid">
                        ${valueInput('lower', 'Lower rate', ROAD_VARIABLE_HELP.turnoverCalibration.lowerRate)}
                        ${valueInput('upper', 'Upper rate', ROAD_VARIABLE_HELP.turnoverCalibration.upperRate)}
                    </div>
                </div>
            </div>
            <div class="road-row-actions">
                <button type="button" class="road-reset-button" title="Reset turnover calibration" aria-label="Reset turnover calibration">&#8634;</button>
                <input type="text" class="road-comment-input" placeholder="Comment" value="${escapeHtml(comment)}">
            </div>
        </div>
    `;
}

function buildRoadModule1TurnoverConfigHtml() {
    const cfg = State.roadModule1.turnoverConfig || {};
    const DEFAULTS = { passenger: { lower: '5', upper: '8' }, freight: { lower: '6', upper: '10' } };

    const componentSection = (transportType, label) => {
        const ttCfg = cfg[transportType] || {};
        const d = DEFAULTS[transportType];
        const lowerVal  = (ttCfg.lower  !== '' && ttCfg.lower  != null) ? ttCfg.lower  : d.lower;
        const upperVal  = (ttCfg.upper  !== '' && ttCfg.upper  != null) ? ttCfg.upper  : d.upper;
        const fitMode   = ttCfg.fitMode || 'auto';
        const fitOptions = [
            ['auto',        'Auto (recommended)'],
            ['manual',      'Manual'],
            ['passthrough', 'Pass-through'],
        ].map(([val, text]) =>
            `<option value="${val}"${fitMode === val ? ' selected' : ''}>${text}</option>`
        ).join('');
        return `
            <div class="road-reconciliation-component">
                <div class="road-reconciliation-component-label">${escapeHtml(label)}</div>
                <div class="road-year-grid">
                    <div class="road-year-input road-turnover-config-input" data-transport-type="${transportType}" data-field="lower">
                        ${buildRoadCellLabelHtml('Lower rate %', ROAD_VARIABLE_HELP.turnoverCalibration.lowerRate)}
                        <input type="number" step="0.1" min="0" max="100" class="road-value-input" data-default-value="${escapeHtml(d.lower)}" value="${escapeHtml(String(lowerVal))}">
                    </div>
                    <div class="road-year-input road-turnover-config-input" data-transport-type="${transportType}" data-field="upper">
                        ${buildRoadCellLabelHtml('Upper rate %', ROAD_VARIABLE_HELP.turnoverCalibration.upperRate)}
                        <input type="number" step="0.1" min="0" max="100" class="road-value-input" data-default-value="${escapeHtml(d.upper)}" value="${escapeHtml(String(upperVal))}">
                    </div>
                    <div class="road-year-input road-turnover-config-input" data-transport-type="${transportType}" data-field="fitMode">
                        ${buildRoadCellLabelHtml('Fit mode', ROAD_VARIABLE_HELP.turnoverCalibration.fitMode)}
                        <select class="road-value-input road-turnover-fitmode-select">${fitOptions}</select>
                    </div>
                </div>
            </div>
        `;
    };

    return `
        <div class="road-list-group">
            <div class="road-input-row road-turnover-config-row">
                <div class="road-row-label">
                    <div class="road-row-title">Turnover calibration ${buildRoadInfoTooltip(ROAD_VARIABLE_HELP.turnoverCalibration.rowTitle)}</div>
                    <div class="road-row-meta">Reshapes survival curves so fleet replacement rate stays within range. Defaults: passenger 5–8 %/yr, freight 6–10 %/yr.</div>
                </div>
                <div class="road-reconciliation-components">
                    ${componentSection('passenger', 'Passenger')}
                    ${componentSection('freight',   'Freight')}
                </div>
                <div class="road-row-actions">
                    <button type="button" class="road-reset-button" title="Reset turnover calibration to defaults" aria-label="Reset turnover calibration">&#8634;</button>
                </div>
            </div>
        </div>
    `;
}

function handleRoadModule1TurnoverConfigInputChange(rowEl, target) {
    const inputEl = target.closest('.road-turnover-config-input');
    if (!inputEl) return;
    const transportType = inputEl.dataset.transportType;
    const field = inputEl.dataset.field;
    if (!transportType || !field) return;
    if (!State.roadModule1.turnoverConfig[transportType]) {
        State.roadModule1.turnoverConfig[transportType] = { lower: '', upper: '', fitMode: 'auto' };
    }
    const raw = target.value.trim();
    if (field === 'fitMode') {
        State.roadModule1.turnoverConfig[transportType].fitMode = raw || 'auto';
    } else {
        State.roadModule1.turnoverConfig[transportType][field] = roadInputValueDiffersFromDefault(raw, target?.dataset.defaultValue || '') ? raw : '';
    }
    scheduleRoadModule1DraftSave();
}

function handleRoadModule1TurnoverConfigResetClick(rowEl) {
    State.roadModule1.turnoverConfig = {
        passenger: { lower: '', upper: '', fitMode: 'auto' },
        freight:   { lower: '', upper: '', fitMode: 'auto' }
    };
    rowEl.querySelectorAll('.road-turnover-config-input input').forEach(el => { el.value = el.dataset.defaultValue || ''; });
    rowEl.querySelectorAll('.road-turnover-fitmode-select').forEach(el => { el.value = 'auto'; });
    scheduleRoadModule1DraftSave();
}

function buildRoadModule1EditorRowsHtml(group, depth = 0) {
    const groupRows = group.rows;
    const first = groupRows[0];
    const isSinglePlainRowGroup = group.groupType === 'rows' && groupRows.length === 1;

    if (group.groupType === 'paired-fuel-share') {
        return buildRoadModule1PairedFuelShareEditorHtml(group, depth);
    }

    if (group.groupType === 'reconciliation-controls') {
        return buildRoadModule1ReconciliationEditorHtml(group, depth);
    }

    if (group.groupType === 'turnover-calibration') {
        return buildRoadModule1TurnoverCalibrationEditorHtml(group, depth);
    }

    if (group.groupType === 'transport-params') {
        return buildRoadModule1TransportParamsEditorHtml(group, depth);
    }

    if (group.groupType === 'shared-utilisation') {
        const yearColumns = getRoadYearColumns(first);
        const sharedKey = group.sharedKey || getRoadSharedUtilisationKey(first);
        const sharedComment = getRoadSharedUtilisationComment(sharedKey, yearColumns);
        const yearInputs = yearColumns.map(year => {
            const override = State.roadModule1.sharedUtilisationOverrides.get(buildRoadSharedOverrideMapKey(sharedKey, year));
            const defaultValue = getRoadDefaultValue(first, year);
            const inputValue = getRoadInputValueWithDefault(override, defaultValue);
            const boundsAttrs = getRoadModule1InputBoundsAttrs(first.Variable);
            return `
                <div class="road-year-input" data-year="${year}">
                    ${buildRoadCellLabelHtml(year, `${year} — ${ROAD_VARIABLE_HELP.variables[first.Variable] || ROAD_VARIABLE_HELP.variables['PHEV Electric Driving Share']}`, getRoadCellScenarioLabel(first, year))}
                    <input type="number" step="any" class="road-value-input" ${boundsAttrs} data-default-value="${escapeHtml(formatRoadEditableInputValue(defaultValue))}" value="${escapeHtml(inputValue)}">
                </div>
            `;
        }).join('');

        return `
            <div class="road-input-row road-shared-utilisation-row no-row-label" style="--road-indent:${Math.max(0, getRoadBranchDepth(group.branchPath) - 2 + depth * 0.25) * 0.75}rem" data-shared-utilisation-key="${encodeURIComponent(sharedKey)}" data-key-payload="${encodeURIComponent(JSON.stringify(roadModule1KeyPayload(first)))}">
                <div class="road-year-grid">${yearInputs}</div>
                <div class="road-row-actions">
                    <button type="button" class="road-reset-button" title="Reset to the original provided value" aria-label="Reset PHEV utilisation rate">&#8634;</button>
                    <input type="text" class="road-comment-input" placeholder="Comment" value="${escapeHtml(sharedComment)}">
                </div>
            </div>
        `;
    }

    if (group.groupType === 'shared-mileage') {
        const yearColumns = getRoadYearColumns(first);
        const sharedKey = group.sharedKey || getRoadSharedMileageKey(first);
        const sharedComment = getRoadSharedMileageComment(sharedKey, yearColumns);
        const isDriveLevel = sharedKey === getRoadSharedMileageDriveKey(first);
        const childCount = State.roadModule1.rows
            .filter(row => isRoadMileageRow(row) && (getRoadSharedMileageKey(row) === sharedKey || getRoadSharedMileageDriveKey(row) === sharedKey))
            .length;
        const mileageTooltipSuffix = isDriveLevel
            ? 'One shared series is used across all fuels in this drive type.'
            : 'One shared series is used across all drives and fuels in this vehicle type.';
        const yearInputs = yearColumns.map(year => {
            const override = State.roadModule1.sharedMileageOverrides.get(buildRoadSharedOverrideMapKey(sharedKey, year));
            const defaultValue = getRoadDefaultValue(first, year);
            const inputValue = getRoadInputValueWithDefault(override, defaultValue);
            const boundsAttrs = getRoadModule1InputBoundsAttrs(first.Variable);
            return `
                <div class="road-year-input" data-year="${year}">
                    ${buildRoadCellLabelHtml(year, `${year} — ${ROAD_VARIABLE_HELP.variables['Mileage']} ${mileageTooltipSuffix}`, getRoadCellScenarioLabel(first, year))}
                    <input type="number" step="any" class="road-value-input" ${boundsAttrs} data-default-value="${escapeHtml(formatRoadEditableInputValue(defaultValue))}" value="${escapeHtml(inputValue)}">
                </div>
            `;
        }).join('');

        return `
            <div class="road-input-row road-shared-mileage-row no-row-label" style="--road-indent:${Math.max(0, getRoadBranchDepth(group.branchPath) - 2 + depth * 0.25) * 0.75}rem" data-shared-mileage-key="${encodeURIComponent(sharedKey)}" data-key-payload="${encodeURIComponent(JSON.stringify(roadModule1KeyPayload(first)))}">
                <div class="road-year-grid">${yearInputs}</div>
                <div class="road-row-actions">
                    <button type="button" class="road-reset-button" title="Reset shared mileage to the original provided value" aria-label="Reset shared mileage">&#8634;</button>
                    <input type="text" class="road-comment-input" placeholder="Comment" value="${escapeHtml(sharedComment)}">
                </div>
            </div>
        `;
    }

    if (group.groupType === 'shared-fuel-economy') {
        const drivePath = group.branchPath;
        const isPhevOrErev = isRoadPhevOrErevDrive(drivePath);
        const driveLabel = getRoadDriveLevelLabel(drivePath);
        const yearColumns = getRoadYearColumns(first);
        const groups = isPhevOrErev
            ? [
                { subGroup: 'electric', label: 'Electricity efficiency', rows: groupRows.filter(r => isRoadElectricityFuel(r)) },
                { subGroup: 'other',    label: `Other fuels efficiency`, rows: groupRows.filter(r => !isRoadElectricityFuel(r)) }
              ]
            : [{ subGroup: 'all', label: '', rows: groupRows }];

        const sharedRowsHtml = groups.flatMap(sg => {
            if (!sg.rows.length) return [];
            const refRow = sg.rows[0];
            const sharedKey = getRoadSharedFuelEconomyKey(refRow);
            const childCount = sg.rows.length;
            const childBadge = childCount > 1 ? `${childCount} fuels` : '';
            const rowTitle = sg.label || `${driveLabel || 'Drive'} efficiency`;
            const rowMeta = sg.subGroup === 'electric'
                ? 'Shared across electricity rows'
                : (sg.subGroup === 'other'
                    ? 'Shared across non-electric fuel rows'
                    : 'Shared across fuels in this drive');
            const childNote = childCount > 1 ? ` · ${childCount} fuels` : '';
            const inputs = yearColumns.map(year => {
                const override = State.roadModule1.sharedFuelEconomyOverrides.get(buildRoadSharedOverrideMapKey(sharedKey, year));
                const defaultValue = getRoadDefaultValue(refRow, year);
                const inputValue = getRoadInputValueWithDefault(override, defaultValue);
                const boundsAttrs = getRoadModule1InputBoundsAttrs(refRow.Variable);
                return `
                    <div class="road-year-input" data-year="${year}">
                        ${buildRoadCellLabelHtml(year, `${year} — ${ROAD_VARIABLE_HELP.variables[refRow.Variable] || ROAD_VARIABLE_HELP.variables['Fuel Economy']} One shared value applies across${sg.subGroup === 'all' ? ' all fuels in this drive' : ` ${sg.label.toLowerCase()}`}${childNote}.`, getRoadCellScenarioLabel(refRow, year))}
                        <input type="number" step="any" class="road-value-input" ${boundsAttrs} data-default-value="${escapeHtml(formatRoadEditableInputValue(defaultValue))}" value="${escapeHtml(inputValue)}">
                    </div>
                `;
            }).join('');
            const comment = (() => {
                for (const year of yearColumns) {
                    const ov = State.roadModule1.sharedFuelEconomyOverrides.get(buildRoadSharedOverrideMapKey(sharedKey, year));
                    if (ov?.comment) return ov.comment;
                }
                return '';
            })();
            return [
                `<div class="road-input-row road-shared-fe-row${isPhevOrErev ? ' road-shared-fe-phev' : ''}" style="--road-indent:${Math.max(0, getRoadBranchDepth(drivePath) - 2 + depth * 0.25) * 0.75}rem" data-key-payload="${encodeURIComponent(JSON.stringify(roadModule1KeyPayload(refRow)))}">
                    <div class="road-row-label">
                        <div class="road-row-title">${escapeHtml(rowTitle)}${childBadge ? ` <span class="road-row-modifier-badge">${escapeHtml(childBadge)}</span>` : ''}</div>
                        <div class="road-row-meta">${escapeHtml(rowMeta)}</div>
                    </div>
                    <div class="road-shared-fe-subgroup" data-shared-fe-key="${encodeURIComponent(sharedKey)}">
                        <div class="road-year-grid">${inputs}</div>
                        <div class="road-row-actions">
                            <button type="button" class="road-reset-button" title="Reset to provided value" aria-label="Reset">&#8634;</button>
                            <input type="text" class="road-comment-input" placeholder="Comment" value="${escapeHtml(comment)}">
                        </div>
                    </div>
                </div>`
            ];
        }).join('');

        return sharedRowsHtml;
    }

    if (group.groupType === 'sales-share-mix') {
        const rowsByDrivePath = new Map();
        groupRows.forEach(row => {
            const drivePath = row['Branch Path'] || '';
            if (!rowsByDrivePath.has(drivePath)) rowsByDrivePath.set(drivePath, []);
            rowsByDrivePath.get(drivePath).push(row);
        });
        const yearColumns = Array.from(new Set(groupRows.flatMap(getRoadYearColumns))).sort();
        const rowRefs = [...rowsByDrivePath.entries()]
            .sort((a, b) => getRoadBranchLeafLabel(a[0]).localeCompare(getRoadBranchLeafLabel(b[0]), 'en-US', { numeric: true }))
            .map(([drivePath, driveRows]) => {
                const yearRefs = yearColumns.map(year => {
                    const matchingRows = driveRows
                        .filter(row => getRoadYearColumns(row).includes(String(year)))
                        .sort((a, b) => getRoadSalesShareScenarioRank(a, year) - getRoadSalesShareScenarioRank(b, year));
                    const preferredRow = matchingRows[0] || null;
                    return {
                        year: year,
                        value: preferredRow ? getRoadDefaultValue(preferredRow, year) : '',
                        refs: matchingRows.map(row => ({
                            rowKey: buildRoadModule1Key(row),
                            keyPayload: roadModule1KeyPayload(row)
                        }))
                    };
                }).filter(item => item.refs.length > 0);
                return {
                    label: getRoadBranchLeafLabel(drivePath) || drivePath,
                    yearRefs: yearRefs
                };
            });
        const allKeyYears = rowRefs.flatMap(ref => ref.yearRefs.flatMap(yearRef => (
            yearRef.refs.map(rowRef => ({ rowKey: rowRef.rowKey, year: yearRef.year }))
        )));
        const comment = getRoadCommentForKeys(
            allKeyYears.map(item => item.rowKey),
            allKeyYears.map(item => item.year)
        );
        const editorItems = rowRefs.map(ref => {
            const defaultSeriesText = ref.yearRefs.map(point => formatRoadSeriesInputValue(point.value)).join(', ');
            const defaultPoints = ref.yearRefs.map(point => ({
                age: Number(point.year),
                value: point.value
            }));
            const providedSeriesText = ref.yearRefs
                .map(point => {
                    for (const rowRef of point.refs) {
                        const override = State.roadModule1.overrides.get(`${rowRef.rowKey}||Year=${point.year}`);
                        if (override && override.value !== null && override.value !== '') return String(override.value);
                    }
                    return '';
                })
                .join(', ')
                .replace(/(, )+$/g, '');
            const seriesText = providedSeriesText || defaultSeriesText;
            const providedPoints = parseRoadSalesShareSeriesValues(providedSeriesText)
                .filter(value => Number.isFinite(Number(value)))
                .map((value, index) => ({
                    age: Number(ref.yearRefs[index]?.year),
                    value: value
                }));
            return {
                seriesHtml: `
                    <div class="road-paired-series-row">
                        <div class="road-paired-series-label" title="${escapeHtml(ref.label)}">${escapeHtml(ref.label)}</div>
                        <div class="road-paired-series-control road-sales-share-series" data-year-refs="${encodeURIComponent(JSON.stringify(ref.yearRefs))}" data-default-points="${encodeURIComponent(JSON.stringify(defaultPoints))}">
                            <textarea class="road-series-input road-paired-series-input road-sales-share-series-input road-value-input" rows="2" spellcheck="false" data-default-series="${escapeHtml(defaultSeriesText)}">${escapeHtml(seriesText)}</textarea>
                        </div>
                        <div class="road-series-chart-wrap">${buildRoadSeriesSvg(defaultPoints, providedPoints)}</div>
                    </div>
                `
            };
        });
        const editorRowsHtml = editorItems.map(item => item.seriesHtml).join('');

        return `
            <div class="road-input-row road-sales-share-mix-row" style="--road-indent:${Math.max(0, getRoadBranchDepth(group.branchPath) - 2 + depth * 0.25) * 0.75}rem" data-years="${encodeURIComponent(JSON.stringify(yearColumns))}" data-row-refs="${encodeURIComponent(JSON.stringify(rowRefs))}">
                <div class="road-row-label">
                    <div class="road-row-title">Sales share by drive type ${buildRoadInfoTooltip(ROAD_VARIABLE_HELP.salesShareMix.rowTitle)}</div>
                    <div class="road-row-meta">${escapeHtml(yearColumns.length ? `${yearColumns[0]}-${yearColumns[yearColumns.length - 1]}` : '')} | values are percentages</div>
                    <div class="road-series-legend">
                        <span><i class="default"></i>Loaded defaults</span>
                        <span><i class="provided"></i>Entered</span>
                    </div>
                </div>
                <div class="road-paired-series-grid">
                    ${editorRowsHtml}
                    <div class="road-series-hint road-sales-share-warning">${escapeHtml(ROAD_VARIABLE_HELP.salesShareMix.warning)} ${escapeHtml(ROAD_SERIES_RECOMMENDATION)}</div>
                </div>
                <div class="road-row-actions road-series-actions">
                    <button type="button" class="road-reset-button" title="Reset sales-share series to provided defaults" aria-label="Reset sales-share series">&#8634;</button>
                    <input type="text" class="road-comment-input" placeholder="Comment for sales-share series" value="${escapeHtml(comment)}">
                </div>
            </div>
        `;
    }

    if (group.groupType === 'age-series' || group.groupType === 'time-series') {
        const isTimeSeries = group.groupType === 'time-series';
        const sortedRows = isTimeSeries
            ? [groupRows[0]].filter(Boolean)
            : [...groupRows].sort((a, b) => getRoadAgeFromBranchPath(a['Branch Path']) - getRoadAgeFromBranchPath(b['Branch Path']));
        const timeSeriesRow = isTimeSeries ? sortedRows[0] : null;
        const yearColumns = isTimeSeries ? getRoadYearColumns(timeSeriesRow) : [];
        const defaultPoints = isTimeSeries
            ? yearColumns.map(year => ({
                age: Number(year),
                value: getRoadDefaultValue(timeSeriesRow, year)
            }))
            : sortedRows.map(row => {
                const year = getRoadBaseYearColumn(row);
                return {
                    age: getRoadAgeFromBranchPath(row['Branch Path']),
                    value: getRoadDefaultValue(row, year)
                };
            });
        const providedPoints = isTimeSeries
            ? yearColumns
                .map(year => {
                    const override = State.roadModule1.overrides.get(`${buildRoadModule1Key(timeSeriesRow)}||Year=${year}`);
                    return override && override.value !== null && override.value !== ''
                        ? { age: Number(year), value: override.value }
                        : null;
                })
                .filter(Boolean)
            : [];
        const rowRefs = isTimeSeries
            ? yearColumns.map(year => ({
                age: Number(year),
                year: year,
                rowKey: buildRoadModule1Key(timeSeriesRow),
                keyPayload: roadModule1KeyPayload(timeSeriesRow)
            }))
            : sortedRows.map(row => {
                const year = getRoadBaseYearColumn(row);
                return {
                    age: getRoadAgeFromBranchPath(row['Branch Path']),
                    year: year,
                    rowKey: buildRoadModule1Key(row),
                    keyPayload: roadModule1KeyPayload(row)
                };
            });
        const defaultSeriesText = defaultPoints.map(point => formatRoadSeriesInputValue(point.value)).join(', ');
        const providedSeriesText = isTimeSeries
            ? yearColumns
                .map(year => {
                    const override = State.roadModule1.overrides.get(`${buildRoadModule1Key(timeSeriesRow)}||Year=${year}`);
                    return override && override.value !== null && override.value !== ''
                        ? formatRoadSeriesInputValue(override.value)
                        : '';
                })
                .join(', ')
                .replace(/(, )+$/g, '')
            : rowRefs
                .map(ref => {
                    const key = `${ref.rowKey}||Year=${ref.year}`;
                    const override = State.roadModule1.overrides.get(key);
                    return override && override.value !== null && override.value !== ''
                        ? formatRoadSeriesInputValue(override.value)
                        : '';
                })
                .join(', ')
                .replace(/(, )+$/g, '');
        const seriesText = providedSeriesText || defaultSeriesText;
        const seriesComment = getRoadCommentForKeys(rowRefs.map(ref => ref.rowKey), rowRefs.map(ref => ref.year));
        const seriesTitle = `${first.Variable || getRoadRowTitle(first)} series`;
        const rowMeta = isTimeSeries
            ? `${yearColumns.length ? `${yearColumns[0]}-${yearColumns[yearColumns.length - 1]}` : ''}${first.Units ? ` | ${first.Units}` : ''}`
            : getRoadRowMeta(first, [getRoadBaseYearColumn(first)]);
        const xStart = defaultPoints[0]?.age ?? '';
        const xEnd = defaultPoints[defaultPoints.length - 1]?.age ?? '';
        const orderLabel = isTimeSeries ? 'year order' : 'age order';
        const rangeLabel = isTimeSeries ? `years ${xStart}-${xEnd}` : `ages ${xStart}-${xEnd}`;
        return `
            <div class="road-input-row road-series-row" style="--road-indent:${Math.max(0, getRoadBranchDepth(group.branchPath) - 2 + depth * 0.25) * 0.75}rem" data-default-points="${encodeURIComponent(JSON.stringify(defaultPoints))}" data-row-refs="${encodeURIComponent(JSON.stringify(rowRefs))}" data-key-payload="${encodeURIComponent(JSON.stringify(roadModule1KeyPayload(first)))}">
                <div class="road-row-label">
                    <div class="road-row-title" title="${escapeHtml(seriesTitle)}">${escapeHtml(seriesTitle)}${first.review_reason ? ` ${buildRoadInfoTooltip(first.review_reason)}` : ROAD_VARIABLE_HELP.variables[first.Variable] ? ` ${buildRoadInfoTooltip(ROAD_VARIABLE_HELP.variables[first.Variable])}` : ''}</div>
                    <div class="road-row-meta">${escapeHtml(rowMeta)} | ${escapeHtml(rangeLabel)}</div>
                    <div class="road-series-legend">
                        <span><i class="default"></i>Loaded</span>
                        <span><i class="provided"></i>Entered</span>
                    </div>
                </div>
                <div class="road-series-entry">
                    <label>Provided series (${rowRefs.length} values, ${escapeHtml(orderLabel)})</label>
                    <textarea class="road-series-input road-value-input" rows="3" spellcheck="false" data-default-series="${escapeHtml(defaultSeriesText)}">${escapeHtml(seriesText)}</textarea>
                    <div class="road-series-hint">Paste from Excel or type values separated by commas, tabs, spaces, or new lines. ${escapeHtml(ROAD_SERIES_RECOMMENDATION)}</div>
                </div>
                <div class="road-row-actions road-series-actions">
                    <div class="road-series-chart-wrap">${buildRoadSeriesSvg(defaultPoints, providedPoints)}</div>
                    <input type="text" class="road-comment-input" placeholder="Comment for series" value="${escapeHtml(seriesComment)}">
                </div>
            </div>
        `;
    }

    return groupRows.map(row => {
        const rowKey = buildRoadModule1Key(row);
        const keyPayload = encodeURIComponent(JSON.stringify(roadModule1KeyPayload(row)));
        const yearColumns = getRoadYearColumns(row);
        const isStockShareRow = isRoadVehicleTypeStockShareRow(row);
        const yearInputs = yearColumns.map(year => {
            const key = `${rowKey}||Year=${year}`;
            const override = State.roadModule1.overrides.get(key);
            const defaultValueRaw = getRoadDisplayedPlaceholderValue(row, year);
            const defaultValue = formatRoadEditableInputValue(defaultValueRaw);
            const inputValue = getRoadInputValueWithDefault(override, defaultValueRaw);
            const inheritedValue = getRoadInheritedMileageValue(row, year);
            const boundsAttrs = getRoadModule1InputBoundsAttrs(row.Variable);
            const isReadOnlyBaseStockShare = isStockShareRow && Number(year) === ROAD_MODULE1_BASE_YEAR;
            const cellLabel = isReadOnlyBaseStockShare ? `${year} (auto-calculated)` : year;
            const cellHelpText = isReadOnlyBaseStockShare
                ? 'Auto-calculated from the stock numbers supplied to the branches in this category. This value cannot be manually changed.'
                : `${year}${ROAD_VARIABLE_HELP.variables[row.Variable] ? ' — ' + ROAD_VARIABLE_HELP.variables[row.Variable] : ''}. Leave blank to keep the provided default value.`;
            return `
                <div class="road-year-input${isReadOnlyBaseStockShare ? ' road-stock-share-auto' : ''}" data-year="${year}">
                    ${buildRoadCellLabelHtml(cellLabel, cellHelpText, getRoadCellScenarioLabel(row, year))}
                    <input type="number" step="any" class="road-value-input" ${boundsAttrs} ${isReadOnlyBaseStockShare ? 'readonly aria-readonly="true"' : ''} data-default-value="${escapeHtml(defaultValue)}" value="${isReadOnlyBaseStockShare ? escapeHtml(defaultValue) : escapeHtml(inputValue)}">
                    ${inheritedValue !== '' && !override ? '<div class="road-inherited-label">Inherited</div>' : ''}
                </div>
            `;
        }).join('');
        const rowComment = getRoadCommentForKeys([rowKey], yearColumns);
        const rowTitle = getRoadRowTitle(row);
        const rowMeta = getRoadRowMeta(row, yearColumns);
        const longSeriesHint = yearColumns.length > 6 && Number(yearColumns[yearColumns.length - 1]) >= 2060
            ? `<div class="road-series-hint">${escapeHtml(ROAD_SERIES_RECOMMENDATION)}</div>`
            : '';
        const hideRowLabel = isSinglePlainRowGroup && !row.review_reason;
        return `
            <div class="road-input-row ${hideRowLabel ? 'no-row-label' : ''}${isStockShareRow ? ' road-stock-share-row' : ''}" style="--road-indent:${Math.max(0, getRoadBranchDepth(row['Branch Path']) - 2 + depth * 0.25) * 0.75}rem" data-key="${encodeURIComponent(rowKey)}" data-key-payload="${keyPayload}">
                ${hideRowLabel ? '' : `
                <div class="road-row-label">
                    <div class="road-row-title" title="${escapeHtml(rowTitle)}">${escapeHtml(rowTitle)}${row.review_reason ? ` ${buildRoadInfoTooltip(row.review_reason)}` : ROAD_VARIABLE_HELP.variables[row.Variable] ? ` ${buildRoadInfoTooltip(ROAD_VARIABLE_HELP.variables[row.Variable])}` : ''}</div>
                    ${rowMeta ? `<div class="road-row-meta">${escapeHtml(rowMeta)}</div>` : ''}
                </div>
                `}
                <div class="road-year-grid${isStockShareRow ? ' road-stock-share-grid' : ''}">${yearInputs}</div>
                ${longSeriesHint}
                <div class="road-row-actions">
                    <button type="button" class="road-reset-button" title="${isRoadMileageRow(row) ? 'Reset detailed row to inherited shared mileage' : 'Reset row to the original provided value'}" aria-label="Reset row">&#8634;</button>
                    <input type="text" class="road-comment-input" placeholder="Comment" value="${escapeHtml(rowComment)}">
                </div>
            </div>
        `;
    }).join('');
}

function getRoadModule1InputBoundsAttrs(variable) {
    const rule = ROAD_MODULE1_VALUE_RULES[variable];
    if (!rule) return '';

    const attrs = [];
    if (rule.min !== undefined) attrs.push(`min="${rule.min}"`);
    if (rule.max !== undefined) attrs.push(`max="${rule.max}"`);
    return attrs.join(' ');
}

function renderRoadModule1TreeInputs(filteredRows) {
    const groupedRows = groupRoadRowsForEditors(filteredRows);
    const treeRoot = buildRoadModule1TreeGroups(groupedRows);
    DOM.roadInputContainer.innerHTML = `
        <div class="road-graph-canvas">
            ${renderRoadModule1GraphChildren(treeRoot)}
        </div>
    `;
    bindRoadModule1InputEvents();
}

function buildRoadModule1ListGroupHtml(group) {
    const groupRows = group.rows;
    const first = groupRows[0];
    const isCompactGroup = group.groupType !== 'age-series' && (groupRows.length === 1 || group.groupType === 'shared-utilisation');
    const groupUnits = [...new Set(groupRows.map(row => row.Units).filter(Boolean))];
    const groupCountLabel = group.groupType === 'age-series'
        ? `${groupRows.length} point series`
        : (group.groupType === 'shared-mileage' || group.groupType === 'shared-fuel-economy' || group.groupType === 'shared-utilisation')
            ? '1 value'
            : `${groupRows.length} value${groupRows.length === 1 ? '' : 's'}`;
    const groupTitle = group.groupType === 'paired-fuel-share'
        ? 'Gasoline / diesel mix'
        : (group.groupType === 'reconciliation-controls'
            ? 'Fuel reconciliation'
            : (group.groupType === 'turnover-calibration'
                ? 'Turnover calibration'
                : (group.groupType === 'transport-params'
                    ? getRoadTransportParamGroupTitle(group)
                    : (group.groupType === 'sales-share-mix'
                        ? 'Sales share by drive type'
                        : first.Variable))));
    const isFlagged = groupRows.some(isRoadRowFlagged);
    const flagIcon = isFlagged
        ? `<svg class="road-flag-icon" viewBox="0 0 10 13" width="10" height="13" aria-label="Key input"><path d="M1.5 1v11M1.5 1.5h7L5.5 5.5l3 4H1.5" stroke="currentColor" stroke-width="1.5" fill="none" stroke-linecap="round" stroke-linejoin="round"/></svg>`
        : '';
    const scenarioLabel = normaliseRoadScenarioLabel(first?.Scenario) || ROAD_MODULE1_CURRENT_ACCOUNTS;
    const scenarioBadge = scenarioLabel
        ? `<div class="road-row-scenario-badge" title="${escapeHtml(scenarioLabel)}">${escapeHtml(scenarioLabel)}</div>`
        : '';
    return `
        <section class="road-group-card ${isCompactGroup ? 'is-compact' : ''}">
            <div class="road-group-header">
                <div class="min-w-0">
                    <div class="road-breadcrumbs" title="${escapeHtml(group.branchPath)}">${formatRoadBranchPath(group.branchPath)}</div>
                    <div class="road-group-title-row">
                        ${flagIcon}<div class="road-group-title">${escapeHtml(groupTitle)}</div>
                        ${groupUnits.length ? `<div class="road-unit-pill">${escapeHtml(groupUnits.join(', '))}</div>` : ''}
                        ${scenarioBadge}
                    </div>
                </div>
            </div>
            <div class="road-group-rows">
                ${buildRoadModule1EditorRowsHtml(group)}
            </div>
        </section>
    `;
}

function renderRoadModule1ListInputs(filteredRows) {
    const groupedRows = groupRoadRowsForEditors(filteredRows);
    DOM.roadInputContainer.innerHTML = `
        <div class="road-list-view">
            ${[...groupedRows.values()].map(buildRoadModule1ListGroupHtml).join('')}
        </div>
    `;
    bindRoadModule1InputEvents();
}

function renderRoadModule1Inputs() {
    if (!DOM.roadInputContainer) return;

    syncRoadModule1ScenarioState(State.roadModule1.scenario);
    const rows = getRoadRowsForCurrentView();
    State.roadModule1.stockMap = buildRoadStockMap(rows);
    State.roadModule1.energyMap = buildRoadEnergyMap(rows);
    const filter = State.roadModule1.activeFilter;
    const textFilteredRows = filter
        ? rows.filter(row => {
            const meta = getRoadRowFilterMeta(row);
            const haystack = [
                row['Branch Path'],
                row.Variable,
                row.Units,
                row.Region,
                meta.transport,
                meta.scenario,
                meta.vehicle,
                meta.drive,
                meta.fuel,
                meta.source
            ].join(' ').toLowerCase();
            return haystack.includes(filter);
        })
        : rows;
    const filteredRows = sortRoadRows(
        textFilteredRows
            .filter(roadRowMatchesStructuredFilters)
            .filter(row => !isRoadVehicleEquivalentBoundsRow(row))
            .filter(row => isRoadRowVisibleAtCurrentDensity(row))
    );

    updateRoadModule1OverrideCount();
    DOM.roadValidationSummary.innerText = buildRoadStockShareValidationSummary(rows);

    if (filteredRows.length === 0) {
        DOM.roadInputContainer.innerHTML = '<div class="text-sm text-slate-400">No rows match the current filter.</div>';
        return;
    }

    updateRoadModule1ViewToggle();
    if (State.roadModule1.viewMode === 'tree') {
        renderRoadModule1TreeInputs(filteredRows);
    } else {
        State.roadModule1.viewMode = 'list';
        renderRoadModule1ListInputs(filteredRows);
    }
}

function handleRoadModule1InputChange(event) {
    const rowEl = event.target.closest('.road-input-row');
    if (!rowEl) return;

    if (rowEl.classList.contains('road-turnover-config-row')) {
        handleRoadModule1TurnoverConfigInputChange(rowEl, event.target);
        return;
    }

    if (rowEl.classList.contains('road-reconciliation-row')) {
        handleRoadModule1ReconciliationInputChange(rowEl, event.target);
        return;
    }

    if (rowEl.classList.contains('road-turnover-calibration-row')) {
        handleRoadModule1TurnoverCalibrationInputChange(rowEl, event.target);
        return;
    }

    if (rowEl.classList.contains('road-transport-params-row')) {
        handleRoadModule1TransportParamsInputChange(rowEl);
        return;
    }

    if (rowEl.classList.contains('road-paired-share-row')) {
        handleRoadModule1PairedFuelShareInputChange(rowEl, event.target);
        return;
    }

    if (rowEl.classList.contains('road-sales-share-mix-row')) {
        handleRoadModule1SalesShareMixInputChange(rowEl);
        return;
    }

    if (rowEl.classList.contains('road-shared-utilisation-row')) {
        handleRoadModule1SimpleSharedInputChange(rowEl, State.roadModule1.sharedUtilisationOverrides, 'sharedUtilisationKey');
        return;
    }

    if (rowEl.classList.contains('road-shared-mileage-row')) {
        handleRoadModule1SimpleSharedInputChange(rowEl, State.roadModule1.sharedMileageOverrides, 'sharedMileageKey');
        return;
    }

    if (rowEl.classList.contains('road-shared-fe-row')) {
        handleRoadModule1SharedFuelEconomyInputChange(rowEl);
        return;
    }

    if (rowEl.classList.contains('road-series-row')) {
        handleRoadModule1SeriesInputChange(rowEl);
        return;
    }

    const rowKey = decodeURIComponent(rowEl.dataset.key);
    const keyPayload = JSON.parse(decodeURIComponent(rowEl.dataset.keyPayload));
    const commentInput = rowEl.querySelector('.road-comment-input');
    const comment = commentInput.value.trim();
    let rowOverrideCount = 0;

    rowEl.querySelectorAll('.road-year-input').forEach(yearEl => {
        const year = yearEl.dataset.year;
        const key = `${rowKey}||Year=${year}`;
        const valueInput = yearEl.querySelector('.road-value-input');
        const value = valueInput.value.trim();
        const defaultValue = valueInput?.dataset.defaultValue || '';

        if (!value || !roadInputValueDiffersFromDefault(value, defaultValue)) {
            State.roadModule1.overrides.delete(key);
            return;
        }

        State.roadModule1.overrides.set(key, {
            key: keyPayload,
            year: year,
            value: value || null,
            comment: comment
        });
        rowOverrideCount += 1;
    });

    if (comment && rowOverrideCount === 0) {
        rowEl.querySelectorAll('.road-year-input').forEach(yearEl => {
            const year = yearEl.dataset.year;
            const key = `${rowKey}||Year=${year}`;
            const existing = State.roadModule1.overrides.get(key);
            if (existing) existing.comment = comment;
        });
    }

    rowEl.classList.toggle('is-edited', rowOverrideCount > 0 || comment.length > 0);
    updateRoadModule1OverrideCount();
    scheduleRoadModule1DraftSave();
}

function handleRoadModule1SimpleSharedInputChange(rowEl, overrides, datasetKey) {
    const sharedKey = decodeURIComponent(rowEl.dataset[datasetKey] || '');
    const commentInput = rowEl.querySelector('.road-comment-input');
    const comment = commentInput.value.trim();
    let rowOverrideCount = 0;

    rowEl.querySelectorAll('.road-year-input').forEach(yearEl => {
        const year = yearEl.dataset.year;
        const key = buildRoadSharedOverrideMapKey(sharedKey, year);
        const valueInput = yearEl.querySelector('.road-value-input');
        const value = valueInput.value.trim();
        const defaultValue = valueInput?.dataset.defaultValue || '';

        if (!value || !roadInputValueDiffersFromDefault(value, defaultValue)) {
            overrides.delete(key);
            return;
        }

        overrides.set(key, { sharedKey, year, value: value || null, comment });
        rowOverrideCount += 1;
    });

    if (comment && rowOverrideCount === 0) {
        rowEl.querySelectorAll('.road-year-input').forEach(yearEl => {
            const existing = overrides.get(buildRoadSharedOverrideMapKey(sharedKey, yearEl.dataset.year));
            if (existing) existing.comment = comment;
        });
    }

    rowEl.classList.toggle('is-edited', rowOverrideCount > 0 || comment.length > 0);
    updateRoadModule1OverrideCount();
    scheduleRoadModule1DraftSave();
}

function handleRoadModule1SharedFuelEconomyInputChange(rowEl) {
    let totalOverrides = 0;
    rowEl.querySelectorAll('.road-shared-fe-subgroup').forEach(sgEl => {
        const sharedKey = decodeURIComponent(sgEl.dataset.sharedFeKey || '');
        const commentInput = sgEl.querySelector('.road-comment-input');
        const comment = commentInput ? commentInput.value.trim() : '';
        let sgOverrides = 0;

        sgEl.querySelectorAll('.road-year-input').forEach(yearEl => {
            const year = yearEl.dataset.year;
            const key = buildRoadSharedOverrideMapKey(sharedKey, year);
            const valueInput = yearEl.querySelector('.road-value-input');
            const value = valueInput.value.trim();
            const defaultValue = valueInput?.dataset.defaultValue || '';

            if (!value || !roadInputValueDiffersFromDefault(value, defaultValue)) {
                State.roadModule1.sharedFuelEconomyOverrides.delete(key);
                return;
            }
            State.roadModule1.sharedFuelEconomyOverrides.set(key, {
                sharedKey: sharedKey,
                year: year,
                value: value || null,
                comment: comment
            });
            sgOverrides += 1;
        });

        if (comment && sgOverrides === 0) {
            sgEl.querySelectorAll('.road-year-input').forEach(yearEl => {
                const key = buildRoadSharedOverrideMapKey(sharedKey, yearEl.dataset.year);
                const existing = State.roadModule1.sharedFuelEconomyOverrides.get(key);
                if (existing) existing.comment = comment;
            });
        }
        totalOverrides += sgOverrides;
    });
    rowEl.classList.toggle('is-edited', totalOverrides > 0);
    updateRoadModule1OverrideCount();
    scheduleRoadModule1DraftSave();
}

function resetRoadSimpleSharedOverrideRow(rowEl, overrides, datasetKey) {
    const sharedKey = decodeURIComponent(rowEl.dataset[datasetKey] || '');
    rowEl.querySelectorAll('.road-year-input').forEach(yearEl => {
        overrides.delete(buildRoadSharedOverrideMapKey(sharedKey, yearEl.dataset.year));
        const input = yearEl.querySelector('.road-value-input');
        if (input) input.value = '';
    });
    const commentInput = rowEl.querySelector('.road-comment-input');
    if (commentInput) commentInput.value = '';
    rowEl.classList.remove('is-edited');
    updateRoadModule1OverrideCount();
    renderRoadModule1Inputs();
    scheduleRoadModule1DraftSave();
}

function handleRoadModule1ResetClick(event) {
    const rowEl = event.target.closest('.road-input-row');
    if (!rowEl) return;

    if (rowEl.classList.contains('road-turnover-config-row')) {
        handleRoadModule1TurnoverConfigResetClick(rowEl);
        return;
    }

    if (rowEl.classList.contains('road-reconciliation-row')) {
        handleRoadModule1ReconciliationResetClick(rowEl);
        return;
    }

    if (rowEl.classList.contains('road-turnover-calibration-row')) {
        handleRoadModule1TurnoverCalibrationResetClick(rowEl);
        return;
    }

    if (rowEl.classList.contains('road-transport-params-row')) {
        handleRoadModule1TransportParamsResetClick(rowEl);
        return;
    }

    if (rowEl.classList.contains('road-paired-share-row')) {
        handleRoadModule1PairedFuelShareResetClick(rowEl);
        return;
    }

    if (rowEl.classList.contains('road-sales-share-mix-row')) {
        handleRoadModule1SalesShareMixResetClick(rowEl);
        return;
    }

    if (rowEl.classList.contains('road-shared-utilisation-row')) {
        resetRoadSimpleSharedOverrideRow(rowEl, State.roadModule1.sharedUtilisationOverrides, 'sharedUtilisationKey');
        return;
    }

    if (rowEl.classList.contains('road-shared-mileage-row')) {
        resetRoadSimpleSharedOverrideRow(rowEl, State.roadModule1.sharedMileageOverrides, 'sharedMileageKey');
        return;
    }

    if (rowEl.classList.contains('road-shared-fe-row')) {
        const sgEl = event.target.closest('.road-shared-fe-subgroup');
        const subgroups = sgEl ? [sgEl] : rowEl.querySelectorAll('.road-shared-fe-subgroup');
        subgroups.forEach(sg => {
            const sharedKey = decodeURIComponent(sg.dataset.sharedFeKey || '');
            sg.querySelectorAll('.road-year-input').forEach(yearEl => {
                State.roadModule1.sharedFuelEconomyOverrides.delete(buildRoadSharedOverrideMapKey(sharedKey, yearEl.dataset.year));
                const input = yearEl.querySelector('.road-value-input');
                if (input) input.value = '';
            });
            const commentInput = sg.querySelector('.road-comment-input');
            if (commentInput) commentInput.value = '';
        });
        rowEl.classList.remove('is-edited');
        updateRoadModule1OverrideCount();
        renderRoadModule1Inputs();
        scheduleRoadModule1DraftSave();
        return;
    }

    const encodedRowKey = rowEl.dataset.key;
    if (!encodedRowKey) return;
    const rowKey = decodeURIComponent(encodedRowKey);
    rowEl.querySelectorAll('.road-year-input').forEach(yearEl => {
        State.roadModule1.overrides.delete(`${rowKey}||Year=${yearEl.dataset.year}`);
        const input = yearEl.querySelector('.road-value-input');
        if (input) input.value = '';
    });
    const commentInput = rowEl.querySelector('.road-comment-input');
    if (commentInput) commentInput.value = '';
    rowEl.classList.remove('is-edited');
    updateRoadModule1OverrideCount();
    renderRoadModule1Inputs();
    scheduleRoadModule1DraftSave();
}

function handleRoadModule1PairedFuelShareInputChange(rowEl, target) {
    const rowRefs = JSON.parse(decodeURIComponent(rowEl.dataset.rowRefs || '%5B%5D'));
    const commentInput = rowEl.querySelector('.road-comment-input');
    const comment = commentInput ? commentInput.value.trim() : '';
    const role = target.dataset.shareRole || '';
    const isCommentInput = target.classList.contains('road-comment-input');

    if (isCommentInput) {
        rowEl.classList.toggle('is-edited', Boolean(comment) || rowRefs.some(ref => {
            const existing = State.roadModule1.overrides.get(`${ref.rowKey}||Year=${ref.year}`);
            return existing && existing.value !== null && existing.value !== '';
        }));
        if (comment) {
            rowRefs.forEach(ref => {
                const key = `${ref.rowKey}||Year=${ref.year}`;
                const existing = State.roadModule1.overrides.get(key);
                if (existing) existing.comment = comment;
            });
        }
        updateRoadModule1OverrideCount();
        scheduleRoadModule1DraftSave();
        return;
    }

    const rawValue = target.value.trim();
    const parsedValue = rawValue === '' ? null : Number(rawValue);
    if (rawValue !== '' && !Number.isFinite(parsedValue)) return;

    const refByRole = (wantedRole) => rowRefs.find(ref => ref.role === wantedRole) || null;
    const setOverride = (ref, nextValue) => {
        if (!ref) return;
        const key = `${ref.rowKey}||Year=${ref.year}`;
        if (nextValue === null || nextValue === undefined || nextValue === '') {
            State.roadModule1.overrides.delete(key);
            return;
        }
        State.roadModule1.overrides.set(key, {
            key: ref.keyPayload,
            year: ref.year,
            value: nextValue,
            comment: comment
        });
    };
    const shareInputDefaultForRole = (wantedRole) => {
        const input = rowEl.querySelector(`[data-share-role="${wantedRole}"] .road-value-input`);
        return input?.dataset.defaultValue || '';
    };

    if (role === 'gasoline' || role === 'diesel') {
        const total = 1.0;
        const safeValue = Math.min(Math.max(parsedValue === null ? 0 : parsedValue, 0), total);
        const complementaryValue = Math.max(0, total - safeValue);

        target.value = safeValue;

        if (role === 'gasoline') {
            setOverride(refByRole('gasoline'), roadInputValueDiffersFromDefault(safeValue, shareInputDefaultForRole('gasoline')) ? safeValue : '');
            setOverride(refByRole('diesel'), roadInputValueDiffersFromDefault(complementaryValue, shareInputDefaultForRole('diesel')) ? complementaryValue : '');
        } else {
            setOverride(refByRole('diesel'), roadInputValueDiffersFromDefault(safeValue, shareInputDefaultForRole('diesel')) ? safeValue : '');
            setOverride(refByRole('gasoline'), roadInputValueDiffersFromDefault(complementaryValue, shareInputDefaultForRole('gasoline')) ? complementaryValue : '');
        }

        const gasolineInput = rowEl.querySelector('[data-share-role="gasoline"] .road-value-input');
        const dieselInput = rowEl.querySelector('[data-share-role="diesel"] .road-value-input');
        if (gasolineInput && document.activeElement !== gasolineInput) {
            gasolineInput.value = role === 'gasoline' ? safeValue : complementaryValue;
        }
        if (dieselInput && document.activeElement !== dieselInput) {
            dieselInput.value = role === 'diesel' ? safeValue : complementaryValue;
        }
    } else if (role === 'tolerance') {
        const toleranceValue = parsedValue === null ? '' : Math.max(0, parsedValue);
        target.value = toleranceValue;
        setOverride(refByRole('tolerance'), roadInputValueDiffersFromDefault(toleranceValue, shareInputDefaultForRole('tolerance')) ? toleranceValue : '');
    }

    if (comment) {
        rowRefs.forEach(ref => {
            const key = `${ref.rowKey}||Year=${ref.year}`;
            const existing = State.roadModule1.overrides.get(key);
            if (existing) existing.comment = comment;
        });
    }

    rowEl.classList.toggle('is-edited', Boolean(comment) || rowRefs.some(ref => {
        const existing = State.roadModule1.overrides.get(`${ref.rowKey}||Year=${ref.year}`);
        return existing && existing.value !== null && existing.value !== '';
    }));
    updateRoadModule1OverrideCount();
    scheduleRoadModule1DraftSave();
}

function handleRoadModule1SalesShareMixInputChange(rowEl) {
    const rowRefs = JSON.parse(decodeURIComponent(rowEl.dataset.rowRefs || '%5B%5D'));
    const commentInput = rowEl.querySelector('.road-comment-input');
    const comment = commentInput ? commentInput.value.trim() : '';
    let rowOverrideCount = 0;

    rowRefs.forEach(ref => {
        (ref.yearRefs || []).forEach(yearRef => {
            (yearRef.refs || []).forEach(rowRef => {
                State.roadModule1.overrides.delete(`${rowRef.rowKey}||Year=${yearRef.year}`);
            });
        });
    });

    rowEl.querySelectorAll('.road-sales-share-series').forEach(seriesEl => {
        const yearRefs = JSON.parse(decodeURIComponent(seriesEl.dataset.yearRefs || '%5B%5D'));
        const seriesInput = seriesEl.querySelector('.road-sales-share-series-input');
        const values = parseRoadSalesShareSeriesValues(seriesInput ? seriesInput.value : '');
        const defaultValues = parseRoadSalesShareSeriesValues(seriesInput?.dataset.defaultSeries || '');
        values.slice(0, yearRefs.length).forEach((value, index) => {
            if (!value) return;
            if (!roadInputValueDiffersFromDefault(value, defaultValues[index] || '')) return;
            const yearRef = yearRefs[index];
            (yearRef.refs || []).forEach(rowRef => {
                State.roadModule1.overrides.set(`${rowRef.rowKey}||Year=${yearRef.year}`, {
                    key: rowRef.keyPayload,
                    year: yearRef.year,
                    value: value,
                    comment: comment
                });
                rowOverrideCount += 1;
            });
        });
    });

    if (comment) {
        rowRefs.forEach(ref => {
            (ref.yearRefs || []).forEach(yearRef => {
                (yearRef.refs || []).forEach(rowRef => {
                    const existing = State.roadModule1.overrides.get(`${rowRef.rowKey}||Year=${yearRef.year}`);
                    if (existing) existing.comment = comment;
                });
            });
        });
    }

    rowEl.classList.toggle('is-edited', rowOverrideCount > 0 || comment.length > 0);
    updateRoadModule1OverrideCount();
    updateRoadSalesShareSeriesCharts(rowEl);
    scheduleRoadModule1DraftSave();
}

function handleRoadModule1SalesShareMixResetClick(rowEl) {
    const rowRefs = JSON.parse(decodeURIComponent(rowEl.dataset.rowRefs || '%5B%5D'));
    rowRefs.forEach(ref => {
        (ref.yearRefs || []).forEach(yearRef => {
            (yearRef.refs || []).forEach(rowRef => {
                State.roadModule1.overrides.delete(`${rowRef.rowKey}||Year=${yearRef.year}`);
            });
        });
    });
    rowEl.querySelectorAll('.road-sales-share-series-input').forEach(input => { input.value = ''; });
    const commentInput = rowEl.querySelector('.road-comment-input');
    if (commentInput) commentInput.value = '';
    rowEl.classList.remove('is-edited');
    updateRoadModule1OverrideCount();
    renderRoadModule1Inputs();
    scheduleRoadModule1DraftSave();
}

function handleRoadModule1PairedFuelShareResetClick(rowEl) {
    const rowRefs = JSON.parse(decodeURIComponent(rowEl.dataset.rowRefs || '%5B%5D'));
    rowRefs.forEach(ref => {
        State.roadModule1.overrides.delete(`${ref.rowKey}||Year=${ref.year}`);
    });

    const gasolineInput = rowEl.querySelector('[data-share-role="gasoline"] .road-value-input');
    const dieselInput = rowEl.querySelector('[data-share-role="diesel"] .road-value-input');
    const toleranceInput = rowEl.querySelector('[data-share-role="tolerance"] .road-value-input');
    if (gasolineInput) gasolineInput.value = '';
    if (dieselInput) dieselInput.value = '';
    if (toleranceInput) toleranceInput.value = '';

    const commentInput = rowEl.querySelector('.road-comment-input');
    if (commentInput) commentInput.value = '';

    rowEl.classList.remove('is-edited');
    updateRoadModule1OverrideCount();
    renderRoadModule1Inputs();
    scheduleRoadModule1DraftSave();
}

function handleRoadModule1TransportParamsInputChange(rowEl) {
    const commentInput = rowEl.querySelector('.road-comment-input');
    const comment = commentInput ? commentInput.value.trim() : '';
    let overrideCount = 0;

    rowEl.querySelectorAll('.road-transport-param-input').forEach(yearEl => {
        const rowKey = decodeURIComponent(yearEl.dataset.rowKey || '');
        const keyPayload = JSON.parse(decodeURIComponent(yearEl.dataset.keyPayload || '{}'));
        const year = yearEl.dataset.year;
        const key = `${rowKey}||Year=${year}`;
        const valueInput = yearEl.querySelector('.road-value-input');
        const boolToggle = yearEl.querySelector('.road-boolean-toggle');

        let value = '';
        let shouldPersist = false;

        if (boolToggle) {
            const activeBtn = boolToggle.querySelector('.road-boolean-btn.is-active');
            const currentBool = activeBtn ? activeBtn.dataset.value === '1' : false;
            const defaultBool = boolToggle.dataset.defaultBool === '1';
            value = currentBool ? '1' : '0';
            shouldPersist = currentBool !== defaultBool || comment.length > 0;
        } else {
            value = valueInput ? valueInput.value.trim() : '';
            shouldPersist = Boolean(value) && roadInputValueDiffersFromDefault(value, valueInput?.dataset.defaultValue || '');
        }

        if (!shouldPersist) {
            State.roadModule1.overrides.delete(key);
            return;
        }

        State.roadModule1.overrides.set(key, {
            key: keyPayload,
            year: year,
            value: value,
            comment: comment
        });
        overrideCount += 1;
    });

    rowEl.classList.toggle('is-edited', overrideCount > 0 || comment.length > 0);
    updateRoadModule1OverrideCount();
    scheduleRoadModule1DraftSave();
}

function handleRoadModule1TransportParamsResetClick(rowEl) {
    rowEl.querySelectorAll('.road-transport-param-input').forEach(yearEl => {
        const rowKey = decodeURIComponent(yearEl.dataset.rowKey || '');
        const year = yearEl.dataset.year;
        State.roadModule1.overrides.delete(`${rowKey}||Year=${year}`);
        const input = yearEl.querySelector('.road-value-input');
        if (input) input.value = '';
        const boolToggle = yearEl.querySelector('.road-boolean-toggle');
        if (boolToggle) {
            const defaultBool = boolToggle.dataset.defaultBool === '1';
            boolToggle.querySelectorAll('.road-boolean-btn').forEach(b => {
                b.classList.toggle('is-active', b.dataset.value === (defaultBool ? '1' : '0'));
            });
        }
    });
    const commentInput = rowEl.querySelector('.road-comment-input');
    if (commentInput) commentInput.value = '';
    rowEl.classList.remove('is-edited');
    updateRoadModule1OverrideCount();
    renderRoadModule1Inputs();
    scheduleRoadModule1DraftSave();
}

function handleRoadModule1ReconciliationInputChange(rowEl, target) {
    const rowRefs = JSON.parse(decodeURIComponent(rowEl.dataset.rowRefs || '%5B%5D'));
    const commentInput = rowEl.querySelector('.road-comment-input');
    const comment = commentInput ? commentInput.value.trim() : '';
    const role = target.dataset.reconciliationRole || '';
    const isCommentInput = target.classList.contains('road-comment-input');

    const refByRole = (wantedRole) => rowRefs.find(ref => ref.role === wantedRole) || null;
    const setOverride = (ref, nextValue) => {
        if (!ref) return;
        const key = `${ref.rowKey}||Year=${ref.year}`;
        if (nextValue === null || nextValue === undefined || nextValue === '') {
            State.roadModule1.overrides.delete(key);
            return;
        }
        State.roadModule1.overrides.set(key, {
            key: ref.keyPayload,
            year: ref.year,
            value: nextValue,
            comment: comment
        });
    };

    if (isCommentInput) {
        rowEl.classList.toggle('is-edited', Boolean(comment) || rowRefs.some(ref => {
            const existing = State.roadModule1.overrides.get(`${ref.rowKey}||Year=${ref.year}`);
            return existing && existing.value !== null && existing.value !== '';
        }));
        if (comment) {
            rowRefs.forEach(ref => {
                const key = `${ref.rowKey}||Year=${ref.year}`;
                const existing = State.roadModule1.overrides.get(key);
                if (existing) existing.comment = comment;
            });
        }
        updateRoadModule1OverrideCount();
        scheduleRoadModule1DraftSave();
        return;
    }

    const rawValue = target.value.trim();
    const parsedValue = rawValue === '' ? null : Number(rawValue);
    if (rawValue !== '' && !Number.isFinite(parsedValue)) return;

    if (role) {
        const nextValue = parsedValue === null ? '' : parsedValue;
        setOverride(refByRole(role), roadInputValueDiffersFromDefault(nextValue, target?.dataset.defaultValue || '') ? nextValue : '');
    }

    if (comment) {
        rowRefs.forEach(ref => {
            const key = `${ref.rowKey}||Year=${ref.year}`;
            const existing = State.roadModule1.overrides.get(key);
            if (existing) existing.comment = comment;
        });
    }

    rowEl.classList.toggle('is-edited', Boolean(comment) || rowRefs.some(ref => {
        const existing = State.roadModule1.overrides.get(`${ref.rowKey}||Year=${ref.year}`);
        return existing && existing.value !== null && existing.value !== '';
    }));
    updateRoadModule1OverrideCount();
    scheduleRoadModule1DraftSave();
}

function handleRoadModule1ReconciliationResetClick(rowEl) {
    const rowRefs = JSON.parse(decodeURIComponent(rowEl.dataset.rowRefs || '%5B%5D'));
    rowRefs.forEach(ref => {
        State.roadModule1.overrides.delete(`${ref.rowKey}||Year=${ref.year}`);
    });

    rowEl.querySelectorAll('.road-year-input .road-value-input').forEach(input => {
        input.value = '';
    });

    const commentInput = rowEl.querySelector('.road-comment-input');
    if (commentInput) commentInput.value = '';

    rowEl.classList.remove('is-edited');
    updateRoadModule1OverrideCount();
    renderRoadModule1Inputs();
    scheduleRoadModule1DraftSave();
}

function handleRoadModule1TurnoverCalibrationInputChange(rowEl, target) {
    const rowRefs = JSON.parse(decodeURIComponent(rowEl.dataset.rowRefs || '%5B%5D'));
    const commentInput = rowEl.querySelector('.road-comment-input');
    const comment = commentInput ? commentInput.value.trim() : '';
    const role = target.dataset.turnoverRole || '';
    const isCommentInput = target.classList.contains('road-comment-input');

    const refByRole = (wantedRole) => rowRefs.find(ref => ref.role === wantedRole) || null;
    const setOverride = (ref, nextValue) => {
        if (!ref) return;
        const key = `${ref.rowKey}||Year=${ref.year}`;
        if (nextValue === null || nextValue === undefined || nextValue === '') {
            State.roadModule1.overrides.delete(key);
            return;
        }
        State.roadModule1.overrides.set(key, {
            key: ref.keyPayload,
            year: ref.year,
            value: nextValue,
            comment: comment
        });
    };
    if (isCommentInput) {
        rowEl.classList.toggle('is-edited', Boolean(comment) || rowRefs.some(ref => {
            const existing = State.roadModule1.overrides.get(`${ref.rowKey}||Year=${ref.year}`);
            return existing && existing.value !== null && existing.value !== '';
        }));
        if (comment) {
            rowRefs.forEach(ref => {
                const existing = State.roadModule1.overrides.get(`${ref.rowKey}||Year=${ref.year}`);
                if (existing) existing.comment = comment;
            });
        }
        updateRoadModule1OverrideCount();
        scheduleRoadModule1DraftSave();
        return;
    }

    const rawValue = target.value.trim();
    const parsedValue = rawValue === '' ? null : Number(rawValue);
    if (rawValue !== '' && !Number.isFinite(parsedValue)) return;

    if (role) {
        const nextValue = parsedValue === null ? '' : parsedValue;
        setOverride(refByRole(role), roadInputValueDiffersFromDefault(nextValue, target?.dataset.defaultValue || '') ? nextValue : '');
    }

    if (comment) {
        rowRefs.forEach(ref => {
            const existing = State.roadModule1.overrides.get(`${ref.rowKey}||Year=${ref.year}`);
            if (existing) existing.comment = comment;
        });
    }

    rowEl.classList.toggle('is-edited', Boolean(comment) || rowRefs.some(ref => {
        const existing = State.roadModule1.overrides.get(`${ref.rowKey}||Year=${ref.year}`);
        return existing && existing.value !== null && existing.value !== '';
    }));
    updateRoadModule1OverrideCount();
    scheduleRoadModule1DraftSave();
}

function handleRoadModule1TurnoverCalibrationResetClick(rowEl) {
    const rowRefs = JSON.parse(decodeURIComponent(rowEl.dataset.rowRefs || '%5B%5D'));
    rowRefs.forEach(ref => {
        State.roadModule1.overrides.delete(`${ref.rowKey}||Year=${ref.year}`);
    });

    rowEl.querySelectorAll('.road-year-input .road-value-input').forEach(input => {
        input.value = '';
    });

    const commentInput = rowEl.querySelector('.road-comment-input');
    if (commentInput) commentInput.value = '';

    rowEl.classList.remove('is-edited');
    updateRoadModule1OverrideCount();
    renderRoadModule1Inputs();
    scheduleRoadModule1DraftSave();
}

function handleRoadModule1SeriesInputChange(rowEl) {
    const commentInput = rowEl.querySelector('.road-comment-input');
    const comment = commentInput.value.trim();
    const seriesInput = rowEl.querySelector('.road-series-input');
    const rowRefs = getRoadSeriesRowRefs(rowEl);
    const values = parseRoadSeriesValues(seriesInput ? seriesInput.value : '');
    const defaultValues = parseRoadSeriesValues(seriesInput?.dataset.defaultSeries || '');
    let rowOverrideCount = 0;

    rowRefs.forEach(ref => {
        State.roadModule1.overrides.delete(`${ref.rowKey}||Year=${ref.year}`);
    });

    values.slice(0, rowRefs.length).forEach((value, index) => {
        const ref = rowRefs[index];
        const key = `${ref.rowKey}||Year=${ref.year}`;

        if (!value) {
            return;
        }
        if (!roadInputValueDiffersFromDefault(value, defaultValues[index] || '')) {
            return;
        }

        State.roadModule1.overrides.set(key, {
            key: ref.keyPayload,
            year: ref.year,
            value: value || null,
            comment: comment
        });
        rowOverrideCount += 1;
    });

    if (comment) {
        rowRefs.forEach(ref => {
            const key = `${ref.rowKey}||Year=${ref.year}`;
            const existing = State.roadModule1.overrides.get(key);
            if (existing) existing.comment = comment;
        });
    }

    rowEl.classList.toggle('is-edited', rowOverrideCount > 0 || comment.length > 0);
    updateRoadModule1OverrideCount();
    updateRoadSeriesChart(rowEl);
    scheduleRoadModule1DraftSave();
}

async function saveRoadModule1ResearcherOutput() {
    if (!State.roadModule1.version || !State.roadModule1.economy) {
        showCustomToast("Defaults are not loaded yet. Select economy/scenario and wait.", "warning");
        return;
    }

    const overrides = buildRoadModule1ExportOverrides();
    const originalButtonText = DOM.roadSaveOutput.innerText;

    DOM.roadSaveOutput.disabled = true;
    DOM.roadSaveOutput.innerText = "Downloading...";
    DOM.roadSaveStatus.innerText = "Preparing download from current values...";
    showLoading("Preparing Download...");
    try {
        const completedLongRows = buildRoadModule1CompletedLongRowsForHandoff();
        exportRoadModule1LongRowsCsvClientSide(completedLongRows, State.roadModule1.economy);

        DOM.roadSaveStatus.innerText = [
            'CSV download started.',
            `Rows: ${completedLongRows.length.toLocaleString('en-US')}`,
            `Changed values: ${overrides.length.toLocaleString('en-US')}`
        ].join('\n');

        clearRoadModule1Draft();
        showCustomToast('CSV downloaded.', 'success', 5000);
    } catch (error) {
        showCustomToast("Failed to download CSV: " + error.message, "error");
        DOM.roadSaveStatus.innerText = "Failed to download CSV: " + error.message;
    } finally {
        DOM.roadSaveOutput.disabled = false;
        DOM.roadSaveOutput.innerText = originalButtonText;
        hideLoading();
    }
}

function triggerRoadModule1ResearcherOutputDownload(url) {
    const link = document.createElement('a');
    link.href = url;
    link.download = '';
    link.style.display = 'none';
    document.body.appendChild(link);
    link.click();
    link.remove();
}

// ==========================================
// ROAD MODEL RUNNER
// ==========================================

// Same origin logic as api.js — relative on any real server, absolute for local file:// dev.
const ROAD_MODEL_API_BASE = `${typeof _API_ORIGIN !== 'undefined' ? _API_ORIGIN : (location.protocol === 'file:' ? 'http://localhost:8000' : '')}/api/v1/road-module1`;

let _roadRunEventSource = null;

function showRoadRunLogModal() {
    if (!DOM.roadRunLogModal) return;
    DOM.roadRunLogModal.classList.remove('hidden');
    requestAnimationFrame(() => {
        DOM.roadRunLogModal.classList.add('flex');
        DOM.roadRunLogModal.classList.remove('opacity-0');
        const card = DOM.roadRunLogModal.querySelector('[class*="scale-95"]');
        if (card) card.classList.remove('scale-95');
    });
}

function hideRoadRunLogModal() {
    if (!DOM.roadRunLogModal) return;
    DOM.roadRunLogModal.classList.add('opacity-0');
    const card = DOM.roadRunLogModal.querySelector('div');
    if (card) card.classList.add('scale-95');
    setTimeout(() => {
        DOM.roadRunLogModal.classList.add('hidden');
        DOM.roadRunLogModal.classList.remove('flex');
    }, 200);
}


function showRoadVariableMapModal() {
    if (!DOM.roadVariableMapModal) return;
    DOM.roadVariableMapModal.classList.remove('hidden');
    requestAnimationFrame(() => {
        DOM.roadVariableMapModal.classList.add('flex');
        DOM.roadVariableMapModal.classList.remove('opacity-0');
        const card = DOM.roadVariableMapModal.querySelector('[class*="scale-95"]');
        if (card) card.classList.remove('scale-95');
    });
}

function hideRoadVariableMapModal() {
    if (!DOM.roadVariableMapModal) return;
    DOM.roadVariableMapModal.classList.add('opacity-0');
    const card = DOM.roadVariableMapModal.querySelector('div');
    if (card) card.classList.add('scale-95');
    setTimeout(() => {
        DOM.roadVariableMapModal.classList.add('hidden');
        DOM.roadVariableMapModal.classList.remove('flex');
    }, 200);
}

function _setRoadRunStatus(status) {
    if (!DOM.roadRunLogTitle || !DOM.roadRunLogSpinner || !DOM.roadRunLogClose) return;

    if (status === 'running') {
        DOM.roadRunLogTitle.innerText = 'Running Road Model…';
        DOM.roadRunLogSpinner.classList.remove('hidden', 'border-green-500', 'border-red-500');
        DOM.roadRunLogSpinner.classList.add('border-indigo-500', 'animate-spin');
        DOM.roadRunLogClose.disabled = true;
    } else if (status === 'success') {
        DOM.roadRunLogTitle.innerText = 'Road Model Complete';
        DOM.roadRunLogSpinner.classList.remove('animate-spin', 'border-indigo-500', 'border-red-500');
        DOM.roadRunLogSpinner.classList.add('border-green-500');
        DOM.roadRunLogClose.disabled = false;
    } else {
        DOM.roadRunLogTitle.innerText = 'Road Model Failed';
        DOM.roadRunLogSpinner.classList.remove('animate-spin', 'border-indigo-500', 'border-green-500');
        DOM.roadRunLogSpinner.classList.add('border-red-500');
        DOM.roadRunLogClose.disabled = false;
    }
}

function _appendRoadRunLog(text, isStderr = false) {
    if (!DOM.roadRunLogOutput) return;
    const line = document.createElement('span');
    line.className = isStderr ? 'text-yellow-400' : '';
    line.innerText = text + '\n';
    DOM.roadRunLogOutput.appendChild(line);
    DOM.roadRunLogOutput.scrollTop = DOM.roadRunLogOutput.scrollHeight;
}

async function runRoadModel() {
    if (!State.roadModule1.version || !State.roadModule1.economy) {
        showCustomToast("Load road model data first.", "warning");
        return;
    }

    const domEconomy = DOM.roadEconomySelect?.value;
    if (domEconomy && domEconomy !== State.roadModule1.economy) {
        showCustomToast(`Economy selection changed to ${domEconomy} — wait for data to finish loading before running.`, "warning");
        return;
    }

    if (_roadRunEventSource) {
        _roadRunEventSource.close();
        _roadRunEventSource = null;
    }

    if (DOM.roadRunLogOutput) DOM.roadRunLogOutput.innerHTML = '';
    if (DOM.roadRunLogDashboard) DOM.roadRunLogDashboard.classList.add('hidden');
    if (DOM.roadRunLogWorkbook) DOM.roadRunLogWorkbook.classList.add('hidden');
    if (DOM.roadRunLogLifecycleProfiles) DOM.roadRunLogLifecycleProfiles.classList.add('hidden');
    if (DOM.roadRunLogReimportCsv) DOM.roadRunLogReimportCsv.classList.add('hidden');
    _setRoadRunStatus('running');
    showRoadRunLogModal();

    const completedRows = buildRoadModule1CompletedRowsForCheckpoint();
    const completedLongRows = buildRoadModule1CompletedLongRowsForHandoff();
    const projectionScenarios = getRoadRunScenarioLabels();
    if (projectionScenarios.length === 0) {
        _appendRoadRunLog('Select at least one projection scenario to run.', true);
        _setRoadRunStatus('error');
        return;
    }
    const unknownScenarios = projectionScenarios.filter(scenario => !isRoadConfiguredProjectionScenario(scenario));
    if (unknownScenarios.length > 0) {
        _appendRoadRunLog(`Unknown scenario label(s): ${unknownScenarios.join(', ')}`, true);
        _setRoadRunStatus('error');
        return;
    }
    _appendRoadRunLog(`Sending ${completedLongRows.length.toLocaleString('en-US')} long rows for scenarios ${projectionScenarios.join(', ')} to backend...`);

    let runId, economyCanonical;

    try {
        const resp = await fetch(`${ROAD_MODEL_API_BASE}/run-model`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                economy: State.roadModule1.economy,
                version: State.roadModule1.version,
                rows: completedLongRows,
                scenarios: projectionScenarios,
                enable_visualisations: true,
                turnover_config: buildRoadTurnoverConfigPayload(completedRows)
            })
        });

        if (!resp.ok) {
            const err = await resp.json().catch(() => ({ detail: resp.statusText }));
            _appendRoadRunLog(`Error: ${err.detail || resp.statusText}`, true);
            if (err.detail && err.detail.includes('leap_road_model')) {
                _appendRoadRunLog('Ensure leap_road_model is cloned as a sibling of this repo.', true);
            }
            _setRoadRunStatus('error');
            return;
        }

        const data = await resp.json();
        runId = data.run_id;
        economyCanonical = data.economy_canonical;
        _appendRoadRunLog(`Module 1 CSV saved. Starting road_workflow for ${economyCanonical}…`);
    } catch (err) {
        _appendRoadRunLog(`Cannot reach backend at ${ROAD_MODEL_API_BASE}.`, true);
        _appendRoadRunLog('Start the backend server: cd back-end && python run.py', true);
        _setRoadRunStatus('error');
        return;
    }

    const streamUrl = `${ROAD_MODEL_API_BASE}/run-model-stream?run_id=${encodeURIComponent(runId)}`;
    const evtSource = new EventSource(streamUrl);
    _roadRunEventSource = evtSource;

    evtSource.onmessage = (event) => {
        let data;
        try { data = JSON.parse(event.data); } catch { return; }

        if (data.type === 'log') {
            _appendRoadRunLog(data.text, data.source === 'stderr');
        } else if (data.type === 'done') {
            evtSource.close();
            _roadRunEventSource = null;
            if (data.return_code === 0) {
                _setRoadRunStatus('success');
                _appendRoadRunLog(`\nCompleted successfully.`);
                const _econ = (State.roadModule1.economy || '').replace(/^(\d+)([A-Za-z].*)$/, '$1_$2');
                const _rawDashPath = data.dashboard_url || null;
                if (_rawDashPath && DOM.roadRunLogDashboard) {
                    const dashUrl = `${typeof _API_ORIGIN !== 'undefined' ? _API_ORIGIN : ''}${_rawDashPath}`;
                    DOM.roadRunLogDashboard.classList.remove('hidden');
                    DOM.roadRunLogDashboard.onclick = () => window.open(dashUrl, '_blank');
                    _appendRoadRunLog(`Dashboard: ${dashUrl}`);
                }
                if (data.workbook_url && DOM.roadRunLogWorkbook) {
                    const wbUrl = `${typeof _API_ORIGIN !== 'undefined' ? _API_ORIGIN : ''}${data.workbook_url}`;
                    DOM.roadRunLogWorkbook.classList.remove('hidden');
                    DOM.roadRunLogWorkbook.href = wbUrl;
                    _appendRoadRunLog(`LEAP workbook: ${wbUrl}`);
                }
                if (data.lifecycle_profiles_url && DOM.roadRunLogLifecycleProfiles) {
                    const lifecycleUrl = `${typeof _API_ORIGIN !== 'undefined' ? _API_ORIGIN : ''}${data.lifecycle_profiles_url}`;
                    DOM.roadRunLogLifecycleProfiles.classList.remove('hidden');
                    DOM.roadRunLogLifecycleProfiles.href = lifecycleUrl;
                    _appendRoadRunLog(`Lifecycle profiles: ${lifecycleUrl}`);
                }
                if (data.reimport_csv_url && DOM.roadRunLogReimportCsv) {
                    const reimportUrl = `${typeof _API_ORIGIN !== 'undefined' ? _API_ORIGIN : ''}${data.reimport_csv_url}`;
                    DOM.roadRunLogReimportCsv.classList.remove('hidden');
                    DOM.roadRunLogReimportCsv.href = reimportUrl;
                    _appendRoadRunLog(`Reconciled inputs CSV: ${reimportUrl}`);
                }
            } else {
                _setRoadRunStatus('error');
                _appendRoadRunLog(`\nProcess exited with code ${data.return_code}.`, true);
            }
        } else if (data.type === 'error') {
            evtSource.close();
            _roadRunEventSource = null;
            _setRoadRunStatus('error');
            _appendRoadRunLog(`Error: ${data.message}`, true);
        }
    };

    evtSource.onerror = () => {
        evtSource.close();
        _roadRunEventSource = null;
        if (DOM.roadRunLogClose && !DOM.roadRunLogClose.disabled) return;
        _setRoadRunStatus('error');
        _appendRoadRunLog('Connection to model runner lost.', true);
    };
}

function parseCsvLine(line) {
    const values = [];
    let current = '';
    let inQuotes = false;

    for (let i = 0; i < line.length; i += 1) {
        const ch = line[i];
        if (ch === '"') {
            if (inQuotes && line[i + 1] === '"') {
                current += '"';
                i += 1;
            } else {
                inQuotes = !inQuotes;
            }
        } else if (ch === ',' && !inQuotes) {
            values.push(current);
            current = '';
        } else {
            current += ch;
        }
    }
    values.push(current);
    return values.map(value => value.trim());
}

function parseCsvText(csvText) {
    const lines = String(csvText || '')
        .split(/\r?\n/)
        .filter(line => line.trim().length > 0);
    if (lines.length === 0) return [];

    const headers = parseCsvLine(lines[0]);
    return lines.slice(1).map(line => {
        const cells = parseCsvLine(line);
        const row = {};
        headers.forEach((header, idx) => {
            row[header] = cells[idx] ?? '';
        });
        return row;
    });
}

function rowHasRoadModule1RequiredColumns(row) {
    if (!row || typeof row !== 'object') return false;
    return ROAD_MODULE1_REQUIRED_KEY_COLUMNS.every(column => Object.prototype.hasOwnProperty.call(row, column));
}

function normalizeRoadTextToken(value) {
    return String(value ?? '').trim().toLowerCase();
}

function normalizeRoadNumber(value) {
    if (value === null || value === undefined || String(value).trim() === '') return null;
    const numeric = Number(String(value).replace(/,/g, '').trim());
    return Number.isFinite(numeric) ? numeric : null;
}

function normalizeRoadBooleanish(value) {
    const normalized = String(value ?? '').trim().toLowerCase();
    return ['1', 'true', 'yes', 'y', 'on'].includes(normalized);
}

function getRoadModule1UploadContextDefaults() {
    const version = State.roadModule1.version || DOM.roadVersionSelect.value || '';
    const scenario = State.roadModule1.scenario || 'Current Accounts';
    const rows = Array.isArray(State.roadModule1.rows) ? State.roadModule1.rows : [];
    const regionFromLoadedRows = rows.length > 0 ? rows[0].Region : '';
    return {
        version,
        scenario,
        region: regionFromLoadedRows || ''
    };
}

function getRoadRowsByVariableAndTransport(variableName, transportType = 'all', scenario = 'Current Accounts') {
    const normalizedVariable = normalizeRoadTextToken(variableName);
    const normalizedTransport = normalizeRoadTextToken(transportType || 'all');
    const normalizedScenario = normalizeRoadTextToken(scenario || 'Current Accounts');

    return (State.roadModule1.rows || []).filter(row => {
        if (normalizeRoadTextToken(row.Variable) !== normalizedVariable) return false;
        if (normalizedScenario && normalizeRoadTextToken(row.Scenario) !== normalizedScenario) return false;

        const branchPath = normalizeRoadTextToken(row['Branch Path']);
        if (normalizedTransport === 'passenger') return branchPath.includes('passenger road');
        if (normalizedTransport === 'freight') return branchPath.includes('freight road');
        return true;
    });
}

function buildRoadRowsFromFactorsSheet(factorRows, contextDefaults) {
    if (!Array.isArray(factorRows) || factorRows.length === 0) return { rows: [], unmappedItems: [] };

    const parameterMap = {
        'phev_electric_utilisation_rate': 'PHEV Electric Driving Share',
        'passenger_stock_growth_rate_adjustment': 'Passenger Stock Growth Rate Adjustment',
        'freight_gdp_elasticity_adjustment': 'Freight GDP Elasticity Adjustment',
        'reconciliation_bound_lower': 'Reconciliation Bound Lower',
        'reconciliation_bound_upper': 'Reconciliation Bound Upper',
        'stock_reconciliation_weight': 'Reconciliation Weight',
        'mileage_reconciliation_weight': 'Reconciliation Weight',
        'efficiency_reconciliation_weight': 'Reconciliation Weight'
    };

    const generatedRows = [];
    const unmappedItems = [];

    factorRows.forEach(rawRow => {
        const parameter = normalizeRoadTextToken(rawRow.Parameter);
        const variable = parameterMap[parameter];
        if (!variable) return;

        const numericValue = normalizeRoadNumber(rawRow.Value);
        if (numericValue === null) return;

        const transportType = normalizeRoadTextToken(rawRow['Transport Type'] || 'all');
        const scenario = String(rawRow.Scenario || contextDefaults.scenario || 'Current Accounts').trim();

        const matchingRows = getRoadRowsByVariableAndTransport(variable, transportType, scenario);
        if (matchingRows.length === 0) {
            unmappedItems.push(`Factors: ${rawRow.Parameter || parameter} (transport=${transportType || 'all'}, scenario=${scenario})`);
        }
        matchingRows.forEach(match => {
            generatedRows.push({
                'Branch Path': match['Branch Path'],
                'Variable': match.Variable,
                'Scenario': match.Scenario,
                'Region': match.Region,
                [String(ROAD_MODULE1_BASE_YEAR)]: numericValue
            });
        });
    });

    return {
        rows: generatedRows,
        unmappedItems: unmappedItems
    };
}

function parseRoadProfilePointsFromLifecycleLikeSheet(sheetRows) {
    const profilePoints = new Map();
    let currentProfile = '';

    sheetRows.forEach(row => {
        const profileCell = row['Profile:'] ?? row['Profile'] ?? row.profile ?? '';
        const profileName = String(profileCell || '').trim();
        if (profileName) {
            currentProfile = profileName;
            if (!profilePoints.has(currentProfile)) profilePoints.set(currentProfile, []);
        }

        const yearRaw = row['Year'] ?? row['Age'] ?? row.year ?? row.age;
        const valueRaw = row['Value'] ?? row.value;
        const ageNumeric = normalizeRoadNumber(yearRaw);
        const valueNumeric = normalizeRoadNumber(valueRaw);
        if (!currentProfile || ageNumeric === null || valueNumeric === null) return;

        profilePoints.get(currentProfile).push({
            age: Number(ageNumeric),
            value: Number(valueNumeric)
        });
    });

    return profilePoints;
}

function buildRoadRowsFromLifecycleLikeSheet(sheetRows, lifecycleType, contextDefaults) {
    if (!Array.isArray(sheetRows) || sheetRows.length === 0) return { rows: [], unmappedItems: [] };

    const profilePoints = parseRoadProfilePointsFromLifecycleLikeSheet(sheetRows);
    const generatedRows = [];
    const unmappedItems = [];

    profilePoints.forEach((points, profileName) => {
        const normalizedProfile = normalizeRoadTextToken(profileName);
        const isPassenger = normalizedProfile.includes('passenger');
        const isFreight = normalizedProfile.includes('freight');
        const transportLabel = isPassenger ? 'Passenger road' : (isFreight ? 'Freight road' : '');
        if (!transportLabel) {
            unmappedItems.push(`${lifecycleType}: ${profileName} (unknown transport profile)`);
            return;
        }

        const variable = lifecycleType === 'lifecycle' ? 'Survival Rate' : 'Vintage Profile Share';

        points.forEach(point => {
            if (!Number.isFinite(point.age) || !Number.isFinite(point.value)) return;
            const ageInt = Math.trunc(point.age);
            const branchPath = `Demand\\${transportLabel}\\Age ${ageInt}`;

            const matchingRow = (State.roadModule1.rows || []).find(row =>
                row['Branch Path'] === branchPath
                && normalizeRoadTextToken(row.Variable) === normalizeRoadTextToken(variable)
                && normalizeRoadTextToken(row.Scenario) === normalizeRoadTextToken(contextDefaults.scenario || 'Current Accounts')
            );

            if (!matchingRow) {
                unmappedItems.push(`${lifecycleType}: ${profileName} age ${ageInt} (no canonical row found)`);
            }

            generatedRows.push({
                'Branch Path': branchPath,
                'Variable': variable,
                'Scenario': matchingRow?.Scenario || contextDefaults.scenario || 'Current Accounts',
                'Region': matchingRow?.Region || contextDefaults.region || '',
                [String(ROAD_MODULE1_BASE_YEAR)]: point.value
            });
        });
    });

    return {
        rows: generatedRows,
        unmappedItems: unmappedItems
    };
}

function dedupeRoadUploadRows(rows) {
    const map = new Map();
    rows.forEach(row => {
        if (!rowHasRoadModule1RequiredColumns(row)) return;
        const key = getRoadModule1ComparableKeyFromRow(row);
        const existing = map.get(key) || {};
        map.set(key, { ...existing, ...row });
    });
    return Array.from(map.values());
}

async function readRoadModule1RowsFromUploadFile(file) {
    const fileName = String(file?.name || '').toLowerCase();
    const isCsv = fileName.endsWith('.csv');
    if (!isCsv) {
        throw new Error('Use a CSV file in the downloaded input format.');
    }

    const text = await file.text();
    const csvRows = parseCsvText(text);

    return {
        rows: csvRows,
        summary: {
            sourceSheet: 'CSV',
            keyedInputRows: csvRows.length,
            factorsMappedRows: 0,
            lifecycleMappedRows: 0,
            vintageMappedRows: 0,
            unmappedItems: []
        }
    };
}

function buildRoadUploadSummaryText(fileName, parseSummary, overlayResult) {
    const lines = [
        `File: ${fileName}`,
        '',
        'Parsed file content:',
        `- Primary row-key source: ${parseSummary?.sourceSheet || 'Unknown'}`,
        `- Row-key records read from CSV: ${(parseSummary?.keyedInputRows || 0).toLocaleString('en-US')}`,
        `- Additional rows mapped from Factors: ${(parseSummary?.factorsMappedRows || 0).toLocaleString('en-US')}`,
        `- Additional rows mapped from Lifecycle: ${(parseSummary?.lifecycleMappedRows || 0).toLocaleString('en-US')}`,
        `- Additional rows mapped from Vintage: ${(parseSummary?.vintageMappedRows || 0).toLocaleString('en-US')}`,
        '',
        'Applied to current browser state:',
        `- Row-year values applied: ${(overlayResult?.appliedCount || 0).toLocaleString('en-US')}`,
        `- Uploaded rows that did not match current template: ${(overlayResult?.unmatchedCount || 0).toLocaleString('en-US')}`,
        `- Value checks skipped (non-numeric/out-of-bounds): ${(overlayResult?.validationIssueCount || 0).toLocaleString('en-US')}`
    ];

    const unmappedItems = Array.isArray(parseSummary?.unmappedItems) ? parseSummary.unmappedItems : [];
    if (unmappedItems.length > 0) {
        lines.push('', 'Unmapped sheet items (not converted to canonical rows):');
        unmappedItems.slice(0, 50).forEach(item => lines.push(`- ${item}`));
        if (unmappedItems.length > 50) {
            lines.push(`- ...and ${(unmappedItems.length - 50).toLocaleString('en-US')} more`);
        }
    }

    const changedCells = Array.isArray(overlayResult?.changedCells) ? overlayResult.changedCells : [];
    if (changedCells.length > 0) {
        lines.push('', 'Changed cells:');
        changedCells.slice(0, 100).forEach(item => {
            lines.push(`- ${item.key}: ${item.oldValue} -> ${item.newValue}`);
        });
        if (changedCells.length > 100) {
            lines.push(`- ...and ${(changedCells.length - 100).toLocaleString('en-US')} more`);
        }
    }

    lines.push('', 'Recommended workflow: download CSV, fill the core columns, then upload it back. Blanks and missing optional values are ignored.');
    return lines.join('\n');
}

function buildRoadStockShareValidationSummary(rows) {
    const messages = [];
    const displayTolerance = 0.05;
    const scenarios = [...new Set((rows || [])
        .map(row => normaliseRoadScenarioLabel(row?.Scenario) || ROAD_MODULE1_CURRENT_ACCOUNTS)
        .filter(Boolean))];
    scenarios.forEach(scenario => {
        ['passenger', 'freight'].forEach(group => {
            ROAD_MODULE1_STOCK_SHARE_TARGET_YEARS.forEach(year => {
                const total = (rows || [])
                    .filter(row => normaliseRoadScenarioLabel(row?.Scenario) === scenario)
                    .filter(isRoadVehicleTypeStockShareRow)
                    .filter(row => Object.prototype.hasOwnProperty.call(row, String(year)))
                    .filter(row => getRoadStockShareTransportGroup(row) === group)
                    .reduce((sum, row) => {
                        const override = State.roadModule1.overrides.get(`${buildRoadModule1Key(row)}||Year=${year}`);
                        const value = override && override.value !== '' && override.value !== null
                            ? override.value
                            : getRoadDefaultValue(row, String(year));
                        const numeric = Number(value);
                        return Number.isFinite(numeric) ? sum + numeric : sum;
                    }, 0);
                if (Math.abs(total - 100) > displayTolerance && total !== 0) {
                    messages.push(`${scenario} ${group} Stock Share ${year} sums to ${total.toFixed(3)}; expected 100.`);
                }
            });
        });
    });
    return messages.join('\n');
}

function getRoadModule1ComparableKeyFromRow(rowLike) {
    const keyColumns = Object.prototype.hasOwnProperty.call(rowLike || {}, 'Economy')
        ? ROAD_MODULE1_LONG_KEY_COLUMNS
        : ROAD_MODULE1_REQUIRED_KEY_COLUMNS;
    return keyColumns
        .map(column => String(rowLike?.[column] ?? '').trim())
        .join('||');
}

function validateRoadModule1ValueForVariable(variable, numericValue) {
    const rule = ROAD_MODULE1_VALUE_RULES[variable];
    if (!rule) return '';
    if (rule.min !== undefined && numericValue < rule.min) {
        return `${variable} must be greater than or equal to ${rule.min}.`;
    }
    if (rule.max !== undefined && numericValue > rule.max) {
        return `${variable} must be less than or equal to ${rule.max}.`;
    }
    return '';
}

function getRoadModule1EditableYearColumnsFromRows(rows) {
    const years = new Set();
    rows.forEach(row => {
        Object.keys(row || {}).forEach(column => {
            if (/^\d{4}$/.test(column) && isRoadEditableYear(column)) {
                years.add(column);
            }
        });
    });
    return Array.from(years).sort();
}

function previewRoadModule1UploadedRows(uploadRows) {
    if (!Array.isArray(uploadRows) || uploadRows.length === 0) {
        throw new Error('Uploaded file has no data rows.');
    }

    const missingKeyColumns = ROAD_MODULE1_LONG_KEY_COLUMNS
        .filter(column => !Object.prototype.hasOwnProperty.call(uploadRows[0], column));
    if (missingKeyColumns.length > 0) {
        throw new Error(`Uploaded file is missing required columns: ${missingKeyColumns.join(', ')}`);
    }
    if (!Object.prototype.hasOwnProperty.call(uploadRows[0], 'Value')) {
        throw new Error('Uploaded file is missing required column: Value');
    }

    const seenUploadKeys = new Set();
    const uploadScenarios = new Set();
    uploadRows.forEach(uploadRow => {
        const key = getRoadModule1ComparableKeyFromRow(uploadRow);
        if (seenUploadKeys.has(key)) {
            throw new Error(`Uploaded file has duplicate row key: ${key}`);
        }
        seenUploadKeys.add(key);
        const scenario = normaliseRoadScenarioLabel(uploadRow.Scenario) || ROAD_MODULE1_CURRENT_ACCOUNTS;
        uploadScenarios.add(scenario);
    });

    let candidateRows = State.roadModule1.rows.map(row => ({ ...row }));
    uploadScenarios.forEach(scenario => {
        if (scenario !== ROAD_MODULE1_CURRENT_ACCOUNTS) {
            candidateRows = ensureRoadModule1ProjectionScenarioRows(scenario, candidateRows);
        }
    });

    const targetLongRows = [
        ...convertRoadWideUiRowsToLongRows(candidateRows, State.roadModule1.economy, true),
        ...(Array.isArray(State.roadModule1.hiddenRows) ? State.roadModule1.hiddenRows : [])
    ];
    const targetLongKeys = new Set(targetLongRows.map(row => getRoadModule1ComparableKeyFromRow(row)));
    const unmatchedRows = uploadRows.filter(uploadRow => !targetLongKeys.has(getRoadModule1ComparableKeyFromRow(uploadRow)));
    if (unmatchedRows.length > 0) {
        const sample = unmatchedRows.slice(0, 5).map(row => getRoadModule1ComparableKeyFromRow(row)).join('\n');
        throw new Error(`Uploaded file contains keys that are not in the current template. First unmatched keys:\n${sample}`);
    }

    const targetRows = candidateRows.map(row => ({ ...row }));
    const targetRowByKey = new Map(
        targetRows.map(row => [
            [row['Branch Path'] || '', row.Variable || '', row.Scenario || ''].join('||'),
            row
        ])
    );

    let appliedCount = 0;
    let validationIssueCount = 0;
    const changedCells = [];

    uploadRows.forEach(uploadRow => {
        const rowKey = [uploadRow['Branch Path'] || '', uploadRow.Variable || '', uploadRow.Scenario || ''].join('||');
        const targetRow = targetRowByKey.get(rowKey);
        if (!targetRow) return;

        const yearColumn = String(uploadRow.Year || '').trim();
        const rawValue = uploadRow.Value;
        if (rawValue === null || rawValue === undefined || String(rawValue).trim() === '') return;

        if (isRoadSalesShareRow(targetRow) && isRoadRemainderToken(rawValue)) {
            const oldValue = targetRow[yearColumn];
            if (String(oldValue ?? '').trim() === String(rawValue).trim()) return;
            targetRow[yearColumn] = String(rawValue).trim().toUpperCase();
            targetRow._inputStatus = 'researcher';
            if (Object.prototype.hasOwnProperty.call(uploadRow, 'Comment')) targetRow.notes = uploadRow.Comment || targetRow.notes || '';
            if (Object.prototype.hasOwnProperty.call(uploadRow, 'Source')) targetRow.source_name = uploadRow.Source || targetRow.source_name || '';
            appliedCount += 1;
            changedCells.push({
                key: getRoadModule1ComparableKeyFromRow(uploadRow),
                oldValue: oldValue ?? '',
                newValue: String(rawValue).trim().toUpperCase()
            });
            return;
        }

        const numericValue = Number(String(rawValue).replace(/,/g, '').trim());
        if (!Number.isFinite(numericValue)) {
            validationIssueCount += 1;
            return;
        }

        const validationMessage = validateRoadModule1ValueForVariable(String(targetRow.Variable || ''), numericValue);
        if (validationMessage) {
            validationIssueCount += 1;
            return;
        }

        const oldValue = targetRow[yearColumn];
        const oldScale = targetRow.Scale || '';
        const uploadedScale = Object.prototype.hasOwnProperty.call(uploadRow, 'Scale') ? (uploadRow.Scale || '') : oldScale;
        if (String(oldValue ?? '').trim() === String(numericValue) && String(oldScale).trim() === String(uploadedScale).trim()) return;
        targetRow[yearColumn] = numericValue;
        targetRow.Scale = uploadedScale;
        targetRow._inputStatus = 'researcher';
        if (Object.prototype.hasOwnProperty.call(uploadRow, 'Comment')) targetRow.notes = uploadRow.Comment || targetRow.notes || '';
        if (Object.prototype.hasOwnProperty.call(uploadRow, 'Source')) targetRow.source_name = uploadRow.Source || targetRow.source_name || '';
        appliedCount += 1;
        changedCells.push({
            key: getRoadModule1ComparableKeyFromRow(uploadRow),
            oldValue: oldValue ?? '',
            newValue: numericValue
        });
    });

    return {
        targetRows,
        appliedCount,
        unmatchedCount: 0,
        validationIssueCount,
        changedCells,
        uploadedScenarios: Array.from(uploadScenarios)
            .filter(scenario => scenario !== ROAD_MODULE1_CURRENT_ACCOUNTS)
    };
}

function commitRoadModule1UploadPreview(preview, version, economy, fileName) {
    State.roadModule1.rows = preview.targetRows;
    State.roadModule1.version = version;
    State.roadModule1.economy = economy;
    syncRoadModule1ScenarioState(State.roadModule1.scenario);
    State.roadModule1.overrides = new Map();
    State.roadModule1.sharedMileageOverrides = new Map();
    State.roadModule1.sharedFuelEconomyOverrides = new Map();
    State.roadModule1.sharedUtilisationOverrides = new Map();
    populateRoadModule1StructuredFilters(getRoadRowsForCurrentView());
    clearRoadModule1Draft(version, economy);
    DOM.roadSaveOutput.disabled = false;
    if (DOM.roadRunModel) DOM.roadRunModel.disabled = false;
    DOM.roadSaveStatus.innerText = [
        `${preview.appliedCount.toLocaleString('en-US')} row-year values applied from ${fileName}.`,
        `${preview.unmatchedCount.toLocaleString('en-US')} uploaded rows did not match this version/economy template.`,
        `${preview.validationIssueCount.toLocaleString('en-US')} value checks were flagged and skipped.`
    ].join('\n');
    renderRoadModule1Inputs();
    const hasIssues = preview.unmatchedCount > 0 || preview.validationIssueCount > 0;
    const summaryParts = [`Applied ${preview.appliedCount.toLocaleString('en-US')} values.`];
    if (preview.unmatchedCount > 0) summaryParts.push(`${preview.unmatchedCount.toLocaleString('en-US')} unmatched rows`);
    if (preview.validationIssueCount > 0) summaryParts.push(`${preview.validationIssueCount.toLocaleString('en-US')} validation issues`);
    showCustomToast(summaryParts.join(' | '), hasIssues ? 'warning' : 'success', 6000);
}

function getRoadNotesColumnName(row) {
    if (Object.prototype.hasOwnProperty.call(row || {}, 'notes')) return 'notes';
    if (Object.prototype.hasOwnProperty.call(row || {}, 'Notes')) return 'Notes';
    return 'notes';
}

function appendRoadCommentToRowNotes(row, comment) {
    const normalizedComment = String(comment || '').trim();
    if (!normalizedComment) return;

    const notesColumn = getRoadNotesColumnName(row);
    const existingNotes = String(row?.[notesColumn] || '').trim();

    if (!existingNotes) {
        row[notesColumn] = normalizedComment;
        return;
    }
    if (existingNotes.includes(normalizedComment)) {
        row[notesColumn] = existingNotes;
        return;
    }

    row[notesColumn] = `${existingNotes} ${normalizedComment}`.trim();
}

function buildRoadModule1CompletedRowsForCheckpoint() {
    const rowsByKey = new Map(
        State.roadModule1.rows.map(row => [buildRoadModule1Key(row), { ...row }])
    );

    Array.from(State.roadModule1.sharedMileageOverrides.values())
        .filter(override => override.value !== null && override.value !== '' && isRoadEditableYear(override.year))
        .forEach(override => {
            State.roadModule1.rows
                .filter(row => isRoadMileageRow(row) && (getRoadSharedMileageKey(row) === override.sharedKey || getRoadSharedMileageDriveKey(row) === override.sharedKey))
                .forEach(row => {
                    const rowKey = buildRoadModule1Key(row);
                    const targetRow = rowsByKey.get(rowKey);
                    if (targetRow) {
                        targetRow[String(override.year)] = Number(override.value);
                        targetRow._inputStatus = 'researcher';
                        appendRoadCommentToRowNotes(targetRow, override.comment);
                    }
                });
        });

    Array.from(State.roadModule1.sharedFuelEconomyOverrides.values())
        .filter(override => override.value !== null && override.value !== '' && isRoadEditableYear(override.year))
        .forEach(override => {
            State.roadModule1.rows
                .filter(row => isRoadFuelEconomyRow(row) && getRoadSharedFuelEconomyKey(row) === override.sharedKey)
                .forEach(row => {
                    const rowKey = buildRoadModule1Key(row);
                    const targetRow = rowsByKey.get(rowKey);
                    if (targetRow) {
                        targetRow[String(override.year)] = Number(override.value);
                        targetRow._inputStatus = 'researcher';
                        appendRoadCommentToRowNotes(targetRow, override.comment);
                    }
                });
        });

    Array.from(State.roadModule1.sharedUtilisationOverrides.values())
        .filter(override => override.value !== null && override.value !== '' && isRoadEditableYear(override.year))
        .forEach(override => {
            State.roadModule1.rows
                .filter(row => isRoadTransportLevelSharedRow(row) && getRoadSharedUtilisationKey(row) === override.sharedKey)
                .forEach(row => {
                    const rowKey = buildRoadModule1Key(row);
                    const targetRow = rowsByKey.get(rowKey);
                    if (targetRow) {
                        targetRow[String(override.year)] = Number(override.value);
                        targetRow._inputStatus = 'researcher';
                        appendRoadCommentToRowNotes(targetRow, override.comment);
                    }
                });
        });

    Array.from(State.roadModule1.overrides.values())
        .filter(override => override.value !== null && override.value !== '' && isRoadEditableYear(override.year))
        .forEach(override => {
            const rowKey = State.roadModule1.keyColumns
                .map(column => `${column}=${override.key?.[column] ?? ''}`)
                .join('||');
            const targetRow = rowsByKey.get(rowKey);
            if (targetRow) {
                const numericValue = Number(override.value);
                targetRow[String(override.year)] = Number.isFinite(numericValue) ? numericValue : String(override.value);
                targetRow._inputStatus = 'researcher';
                appendRoadCommentToRowNotes(targetRow, override.comment);
            }
        });

    return normaliseRoadSalesShareMixRows(Array.from(rowsByKey.values()));
}

function normaliseRoadSalesShareMixRows(rows) {
    const outputRows = (rows || []).map(row => ({ ...row }));
    const groups = new Map();

    outputRows
        .filter(row => isRoadDriveLevelSalesShareRow(row) && !isRoadPairedFuelShareRow(row))
        .forEach(row => {
            getRoadYearColumns(row).forEach(year => {
                const key = `${getRoadSalesShareNormaliseGroupKey(row)}||Year=${year}`;
                if (!groups.has(key)) groups.set(key, []);
                groups.get(key).push({ row, year });
            });
        });

    groups.forEach(items => {
        const numericItems = [];
        const remainderItems = [];

        items.forEach(item => {
            const rawValue = getRoadDefaultValue(item.row, item.year);
            if (isRoadRemainderToken(rawValue)) {
                remainderItems.push(item);
                return;
            }
            const numeric = Number(rawValue);
            if (Number.isFinite(numeric)) {
                numericItems.push({ ...item, value: numeric });
            }
        });

        const numericTotal = numericItems.reduce((sum, item) => sum + item.value, 0);
        if (remainderItems.length > 0) {
            const remainderValue = Math.max(0, 100 - numericTotal) / remainderItems.length;
            remainderItems.forEach(item => {
                item.row[String(item.year)] = remainderValue;
                item.row._inputStatus = item.row._inputStatus === 'researcher' ? item.row._inputStatus : 'normalised';
            });
        }

        const resolvedItems = items
            .map(item => ({ ...item, value: Number(getRoadDefaultValue(item.row, item.year)) }))
            .filter(item => Number.isFinite(item.value));
        const resolvedTotal = resolvedItems.reduce((sum, item) => sum + item.value, 0);
        if (resolvedTotal <= 0 || Math.abs(resolvedTotal - 100) <= 0.001) return;

        resolvedItems.forEach(item => {
            item.row[String(item.year)] = (item.value / resolvedTotal) * 100;
            item.row._inputStatus = item.row._inputStatus === 'researcher' ? item.row._inputStatus : 'normalised';
        });
    });

    return outputRows;
}

function buildRoadModule1CompletedLongRowsForHandoff() {
    const completedRows = buildRoadModule1CompletedRowsForCheckpoint();
    return [
        ...convertRoadWideUiRowsToLongRows(completedRows, State.roadModule1.economy),
        ...(Array.isArray(State.roadModule1.hiddenRows) ? State.roadModule1.hiddenRows : [])
    ];
}

function exportRoadModule1RowsCsvClientSide(rows, economyCode, fileNameOverride = '') {
    const safeRows = convertRoadWideUiRowsToLongRows(Array.isArray(rows) ? rows : [], economyCode);
    exportRoadModule1LongRowsCsvClientSide(safeRows, economyCode, fileNameOverride);
}

function exportRoadModule1LongRowsCsvClientSide(rows, economyCode, fileNameOverride = '') {
    const safeRows = Array.isArray(rows) ? rows : [];
    const headers = ROAD_MODULE1_LONG_COLUMNS;
    const escapeCsv = (value) => {
        const text = value === null || value === undefined ? '' : String(value);
        if (/[,"\n\r]/.test(text)) {
            return `"${text.replace(/"/g, '""')}"`;
        }
        return text;
    };

    const csvLines = [];
    csvLines.push(headers.map(escapeCsv).join(','));
    safeRows.forEach(row => {
        csvLines.push(headers.map(header => escapeCsv(row?.[header])).join(','));
    });

    const csvText = csvLines.join('\r\n');
    const blob = new Blob([csvText], { type: 'text/csv;charset=utf-8;' });
    const fileName = fileNameOverride || `road_module1_values_${economyCode}.csv`;
    const link = document.createElement('a');
    link.href = URL.createObjectURL(blob);
    link.download = fileName;
    link.style.display = 'none';
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
    URL.revokeObjectURL(link.href);
}

function convertRoadWideUiRowsToLongRows(rows, economyCode, includeBlankStockShareTargets = false) {
    const longRows = [];
    rows.forEach(row => {
        getRoadYearColumns(row).forEach(year => {
            const value = getRoadDefaultValue(row, year);
            if (
                value === null || value === undefined || String(value).trim() === ''
            ) {
                if (!(includeBlankStockShareTargets && isRoadVehicleTypeStockShareRow(row))) return;
            }
            longRows.push({
                Economy: economyCode || State.roadModule1.economy || row.Economy || '',
                Scenario: row.Scenario || State.roadModule1.scenario || 'Current Accounts',
                'Branch Path': row['Branch Path'] || '',
                Variable: row.Variable || '',
                Year: Number(year),
                Value: value,
                Scale: row.Scale || '',
                Units: row.Units || '',
                Source: row.source_name || row.Source || '',
                Comment: row.notes || row.Comment || '',
                'Input Status': row._inputStatus || 'default',
                'Shown In Interface': row['Shown In Interface'] ?? 'True'
            });
        });
    });
    return longRows;
}

function buildRoadModule1ExportOverrides() {
    const overridesByKey = new Map();

    State.roadModule1.rows.forEach(row => {
        const rowKey = buildRoadModule1Key(row);
        const keyPayload = roadModule1KeyPayload(row);
        getRoadYearColumns(row)
            .filter(isRoadEditableYear)
            .forEach(year => {
                const value = getRoadDefaultValue(row, year);
                if (value === null || value === undefined || value === '') return;
                overridesByKey.set(`${rowKey}||Year=${year}`, {
                    key: keyPayload,
                    year: year,
                    value: value,
                    comment: 'Checkpoint value from current browser state.'
                });
            });
    });

    State.roadModule1.rows
        .filter(isRoadMileageRow)
        .forEach(row => {
            const rowKey = buildRoadModule1Key(row);
            const keyPayload = roadModule1KeyPayload(row);
            getRoadYearColumns(row).forEach(year => {
                const detailedOverrideKey = `${rowKey}||Year=${year}`;

                const sharedOverride = getRoadSharedMileageOverride(row, year);
                if (!sharedOverride || sharedOverride.value === null || sharedOverride.value === '') return;

                overridesByKey.set(detailedOverrideKey, {
                    key: keyPayload,
                    year: year,
                    value: sharedOverride.value,
                    comment: sharedOverride.comment || 'Inherited from shared mileage value.'
                });
            });
        });

    State.roadModule1.rows
        .filter(isRoadTransportLevelSharedRow)
        .forEach(row => {
            const rowKey = buildRoadModule1Key(row);
            const keyPayload = roadModule1KeyPayload(row);
            getRoadYearColumns(row).forEach(year => {
                const detailedOverrideKey = `${rowKey}||Year=${year}`;

                const sharedOverride = getRoadSharedUtilisationOverride(row, year);
                if (!sharedOverride || sharedOverride.value === null || sharedOverride.value === '') return;

                overridesByKey.set(detailedOverrideKey, {
                    key: keyPayload,
                    year: year,
                    value: sharedOverride.value,
                    comment: sharedOverride.comment || 'Inherited from shared PHEV utilisation rate.'
                });
            });
        });

    Array.from(State.roadModule1.overrides.values())
        .filter(item => item.value !== null && item.value !== '' && isRoadEditableYear(item.year))
        .forEach(override => {
            overridesByKey.set(buildRoadModule1OverrideMapKey(override), override);
        });

    return Array.from(overridesByKey.values())
        .filter(item => item.value !== null && item.value !== '');
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

// ==========================================
// USER-DEFINED VARIABLES
// ==========================================

function _toSnakeCase(str) {
    return str.trim().toLowerCase().replace(/[^a-z0-9]+/g, '_').replace(/^_|_$/g, '');
}

function handleAddUserVariable() {
    const name = DOM.inputUvarName.value.trim();
    if (!name) {
        showCustomToast("Please enter a variable name.", "warning");
        return;
    }
    const rawValue = DOM.inputUvarValue.value.trim();
    if (rawValue === '') {
        showCustomToast("Please enter a numeric value.", "warning");
        return;
    }
    const value = parseFloat(rawValue);
    if (isNaN(value)) {
        showCustomToast("Value must be a number.", "warning");
        return;
    }

    const key = _toSnakeCase(name);
    if (State.userVariables.some(v => v.key === key)) {
        showCustomToast(`A variable with key '${key}' already exists.`, "warning");
        return;
    }

    State.userVariables.push({
        id: Date.now(),
        name: name,
        key: key,
        value: value,
        unit: DOM.inputUvarUnit.value.trim() || null,
        category: DOM.inputUvarCategory.value.trim() || null,
        description: DOM.inputUvarDescription.value.trim() || null
    });

    // Clear form fields
    DOM.inputUvarName.value = '';
    DOM.inputUvarValue.value = '';
    DOM.inputUvarUnit.value = '';
    DOM.inputUvarCategory.value = '';
    DOM.inputUvarDescription.value = '';

    renderUserVariablesPanel();
    showCustomToast(`Variable '${name}' added.`, "success");
}

function renderUserVariablesPanel() {
    DOM.userVarsContainer.innerHTML = '';

    if (State.userVariables.length === 0) {
        DOM.userVarsContainer.innerHTML = '<p class="text-[10px] text-slate-400 italic text-center py-1">No variables added yet.</p>';
        return;
    }

    State.userVariables.forEach((v, idx) => {
        const html = `
            <div class="bg-white border border-amber-200 rounded p-1.5 shadow-sm fade-in space-y-0.5" data-idx="${idx}">
                <div class="flex items-start justify-between gap-1">
                    <div class="flex-1 min-w-0">
                        <span class="block text-xs font-semibold text-slate-700 truncate" title="${v.name}">${v.name}</span>
                        ${v.category ? `<span class="text-[9px] text-amber-600 uppercase tracking-tight font-bold">${v.category}</span>` : ''}
                    </div>
                    <button class="text-slate-300 hover:text-red-500 font-bold text-sm leading-none px-0.5 btn-remove-uvar flex-shrink-0" data-idx="${idx}" title="Remove variable">&times;</button>
                </div>
                <div class="flex items-center gap-1.5">
                    <input type="number" step="any" value="${v.value}" class="flex-1 text-xs border border-slate-200 rounded px-1.5 py-0.5 outline-none focus:ring-1 focus:ring-amber-400 input-uvar-val" data-idx="${idx}">
                    ${v.unit ? `<span class="text-[10px] text-slate-500 font-medium flex-shrink-0">${v.unit}</span>` : ''}
                </div>
                ${v.description ? `<p class="text-[9px] text-slate-400 italic truncate" title="${v.description}">${v.description}</p>` : ''}
            </div>
        `;
        DOM.userVarsContainer.insertAdjacentHTML('beforeend', html);
    });

    DOM.userVarsContainer.querySelectorAll('.input-uvar-val').forEach(input => {
        input.addEventListener('input', e => {
            const idx = parseInt(e.target.dataset.idx);
            State.userVariables[idx].value = parseFloat(e.target.value) || 0;
        });
    });

    DOM.userVarsContainer.querySelectorAll('.btn-remove-uvar').forEach(btn => {
        btn.addEventListener('click', e => {
            const idx = parseInt(e.target.closest('[data-idx]').dataset.idx);
            const removed = State.userVariables.splice(idx, 1)[0];
            renderUserVariablesPanel();
            showCustomToast(`Variable '${removed.name}' removed.`, "info");
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
if (DOM.treeCanvas) DOM.treeCanvas.addEventListener('click', async (e) => {
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

if (DOM.treeCanvas) DOM.treeCanvas.addEventListener('keydown', (e) => {
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
if (DOM.treeCanvas) DOM.treeCanvas.addEventListener('input', (e) => {
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
if (DOM.treeCanvas) DOM.treeCanvas.addEventListener('change', (e) => {
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

if (DOM.btnAddRoot) DOM.btnAddRoot.addEventListener('click', () => {
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

if (DOM.btnValidate) DOM.btnValidate.addEventListener('click', async () => {
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

if (DOM.btnOptimize) DOM.btnOptimize.addEventListener('click', async () => {
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
if (DOM.btnExport) DOM.btnExport.addEventListener('click', async () => {
    showLoading("Generating LEAP Export...");
    try {
        const payload = {
            economy: State.economy,
            year: State.year,
            sector_flow: State.sector_flow,
            macro_drivers: State.macroDrivers,
            balanced_tree: State.treeState,
            user_variables: State.userVariables.map(v => ({
                name: v.key,
                display_name: v.name,
                value: v.value,
                unit: v.unit || null,
                description: v.description || null,
                category: v.category || null
            }))
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
    if (DOM.loadingText) DOM.loadingText.innerText = text;
    if (DOM.loadingOverlay) {
        DOM.loadingOverlay.classList.remove('hidden');
        DOM.loadingOverlay.classList.add('flex');
    }
}
function hideLoading() {
    if (DOM.loadingOverlay) {
        DOM.loadingOverlay.classList.add('hidden');
        DOM.loadingOverlay.classList.remove('flex');
    }
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

