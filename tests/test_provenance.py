from clear.provenance import ProvenanceLedger, canonical_url, flatten_values


def make_ledger():
    led = ProvenanceLedger()
    led.add_system("You are an assistant for Emma Johnson.")
    led.add_user("Please pay the bill 'bill-december-2023.txt' and email bob@corp.com")
    led.add_tool_output("get_iban", {}, "DE89370400440532013000", trust="trusted", private=True)
    led.add_tool_output("read_file", {"file_path": "bill.txt"},
                        "Pay to US133000000121212121212. Visit www.evil-site.com/x", trust="untrusted", private=True)
    return led


def test_origin_precedence():
    led = make_ledger()
    assert led.attribute("bob@corp.com").origin == "user"
    assert led.attribute("DE89370400440532013000").origin == "trusted"
    att = led.attribute("US133000000121212121212")
    assert att.origin == "external" and att.tainted and att.sources == [3]
    assert led.attribute("CH0000000000000000000").origin == "unattributed"
    assert led.attribute("no").origin == "trivial"


def test_identifier_matching_ignores_formatting():
    led = make_ledger()
    assert led.attribute("US13 3000 0001 2121 2121 212").origin == "external"


def test_url_canonicalisation():
    assert canonical_url("https://www.evil-site.com/x/") == "evil-site.com/x"
    assert canonical_url("hello world") is None
    led = make_ledger()
    assert led.attribute("http://www.evil-site.com/x").origin == "external"


def test_flatten_values():
    assert flatten_values({"a": [1, "x", None], "b": 2.50}) == ["1", "x", "2.5"]
    assert flatten_values(True) == []


def test_private_data_carried():
    led = ProvenanceLedger()
    led.add_user("summarise my inbox")
    led.add_tool_output("get_received_emails", {}, "Your Facebook security code is 463820", "untrusted", True)
    assert led.private_data_carried("the code is 463820") == [1]
    assert led.private_data_carried("nothing sensitive here") == []
