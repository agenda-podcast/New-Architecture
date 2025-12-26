#!/usr/bin/env python3
"""
Template selection module for Blender video rendering.

Implements weighted random selection with controlled randomness
to ensure visually distinct videos while maintaining quality.
"""
import random
import hashlib
from pathlib import Path
from typing import List, Dict, Any, Optional
import yaml


class TemplateSelector:
    """
    Select Blender templates using weighted randomness.
    """
    
    def __init__(self, templates_dir: Path, inventory_path: Path):
        """
        Initialize template selector.
        
        Args:
            templates_dir: Path to templates directory
            inventory_path: Path to inventory.yml file
        """
        self.templates_dir = templates_dir
        self.inventory_path = inventory_path
        self.inventory = self._load_inventory()
        self.last_n_templates = []  # Track recently used templates
        self.max_history = 5  # Remember last N templates to avoid repeats
    
    def _load_inventory(self) -> Dict[str, Any]:
        """
        Load template inventory from YAML.
        
        Returns:
            Inventory dictionary
        """
        if not self.inventory_path.exists():
            print(f"Warning: Template inventory not found: {self.inventory_path}")
            return {}
        
        with open(self.inventory_path, 'r') as f:
            inventory = yaml.safe_load(f)
        
        return inventory
    
    def get_available_templates(self, category: str = None) -> List[str]:
        """
        Get list of available templates.
        
        Args:
            category: Category filter (safe, cinematic, experimental)
                     If None, returns all templates
        
        Returns:
            List of template IDs
        """
        templates = []
        
        for template_id, template_data in self.inventory.items():
            # Skip base template (not selectable)
            if not template_data.get('selectable', True):
                continue
            
            # Filter by category if specified
            if category and template_data.get('category') != category:
                continue
            
            templates.append(template_id)
        
        return templates
    
    def select_template(self, seed: str, style: str = 'auto') -> Optional[Dict[str, Any]]:
        """
        Select template using weighted random selection.
        
        Args:
            seed: Random seed for deterministic selection
            style: Selection style ('none', 'safe', 'cinematic', 'experimental', 'auto')
                  - 'none': Returns minimal template with no effects
                  - 'safe'/'cinematic'/'experimental': Forces specific category
                  - 'auto': Uses weighted selection (60% safe, 30% cinematic, 10% experimental)
        
        Returns:
            Template data dictionary or None if no template available
        """
        # Seed the random generator for deterministic selection
        random.seed(seed)
        
        # Handle special style cases
        if style == 'none':
            # Return minimal template (no effects)
            return self.inventory.get('minimal')
        
        # Determine category based on style
        if style == 'auto':
            # Weighted random selection
            weights = self.inventory.get('selection_weights', {
                'safe': 0.60,
                'cinematic': 0.30,
                'experimental': 0.10
            })
            
            categories = list(weights.keys())
            category_weights = list(weights.values())
            
            category = random.choices(categories, weights=category_weights)[0]
        else:
            # Force specific category
            category = style
        
        # Get available templates in category
        available_templates = self.get_available_templates(category)
        
        if not available_templates:
            print(f"Warning: No templates available in category '{category}'")
            return None
        
        # Exclude recently used templates to avoid repeats
        available_templates = [
            t for t in available_templates 
            if t not in self.last_n_templates
        ]
        
        # If all templates were recently used, reset history
        if not available_templates:
            self.last_n_templates = []
            available_templates = self.get_available_templates(category)
        
        # Select random template from available
        selected_id = random.choice(available_templates)
        selected_template = self.inventory.get(selected_id, {})
        
        # Update history
        self.last_n_templates.append(selected_id)
        if len(self.last_n_templates) > self.max_history:
            self.last_n_templates.pop(0)
        
        # Add template ID to result
        selected_template['id'] = selected_id
        
        return selected_template
    
    def get_template_path(self, template_id: str) -> Optional[Path]:
        """
        Get full path to template file.
        
        Args:
            template_id: Template ID from inventory
        
        Returns:
            Path to template .blend file or None if not found
        """
        template_data = self.inventory.get(template_id)
        
        if not template_data:
            return None
        
        relative_path = template_data.get('path')
        if not relative_path:
            return None
        
        # Resolve path relative to repo root
        template_path = self.templates_dir.parent / relative_path
        
        if not template_path.exists():
            print(f"Warning: Template file not found: {template_path}")
            return None
        
        return template_path
    
    def validate_template(self, template_id: str) -> bool:
        """
        Validate that template exists and is usable.
        
        Args:
            template_id: Template ID from inventory
        
        Returns:
            True if template is valid
        """
        template_path = self.get_template_path(template_id)
        
        if not template_path:
            return False
        
        if not template_path.exists():
            return False
        
        if not template_path.suffix == '.blend':
            print(f"Error: Template is not a .blend file: {template_path}")
            return False
        
        return True
    
    def get_effect_incompatibilities(self) -> List[List[str]]:
        """
        Get list of incompatible effect combinations.
        
        Returns:
            List of incompatibility pairs
        """
        constraints = self.inventory.get('constraints', {})
        return constraints.get('global_incompatibilities', [])
    
    def check_effect_compatibility(self, effects: List[str]) -> bool:
        """
        Check if effect combination is compatible.
        
        Args:
            effects: List of effects to check
        
        Returns:
            True if all effects are compatible
        """
        incompatibilities = self.get_effect_incompatibilities()
        
        for effect1 in effects:
            for effect2 in effects:
                if effect1 == effect2:
                    continue
                
                # Check if this pair is in incompatibilities list
                for incompatible_pair in incompatibilities:
                    if effect1 in incompatible_pair and effect2 in incompatible_pair:
                        return False
        
        return True


def generate_deterministic_seed(topic_id: str, date_str: str, content_code: str) -> str:
    """
    Generate deterministic seed from metadata.
    
    Args:
        topic_id: Topic ID (e.g., 'topic-01')
        date_str: Date string (YYYYMMDD)
        content_code: Content code (e.g., 'L1', 'M2')
    
    Returns:
        Hex seed string
    """
    seed_input = f"{topic_id}-{date_str}-{content_code}"
    seed_hash = hashlib.sha256(seed_input.encode()).hexdigest()
    return seed_hash[:12]


def main():
    """
    Test template selector.
    """
    import sys
    
    # Setup paths
    script_dir = Path(__file__).parent
    repo_root = script_dir.parent.parent
    templates_dir = repo_root / 'templates'
    inventory_path = templates_dir / 'inventory.yml'
    
    # Create selector
    selector = TemplateSelector(templates_dir, inventory_path)
    
    # Test seed generation
    seed = generate_deterministic_seed('topic-01', '20251219', 'L1')
    print(f"Generated seed: {seed}")
    
    # Test template selection
    print("\nTesting template selection:")
    
    for style in ['auto', 'safe', 'cinematic', 'experimental', 'none']:
        print(f"\n  Style: {style}")
        template = selector.select_template(seed, style)
        
        if template:
            template_id = template.get('id', 'unknown')
            print(f"    Selected: {template_id}")
            print(f"    Category: {template.get('category', 'unknown')}")
            print(f"    Effects: {template.get('effects', [])}")
            
            # Validate template
            is_valid = selector.validate_template(template_id)
            print(f"    Valid: {is_valid}")
        else:
            print("    No template selected")
    
    # Test effect compatibility
    print("\nTesting effect compatibility:")
    
    test_effects = [
        ['color_grade', 'grain'],  # Compatible
        ['heavy_glow', 'heavy_sharpen'],  # Incompatible
        ['film_burn', 'light_leaks'],  # Incompatible
    ]
    
    for effects in test_effects:
        compatible = selector.check_effect_compatibility(effects)
        status = "✓ Compatible" if compatible else "✗ Incompatible"
        print(f"  {effects}: {status}")
    
    return 0


if __name__ == '__main__':
    import sys
    sys.exit(main())
