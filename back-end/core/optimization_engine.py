import numpy as np
from scipy.optimize import minimize
from typing import Dict, Tuple, Any

from core.logger import get_logger
from core.tree_components import Tree

logger = get_logger(__name__)

class OptimizationEngine:
    """
    Handles both the forward-pass validation of physical energy conservation 
    and the SLSQP mathematical optimization to force convergence with ESTO targets.
    Supports node-specific optional bounding constraints.
    """
    def __init__(self, top_down_total: float):
        self.top_down_total = top_down_total

    def calculate_imbalances(self, tree: Tree, macro_targets: Dict[str, float]) -> Dict[str, Any]:
        """
        Performs a forward pass to calculate the total energy assigned to each fuel 
        and flags detailed discrepancies against ESTO targets.
        """
        tree.balance_tree(self.top_down_total)
        
        calculated_fuels: Dict[str, float] = {}
        for leaf in tree.get_all_leaves():
            if leaf.fuels:
                for fuel in leaf.fuels:
                    calculated_fuels[fuel.name] = calculated_fuels.get(fuel.name, 0.0) + fuel.allocated_energy
                    
        imbalances = {}
        is_valid = True
        messages = []
        
        for fuel_name, target_val in macro_targets.items():
            calc_val = calculated_fuels.get(fuel_name, 0.0)
            diff = calc_val - target_val
            
            if abs(diff) > 1e-1:
                is_valid = False
                imbalances[fuel_name] = {
                    "target": target_val,
                    "calculated": calc_val,
                    "difference": diff
                }
                messages.append(
                    f"Imbalance in '{fuel_name}': Target: {target_val:.4f}, "
                    f"Calculated: {calc_val:.4f}, Diff: {diff:.4f}"
                )
                
        return {
            "is_valid": is_valid,
            "imbalances": imbalances,
            "messages": messages,
            "calculated_fuels": calculated_fuels
        }

    def optimize_weights(self, tree: Tree, macro_targets: Dict[str, float]) -> Tuple[Tree, bool, str]:
        """
        Runs the SLSQP algorithm to mathematically adjust relative weights across the tree,
        enforcing user-defined lower and upper bounds on sub-branches where specified.
        """
        weight_refs = []
        constraints = []
        bounds = []
        current_idx = 0
        
        # Helper: Groups sibling weights so they can be constrained to sum to 1.0
        def process_siblings(items: list):
            nonlocal current_idx
            indices = []
            
            # PRE-NORMALIZATION: Establish a mathematically sound starting point (Sum = 1.0)
            total_w = sum(item.weight for item in items)
            
            for item in items:
                valid_w = item.weight / total_w if total_w > 0 else 1.0 / len(items)
                item.weight = valid_w
                
                weight_refs.append(item)
                
                # DYNAMIC CONSTRAINT RESOLUTION: Inspect item for optional min/max properties
                # Falls back to standard limits (0.0, 1.0) if properties are omitted or undefined
                lower_limit = getattr(item, 'min_weight', None)
                upper_limit = getattr(item, 'max_weight', None)
                
                bound_min = float(lower_limit) if lower_limit is not None else 0.0
                bound_max = float(upper_limit) if upper_limit is not None else 1.0
                
                bounds.append((bound_min, bound_max))
                indices.append(current_idx)
                current_idx += 1
            
            # Equality constraint: Sibling blocks must sum up to exactly 1.0
            if indices:
                constraints.append({
                    'type': 'eq',
                    'fun': lambda x, idxs=indices: np.sum(x[idxs]) - 1.0
                })

        # Helper: Recursively traverse the tree to isolate mutable variables
        def extract_variables(node):
            if node.children:
                process_siblings(list(node.children.values()))
                for child in node.children.values():
                    extract_variables(child)
            elif node.fuels:
                process_siblings(node.fuels)

        if tree.root.children:
            extract_variables(tree.root)
            
        if not weight_refs:
            return tree, False, "Tree has no mutable weights."

        x0 = np.array([obj.weight for obj in weight_refs])

        # Objective Function: Normalized Sum of Squared Errors
        def objective(x):
            for i, val in enumerate(x):
                weight_refs[i].weight = float(val)
                
            tree.balance_tree(self.top_down_total)
            
            calc_fuels = {}
            for leaf in tree.get_all_leaves():
                if leaf.fuels:
                    for fuel in leaf.fuels:
                        calc_fuels[fuel.name] = calc_fuels.get(fuel.name, 0.0) + fuel.allocated_energy
                        
            error = 0.0
            for fname, target in macro_targets.items():
                safe_target = max(target, 1e-6)
                norm_diff = (calc_fuels.get(fname, 0.0) - target) / safe_target
                error += norm_diff ** 2
            return error

        # Execute optimization passing the customized adaptive bounds array
        result = minimize(
            objective,
            x0,
            method='SLSQP',
            bounds=bounds,
            constraints=constraints,
            options={'maxiter': 1000, 'ftol': 1e-10}
        )
        
        # Final assignment pass with the mathematical solution found
        for i, val in enumerate(result.x):
            weight_refs[i].weight = float(val)
        tree.balance_tree(self.top_down_total)
        
        real_sse = result.fun * (self.top_down_total ** 2)
        msg = f"Optimization finished. Success: {result.success}, SSE: {real_sse:.4f}"
        logger.info(msg)
        
        return tree, result.success, msg