"""Matching and scoring agent."""

import logging

from sqlalchemy.orm import Session

from app.ai.availability import evaluate_availability
from app.ai.scoring import calculate_candidate_score, calculate_final_score
from app.ai.state import GraphState
from app.db.models import SkillMaster, TeamMember, TeamMemberEmbedding, TeamMemberSkill
from app.db.repositories.embedding_repository import EmbeddingRepository
from app.db.session import SessionLocal
from app.services.embedding_generator import EmbeddingGenerator

logger = logging.getLogger(__name__)


def matching_scoring_node(state: GraphState) -> GraphState:
    """Execute deterministic matching and scoring for all team members.
    
    This node:
    1. Retrieves all active team members from the database
    2. Evaluates availability for each member
    3. Calculates skill and experience scores
    4. Populates state.candidate_scores with ranked results
    """
    logger.info("Executing Matching_Scoring_Agent node")
    
    # Extract required data from state
    normalized_skills = state.get("normalized_skills")
    requisition_input = state.get("requisition_input")
    parsed_jd = state.get("parsed_jd")
    
    if not normalized_skills or not requisition_input:
        logger.error("Missing required state: normalized_skills or requisition_input")
        state["error_message"] = "Missing normalized_skills or requisition_input"
        return state
    
    # Extract requisition parameters
    mandatory_skill_ids = normalized_skills.get("mandatory_skill_ids", [])
    preferred_skill_ids = normalized_skills.get("preferred_skill_ids", [])
    
    # Extract experience requirements from parsed_jd
    min_experience_months = None
    max_experience_months = None
    if parsed_jd and parsed_jd.get("experience"):
        min_experience_months = parsed_jd["experience"].get("min_months")
        max_experience_months = parsed_jd["experience"].get("max_months")
    
    # Extract date requirements for availability check
    expected_start_date = None
    requisition_duration_month = None
    if parsed_jd:
        expected_start_date = parsed_jd.get("expected_start_date")
        requisition_duration_month = parsed_jd.get("requisition_duration_month")
    
    # Query database for all active team members
    db: Session = SessionLocal()
    try:
        team_members = db.query(TeamMember).filter(TeamMember.is_active).all()

        logger.info(f"Found {len(team_members)} active team members to evaluate")

        # Build skill_id → skill_name lookup for enriching results
        skill_masters = db.query(SkillMaster).all()
        skill_id_to_name = {s.skill_id: s.skill_name for s in skill_masters}

        # --- Build rich JD embedding text from all available JD fields ---
        # Using only jd_text ignores title/role and explicit skill lists which are
        # the strongest semantic signals.  Combining them produces a much better
        # embedding for cosine-similarity matching against resume embeddings.
        jd_info = requisition_input.get("job_description", {})
        if isinstance(jd_info, dict):
            _title = jd_info.get("title", "")
            _role = jd_info.get("role", "")
            _mandatory_names: list[str] = jd_info.get("mandatory_skills", []) or []
            _preferred_names: list[str] = jd_info.get("preferred_skills", []) or []
            _jd_text = jd_info.get("jd_text", "")
            _embed_parts: list[str] = []
            if _title:
                _embed_parts.append(f"Job Title: {_title}")
            if _role:
                _embed_parts.append(f"Role: {_role}")
            if _mandatory_names:
                _embed_parts.append(f"Required Skills: {', '.join(_mandatory_names)}")
            if _preferred_names:
                _embed_parts.append(f"Preferred Skills: {', '.join(_preferred_names)}")
            if _jd_text:
                _embed_parts.append(f"Job Description: {_jd_text}")
            jd_embed_text = "\n".join(_embed_parts)
        else:
            _mandatory_names = []
            _preferred_names = []
            jd_embed_text = str(jd_info)

        # Lowercase JD skill terms used for fuzzy matching against resume metadata
        jd_mandatory_terms = [s.lower().strip() for s in _mandatory_names]
        jd_preferred_terms = [s.lower().strip() for s in _preferred_names]
        # Fall back to parsed_jd skill names if the form skill lists are empty
        if not jd_mandatory_terms and parsed_jd:
            jd_mandatory_terms = [
                s.lower().strip()
                for s in parsed_jd.get("extracted_mandatory_skills", [])
            ]
        if not jd_preferred_terms and parsed_jd:
            jd_preferred_terms = [
                s.lower().strip()
                for s in parsed_jd.get("extracted_preferred_skills", [])
            ]

        # --- Load resume profile text for fuzzy skill keyword matching ---
        # team_member_embeddings.metadata_json['skills'] can have extraction
        # artefacts (e.g. comma inside a rating like "Python (4, 5)" → broken list).
        # Searching the full profile_text (which contains the entire scrubbed resume)
        # is far more robust: if a JD skill term appears anywhere in the resume text
        # then the candidate mentioned it and should be considered a match.
        embedding_text_map: dict[str, str] = {}  # team_member_id → lowercase profile_text
        try:
            for emb in db.query(TeamMemberEmbedding).all():
                if emb.profile_text:
                    embedding_text_map[emb.team_member_id] = emb.profile_text.lower()
            logger.info(
                f"Loaded profile text for {len(embedding_text_map)} members from embeddings"
            )
        except Exception as e:
            logger.warning(f"Failed to load embedding profile text map: {e}")

        # --- Vector similarity: generate JD embedding and compare to stored resume embeddings ---
        vector_similarity_map: dict[str, float] = {}
        try:
            if jd_embed_text:
                embedder = EmbeddingGenerator()
                jd_embedding = embedder.generate(jd_embed_text)
                embedding_repo = EmbeddingRepository(db)
                similar = embedding_repo.find_similar_by_vector(jd_embedding, top_k=200)
                vector_similarity_map = {tid: sim for tid, sim in similar}
                logger.info(
                    f"Vector similarity computed for {len(vector_similarity_map)} members"
                )
        except Exception as e:
            logger.warning(f"JD embedding/similarity failed, skipping: {e}")

        candidate_scores = []

        # ------------------------------------------------------------------ #
        # Semantic pipeline (BGE + FAISS hybrid search + cross-encoder rerank) #
        # Try this first; if the FAISS store has indexed chunks we use it and  #
        # skip the heavy per-member scoring loop below.                        #
        # ------------------------------------------------------------------ #
        try:
            from app.services.vector_store import FaissVectorStore
            from app.services.semantic_pipeline import run_semantic_pipeline

            _store = FaissVectorStore.get_instance()
            if _store.total_vectors > 0:
                logger.info(
                    "FAISS store has %d vectors — running semantic pipeline",
                    _store.total_vectors,
                )

                # Pre-compute availability for every active member so the
                # semantic pipeline can apply availability scoring.
                avail_filter: dict[str, float] = {}
                for _m in team_members:
                    try:
                        _av = evaluate_availability(
                            db,
                            _m.team_member_id,
                            expected_start_date,
                            requisition_duration_month,
                            threshold_percentage=80.0,
                        )
                        avail_filter[_m.team_member_id] = _av["available_capacity"]
                    except Exception:
                        avail_filter[_m.team_member_id] = 100.0

                sem_results = run_semantic_pipeline(
                    jd_text=jd_embed_text,
                    jd_title=_title,
                    jd_role=_role,
                    mandatory_skills=_mandatory_names,
                    preferred_skills=_preferred_names,
                    min_experience_months=min_experience_months,
                    max_experience_months=max_experience_months,
                    db=db,
                    availability_filter=avail_filter,
                )

                if sem_results:
                    # Enrich with profile_url and normalised skill gap names
                    member_map = {m.team_member_id: m for m in team_members}
                    for c in sem_results:
                        member = member_map.get(c["team_member_id"])
                        c["profile_url"] = (member.profile_url if member else None) or ""
                        c["skills_matched_names"] = c.get("matched_skills", [])
                        matched_lower = {s.lower() for s in c.get("matched_skills", [])}
                        c["skill_gaps_names"] = [
                            s for s in _mandatory_names
                            if s.lower() not in matched_lower
                        ]

                    state["candidate_scores"] = sem_results
                    logger.info(
                        "Semantic pipeline returned %d candidates; skipping legacy loop",
                        len(sem_results),
                    )
                    return state
                else:
                    logger.info(
                        "Semantic pipeline returned no candidates; falling back to legacy scoring"
                    )
            else:
                logger.info(
                    "FAISS store is empty — falling back to legacy scoring loop"
                )
        except Exception as _sem_exc:
            logger.warning(
                "Semantic pipeline error — falling back to legacy scoring: %s",
                _sem_exc,
                exc_info=True,
            )

        # ------------------------------------------------------------------ #
        # Legacy deterministic scoring loop (used when FAISS is not populated) #
        # ------------------------------------------------------------------ #
        for member in team_members:
            try:
                # Get member's skills
                member_skill_ids = [
                    skill.skill_id 
                    for skill in db.query(TeamMemberSkill)
                    .filter(TeamMemberSkill.team_member_id == member.team_member_id)
                    .all()
                ]
                
                # Evaluate availability
                availability_result = evaluate_availability(
                    db,
                    member.team_member_id,
                    expected_start_date,
                    requisition_duration_month,
                    threshold_percentage=80.0,
                )
                
                # Calculate complete candidate score (include vector similarity if available)
                score_result = calculate_candidate_score(
                    team_member_id=member.team_member_id,
                    team_member_skill_ids=member_skill_ids,
                    team_member_experience_months=member.experience_in_months or 0,
                    mandatory_skill_ids=mandatory_skill_ids,
                    preferred_skill_ids=preferred_skill_ids,
                    min_experience_months=min_experience_months,
                    max_experience_months=max_experience_months,
                    is_available=availability_result["is_available"],
                    available_capacity=availability_result["available_capacity"],
                    vector_similarity=vector_similarity_map.get(member.team_member_id, 0.0),
                )

                # Enrich with display info
                score_result["full_name"] = member.full_name or member.team_member_id
                score_result["profile_url"] = member.profile_url

                # Enrich matched/gap skill IDs → human-readable names
                match_reasons = score_result.get("match_reasons", {})
                mandatory_matched = match_reasons.get("mandatory_matched", [])
                preferred_matched = match_reasons.get("preferred_matched", [])
                all_matched_ids = mandatory_matched + preferred_matched
                score_result["skills_matched_names"] = [
                    skill_id_to_name.get(sid, sid) for sid in all_matched_ids
                ]
                # Gaps = mandatory skills NOT in the member's matched list
                matched_mandatory_set = set(mandatory_matched)
                score_result["skill_gaps_names"] = [
                    skill_id_to_name.get(sid, sid)
                    for sid in mandatory_skill_ids
                    if sid not in matched_mandatory_set
                ]

                # --- Semantic fuzzy skill matching from resume embedding metadata ---
                # This scores candidates whose skills are stored in embedding metadata
                # rather than (or in addition to) skill_master / team_member_skill rows.
                # We search the full profile_text (scrubbed resume) for each JD skill term
                # using a simple case-insensitive keyword-in-text check.  This avoids
                # extraction artefacts in the metadata_json skills list.
                vec_sim_val = score_result.get("vector_similarity", 0.0)
                member_profile_text = embedding_text_map.get(member.team_member_id, "")
                metadata_mandatory_matched = 0
                metadata_preferred_matched = 0
                if member_profile_text:
                    for jd_term in jd_mandatory_terms:
                        if jd_term in member_profile_text:
                            metadata_mandatory_matched += 1
                    for jd_term in jd_preferred_terms:
                        if jd_term in member_profile_text:
                            metadata_preferred_matched += 1

                # Compute effective skill score: best of exact-ID match or fuzzy text match
                _n_jd_mandatory = len(jd_mandatory_terms) or 1
                _n_jd_preferred = len(jd_preferred_terms) or 1
                _meta_mand_ratio = metadata_mandatory_matched / _n_jd_mandatory
                _meta_pref_ratio = metadata_preferred_matched / _n_jd_preferred
                metadata_skill_score = 0.7 * _meta_mand_ratio + 0.3 * _meta_pref_ratio
                effective_skill_score = max(score_result["skill_score"], metadata_skill_score)

                if effective_skill_score > score_result["skill_score"]:
                    score_result["final_score"] = calculate_final_score(
                        effective_skill_score,
                        score_result["experience_score"],
                        vector_similarity=vec_sim_val,
                    )
                    score_result["skill_score"] = round(effective_skill_score, 4)
                    score_result["metadata_skill_score"] = round(metadata_skill_score, 4)
                    score_result["metadata_mandatory_matched"] = metadata_mandatory_matched
                    # Enrich matched skill names for display using the JD term labels
                    extra_matched: list[str] = []
                    for jd_term in jd_mandatory_terms:
                        if member_profile_text and jd_term in member_profile_text:
                            extra_matched.append(
                                next(
                                    (s for s in _mandatory_names if s.lower().strip() == jd_term),
                                    jd_term.title(),
                                )
                            )
                    if extra_matched:
                        score_result["skills_matched_names"] = list(
                            dict.fromkeys(
                                score_result.get("skills_matched_names", []) + extra_matched
                            )
                        )
                        _matched_lower = {n.lower().strip() for n in extra_matched}
                        score_result["skill_gaps_names"] = [
                            g for g in score_result.get("skill_gaps_names", [])
                            if g.lower().strip() not in _matched_lower
                        ]

                n_mandatory_matched = len(mandatory_matched)
                n_preferred_matched = len(preferred_matched)
                final_score_val = score_result.get("final_score", 0.0)

                # --- Relevance filter: exclude candidates with no connection to the JD ---
                #
                # Three gates — any one is sufficient for relevance:
                #   Gate 1 (exact): mandatory skill-master ID matched in team_member_skill
                #   Gate 2 (fuzzy): JD skill term substring-matched in resume metadata skills
                #   Gate 3 (semantic): cosine similarity of rich JD embedding vs resume >= 0.50
                #
                # Additionally final_score must be >= 0.30 to suppress noise.
                has_mandatory_skills_in_jd = (
                    len(mandatory_skill_ids) > 0 or len(jd_mandatory_terms) > 0
                )

                if has_mandatory_skills_in_jd:
                    has_relevance = (
                        (n_mandatory_matched >= 1)
                        or (metadata_mandatory_matched >= 1)
                        or (vec_sim_val >= 0.50)
                    )
                else:
                    # No mandatory skills at all — rely on metadata or vector alone
                    has_relevance = (metadata_mandatory_matched >= 1) or (vec_sim_val >= 0.45)

                above_min_score = final_score_val >= 0.30

                if not has_relevance or not above_min_score:
                    logger.debug(
                        f"Filtering out {member.team_member_id} "
                        f"({score_result.get('full_name', '')}): "
                        f"vec_sim={vec_sim_val:.3f}, "
                        f"mandatory_matched={n_mandatory_matched}, "
                        f"meta_mandatory_matched={metadata_mandatory_matched}, "
                        f"preferred_matched={n_preferred_matched}, "
                        f"final_score={final_score_val:.3f}"
                    )
                    continue

                candidate_scores.append(score_result)
                
            except Exception as e:
                logger.error(f"Error scoring team member {member.team_member_id}: {str(e)}", exc_info=True)
                continue
        
        # Sort candidates by final_score descending
        candidate_scores.sort(key=lambda x: x["final_score"], reverse=True)
        
        state["candidate_scores"] = candidate_scores
        logger.info(f"Matching_Scoring_Agent completed with {len(candidate_scores)} scored candidates")
        
    except Exception as e:
        logger.error(f"Error in matching_scoring_node: {str(e)}", exc_info=True)
        state["error_message"] = f"Matching scoring failed: {str(e)}"
    finally:
        db.close()
    
    return state
