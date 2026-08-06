// Road data preparation guide.
// To extend the tour, add a step to ROAD_MODEL_GUIDE_STEPS. Each step needs a
// title, copy, and a selector for the UI area it should highlight. Multiple
// selectors separated by commas are tried from left to right. Optional image
// and placeholder fields add a screenshot or a clearly marked future slot.

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
        target: '#road-reference-links',
        title: 'Find more information here',
        copy: 'Open road model overview explains what the model does. Open methodology guide explains the assumptions and calculation method. Branch and Measure hierarchy shows how the input data is organised.'
    },
    {
        target: '#road-left-top .pt-4',
        title: 'Navigation tools for your work',
        copy: 'Use List or Tree view, data density, filters and sorting whenever they help you find the variables you are working on. These controls only change what you see; they do not change the model data or results.'
    },
    {
        target: '#road-input-container',
        title: 'Focus on the inputs that matter most to you',
        copy: 'You can leave every starting value as it is: they are based on the previous Outlook and remain the default. Blue flag icons mark key inputs with relatively high uncertainty and impact on results, so they are a good place to focus when you have local evidence or expert judgement to add.'
    },
    {
        target: '#road-helper-wrapper',
        title: 'Use the contextual helper',
        copy: 'Click or hover over an input row to see what its measure, vehicle type and drive type mean. The helper is especially useful when you are working through unfamiliar branches or reconciliation settings.'
    },
    {
        target: '#road-upload-provided-values',
        title: 'Bring in work prepared elsewhere',
        copy: 'Your file needs to match this structure, variables and column names or it will not work. You can change the values, sources and comments for the existing rows.',
        image: 'assets/guide/module1-long-csv-structure.png',
        imageAlt: 'The filled CSV structure, showing Economy, Scenario, Branch Path, Variable, Year, Value, Scale, Units, Source, Comment, Input Status and Shown In Interface columns.'
    },
    {
        target: '#road-save-output',
        title: 'Keep a portable working copy',
        copy: 'Your progress is saved in this browser when you leave. If you have made a lot of progress you do not want to risk losing to a browser or website problem, download the Filled CSV as a backup. You can upload it later to continue from the same point.'
    },
    {
        target: '#road-run-model',
        title: 'Run the detailed road calculation',
        copy: 'Run Road Model reconciles the recorded base-year fleet values to ESTO road-energy data, projects the fleet and technologies, and prepares a LEAP-ready import workbook. Reconciliation can make small changes to the values you entered so that the fleet produces the observed ESTO energy total.'
    },
    {
        target: '#road-run-model',
        title: 'Review the model results',
        copy: 'After a run, the results window shows the completed calculation and the files available to use.',
        image: 'assets/guide/road-model-results.png',
        imageAlt: 'Road model results window after a completed model run.'
    },
    {
        target: '#road-run-model',
        title: 'Check the results dashboard',
        copy: 'Use Open Dashboard after a run to review charts and tables that summarise the projected fleet, energy use and calibration quality before continuing in LEAP.',
        image: 'assets/guide/road-model-dashboard.png',
        imageAlt: 'Road model results dashboard with charts and tables.'
    },
    {
        target: '#road-run-model',
        title: 'Use the files created by the run',
        copy: 'Download LEAP Workbook is the road-model import for LEAP. Download Lifecycle Profiles provides lifecycle-emissions profiles. Download Reconciled Inputs lets you bring the adjusted base-year inputs back into this interface. This step will also show how to insert lifecycle results in LEAP.',
        placeholder: 'Lifecycle-results-in-LEAP screenshot to be added'
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
    const image = get('#road-guide-image');
    const placeholder = get('#road-guide-placeholder');
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
        image.hidden = !step.image;
        if (step.image) image.src = step.image;
        else image.removeAttribute('src');
        image.alt = step.imageAlt || '';
        placeholder.hidden = !step.placeholder;
        placeholder.textContent = step.placeholder || '';
        dialog.classList.toggle('road-guide-has-image', Boolean(step.image));
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
