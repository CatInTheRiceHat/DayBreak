import json
import urllib.request
import urllib.error
import re
from typing import Dict, Any

OLLAMA_URL = "http://localhost:11434"
MODEL = "qwen3.5"

SYSTEM_PROMPT = """\
You are the natural language control engine for a healthy algorithmic recommender system.
The user will tell you their mood, what they want to see, or what they are avoiding.
You must translate their intent into a strict JSON configuration for the algorithm.

# Tuning Parameters:
- preset: Select the closest base template ("baseline", "entertainment", "learning", "inspiration").
- weights: Custom tuning of 4 dimensions (MUST sum to 1.0):
    * e (engagement): High if they just want viral/popular content.
    * d (diversity): High if they want to break their filter bubble.
    * p (prosocial): High if they are anxious/sad and need wholesome, educational, or uplifting content.
    * r (risk penalization): High if they are vulnerable, young, or explicitly avoiding toxic/stressful content.
- novelty_tolerance: (0.0 to 1.0) How "weird" or new the content should be. 0.0 = familiar comfort, 1.0 = wild serendipity.
- boost_topics: List of topic strings to feature heavily (e.g. ["sports", "gaming"]).
- reduce_topics: List of topic strings to hard-block (e.g. ["news"]).
- override_passive_history: true if the user implies they are bored of their current feed and want a hard reset; otherwise false.

# Return STRICT JSON ONLY. No markdown, no explanations.
Example output:
{
  "preset": "inspiration",
  "weights": {"e": 0.3, "d": 0.4, "p": 0.2, "r": 0.1},
  "boost_topics": ["lifestyle"],
  "reduce_topics": ["gaming", "news"],
  "novelty_tolerance": 0.8,
  "override_passive_history": false
}
"""

def parse_intent(user_text: str) -> Dict[str, Any]:
    """
    Takes user natural language input and queries the local Ollama LLM
    to generate UCRS algorithm configuration weights.
    """
    payload = json.dumps({
        "model": MODEL,
        "messages": [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": user_text}
        ],
        "stream": False,
        "think": False,  # skip reasoning overhead for speed
        "format": "json", 
        "options": {"temperature": 0.2}
    }).encode("utf-8")

    default_fallback = {
        "preset": "baseline",
        "weights": {"e": 0.6, "d": 0.2, "p": 0.1, "r": 0.1},
        "boost_topics": [],
        "reduce_topics": [],
        "novelty_tolerance": 0.5,
        "override_passive_history": False
    }

    try:
        req = urllib.request.Request(
            f"{OLLAMA_URL}/api/chat",
            data=payload,
            headers={"Content-Type": "application/json"},
            method="POST"
        )
        
        with urllib.request.urlopen(req, timeout=30) as resp:
            result = json.loads(resp.read())
            raw_text = result.get("message", {}).get("content", "")
            
            # Extract JSON carefully
            match = re.search(r"\{[^{}]*\}", raw_text, re.DOTALL)
            json_str = match.group() if match else raw_text
            
            try:
                parsed = json.loads(json_str)
                
                # Gentle merge into defaults
                out = default_fallback.copy()
                
                if "preset" in parsed:
                    out["preset"] = parsed["preset"]
                    
                if "weights" in parsed:
                    w = parsed["weights"]
                elif "e" in parsed and "d" in parsed:
                    w = parsed
                else:
                    w = None
                
                if w:
                    total = sum(float(w.get(k, 0)) for k in ["e", "d", "p", "r"])
                    if total > 0:
                        out["weights"] = {k: float(w.get(k, 0)) / total for k in ["e", "d", "p", "r"]}
                
                if "boost_topics" in parsed and isinstance(parsed["boost_topics"], list):
                    out["boost_topics"] = parsed["boost_topics"]
                if "reduce_topics" in parsed and isinstance(parsed["reduce_topics"], list):
                    out["reduce_topics"] = parsed["reduce_topics"]
                if "novelty_tolerance" in parsed:
                    out["novelty_tolerance"] = float(parsed["novelty_tolerance"])
                if "override_passive_history" in parsed:
                    out["override_passive_history"] = bool(parsed["override_passive_history"])
                    
                return out

            except json.JSONDecodeError:
                print(f"[intent] Parse failed on: {raw_text}")
                pass
                
    except Exception as e:
        print(f"[intent] LLM generation error: {e}")
        
    return default_fallback


if __name__ == "__main__":
    test_queries = [
        "I'm feeling really anxious and just want to look at some cute wholesome animal videos to calm down.",
        "I've been doomscrolling for an hour. Break me out of this loop and show me some crazy new science stuff.",
        "just show me whatever people are watching right now, no news though"
    ]
    
    print("Testing Chrysalis Natural Language UCRS Control...")
    print("=" * 60)
    for q in test_queries:
        print(f'USER INPUT: "{q}"')
        result = parse_intent(q)
        print(f"ALGORITHM JSON:")
        print(json.dumps(result, indent=2))
        print("-" * 60)
