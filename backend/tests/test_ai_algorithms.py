from app.ai_engine import decide_sos, estimate_road_risk, forward_chain, safest_route


def test_forward_chaining_derives_operational_facts():
    facts, explanation = forward_chain({'flood_level': 'high', 'medical_assistance': True})
    assert facts['critical_priority'] is True
    assert facts['hospital_required'] is True
    assert len(explanation) == 3


def test_risk_is_labeled_and_bounded():
    result = estimate_road_risk({'rainfall': 'high', 'river_proximity': 'high', 'flood_reports': 3})
    assert 0 <= result['unsafe_probability'] <= 1
    assert result['label'] == 'HIGH'


def test_route_avoids_blocked_road():
    route = safest_route()
    assert route['path'][0] == 'citizen'
    assert route['path'][-1] == 'shelter_07'


def test_decision_contains_explanation():
    decision = decide_sos({'medical_assistance': True})
    assert decision['priority'] == 'CRITICAL'
    assert decision['explanation']
