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
        copy: 'Select the economy you are working on. You can leave the default values as they are: they are based on previous Outlooks and are automatically reconciled to match the most recent ESTO road-energy year when the model runs.'
    },
    {
        target: '#road-reference-links',
        title: 'Reference material',
        copy: 'Use these links whenever you need more detail. Overview explains the model’s purpose and role in the Outlook. Methodology explains the assumptions and calculations. Hierarchy shows how the input variables are organised.'
    },
    {
        target: '#road-left-top .pt-4',
        title: 'Navigation tools for your work',
        copy: 'Use List or Tree view, data density, filters and sorting whenever they help you find the variables you are working on. These controls only change what you see; they do not change the model data or results.'
    },
    {
        target: '#road-input-container',
        title: 'Focus on the inputs that matter most to you',
        copy: 'You can leave the defaults as they are. They are based on previous Outlooks and are reconciled to the most recent ESTO road-energy year when the model runs. Blue flag icons mark inputs with relatively high uncertainty and impact on results, so focus there when you have local evidence or expert judgement to add.'
    },
    {
        target: '#road-helper-wrapper',
        title: 'Use the contextual helper',
        copy: 'Click or hover over an input row to see what its measure, vehicle type and drive type mean. The helper is especially useful when you are working through unfamiliar branches or reconciliation settings.'
    },
    {
        target: '#road-upload-provided-values',
        title: 'Bring in work prepared elsewhere',
        copy: 'Click Upload Filled CSV to load a CSV you prepared in Excel or another tool. It needs to match this structure, variables and column names or it will not work. You can change the values, sources and comments for the existing rows.',
        image: 'assets/guide/module1-long-csv-structure.png?v=20260806b',
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
        title: 'Import the road workbook into LEAP',
        copy: 'After a run, Download LEAP Workbook. The two screenshots show how to import the workbook in LEAP. Use the arrows to move through the screenshots without leaving this note.',
        gallery: [
            {
                image: 'assets/guide/leap-workbook/01-import-options.png?v=20260806b',
                alt: 'LEAP Analysis menu showing Import from Excel Template.',
                caption: 'In LEAP, open your area and choose Analysis > Import from Excel Template. First click a cell in the Excel workbook you want to import.'
            },
            {
                image: 'assets/guide/leap-workbook/02-import-workbook.png?v=20260806b',
                alt: 'LEAP import from Excel options.',
                caption: 'Use these options to make sure the data is imported into the right places.'
            }
        ]
    },
    {
        target: '#road-run-model',
        title: 'Import lifecycle profiles into LEAP',
        copy: 'After a run, select Download Lifecycle Profiles. These screenshots show the lifecycle profile range and the related LEAP import settings. Use the arrows to move through the steps without leaving this note.',
        gallery: [
            { image: 'assets/guide/lifecycle-profiles/01-excel-range.png', alt: 'Lifecycle profile Excel range.' },
            { image: 'assets/guide/lifecycle-profiles/02-leap-import.png', alt: 'LEAP lifecycle profile import screen.' },
            { image: 'assets/guide/lifecycle-profiles/03-excel-range-name.png', alt: 'Lifecycle profile Excel range name.' },
            { image: 'assets/guide/lifecycle-profiles/04-settings-3.png', alt: 'LEAP lifecycle import settings step 3.' },
            { image: 'assets/guide/lifecycle-profiles/05-settings-4.png', alt: 'LEAP lifecycle import settings step 4.' },
            { image: 'assets/guide/lifecycle-profiles/06-settings-5.png', alt: 'LEAP lifecycle import settings step 5.' },
            { image: 'assets/guide/lifecycle-profiles/07-settings-6.png', alt: 'LEAP lifecycle import settings step 6.' },
            { image: 'assets/guide/lifecycle-profiles/08-settings-7.png', alt: 'LEAP lifecycle import settings step 7.' }
        ]
    },
    {
        target: '#road-run-model',
        title: 'More LEAP guidance',
        copy: 'More information on using the road model in LEAP is in OneDrive: Guides and notes/Transport/Transport guide for LEAP. The table below summarises the safest changes to make in LEAP.',
        image: 'assets/guide/leap-safe-changes-reference.png',
        imageAlt: 'Transport guide for LEAP showing the safe LEAP changes section.',
        table: {
            caption: 'Safe changes in projection scenarios — not Current Accounts',
            headers: ['Change', 'Where', 'Effect', 'Check'],
            rows: [
                ['Technology uptake', 'Sales Share: vehicle / drive', 'New sales mix', 'Shares = 100%; stock changes gradually'],
                ['Mileage factor', 'Mileage Correction Factor: fuel', 'km per vehicle / energy', 'Energy changes; stock does not'],
                ['Efficiency factor', 'Fuel Economy Correction Factor: fuel', 'Energy per km', 'Check unit direction'],
                ['Fuel split', 'Device Share: fuel', 'Technology fuel mix', 'Shares = 100%; use pre-LEAP PHEV/EREV shares'],
                ['Availability', 'First Sales Year', 'Blocks early sales', 'Check pre-year sales handling'],
                ['Accelerated retirement', 'Scrappage variables: drive / engine', 'Faster retirement', 'Advanced: check stock, sales and retirements']
            ]
        }
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
    const gallery = get('#road-guide-gallery');
    const galleryImage = get('#road-guide-gallery-image');
    const galleryCaption = get('#road-guide-gallery-caption');
    const galleryPrevious = get('#road-guide-gallery-previous');
    const galleryNext = get('#road-guide-gallery-next');
    const tableContainer = get('#road-guide-table');
    const stepNumber = get('#road-guide-step');
    const total = get('#road-guide-total');
    const back = get('#road-guide-back');
    const next = get('#road-guide-next');
    const closeButton = get('#road-guide-close');
    let currentStep = 0;
    let launchFocus = null;
    let galleryImages = [];
    let galleryIndex = 0;

    const resolveTarget = (selector) => selector.split(',')
        .map((part) => get(part.trim()))
        .find(Boolean) || get('#road-module1-main');
    const clearHighlight = () => document.querySelectorAll('.road-guide-highlight')
        .forEach((element) => element.classList.remove('road-guide-highlight'));
    const renderGalleryImage = () => {
        const galleryItem = galleryImages[galleryIndex];
        if (!galleryItem) return;
        galleryImage.src = galleryItem.image;
        galleryImage.alt = galleryItem.alt || '';
        const imageNumber = `${galleryIndex + 1} of ${galleryImages.length}`;
        galleryCaption.textContent = galleryItem.caption
            ? `${imageNumber} — ${galleryItem.caption}`
            : imageNumber;
        galleryPrevious.disabled = galleryImages.length < 2;
        galleryNext.disabled = galleryImages.length < 2;
    };
    const renderTable = (table) => {
        tableContainer.replaceChildren();
        tableContainer.hidden = !table;
        if (!table) return;
        const caption = document.createElement('div');
        caption.className = 'road-guide-table-caption';
        caption.textContent = table.caption;
        const htmlTable = document.createElement('table');
        const head = document.createElement('thead');
        const headerRow = document.createElement('tr');
        table.headers.forEach((label) => {
            const cell = document.createElement('th');
            cell.scope = 'col';
            cell.textContent = label;
            headerRow.appendChild(cell);
        });
        head.appendChild(headerRow);
        const body = document.createElement('tbody');
        table.rows.forEach((row) => {
            const tableRow = document.createElement('tr');
            row.forEach((value) => {
                const cell = document.createElement('td');
                cell.textContent = value;
                tableRow.appendChild(cell);
            });
            body.appendChild(tableRow);
        });
        htmlTable.append(head, body);
        tableContainer.append(caption, htmlTable);
    };
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
        galleryImages = step.gallery || [];
        galleryIndex = 0;
        gallery.hidden = !galleryImages.length;
        if (galleryImages.length) renderGalleryImage();
        else {
            galleryImage.removeAttribute('src');
            galleryImage.alt = '';
            galleryCaption.textContent = '';
        }
        renderTable(step.table);
        dialog.classList.toggle('road-guide-has-image', Boolean(step.image || galleryImages.length || step.table));
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
    galleryPrevious.addEventListener('click', () => {
        galleryIndex = (galleryIndex - 1 + galleryImages.length) % galleryImages.length;
        renderGalleryImage();
    });
    galleryNext.addEventListener('click', () => {
        galleryIndex = (galleryIndex + 1) % galleryImages.length;
        renderGalleryImage();
    });
    document.addEventListener('keydown', (event) => {
        if (!dialog.hidden && event.key === 'Escape') close();
    });
}

document.addEventListener('DOMContentLoaded', setupRoadModelGuide);
