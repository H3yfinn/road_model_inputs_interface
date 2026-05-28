import pandas as pd
import os
from typing import List, Optional
from core.logger import get_logger
from core.tree_components import Tree, Node
from api.schemas import MacroDrivers, UserVariable

logger = get_logger(__name__)


def _branch_path(node: Node) -> str:
    """Build backslash-separated LEAP branch path by walking up to the root."""
    parts = []
    current = node
    while current.parent is not None:
        parts.append(current.name)
        current = current.parent
    return "\\".join(reversed(parts))


def _inherited_driver(node: Node) -> Optional[str]:
    """Walk up the tree to find the nearest macro_driver assignment."""
    current = node
    while current is not None:
        if current.macro_driver:
            return current.macro_driver
        current = current.parent
    return None


class LEAPExporter:
    """
    Exports the fully balanced energy tree into a multi-sheet Excel workbook
    compatible with LEAP (Low Emissions Analysis Platform).

    Sheets produced:
      - LEAP_Data          : leaf-level energy outputs for LEAP import
      - Config_Parameters  : reconciliation weights and bounds for all tree nodes
      - User_Variables     : researcher-defined variables (optional, only if provided)
    """

    def __init__(
        self,
        tree: Tree,
        economy: str,
        year: int,
        sector_flow: str,
        macro_drivers: MacroDrivers,
        user_variables: Optional[List[UserVariable]] = None,
        output_dir: str = "output",
    ):
        self.tree = tree
        self.economy = economy
        self.year = year
        self.sector_flow = sector_flow
        self.macro_drivers = macro_drivers
        self.user_variables: List[UserVariable] = user_variables or []
        self.output_dir = output_dir

    # ------------------------------------------------------------------
    # Public entry point
    # ------------------------------------------------------------------

    def generate(self) -> str:
        os.makedirs(self.output_dir, exist_ok=True)

        safe_flow = self.sector_flow.replace(" ", "_").replace(".", "")
        filename = f"{self.economy}_{self.year}_{safe_flow}_LEAP_Export.xlsx"
        filepath = os.path.join(self.output_dir, filename)

        try:
            with pd.ExcelWriter(filepath, engine="openpyxl") as writer:
                self._write_leap_data(writer)
                self._write_config_parameters(writer)
                if self.user_variables:
                    self._write_user_variables(writer)
            logger.info(f"Successfully generated LEAP export at {filepath}")
        except Exception as e:
            logger.error(f"Failed to write Excel file: {e}")
            raise IOError(
                f"Could not save LEAP export to {filepath}. Ensure the directory is writable."
            )

        return filepath

    # ------------------------------------------------------------------
    # Sheet writers
    # ------------------------------------------------------------------

    def _write_leap_data(self, writer: pd.ExcelWriter) -> None:
        leaves = self.tree.get_all_leaves()
        if not leaves:
            raise ValueError(
                "Cannot export an empty tree. Ensure the tree is built and balanced."
            )

        data = []
        for leaf in leaves:
            path = _branch_path(leaf)
            driver_name = _inherited_driver(leaf)
            driver_value = None
            intensity = 0.0

            if driver_name and hasattr(self.macro_drivers, driver_name):
                driver_value = getattr(self.macro_drivers, driver_name)
                if driver_value and driver_value > 0:
                    intensity = leaf.allocated_energy / driver_value
            elif driver_name is None:
                driver_name = "Not Assigned"

            # For leaf nodes with fuels, report the first fuel's COP; for bare
            # leaf nodes (no fuels defined), fall back to 1.0.
            efficiency = leaf.fuels[0].efficiency if leaf.fuels else 1.0
            effective_energy = (
                sum(f.effective_energy for f in leaf.fuels)
                if leaf.fuels
                else leaf.allocated_energy
            )

            data.append(
                {
                    "Economy": self.economy,
                    "Year": self.year,
                    "Sector Flow": self.sector_flow,
                    "LEAP Branch Path": path,
                    "Node Weight": round(leaf.weight, 4),
                    "Efficiency (COP)": efficiency,
                    "Final Energy Demand (Allocated)": round(leaf.allocated_energy, 4),
                    "Useful Energy (Effective)": round(effective_energy, 4),
                    "Macro Driver": driver_name or "Not Assigned",
                    "Driver Value": driver_value if driver_value else "N/A",
                    "Energy Intensity": round(intensity, 8) if intensity else 0.0,
                }
            )

        pd.DataFrame(data).to_excel(writer, sheet_name="LEAP_Data", index=False)

    def _write_config_parameters(self, writer: pd.ExcelWriter) -> None:
        """Write a flat table of every tree node with its weights and bounds.

        This is the reconciliation config that Module 6 reads to apply
        user-specified min/max constraints during stock projection.
        """
        rows = []

        def _traverse(node: Node) -> None:
            if node.parent is not None:  # skip invisible root
                rows.append(
                    {
                        "LEAP Branch Path": _branch_path(node),
                        "Node Weight": round(node.weight, 6),
                        "Normalized Weight": round(node.normalized_weight, 6),
                        "Min Weight": node.min_weight if node.min_weight is not None else "",
                        "Max Weight": node.max_weight if node.max_weight is not None else "",
                        "Macro Driver": node.macro_driver or "",
                        "Is Leaf": node.is_leaf,
                        "Allocated Energy (PJ)": round(node.allocated_energy, 4),
                    }
                )
            for child in node.children.values():
                _traverse(child)

        _traverse(self.tree.root)

        if rows:
            pd.DataFrame(rows).to_excel(
                writer, sheet_name="Config_Parameters", index=False
            )

    def _write_user_variables(self, writer: pd.ExcelWriter) -> None:
        """Write researcher-defined variables to their own sheet."""
        data = [
            {
                "Category": v.category or "",
                "Variable Name": v.display_name,
                "Key": v.name,
                "Value": v.value,
                "Unit": v.unit or "",
                "Description": v.description or "",
            }
            for v in self.user_variables
        ]
        pd.DataFrame(data).to_excel(writer, sheet_name="User_Variables", index=False)
