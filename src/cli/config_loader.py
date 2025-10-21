"""
Configuration loader for CLI.

Handles loading and merging of configuration files with CLI arguments.
"""

import json
import os
from typing import Any, Dict, Optional

class ConfigLoader:
    """Loads and merges configuration from files and CLI arguments."""
    
    def __init__(self):
        """Initialize config loader."""
        pass
    
    def load_config_file(self, config_path: str) -> Dict[str, Any]:
        """
        Load configuration from JSON file.
        
        Args:
            config_path: Path to configuration file
            
        Returns:
            Dict[str, Any]: Configuration dictionary
            
        Raises:
            FileNotFoundError: If config file doesn't exist
            json.JSONDecodeError: If config file is invalid JSON
            ValueError: If config file contains invalid values
        """
        if not os.path.exists(config_path):
            raise FileNotFoundError(f"Configuration file not found: {config_path}")
        
        try:
            with open(config_path, 'r', encoding='utf-8') as f:
                config = json.load(f)
        except json.JSONDecodeError as e:
            raise json.JSONDecodeError(f"Invalid JSON in config file: {e}")
        
        # Validate basic structure
        if not isinstance(config, dict):
            raise ValueError("Configuration file must contain a JSON object")
        
        return config
    
    def merge_configs(self, base_config: Dict[str, Any], 
                     override_config: Dict[str, Any]) -> Dict[str, Any]:
        """
        Merge two configuration dictionaries.
        
        Args:
            base_config: Base configuration
            override_config: Configuration to override with
            
        Returns:
            Dict[str, Any]: Merged configuration
        """
        merged = base_config.copy()
        merged.update(override_config)
        return merged
    
    def args_to_config(self, args: Dict[str, Any]) -> Dict[str, Any]:
        """
        Convert CLI arguments to configuration dictionary.
        
        Args:
            args: Parsed CLI arguments
            
        Returns:
            Dict[str, Any]: Configuration dictionary
        """
        config = {}
        
        # Profile
        if hasattr(args, 'profile') and args.profile:
            config['profile'] = args.profile
        
        # Boolean flags
        boolean_flags = {
            'show_time': 'show_time',
            'no_time': 'show_time',
            'show_reactions': 'show_reactions', 
            'no_reactions': 'show_reactions',
            'show_reaction_authors': 'show_reaction_authors',
            'no_reaction_authors': 'show_reaction_authors',
            'show_optimization': 'show_optimization',
            'no_optimization': 'show_optimization',
            'show_markdown': 'show_markdown',
            'no_markdown': 'show_markdown',
            'show_links': 'show_links',
            'no_links': 'show_links',
            'show_tech_info': 'show_tech_info',
            'no_tech_info': 'show_tech_info',
            'show_service_notifications': 'show_service_notifications',
            'no_service_notifications': 'show_service_notifications',
        }
        
        for arg_name, config_key in boolean_flags.items():
            if hasattr(args, arg_name) and getattr(args, arg_name) is not None:
                # Handle negative flags (no_*)
                if arg_name.startswith('no_'):
                    config[config_key] = False
                else:
                    config[config_key] = True
        
        # String values
        string_fields = {
            'my_name': 'my_name',
            'partner_name': 'partner_name',
            'streak_break_time': 'streak_break_time',
        }
        
        for arg_name, config_key in string_fields.items():
            if hasattr(args, arg_name) and getattr(args, arg_name):
                config[config_key] = getattr(args, arg_name)
        
        return config
    
    def get_default_config(self) -> Dict[str, Any]:
        """
        Get default configuration.
        
        Returns:
            Dict[str, Any]: Default configuration
        """
        return {
            "profile": "group",
            "show_time": True,
            "show_reactions": True,
            "show_reaction_authors": False,
            "my_name": "Me",
            "partner_name": "Partner",
            "show_optimization": False,
            "streak_break_time": "20:00",
            "show_markdown": True,
            "show_links": True,
            "show_tech_info": True,
            "show_service_notifications": True,
        }
    
    def load_and_merge_config(self, config_path: Optional[str], 
                             cli_args: Dict[str, Any]) -> Dict[str, Any]:
        """
        Load configuration file and merge with CLI arguments.
        
        Args:
            config_path: Path to configuration file (optional)
            cli_args: CLI arguments dictionary
            
        Returns:
            Dict[str, Any]: Final merged configuration
        """
        # Start with default config
        final_config = self.get_default_config()
        
        # Load config file if provided
        if config_path:
            try:
                file_config = self.load_config_file(config_path)
                final_config = self.merge_configs(final_config, file_config)
            except Exception as e:
                raise ValueError(f"Failed to load config file: {e}")
        
        # Merge CLI arguments (highest priority)
        cli_config = self.args_to_config(cli_args)
        final_config = self.merge_configs(final_config, cli_config)
        
        return final_config
    
    def validate_config(self, config: Dict[str, Any]) -> list[str]:
        """
        Validate configuration dictionary.
        
        Args:
            config: Configuration to validate
            
        Returns:
            list[str]: List of validation issues (empty if valid)
        """
        issues = []
        
        # Required fields
        required_fields = ["profile", "show_time", "show_reactions"]
        for field in required_fields:
            if field not in config:
                issues.append(f"Missing required field: {field}")
        
        # Profile validation
        profile = config.get("profile")
        supported_profiles = ["group", "personal", "posts", "channel"]
        if profile not in supported_profiles:
            issues.append(f"Unsupported profile: {profile}. "
                         f"Supported: {', '.join(supported_profiles)}")
        
        # Boolean fields validation
        boolean_fields = [
            "show_time",
            "show_reactions", 
            "show_reaction_authors",
            "show_optimization",
            "show_markdown",
            "show_links",
            "show_tech_info",
            "show_service_notifications",
        ]
        for field in boolean_fields:
            if field in config and not isinstance(config[field], bool):
                issues.append(f"Field {field} must be boolean")
        
        # String fields validation
        string_fields = ["my_name", "partner_name", "streak_break_time"]
        for field in string_fields:
            if field in config and not isinstance(config[field], str):
                issues.append(f"Field {field} must be string")
        
        # Time format validation
        streak_time = config.get("streak_break_time", "")
        if streak_time:
            import re
            if not re.match(r"^\d{1,2}:\d{2}$", streak_time):
                issues.append("Field streak_break_time must be in HH:MM format")
        
        return issues
