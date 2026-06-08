// Single source of truth for all ? tooltip text shown next to Road Model variables.
// Used by app.js for every inline help tip; update here to change all tooltips at once.
const ROAD_VARIABLE_HELP = {

    // Keyed by the exact Variable column value from the CSV / ROAD_MODULE1_VALUE_RULES.
    variables: {
        'Stock':
            'Base-year vehicle count for this branch. Used as the starting stock for projections.',
        'Sales Share':
            'Percentage of new vehicle sales in this branch with this drive or fuel (0–100).',
        'Stock Share':
            'Percentage of total vehicle stock attributed to this drive or fuel (0–100).',
        'Final On-Road Fuel Economy':
            'Energy actually consumed per km driven, including all on-road losses (real-world efficiency).',
        'Fuel Economy':
            'Modelled fuel economy for this vehicle/fuel combination, in energy per km.',
        'Mileage':
            'Annual distance travelled per vehicle, in km per vehicle per year.',
        'Passenger Vehicle Saturation':
            'Long-run saturation of passenger vehicles per capita. Shared across all passenger road transport types.',
        'Passenger Saturation Reached':
            'Whether passenger vehicle ownership saturation has been reached. When true, the model switches to a plateau growth mode.',
        'Passenger Stock Growth Rate Adjustment':
            'Multiplicative adjustment to the base passenger stock growth rate. 1.0 = no change; 0.9 = 10% slower growth.',
        'PHEV Electric Driving Share':
            'Economy-wide fraction of PHEV driving done on electricity. One value applies across the whole economy and is used in Module 6.',
        'Freight GDP Elasticity Adjustment':
            'Multiplicative adjustment to the freight–GDP elasticity. 1.0 = no change; 0.8 = 20% lower elasticity.',
        'Reconciliation Bound Lower':
            'Minimum allowed adjustment factor during fuel reconciliation (e.g. 0.85 = −15% maximum downward correction).',
        'Reconciliation Bound Upper':
            'Maximum allowed adjustment factor during fuel reconciliation (e.g. 1.15 = +15% maximum upward correction).',
        'Reconciliation Weight':
            'Relative weight controlling how much of the reconciliation correction is absorbed by this component (stock, mileage, or efficiency). Weights across all three should sum to 1.',
        'Gasoline/Diesel Share Tolerance':
            'Acceptable deviation (%) between the gasoline/diesel split entered and the reconciled fuel total before a warning is raised.',
        'Survival Rate':
            'Age-dependent fraction of vehicles from a given vintage that remain on-road. Entered as a full age series (one value per age cohort).',
        'Vehicle Equivalent Weight':
            'Weighting factor used to convert vehicle types into comparable activity units for fleet-wide calculations.',
        'Vintage Profile Share':
            'Age distribution of the current stock, used to disaggregate the fleet into individual vintage cohorts. Entered as an age series.'
    },

    // Maps transport-param role keys → variable name in `variables` above.
    paramRoles: {
        pvs:                        'Passenger Vehicle Saturation',
        pvs_reached:                'Passenger Saturation Reached',
        passenger_growth_adjustment:'Passenger Stock Growth Rate Adjustment',
        freight_elasticity_adjustment:'Freight GDP Elasticity Adjustment',
        vew:                        'Vehicle Equivalent Weight'
    },

    // Reconciliation editor sub-field tooltips.
    reconciliation: {
        rowTitle:         'These values constrain how reconciliation adjusts stock, mileage, and/or efficiency to match fuel totals.',
        stockWeight:      'Share of the energy correction applied by adjusting vehicle stock.',
        stockLower:       'Minimum allowed stock adjustment factor (e.g. 0.85 = −15%).',
        stockUpper:       'Maximum allowed stock adjustment factor (e.g. 1.15 = +15%).',
        mileageWeight:    'Share of the energy correction applied by adjusting annual km per vehicle.',
        mileageLower:     'Minimum allowed mileage adjustment factor (e.g. 0.85 = −15%).',
        mileageUpper:     'Maximum allowed mileage adjustment factor (e.g. 1.15 = +15%).',
        efficiencyWeight: 'Share of the energy correction applied by adjusting fuel economy.',
        efficiencyLower:  'Minimum allowed efficiency adjustment factor (e.g. 0.90 = −10%).',
        efficiencyUpper:  'Maximum allowed efficiency adjustment factor (e.g. 1.10 = +10%).'
    },

    // Paired gasoline/diesel share row.
    pairedFuelShare: {
        rowTitle:  'Only the conventional gasoline/diesel split is shown here; alternative fuels such as biogasoline are excluded.',
        gasoline:  'Gasoline share: enter a fraction between 0 and 1 for this transport type.',
        diesel:    'Diesel share: enter a fraction between 0 and 1 for this transport type.',
        tolerance: 'Tolerance: acceptable deviation between this split and the reconciled fuel total (fraction, 0–1).'
    }
};
