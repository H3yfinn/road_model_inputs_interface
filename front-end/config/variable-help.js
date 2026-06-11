// Single source of truth for all ? tooltip text shown next to Road Model variables.
// Used by app.js for every inline help tip; update here to change all tooltips at once.
const ROAD_VARIABLE_HELP = {

    // Keyed by the exact Variable column value from the CSV / ROAD_MODULE1_VALUE_RULES.
    variables: {
        'Stock':
            'Number of vehicles on the road for this row. In the base year, this is one of the main values used to anchor the model before projections begin.',

        'Sales Share':
            'Share of new vehicle sales going to this vehicle, drive, or fuel category. Enter as a percentage from 0 to 100. Higher values mean more new vehicles enter this category.',

        'Stock Share':
            'Share of the existing vehicle stock in this category. Enter as a percentage from 0 to 100. This is mainly used to set the base-year fleet split.',

        'Device Share':
            'Share of an engine type using this fuel. Enter as a percentage from 0 to 100. The fuel shares under the same engine type should add to 100%.',

        'Final On-Road Fuel Economy':
            'The effective fuel economy used in the model after any correction factors. Check the unit shown in the row, usually MJ/100 km. Lower values mean the vehicle uses less energy per km.',

        'Fuel Economy':
            'Energy used to drive a given distance for this vehicle and fuel. Check the unit shown in the row, usually MJ/100 km. Lower values mean better efficiency.',

        'Mileage':
            'Average distance travelled by each vehicle each year, in km per vehicle per year. Higher mileage increases energy use if stock and fuel economy stay the same.',

        'Passenger Vehicle Saturation':
            'Long-run passenger vehicle ownership level for the economy. This helps set where passenger vehicle stock growth slows or levels off.',

        'Passenger Saturation Reached':
            'Marks whether passenger vehicle ownership is already near its long-run saturation level. When true, passenger stock growth is treated more like a plateau than rapid motorisation.',

        'Passenger Stock Growth Rate Adjustment':
            'Multiplier applied to the default passenger stock growth path. Use 1.0 for no change, 0.9 for 10% slower growth, or 1.1 for 10% faster growth.',

        'PHEV Electric Driving Share':
            'Economy-wide share of PHEV driving done using electricity rather than liquid fuel. One value applies across the economy and is used later in the LEAP transport workflow.',

        'Freight GDP Elasticity Adjustment':
            'Multiplier applied to the default link between freight activity and GDP growth. Use 1.0 for no change, 0.8 for a weaker GDP link, or 1.2 for a stronger GDP link.',

        'Reconciliation Bound Lower':
            'Lowest adjustment factor allowed during base-year reconciliation. For example, 0.85 means this value can be adjusted down by up to 15%.',

        'Reconciliation Bound Upper':
            'Highest adjustment factor allowed during base-year reconciliation. For example, 1.15 means this value can be adjusted up by up to 15%.',

        'Reconciliation Weight':
            'Controls how much this item absorbs during base-year reconciliation. The stock, mileage, and efficiency weights should add to 1. Higher weight means more of the correction is applied here.',

        'Gasoline/Diesel Share Tolerance':
            'Allowed difference between the entered gasoline/diesel split and the reconciled fuel result before the tool warns you. Use this to avoid warnings for very small differences.',

        'Survival Rate':
            'Share of vehicles from each age group that remain on the road. This controls how quickly old vehicles retire and how many new sales are needed to replace them.',

        'Vehicle Equivalent Weight':
            'Conversion factor used to compare different vehicle types in a common ownership unit. For example, buses count more than cars because one bus represents much more transport capacity.',

        'Vintage Profile Share':
            'Age distribution of the base-year vehicle stock. This tells the model how much of the current fleet is new, middle-aged, or old.'
    },

    // Maps transport-param role keys → variable name in `variables` above.
    paramRoles: {
        pvs:                         'Passenger Vehicle Saturation',
        pvs_reached:                 'Passenger Saturation Reached',
        passenger_growth_adjustment: 'Passenger Stock Growth Rate Adjustment',
        freight_elasticity_adjustment:'Freight GDP Elasticity Adjustment',
        vew:                         'Vehicle Equivalent Weight'
    },

    // Reconciliation editor sub-field tooltips.
    reconciliation: {
        rowTitle:
            'Base-year reconciliation adjusts stock, mileage, and/or efficiency so modelled fuel use matches the observed fuel totals. These settings control how much adjustment is allowed.',

        stockWeight:
            'Share of the reconciliation correction applied by adjusting vehicle stock. Higher weight means stock changes more than mileage or efficiency.',

        stockLower:
            'Lowest stock adjustment allowed. For example, 0.85 means stock can be reduced by up to 15%.',

        stockUpper:
            'Highest stock adjustment allowed. For example, 1.15 means stock can be increased by up to 15%.',

        mileageWeight:
            'Share of the reconciliation correction applied by adjusting annual km per vehicle. Higher weight means mileage changes more than stock or efficiency.',

        mileageLower:
            'Lowest mileage adjustment allowed. For example, 0.85 means mileage can be reduced by up to 15%.',

        mileageUpper:
            'Highest mileage adjustment allowed. For example, 1.15 means mileage can be increased by up to 15%.',

        efficiencyWeight:
            'Share of the reconciliation correction applied by adjusting fuel economy. Higher weight means efficiency changes more than stock or mileage.',

        efficiencyLower:
            'Lowest fuel-economy adjustment allowed. For example, 0.90 means energy use per km can be reduced by up to 10%.',

        efficiencyUpper:
            'Highest fuel-economy adjustment allowed. For example, 1.10 means energy use per km can be increased by up to 10%.'
    },

    // Turnover calibration panel (detailed mode).
    turnoverCalibration: {
        rowTitle:
            'Turnover calibration reshapes the survival curve so the implied annual fleet replacement rate stays within the specified range. A higher rate means vehicles retire faster and more new sales are needed each year. Leave blank to use APEC-wide defaults (passenger 5–8 %/yr, freight 6–10 %/yr).',

        lowerRate:
            'Minimum acceptable fleet turnover rate, entered as a percentage. For example, 5 means at least 5 % of the fleet is replaced each year (average vehicle life ≤ 20 years). The model will stretch the survival curve if the implied rate falls below this.',

        upperRate:
            'Maximum acceptable fleet turnover rate, entered as a percentage. For example, 8 means no more than 8 % of the fleet is replaced each year (average vehicle life ≥ 12.5 years). The model will compress the survival curve if the implied rate exceeds this.',

        fitMode:
            'How the survival curve is adjusted to meet the turnover bounds. Auto: binary-searches for the best scale factor automatically (recommended). Manual: applies the fixed scale factor below. Pass-through: uses the curve as-is and only warns if it is out of bounds.'
    },

    // Paired gasoline/diesel share row.
    pairedFuelShare: {
        rowTitle:
            'This row only controls the conventional gasoline/diesel split. Alternative fuels such as biogasoline, biodiesel, electricity, and hydrogen are handled separately.',

        gasoline:
            'Gasoline share for this transport type. Enter as a fraction from 0 to 1, not a percentage. For example, 0.65 means 65%.',

        diesel:
            'Diesel share for this transport type. Enter as a fraction from 0 to 1, not a percentage. For example, 0.35 means 35%.',

        tolerance:
            'Allowed difference between the entered gasoline/diesel split and the reconciled result. Enter as a fraction from 0 to 1. For example, 0.02 allows a 2 percentage-point difference.'
    }
};