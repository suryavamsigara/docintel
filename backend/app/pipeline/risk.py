import logging

logger = logging.getLogger(__name__)

def run_risk_stage(anomaly_data: dict, ext_data: dict) -> dict:
    """Stage 4: Risk Scoring."""
    try:
        anomalies = anomaly_data.get("anomalies", [])
        doc_type = ext_data.get("doc_type", "other")
        
        # Base risk depends on document type
        base_scores = {
            "contract": 15,
            "nda": 10,
            "invoice": 5,
            "financial_statement": 10,
            "rfp": 5,
            "other": 5
        }
        
        overall_score = base_scores.get(doc_type, 10)
        
        category_breakdown = {
            "Legal": 0,
            "Financial": 0,
            "Compliance": 0,
            "Operational": 0
        }
        
        # Weighting
        weights = {
            "critical": 15,
            "warning": 5,
            "informational": 1
        }
        
        # Calculate raw penalty
        penalty_score = 0
        for anomaly in anomalies:
            sev = anomaly.get("severity", "informational").lower()
            cat = anomaly.get("category", "Operational")
            points = weights.get(sev, 1)
            
            penalty_score += points
            if cat in category_breakdown:
                category_breakdown[cat] += points
            else:
                category_breakdown["Operational"] += points
                
        # Calculate final score (Starts at 0 risk, adds penalties, asymptotes at 100)
        # Using a simple curve: Score = 100 * (1 - (0.98 ^ penalty_score))
        # This means 1 critical (15 pts) = ~53/100. 4 criticals (60 pts) = ~95/100.
        overall_score = int(100 * (1 - (0.98 ** penalty_score)))
        
        overall_score = max(overall_score, base_scores.get(doc_type, 5))
        overall_score = min(100, overall_score)
        
        # Determine level
        if overall_score < 40:
            level = "Low"
        elif overall_score < 75:
            level = "Medium"
        else:
            level = "High"

        return {
            "stage": "risk",
            "status": "complete",
            "data": {
                "overall_score": overall_score,
                "risk_level": level,
                "categories": category_breakdown,
                "total_anomalies": len(anomalies)
            }
        }
        
    except Exception as e:
        logger.error(f"Risk stage failed: {e}", exc_info=True)
        return {"stage": "risk", "status": "error", "error": str(e)}