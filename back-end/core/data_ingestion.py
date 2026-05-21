import pandas as pd
from core.logger import get_logger
from typing import Dict, Optional

logger = get_logger(__name__)

class APECDataIngestor:
    """
    Handles the extraction and transformation of top-down macroeconomic 
    energy balances from the APEC wide-format CSV database.
    Leverages a multi-level hierarchical index (MultiIndex) for optimized 
    O(1) / O(log N) data retrieval.
    """
    def __init__(self, filepath: str, code_to_name_path: Optional[str] = None):
        self.filepath: str = filepath
        self.code_to_name_path: Optional[str] = code_to_name_path
        self._df: pd.DataFrame | None = None
        
        # Mapping dictionaries to translate frontend codes to DB strings
        self._code_map: Dict[str, str] = {}

    def load_data(self) -> None:
        """Loads the raw CSV and mapping files into memory and constructs the MultiIndex."""
        # 1. Load Main APEC Database
        raw_df = pd.read_csv(self.filepath, low_memory=False)
        raw_df.columns = raw_df.columns.str.strip().str.lower()
        raw_df['is_subtotal'] = raw_df['is_subtotal'].astype(str).str.strip().str.lower() == 'true'
        
        # Transform the flat DataFrame into a sorted MultiIndex structure for high-performance lookups
        raw_df.set_index(['economy', 'flows', 'is_subtotal', 'products'], inplace=True)
        raw_df.sort_index(inplace=True)
        self._df = raw_df
        
        # 2. Load Mapping Dictionary (if provided)
        if self.code_to_name_path:
            try:
                mapping_df = pd.read_csv(self.code_to_name_path)
                if '9th_label' in mapping_df.columns and 'esto_label' in mapping_df.columns:
                    valid_maps = mapping_df.dropna(subset=['9th_label', 'esto_label'])
                    self._code_map = dict(zip(valid_maps['9th_label'], valid_maps['esto_label']))
                logger.info("Successfully loaded database mappings.")
            except Exception as e:
                logger.error(f"Failed to load mapping CSV: {e}")

    def resolve_label(self, code_or_name: str) -> str:
        """Translates an internal tree code to the official APEC DB string if a mapping exists."""
        return self._code_map.get(code_or_name, code_or_name)

    def get_active_fuels(self, economy: str, year: int, sector_flow: str) -> Dict[str, float]:
        """
        Fetches the dynamic valid fuels for a specific sector/economy/year.
        Filters for physical base fuels (is_subtotal == False) with non-zero energy 
        and a product code prefix less than or equal to 17.
        """
        year_col = str(year)
        if self._df is not None and year_col not in self._df.columns:
            raise ValueError(f"Year '{year}' column not found in the database.")

        db_flow = self.resolve_label(sector_flow)
        active_fuels = {}
        
        try:
            # Slices the MultiIndex instantly down to the 'products' level for the given criteria
            # Resulting DataFrame is indexed solely by 'products'
            fuels_df = self._df.loc[(economy, db_flow, False)]
        except KeyError:
            # Return empty dictionary if no matching records exist for the economy/flow combination
            return {}

        # Extract the target year series and drop missing values efficiently
        year_series = fuels_df[year_col].fillna(0.0)
        
        for product_name, val in year_series.items():
            val_float = float(val)
            if val_float == 0.0:
                continue
            try:
                product_str = str(product_name)
                # Extract the numeric prefix (e.g., "07.01" from "07.01 Natural gas")
                prefix_str = product_str.split(' ')[0]
                main_prefix = int(prefix_str.split('.')[0])
                
                if main_prefix <= 17:
                    active_fuels[product_str] = val_float
            except (ValueError, IndexError):
                # Skip products that do not follow the standard numeric prefix convention
                continue
                
        return active_fuels

    def get_total_energy(self, economy: str, year: int, sector_flow: str) -> float:
        """
        Fetches the '19 Total' macro energy aggregate for a specific sector/flow.
        Used to initialize the root node of the energy tree.
        """
        year_col = str(year)
        if self._df is not None and year_col not in self._df.columns:
            raise ValueError(f"Year '{year}' column not found in the database.")

        db_flow = self.resolve_label(sector_flow)

        try:
            # Direct MultiIndex tuple coordination lookup: O(1) complexity
            total_val = self._df.loc[(economy, db_flow, True, '19 Total'), year_col]
            
            # Handle potential non-unique row edge cases safely by resolving to a scalar
            if isinstance(total_val, pd.Series):
                if total_val.empty:
                    raise ValueError(f"No '19 Total' record found for Economy: {economy}, Flow: {db_flow}")
                return float(total_val.iloc[0])
                
            return float(total_val)
        except KeyError:
            raise ValueError(f"No '19 Total' record found for Economy: {economy}, Flow: {db_flow}")

    def get_fuel_limits(self, economy: str, year: int, sector_flow: str) -> Dict[str, float]:
        """
        Fetches the specific base fuel totals for top-down validation.
        Returns a dictionary mapping fuel product strings to their maximum allowed macroeconomic energy.
        """
        year_col = str(year)
        db_flow = self.resolve_label(sector_flow)

        try:
            # Instantly slice the hierarchy to retrieve base fuels
            fuels_df = self._df.loc[(economy, db_flow, False)]
            
            # Enforce exclusion of the total aggregator if misclassified under base fuels
            if '19 Total' in fuels_df.index:
                fuels_df = fuels_df.drop('19 Total')
                
            if fuels_df.empty:
                logger.warning(f"No base fuel records found for Economy: {economy}, Flow: {db_flow}")
                return {}
                
            return fuels_df[year_col].fillna(0.0).to_dict()
        except KeyError:
            logger.warning(f"No base fuel records found for Economy: {economy}, Flow: {db_flow}")
            return {}