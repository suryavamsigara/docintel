import logging

logger = logging.getLogger(__name__)

def run_risk_stage(anomaly_data: dict, ext_data: dict) -> dict:
    """Stage 4: Risk Scoring."""
    try:
        anomalies = anomaly_data.get("anomalies", [])
        doc_type = ext_data.get("doc_type", "other")
        
        # Base risk depends on document type
        base_scores = {
            "contract": 20,
            "nda": 15,
            "invoice": 10,
            "financial_statement": 15,
            "rfp": 10,
            "other": 10
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
            "critical": 25,
            "warning": 10,
            "informational": 3
        }
        
        for anomaly in anomalies:
            sev = anomaly.get("severity", "informational").lower()
            cat = anomaly.get("category", "Operational")
            points = weights.get(sev, 3)
            
            overall_score += points
            if cat in category_breakdown:
                category_breakdown[cat] += points
            else:
                category_breakdown["Operational"] += points
                
        # Cap score at 100
        overall_score = min(100, overall_score)
        
        # Determine level
        if overall_score < 35:
            level = "Low"
        elif overall_score < 70:
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