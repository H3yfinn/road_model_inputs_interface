import pandas as pd
import os
from core.logger import get_logger
from core.tree_components import Tree
from api.schemas import MacroDrivers

logger = get_logger(__name__)

class LEAPExporter:
    """
    Exports the fully balanced energy tree into a format 
    compatible with LEAP (Low Emissions Analysis Platform).
    """
    def __init__(self, tree: Tree, economy: str, year: int, sector_flow: str, macro_drivers: MacroDrivers, output_dir: str = "output"):
        self.tree: Tree = tree
        self.economy: str = economy
        self.year: int = year
        self.sector_flow: str = sector_flow
        self.macro_drivers = macro_drivers
        self.output_dir: str = output_dir

    def generate(self) -> str:
        """
        Traverses the balanced tree and generates an Excel workbook 
        with the final calculated energies for each branch.
        """
        os.makedirs(self.output_dir, exist_ok=True)
        
        data = []
        leaves = self.tree.get_all_leaves()
        
        if not leaves:
            raise ValueError("Cannot export an empty tree. Ensure the tree is built and balanced.")

        for leaf in leaves:
            # LEAP branches are usually separated by backslashes. 
            # We skip index 0 to omit the invisible 'root' node.
            # Example: 'Urban\Electricity\Space Heating\Heat Pump'
            branch_path = "\\".join(leaf.path[1:]) 
            
            # energy intensity calculation 
            driver_name = leaf.get_inherited_driver()
            driver_value = None
            intensity = 0.0
            
            if driver_name and hasattr(self.macro_drivers, driver_name):
                driver_value = getattr(self.macro_drivers, driver_name)
                if driver_value and driver_value > 0:
                    intensity = leaf.allocated_energy / driver_value
            elif driver_name is None:
                driver_name = "Not Assigned"

            # We extract both Allocated (Grid Demand) and Effective (Useful Energy) 
            # so the modeler has full transparency into the COP transformation.
            data.append({
                "Economy": self.economy,
                "Year": self.year,
                "Sector Flow": self.sector_flow,
                "LEAP Branch Path": branch_path,
                "Node Weight": round(leaf.weight, 4),
                "Efficiency (COP)": leaf.efficiency,
                "Final Energy Demand (Allocated)": round(leaf.allocated_energy, 4),
                "Useful Energy (Effective)": round(leaf.effective_energy, 4),
                "Macro Driver": driver_name,
                "Driver Value": driver_value if driver_value else "N/A",
                "Energy Intensity": round(intensity, 8) if intensity else 0.0
            })

        df = pd.DataFrame(data)
        
        # Construct a safe filename
        safe_flow_name = self.sector_flow.replace(" ", "_").replace(".", "")
        filename = f"{self.economy}_{self.year}_{safe_flow_name}_LEAP_Export.xlsx"
        filepath = os.path.join(self.output_dir, filename)
        
        # Export to Excel
        try:
            df.to_excel(filepath, index=False, sheet_name="LEAP_Data")
            logger.info(f"Successfully generated LEAP export at {filepath}")
        except Exception as e:
            logger.error(f"Failed to write Excel file: {e}")
            raise IOError(f"Could not save LEAP export to {filepath}. Ensure the directory is writable.")
        
        return filepath