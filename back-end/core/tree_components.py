from typing import Optional, Dict, Any, List

class FuelItem:
    """Internal domain model for fuels attached to leaf nodes."""
    def __init__(self, name: str, weight: float, efficiency: float = 1.0):
        self.name = name
        self.weight = weight
        self.efficiency = efficiency
        
        self.normalized_weight: float = 0.0
        self.allocated_energy: float = 0.0
        self.effective_energy: float = 0.0

class Node:
    """Represents an element in the hierarchy without altering energy balance."""
    def __init__(self, name: str, weight: float, parent: Optional['Node'] = None):
        self.name: str = name
        self.weight: float = weight
        # Added optional bounding constraints for intermediate or leaf weight configurations
        self.min_weight: Optional[float] = None
        self.max_weight: Optional[float] = None
        self.macro_driver: Optional[str] = None
        self.tags: List[str] = []
        self.parent: Optional['Node'] = parent
        self.children: Dict[str, 'Node'] = {}
        self.fuels: List[FuelItem] = []
        
        self.normalized_weight: float = 0.0  
        self.allocated_energy: float = 0.0

    def add_child(self, child_node: 'Node') -> None:
        self.children[child_node.name] = child_node
        child_node.parent = self
    
    @property
    def is_leaf(self) -> bool:
        return len(self.children) == 0


class Tree:
    def __init__(self, root_name: str = "root"):
        self.root = Node(name=root_name, weight=1.0)
        self.root.normalized_weight = 1.0

    def build_from_state(self, state_data: dict, current_node: Optional[Node] = None) -> None:
        if current_node is None:
            current_node = self.root

        for key, value_obj in state_data.items():
            is_dict = isinstance(value_obj, dict)
            weight = value_obj.get('weight', 0.0) if is_dict else getattr(value_obj, 'weight', 0.0)
            
            child_node = Node(name=key, weight=weight, parent=current_node)
            
            # Extract optional weight boundaries from incoming API schema structure
            child_node.min_weight = value_obj.get('min_weight') if is_dict else getattr(value_obj, 'min_weight', None)
            child_node.max_weight = value_obj.get('max_weight') if is_dict else getattr(value_obj, 'max_weight', None)
            
            child_node.macro_driver = value_obj.get('macro_driver') if is_dict else getattr(value_obj, 'macro_driver', None)

            node_tags = value_obj.get('tags') if is_dict else getattr(value_obj, 'tags', None)
            if node_tags:
                child_node.tags = node_tags
            
            # Extract assigned fuels if present
            fuels_data = value_obj.get('fuels') if is_dict else getattr(value_obj, 'fuels', None)
            if fuels_data:
                for f_data in fuels_data:
                    f_dict = f_data if isinstance(f_data, dict) else vars(f_data)
                    child_node.fuels.append(
                        FuelItem(f_dict['name'], f_dict['weight'], f_dict.get('efficiency', 1.0))
                    )

            current_node.add_child(child_node)
            
            children = value_obj.get('children') if is_dict else getattr(value_obj, 'children', None)
            if children:
                self.build_from_state(children, child_node)

    def balance_tree(self, top_down_total_energy: float) -> None:
        self.root.allocated_energy = top_down_total_energy
        self._distribute_energy(self.root)

    def _distribute_energy(self, node: Node) -> None:
        if node.is_leaf:
            # Reached final generation: Distribute energy into the assigned fuels
            if node.fuels:
                total_f_weight = sum(f.weight for f in node.fuels)
                for fuel in node.fuels:
                    fuel.normalized_weight = fuel.weight / total_f_weight if total_f_weight > 0 else (1.0 / len(node.fuels))
                    # The allocated physical energy
                    fuel.allocated_energy = node.allocated_energy * fuel.normalized_weight
                    # Only apply efficiency at the very end
                    fuel.effective_energy = fuel.allocated_energy * fuel.efficiency
            return

        total_weight = sum(child.weight for child in node.children.values())
        
        for child in node.children.values():
            child.normalized_weight = child.weight / total_weight if total_weight > 0 else (1.0 / len(node.children))
            # Strict energy propagation
            child.allocated_energy = node.allocated_energy * child.normalized_weight
            
            self._distribute_energy(child)

    def to_calculated_schema(self) -> dict:
        return {name: self._node_to_dict(child) for name, child in self.root.children.items()}
        
    def _node_to_dict(self, node: Node) -> dict:
        # Included min_weight and max_weight in the outbound calculated serial representation
        data = {
            "weight": node.weight,
            "normalized_weight": node.normalized_weight,
            "min_weight": node.min_weight,
            "max_weight": node.max_weight,
            "macro_driver": node.macro_driver,
            "tags": node.tags if node.tags else None,
            "allocated_energy": node.allocated_energy,
        }
        
        if node.fuels:
            data["fuels"] = [{
                "name": f.name,
                "weight": f.weight,
                "efficiency": f.efficiency,
                "normalized_weight": f.normalized_weight,
                "allocated_energy": f.allocated_energy,
                "effective_energy": f.effective_energy
            } for f in node.fuels]
        else:
            data["fuels"] = None
            
        if not node.is_leaf:
            data["children"] = {name: self._node_to_dict(child) for name, child in node.children.items()}
        else:
            data["children"] = None
            
        return data

    def get_all_leaves(self) -> list[Node]:
        leaves = []
        def _traverse(n: Node) -> None:
            if n.is_leaf:
                leaves.append(n)
            for child in n.children.values():
                _traverse(child)
        _traverse(self.root)
        return leaves