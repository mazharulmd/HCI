import math
import random

from clear.baselines import ConfirmAll, EnvelopeOnly, InjectionDetector, StrictIFC
from clear.human_model import HumanParams, SimulatedUser, phi
from clear.manifest import ToolManifest
from clear.risk import Assessment, Tier

MAN = ToolManifest.load()


def fake(spec, **f):
    return Assessment(spec.name, {}, spec, {"tau": 0, "kappa": 0, "delta": 0, "iota": 0, **f}, 0, 0, Tier.ALLOW)


def test_baselines():
    send = MAN.get("send_email")
    read = MAN.get("get_unread_emails")
    assert ConfirmAll().decide(send, fake(send)) == "confirm"
    assert ConfirmAll().decide(read, fake(read)) == "allow"
    assert StrictIFC().decide(send, fake(send, tau=0.5)) == "deny"
    assert StrictIFC().decide(send, fake(send)) == "allow"
    assert EnvelopeOnly().decide(send, fake(send, delta=1.0)) == "deny"
    assert EnvelopeOnly().decide(send, fake(send, delta=0.5)) == "allow"
    assert InjectionDetector(0.5).flags(0.6) and not InjectionDetector(0.5).flags(0.4)


def test_sdt_probabilities():
    u = SimulatedUser(HumanParams(d0=1.0, d_prov=1.0, d_force=0.0, criterion=0.0, a_min=1.0, lam=10))
    # equal-variance SDT, unbiased criterion: P(deny | malicious) = Phi(d/2)
    assert math.isclose(u.p_deny(True, "confirm", evidence=True), phi(1.0), rel_tol=1e-9)
    assert math.isclose(u.p_deny(False, "confirm", evidence=True), phi(-1.0), rel_tol=1e-9)
    assert u.p_deny(True, "confirm", evidence=True) > u.p_deny(True, "confirm", evidence=False)


def test_habituation_and_forcing():
    p = HumanParams(a_min=0.2, lam=5.0)
    u = SimulatedUser(p, random.Random(0))
    first = u.attention("confirm")
    for _ in range(30):
        u.respond(False, "confirm", evidence=False)
    assert u.attention("confirm") < first
    assert abs(u.attention("confirm") - 0.2) < 0.01
    assert u.attention("force") == 1.0          # forcing dialogs keep engagement
    assert SimulatedUser(HumanParams(lam=float("inf"))).attention("confirm") == 1.0
