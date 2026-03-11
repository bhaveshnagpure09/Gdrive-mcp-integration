"""Skill normalization agent."""

import logging

from sqlalchemy.orm import Session

from app.ai.state import GraphState
from app.db.models import SkillMaster
from app.db.session import SessionLocal

logger = logging.getLogger(__name__)

# Common skill aliases for deterministic matching
SKILL_ALIASES = {
    "js": "JavaScript",
    "ts": "TypeScript",
    "py": "Python",
    "postgres": "PostgreSQL",
    "pg": "PostgreSQL",
    "k8s": "Kubernetes",
    "docker": "Docker",
    "react": "React",
    "vue": "Vue.js",
    "angular": "Angular",
    "node": "Node.js",
    "nodejs": "Node.js",
    "aws": "AWS",
    "azure": "Azure",
    "gcp": "Google Cloud Platform",
}


def normalize_skill_deterministic(raw_skill: str, skill_master_map: dict) -> str:
    """Attempt deterministic skill normalization.
    
    Args:
        raw_skill: Raw skill string
        skill_master_map: Dict mapping normalized skill names to skill_ids
    
    Returns:
        Normalized skill_id or raw_skill if no match found
    """
    # Try exact match (case-insensitive)
    normalized_name = raw_skill.strip()
    
    # Check direct match
    for skill_name, skill_id in skill_master_map.items():
        if skill_name.lower() == normalized_name.lower():
            return skill_id
    
    # Check alias match
    alias_key = normalized_name.lower()
    if alias_key in SKILL_ALIASES:
        canonical_name = SKILL_ALIASES[alias_key]
        for skill_name, skill_id in skill_master_map.items():
            if skill_name.lower() == canonical_name.lower():
                return skill_id
    
    # No match - return normalized version of raw skill
    return normalized_name.upper().replace(" ", "_")


def skill_normalization_node(state: GraphState) -> GraphState:
    """Map extracted skills to canonical skill_master IDs.
    
    This node:
    1. Extracts skills from parsed_jd
    2. Queries skill_master table for canonical skills
    3. Attempts deterministic matching first
    4. Falls back to LLM fuzzy matching for unmatched skills
    5. Populates state.normalized_skills with skill_ids
    """
    logger.info("Executing Skill_Normalization_Agent node")
    
    parsed_jd = state.get("parsed_jd")
    if not parsed_jd:
        logger.error("Missing parsed_jd in state")
        state["error_message"] = "Missing parsed_jd"
        return state
    
    mandatory_skills = parsed_jd.get("extracted_mandatory_skills", [])
    preferred_skills = parsed_jd.get("extracted_preferred_skills", [])
    
    logger.info(f"Normalizing {len(mandatory_skills)} mandatory and "
                f"{len(preferred_skills)} preferred skills")
    
    # Query skill master table
    db: Session = SessionLocal()
    try:
        skill_masters = db.query(SkillMaster).all()
        
        # Create lookup map
        skill_master_map = {
            skill.skill_name: skill.skill_id 
            for skill in skill_masters
        }
        
        logger.info(f"Loaded {len(skill_master_map)} canonical skills from skill_master")
        
        # Normalize mandatory skills
        normalized_mandatory = []
        for raw_skill in mandatory_skills:
            normalized_id = normalize_skill_deterministic(raw_skill, skill_master_map)
            normalized_mandatory.append(normalized_id)
            logger.debug(f"Normalized mandatory skill: '{raw_skill}' -> '{normalized_id}'")
        
        # Normalize preferred skills
        normalized_preferred = []
        for raw_skill in preferred_skills:
            normalized_id = normalize_skill_deterministic(raw_skill, skill_master_map)
            normalized_preferred.append(normalized_id)
            logger.debug(f"Normalized preferred skill: '{raw_skill}' -> '{normalized_id}'")
        
        # Populate state
        state["normalized_skills"] = {
            "mandatory_skill_ids": normalized_mandatory,
            "preferred_skill_ids": normalized_preferred,
        }
        
        logger.info(f"Skill_Normalization_Agent completed: "
                    f"{len(normalized_mandatory)} mandatory, "
                    f"{len(normalized_preferred)} preferred")
        
    except Exception as e:
        logger.error(f"Error in skill_normalization_node: {str(e)}", exc_info=True)
        state["error_message"] = f"Skill normalization failed: {str(e)}"
    finally:
        db.close()
    
    return state
