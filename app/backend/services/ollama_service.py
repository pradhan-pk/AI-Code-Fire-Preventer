import aiohttp
import logging
import json
from typing import Optional, List, Dict, Any

logger = logging.getLogger(__name__)

class OllamaService:
    def __init__(self, base_url: str = "http://host.docker.internal:11434"):
        self.base_url = base_url
        self.model = "deepseek-coder-v2:16b"
    
    async def check_connection(self) -> bool:
        """Check if Ollama service is available"""
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(f"{self.base_url}/api/tags", timeout=aiohttp.ClientTimeout(total=5)) as response:
                    return response.status == 200
        except Exception as e:
            logger.error(f"Ollama connection check failed: {str(e)}")
            return False
    
    async def generate_embedding(self, text: str) -> List[float]:
        """Generate embedding for text using Ollama"""
        try:
            async with aiohttp.ClientSession() as session:
                payload = {
                    "model": self.model,
                    "prompt": text
                }
                
                async with session.post(
                    f"{self.base_url}/api/embeddings",
                    json=payload,
                    timeout=aiohttp.ClientTimeout(total=30)
                ) as response:
                    if response.status == 200:
                        data = await response.json()
                        return data.get('embedding', [])
                    else:
                        logger.error(f"Failed to generate embedding: {response.status}")
                        return []
        except Exception as e:
            logger.error(f"Error generating embedding: {str(e)}")
            return []
    
    async def analyze_code(self, code: str, context: str = "") -> Dict[str, Any]:
        """Analyze code using Ollama LLM"""
        try:
            prompt = f"""Analyze the following code and identify:
1. Key functions and their purpose
2. External dependencies and imports
3. Potential side effects
4. Data structures used

Code:
{code}

Context: {context}

Provide analysis in JSON format with keys: functions, dependencies, side_effects, data_structures"""
            
            async with aiohttp.ClientSession() as session:
                payload = {
                    "model": self.model,
                    "prompt": prompt,
                    "stream": False,
                    "options": {
                        "temperature": 0.2
                    }
                }
                
                async with session.post(
                    f"{self.base_url}/api/generate",
                    json=payload,
                    timeout=aiohttp.ClientTimeout(total=60)
                ) as response:
                    if response.status == 200:
                        data = await response.json()
                        response_text = data.get('response', '{}')
                        
                        # Try to parse JSON response
                        try:
                            return json.loads(response_text)
                        except:
                            return {"raw_analysis": response_text}
                    else:
                        logger.error(f"Failed to analyze code: {response.status}")
                        return {}
        except Exception as e:
            logger.error(f"Error analyzing code: {str(e)}")
            return {}
    
    async def analyze_impact(self, changed_code: str, dependent_code: str, module_context: str) -> Dict[str, Any]:
        """Analyze impact of code changes on dependent modules"""
        try:
            prompt = f"""Analyze the impact of the following code change on dependent modules:

Changed Code:
{changed_code}

Dependent Code:
{dependent_code}

Module Context: {module_context}

Determine:
1. Will this change break the dependent code? (yes/no)
2. Impact severity (low/medium/high/critical)
3. Specific breaking changes if any
4. Recommended actions

Provide response in JSON format with keys: will_break, severity, breaking_changes, recommendations"""
            
            async with aiohttp.ClientSession() as session:
                payload = {
                    "model": self.model,
                    "prompt": prompt,
                    "stream": False,
                    "options": {
                        "temperature": 0.1
                    }
                }
                
                async with session.post(
                    f"{self.base_url}/api/generate",
                    json=payload,
                    timeout=aiohttp.ClientTimeout(total=60)
                ) as response:
                    if response.status == 200:
                        data = await response.json()
                        response_text = data.get('response', '{}')
                        
                        try:
                            return json.loads(response_text)
                        except:
                            return {
                                "raw_analysis": response_text,
                                "will_break": "unknown",
                                "severity": "medium"
                            }
                    else:
                        return {"will_break": "unknown", "severity": "medium"}
        except Exception as e:
            logger.error(f"Error analyzing impact: {str(e)}")
            return {"will_break": "unknown", "severity": "medium"}