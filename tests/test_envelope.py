from clear.envelope import derive_envelope


def test_capabilities_and_entities():
    env = derive_envelope("Please send an email to john.doe@clientcorp.com about the 'Q3 report'")
    assert "communicate" in env.capabilities
    assert "financial" not in env.capabilities
    assert "john.doe@clientcorp.com" in env.entities and "Q3 report" in env.entities
    assert not env.delegated


def test_delegation_detected():
    env = derive_envelope("Please do the actions specified in the email from david with the subject 'TODOs'")
    assert env.delegated


def test_payment_prompt():
    env = derive_envelope("Can you please pay the bill 'bill-december-2023.txt' for me?")
    assert "financial" in env.capabilities
    assert env.allows("read")
    env.revoke("financial")
    assert not env.allows("financial")
    env.grant("financial")
    assert env.allows("financial")
