// road-model-helper.js
// Compact contextual helper panel for the Road Model inputs interface.
// Loaded after app.js so escapeHtml and State are available in global scope.

const ROAD_HELPER_VARIABLE_EXPLANATIONS = {
    'Stock': "Number of vehicles in the fleet. Often economies have these values recorded as 'registered vehicles' or 'vehicles in use'.",
    'Mileage': "Average distance travelled per vehicle per year. Not often available from the economy directly.",
    'Sales': "Number of new vehicles added to the fleet in that year (i.e. vehicle registrations).",
    'Fuel Economy': "Energy used per 100 km. Lower values mean better efficiency. Not often available from the economy directly.",
    'Final On-Road Fuel Economy': "Energy used per 100 km. Lower values mean better efficiency. Not often available from the economy directly.",
    'Sales Share': "Share of new vehicle sales assigned to this drive or technology in that year. Related rows should sum to 100%, otherwise you will need to normalise them.",
    'Stock Share': "Share of the vehicle stock assigned to this drive or technology. Related rows should sum to 100%, otherwise you will need to normalise them.",
    'Vehicle Equivalent Weight': "Conversion weight used to compare different vehicle types in a common vehicle-equivalent ownership measure. For example, buses count as more than one car-equivalent.",
    'Passenger Vehicle Saturation': "Long-run passenger vehicle ownership level used to shape future stock and sales growth.",
    'PHEV Electric Driving Share': "Share of PHEV driving assumed to be powered by electricity rather than liquid fuel. Be careful to assume the share of activity rather than share of energy, which is different due to the lower fuel economy of PHEV electric driving.",
    'Reconciliation Weight': "Relative priority given to changing this measure during reconciliation. Higher weights mean the value is changed more aggressively.",
    'Reconciliation Bound Lower': "Lower limit used during reconciliation. The adjusted value should not normally fall below this bound. Good for ensuring mileage and fuel economy values do not get adjusted to unrealistically low levels during reconciliation, which can happen if the stock share (or energy value) is far off what it needs to be.",
    'Reconciliation Bound Upper': "Upper limit used during reconciliation. The adjusted value should not normally rise above this bound. Good for ensuring mileage and fuel economy values do not get adjusted to unrealistically high levels during reconciliation, which can happen if the stock share (or energy value) is far off what it needs to be.",
    'Survival Rate': "Share of vehicles that remain in the fleet at each age. Used to calculate retirements and turnover.",
    'Vintage Profile Share': "Share of the base-year fleet assigned to each vehicle age. Used to represent the starting age structure of the fleet.",
};

const ROAD_HELPER_VEHICLE_GROUP_EXPLANATIONS = {
    'LPVs': "light passenger vehicles, including cars, SUVs and similar passenger vehicles.",
    'Motorcycles': "two- and three-wheelers in the passenger road fleet.",
    'Buses': "passenger buses.",
    'Trucks': "freight trucks. Broken into Heavy and Medium within the drive categories for this vehicle type.",
    'LCVs': "light commercial vehicles used for freight road transport.",
};

const ROAD_HELPER_DRIVE_TYPE_EXPLANATIONS = {
    'ICE': "internal-combustion engine vehicles.",
    'HEV': "hybrid electric vehicles without plug-in charging.",
    'PHEV': "plug-in hybrid electric vehicles.",
    'EREV': "extended-range electric vehicles.",
    'BEV': "battery electric vehicles.",
    'FCEV': "fuel-cell electric vehicles.",
};

const ROAD_HELPER_SIZE_CLASS_EXPLANATIONS = {
    'LPVs': {
        'small': "For LPVs, small is generally assumed for regular cars if the economy does not have a more specific segment of smaller cars, such as Kei cars in Japan.",
        'medium': "For LPVs, medium is generally assumed for SUVs if the economy does not have a specific segment of small cars, in which case this segment is used for regular cars.",
        'large': "For LPVs, large is generally assumed for pickup trucks if the economy does not have a specific segment of small cars, in which case this segment is used for SUVs and pickup trucks.",
    },
    'Trucks': {
        'medium': "For trucks, medium is generally assumed for trucks above 3.5 tonnes and below 16 tonnes if the economy does not have more specific medium freight truck segments.",
        'heavy': "For trucks, heavy is generally assumed for trucks above 16 tonnes if the economy does not have more specific heavy freight truck segments.",
    },
};

// Parts of the branch path to skip in the helper output
const ROAD_HELPER_SKIP_PARTS_LC = new Set(['demand', 'passenger road', 'freight road']);

// Module-level selection state
let _roadHelperSelectedInput = null;
let _roadHelperHoverInput = null;

// ==========================================
// Pure helper functions
// ==========================================

function roadHelperParseBranchPath(row) {
    // Branch paths in this codebase use backslash as separator
    const raw = row['Branch Path'] || row['branch_path'] || row['branchPath'] || row['Branch'] || row['Path'] || '';
    if (!raw) return [];
    return String(raw).split('\\').map(p => p.trim()).filter(Boolean);
}

function roadHelperGetVariableExplanation(variable) {
    return ROAD_HELPER_VARIABLE_EXPLANATIONS[String(variable || '').trim()] || null;
}

function roadHelperGetVehicleGroupExplanation(part) {
    return ROAD_HELPER_VEHICLE_GROUP_EXPLANATIONS[String(part || '').trim()] || null;
}

function roadHelperGetDriveTypeExplanation(drive) {
    return ROAD_HELPER_DRIVE_TYPE_EXPLANATIONS[String(drive || '').toUpperCase().trim()] || null;
}

function roadHelperGetSizeClassExplanation(size, vehicleGroup) {
    const groupMap = ROAD_HELPER_SIZE_CLASS_EXPLANATIONS[String(vehicleGroup || '').trim()];
    if (!groupMap) return null;
    return groupMap[String(size || '').toLowerCase().trim()] || null;
}

function roadHelperBuildBranchExplanations(branchParts) {
    const explanations = [];
    let currentVehicleGroup = null;

    for (const part of branchParts) {
        if (ROAD_HELPER_SKIP_PARTS_LC.has(part.toLowerCase())) continue;

        // Check if it is a known vehicle group first
        const vgExpl = roadHelperGetVehicleGroupExplanation(part);
        if (vgExpl) {
            currentVehicleGroup = part;
            explanations.push({ label: part, text: vgExpl });
            continue;
        }

        // Try as drive type + optional size (e.g. "ICE medium", "BEV", "FCEV heavy")
        const tokens = part.trim().split(/\s+/);
        const drive = tokens[0] ? tokens[0].toUpperCase() : '';
        const size = tokens[1] ? tokens[1].toLowerCase() : '';
        const driveExpl = roadHelperGetDriveTypeExplanation(drive);
        if (driveExpl) {
            let text = driveExpl;
            if (size && currentVehicleGroup) {
                const sizeExpl = roadHelperGetSizeClassExplanation(size, currentVehicleGroup);
                if (sizeExpl) text += ' ' + sizeExpl;
            }
            explanations.push({ label: part, text });
            continue;
        }

        // Unknown branch element: silently skip, do not crash
    }

    return explanations;
}

function roadHelperGetEconomyLabel() {
    const el = document.getElementById('road-economy-select');
    if (el && el.selectedIndex >= 0) {
        const opt = el.options[el.selectedIndex];
        if (opt && opt.text && opt.text.trim()) return opt.text.trim();
    }
    try {
        return (State && State.roadModule1 && State.roadModule1.economy) || 'this economy';
    } catch (_e) {
        return 'this economy';
    }
}

function roadHelperFindRowByKeyPayload(keyPayload) {
    try {
        const rows = State.roadModule1.rows;
        return rows.find(row =>
            row['Branch Path'] === keyPayload['Branch Path'] &&
            row['Variable'] === keyPayload['Variable'] &&
            row['Scenario'] === keyPayload['Scenario'] &&
            row['Region'] === keyPayload['Region']
        ) || null;
    } catch (_e) {
        return null;
    }
}

function roadHelperEscape(str) {
    // Delegates to app.js escapeHtml if available (loaded before this file)
    if (typeof escapeHtml === 'function') return escapeHtml(str);
    return String(str || '')
        .replace(/&/g, '&amp;')
        .replace(/</g, '&lt;')
        .replace(/>/g, '&gt;')
        .replace(/"/g, '&quot;')
        .replace(/'/g, '&#039;');
}

function buildRoadHelperHtml(row, year) {
    const e = roadHelperEscape;

    if (!row) {
        return '<p class="road-helper-default-text">Click a cell in the table to see what that assumption means. The helper will explain the selected variable and the main parts of the branch path.</p>';
    }

    const branchParts = roadHelperParseBranchPath(row);
    if (!branchParts.length) {
        return '<p class="road-helper-default-text">No branch path was found for this row.</p>';
    }

    const variable = String(row['Variable'] || '').trim();
    const economyLabel = roadHelperGetEconomyLabel();

    // Build display path (skip "Demand" for the subtitle)
    const displayParts = branchParts.filter(p => p.toLowerCase() !== 'demand');
    const displayPath = displayParts.join(' → ');

    // Use "Fuel Economy" explanation for the alias "Final On-Road Fuel Economy"
    const varExpl = roadHelperGetVariableExplanation(variable);
    const displayVarLabel = variable === 'Final On-Road Fuel Economy' ? 'Fuel Economy' : variable;

    // Selected cell label
    const yearLabel = year ? ' · Column ' + e(year) : '';
    const selectedCellLine = e(variable) + ' · ' + e(displayPath) + yearLabel;

    // "What this means" paragraph
    let whatHtml;
    if (varExpl) {
        whatHtml = '<p class="road-helper-explanation">You are editing <strong>' + e(displayVarLabel) + '</strong> for ' + e(displayPath) + ' in ' + e(economyLabel) + '.</p>'
            + '<p class="road-helper-explanation road-helper-explanation--body">' + e(varExpl) + '</p>';
    } else {
        whatHtml = '<p class="road-helper-explanation">You are editing <strong>' + e(variable) + '</strong> for ' + e(displayPath) + ' in ' + e(economyLabel) + '.</p>'
            + '<p class="road-helper-explanation road-helper-explanation--body road-helper-explanation--unknown">This variable is not yet in the helper dictionary. Use the branch path and nearby rows to interpret it.</p>';
    }

    // Branch details
    const branchExplanations = roadHelperBuildBranchExplanations(branchParts);
    let branchHtml = '';
    if (branchExplanations.length) {
        const items = branchExplanations.map(exp =>
            '<li><strong>' + e(exp.label) + ':</strong> ' + e(exp.text) + '</li>'
        ).join('');
        branchHtml = '<div class="road-helper-section-label">Branch details</div>'
            + '<ul class="road-helper-branch-list">' + items + '</ul>';
    }

    return '<div class="road-helper-section-label">Selected cell</div>'
        + '<div class="road-helper-selected-cell-path">' + selectedCellLine + '</div>'
        + '<div class="road-helper-section-label">What this means</div>'
        + whatHtml
        + branchHtml;
}

// ==========================================
// DOM update
// ==========================================

function updateRoadModelHelper() {
    const contentEl = document.getElementById('road-model-helper-content');
    if (!contentEl) return;

    const activeInput = _roadHelperSelectedInput || _roadHelperHoverInput;
    if (!activeInput) {
        contentEl.innerHTML = buildRoadHelperHtml(null, null);
        return;
    }

    // Find the nearest ancestor with a key-payload (regular rows only)
    const rowEl = activeInput.closest('[data-key-payload]');
    if (!rowEl) {
        contentEl.innerHTML = buildRoadHelperHtml(null, null);
        return;
    }

    let row = null;
    try {
        const keyPayload = JSON.parse(decodeURIComponent(rowEl.dataset.keyPayload || '%7B%7D'));
        row = roadHelperFindRowByKeyPayload(keyPayload);
    } catch (_e) {
        // fall through to null row
    }

    // Year from nearest .road-year-input ancestor
    const yearEl = activeInput.closest('.road-year-input');
    const year = yearEl ? yearEl.dataset.year : null;

    contentEl.innerHTML = buildRoadHelperHtml(row, year);
}

// ==========================================
// Selection tracking
// ==========================================

function roadHelperSelectInput(input) {
    // Remove highlight from the previous cell
    if (_roadHelperSelectedInput && _roadHelperSelectedInput !== input) {
        _roadHelperSelectedInput.classList.remove('road-cell-selected');
    }
    _roadHelperSelectedInput = input;
    if (input) {
        input.classList.add('road-cell-selected');
    }
    updateRoadModelHelper();
}

// ==========================================
// Setup
// ==========================================

function setupRoadModelHelper() {
    const container = document.getElementById('road-input-container');
    if (!container) return;

    // Focus/click: update helper and persist selection
    container.addEventListener('focusin', (e) => {
        if (e.target.classList.contains('road-value-input')) {
            roadHelperSelectInput(e.target);
        }
    });

    // Click reinforces selection (some inputs may not re-fire focusin)
    container.addEventListener('click', (e) => {
        if (e.target.classList.contains('road-value-input')) {
            roadHelperSelectInput(e.target);
        }
    });

    // Hover: only update when no cell is focused
    container.addEventListener('mouseover', (e) => {
        if (!_roadHelperSelectedInput && e.target.classList.contains('road-value-input')) {
            _roadHelperHoverInput = e.target;
            updateRoadModelHelper();
        }
    });

    container.addEventListener('mouseout', (e) => {
        if (!_roadHelperSelectedInput && e.target === _roadHelperHoverInput) {
            _roadHelperHoverInput = null;
            updateRoadModelHelper();
        }
    });

    // When the table re-renders (new economy loaded, filter change, etc.), the selected
    // input element is replaced. Clear stale references so the helper resets cleanly.
    const observer = new MutationObserver(() => {
        if (_roadHelperSelectedInput && !document.contains(_roadHelperSelectedInput)) {
            _roadHelperSelectedInput = null;
            _roadHelperHoverInput = null;
            updateRoadModelHelper();
        }
    });
    observer.observe(container, { childList: true, subtree: false });
}

// setupRoadModelHelper() is called directly from setupRoadModule1() in app.js.
