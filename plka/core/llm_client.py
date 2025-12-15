"""
LLMClient component for PLKA
Handles communication with local (KoboldCpp) and cloud LLMs
"""

import requests
import json
import os
from typing import Dict, Any, Optional
from pathlib import Path


class LLMClient:
    def __init__(self, config_path: str = "/workspace/plka/config/llm_profiles.json"):
        self.config_path = config_path
        self.config = self._load_config()
        self.koboldcpp_url = self.config.get('koboldcpp_url', 'http://localhost:5001')
    
    def _load_config(self) -> Dict[str, Any]:
        """Load LLM configuration, creating a default if it doesn't exist."""
        config_path = Path(self.config_path)
        
        if config_path.exists():
            with open(config_path, 'r') as f:
                return json.load(f)
        else:
            # Create a default configuration based on hardware detection
            default_config = self._create_default_config()
            
            # Ensure the config directory exists
            config_path.parent.mkdir(parents=True, exist_ok=True)
            
            # Write the default config
            with open(config_path, 'w') as f:
                json.dump(default_config, f, indent=2)
            
            return default_config
    
    def _create_default_config(self) -> Dict[str, Any]:
        """Create a default configuration based on hardware detection."""
        hardware_class = self._detect_hardware()
        
        # Define model recommendations based on hardware class
        model_profiles = {
            "cpu_low": {
                "planner": "phi3-mini-q5.gguf",
                "coder": "qwen2.5-coder-7b-q4.gguf"
            },
            "cpu_medium": {
                "planner": "phi3-mini-q5.gguf", 
                "coder": "qwen2.5-coder-14b-q4.gguf"
            },
            "cpu_high": {
                "planner": "deepseek-r1-7b-q4.gguf",
                "coder": "qwen2.5-coder-14b-q5.gguf"
            },
            "gpu_12gb+": {
                "planner": "deepseek-r1-14b-q4.gguf",
                "coder": "qwen2.5-coder-32b-q4.gguf"
            }
        }
        
        profiles = model_profiles.get(hardware_class, model_profiles["cpu_medium"])
        
        return {
            "hardware_class": hardware_class,
            "koboldcpp_url": "http://localhost:5001",
            "profiles": {
                "planner": {
                    "local": profiles["planner"],
                    "cloud": "gpt-4o-mini"
                },
                "coder": {
                    "local": profiles["coder"], 
                    "cloud": "gpt-4o"
                }
            }
        }
    
    def _detect_hardware(self) -> str:
        """Detect hardware capabilities to recommend appropriate models."""
        try:
            import psutil
            import subprocess
            
            cpu_cores = psutil.cpu_count()
            ram_gb = psutil.virtual_memory().total // (1024**3)
            
            # Check for NVIDIA GPU
            try:
                nvidia_result = subprocess.run(
                    ['nvidia-smi', '--query-gpu=memory.total', '--format=csv,noheader,nounits'], 
                    capture_output=True, 
                    text=True,
                    timeout=10
                )
                if nvidia_result.returncode == 0 and nvidia_result.stdout.strip():
                    gpu_vram = int(nvidia_result.stdout.strip().split('\n')[0])  # Take first GPU
                    if gpu_vram >= 12 * 1024:  # 12GB+
                        return "gpu_12gb+"
            except (subprocess.TimeoutExpired, subprocess.CalledProcessError, ValueError):
                # No GPU detected or error occurred
                pass
            
            # Fallback to CPU-based classification
            if ram_gb >= 32 and cpu_cores >= 8:
                return "cpu_high"
            elif ram_gb >= 16:
                return "cpu_medium"
            else:
                return "cpu_low"
        except ImportError:
            # If psutil is not available, default to medium
            return "cpu_medium"
    
    def generate(self, prompt: str, profile: str = "planner", use_cloud: bool = False) -> str:
        """
        Generate text using the specified profile.
        
        Args:
            prompt: Input prompt for the LLM
            profile: Either 'planner' or 'coder'
            use_cloud: Whether to use cloud model instead of local
            
        Returns:
            Generated text from the LLM
        """
        if use_cloud:
            # For now, we'll simulate cloud response - in a real implementation
            # this would call actual cloud APIs like OpenAI
            return self._simulate_cloud_response(prompt, profile)
        else:
            # Use local KoboldCpp
            return self._generate_with_koboldcpp(prompt, profile)
    
    def _generate_with_koboldcpp(self, prompt: str, profile: str) -> str:
        """Generate text using local KoboldCpp server."""
        url = f"{self.koboldcpp_url}/api/v1/generate"
        
        # Get model for the profile
        model_name = self.config['profiles'][profile]['local']
        
        payload = {
            'prompt': prompt,
            'max_length': 500,
            'temperature': 0.7,
            'top_p': 0.9,
            'rep_pen': 1.1,
            'singleline': False
        }
        
        try:
            response = requests.post(url, json=payload, timeout=120)
            response.raise_for_status()
            
            result = response.json()
            return result.get('results', [{}])[0].get('text', '').strip()
        except requests.exceptions.RequestException as e:
            # If KoboldCpp is not available, return a simulated response
            print(f"Warning: Could not connect to KoboldCpp at {self.koboldcpp_url}: {e}")
            return self._simulate_local_response(prompt, profile)
        except Exception as e:
            print(f"Error generating with KoboldCpp: {e}")
            return self._simulate_local_response(prompt, profile)
    
    def _simulate_cloud_response(self, prompt: str, profile: str) -> str:
        """Simulate a cloud-based LLM response."""
        # In a real implementation, this would call cloud APIs
        # For now, we'll return a simulated response based on the profile
        if profile == "planner":
            return f"[PLANNER SIMULATION] Based on your request: '{prompt[:50]}...', I recommend analyzing the code structure and creating a detailed plan for implementation."
        else:  # coder
            return f"[CODER SIMULATION] Here's the code implementation for: '{prompt[:50]}...'\n\n# Generated code would go here\npass"
    
    def _simulate_local_response(self, prompt: str, profile: str) -> str:
        """Simulate a local LLM response when KoboldCpp is unavailable."""
        if profile == "planner":
            return f"[LOCAL SIMULATION] Plan for: '{prompt[:50]}...'\n\n1. Analyze the existing codebase\n2. Identify the necessary changes\n3. Implement the solution\n4. Test the changes"
        else:  # coder
            return f"[LOCAL SIMULATION] Code for: '{prompt[:50]}...'\n\n# Implementation would go here\n# This is a simulated response since KoboldCpp is not available\ndef placeholder_function():\n    # TODO: Implement based on requirements\n    pass"


# Example usage:
if __name__ == "__main__":
    client = LLMClient()
    print("LLM Client initialized with config:", client.config)
    
    # Example: Generate a plan
    plan = client.generate("Create a function that adds two numbers", "planner")
    print("Plan:", plan)
    
    # Example: Generate code
    code = client.generate("Plan: Create a function that adds two numbers. Current code: def add(a, b):", "coder")
    print("Code:", code)