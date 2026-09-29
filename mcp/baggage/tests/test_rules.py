from baggage_policy_mcp.rules import lookup_baggage_rules


def test_power_bank_checked_warns():
    result = lookup_baggage_rules(baggage_type="checked", item="power bank")
    assert result.disclaimer
    assert any("cabin" in w.lower() or "lithium" in w.lower() for w in result.warnings)
    assert "external_batteries" in result.matched_rule_ids


def test_liquid_over_100ml_cabin():
    result = lookup_baggage_rules(baggage_type="cabin", item="shampoo 250 ml")
    assert any("100 ml" in w for w in result.warnings)


def test_unknown_baggage_type_deterministic():
    result = lookup_baggage_rules(baggage_type="unknown", item="power bank")
    assert result.disclaimer.startswith("DEMONSTRATION")
    assert result.matched_rule_ids


def test_general_rules_include_disclaimer():
    result = lookup_baggage_rules(baggage_type="cabin", include_general_rules=True)
    assert result.general_rules
    assert "DEMONSTRATION" in result.disclaimer
