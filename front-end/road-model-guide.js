// Road data preparation guide.
// To extend the tour, add a step to ROAD_MODEL_GUIDE_STEPS. Each step needs a
// title, copy, and a selector for the UI area it should highlight. Multiple
// selectors separated by commas are tried from left to right.

const ROAD_MODEL_GUIDE_STEPS = [
    {
        target: '#road-app-banner',
        title: 'Why this road model exists',
        copy: 'This interface prepares the detailed road-transport base year and first projection before they are passed to LEAP. Road fleets need linked vehicle stock, turnover, drive type, mileage, fuel economy and fuel-allocation data. LEAP is the destination for the Outlook energy model, but it is not designed to manage this level of road-fleet data or modelling complexity directly.'
    },
    {
        target: '#road-economy-select',
        title: 'Choose an economy',
        copy: 'Select the economy you are working on. The interface loads its documented default package, including both Current Accounts base-year rows and the Target projection rows that the road model needs.'
    },
    {
        target: '#road-variable-map-btn',
        title: 'Read the method and explore the hierarchy',
        copy: 'Use the overview and methodology links when you need the full process, and open Branch and Measure hierarchy to see how inputs are organised. These references help keep updates consistent with the shared road data method as the dataset improves.'
    },
    {
        target: '#road-left-top .pt-4',
        title: 'Set up a useful working view',
        copy: 'Switch between List and Tree views, choose how much detail to show, then filter or sort the input rows. These controls only change what you see; they do not change the model data or results.'
    },
    {
        target: '#road-input-container',
        title: 'Review and improve the inputs',
        copy: 'Edit the available values for your economy, adding your source and comment where relevant. This is where local knowledge improves the long-lived road dataset: the same structured rows can be reviewed, updated and reused in later Outlook cycles.'
    },
    {
        target: '#road-helper-wrapper',
        title: 'Use the contextual helper',
        copy: 'Click or hover over an input row to see what its measure, vehicle type and drive type mean. The helper is especially useful when you are working through unfamiliar branches or reconciliation settings.'
    },
    {
        target: '#road-upload-provided-values',
        title: 'Bring in work prepared elsewhere',
        copy: 'Upload a filled CSV when values have been prepared in a spreadsheet or another tool. It can update existing row keys only, which protects the shared data contract while allowing researcher overrides.'
    },
    {
        target: '#road-save-output',
        title: 'Keep a portable working copy',
        copy: 'Download Filled CSV saves the current package, including the defaults and your overrides. You can use it for review, share it with colleagues, and upload it later to continue the same work.'
    },
    {
        target: '#road-run-model',
        title: 'Run the detailed road calculation',
        copy: 'Run Road Model reconciles the base-year fleet against road energy, projects the fleet and technologies, and prepares a LEAP-ready import workbook. The results dashboard helps you check the calculation before the simpler, economy-wide Outlook modelling continues in LEAP.'
    },
    {
        target: '#road-app-banner',
        title: 'A sustainable hand-off to LEAP',
        copy: 'The interface, its source-backed database and its documented method are designed to preserve improvements over time rather than recreate the road dataset each Outlook cycle. Once reviewed, this detailed road package becomes a transparent input to LEAP, where it sits alongside the rest of the Outlook model.'
    }
];

function setupRoadModelGuide() {
    const get = (selector) => document.querySelector(selector);
    const launch = get('#road-guide-launch');
    const dialog = get('#road-guide-dialog');
    const backdrop = get('#road-guide-backdrop');
    if (!launch || !dialog || !backdrop || launch.dataset.guideBound === '1') return;

    const title = get('#road-guide-title');
    const copy = get('#road-guide-copy');
    const stepNumber = get('#road-guide-step');
    const total = get('#road-guide-total');
    const back = get('#road-guide-back');
    const next = get('#road-guide-next');
    const closeButton = get('#road-guide-close');
    let currentStep = 0;
    let launchFocus = null;

    const resolveTarget = (selector) => selector.split(',')
        .map((part) => get(part.trim()))
        .find(Boolean) || get('#road-module1-main');
    const clearHighlight = () => document.querySelectorAll('.road-guide-highlight')
        .forEach((element) => element.classList.remove('road-guide-highlight'));
    const show = (index) => {
        currentStep = Math.max(0, Math.min(index, ROAD_MODEL_GUIDE_STEPS.length - 1));
        const step = ROAD_MODEL_GUIDE_STEPS[currentStep];
        const target = resolveTarget(step.target);
        clearHighlight();
        title.textContent = step.title;
        copy.textContent = step.copy;
        stepNumber.textContent = String(currentStep + 1);
        total.textContent = String(ROAD_MODEL_GUIDE_STEPS.length);
        back.style.visibility = currentStep === 0 ? 'hidden' : 'visible';
        next.innerHTML = currentStep === ROAD_MODEL_GUIDE_STEPS.length - 1
            ? 'Done <span aria-hidden="true">✓</span>'
            : 'Next <span aria-hidden="true">→</span>';
        target.classList.add('road-guide-highlight');
        target.scrollIntoView({ behavior: 'smooth', block: 'center', inline: 'nearest' });
    };
    const close = () => {
        dialog.hidden = true;
        backdrop.hidden = true;
        clearHighlight();
        launchFocus?.focus();
    };

    launch.dataset.guideBound = '1';
    launch.addEventListener('click', () => {
        launchFocus = document.activeElement;
        dialog.hidden = false;
        backdrop.hidden = false;
        show(0);
        closeButton.focus();
    });
    closeButton.addEventListener('click', close);
    backdrop.addEventListener('click', close);
    next.addEventListener('click', () => currentStep === ROAD_MODEL_GUIDE_STEPS.length - 1 ? close() : show(currentStep + 1));
    back.addEventListener('click', () => show(currentStep - 1));
    document.addEventListener('keydown', (event) => {
        if (!dialog.hidden && event.key === 'Escape') close();
    });
}

document.addEventListener('DOMContentLoaded', setupRoadModelGuide);
