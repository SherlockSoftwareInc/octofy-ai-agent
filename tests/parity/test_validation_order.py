"""Validation order contract: safety → sentinels → hash → critic → DB."""

from app.core.orchestrator import attempts as attempts_mod


def test_attempt_loop_source_defines_order():
    src = open(attempts_mod.__file__, encoding="utf-8").read()
    safety = src.find("# 1. Safety")
    sentinels = src.find("# 2. Sentinels")
    structural = src.find("# 3. Structural hash")
    db_pre = src.find("# 4. Attempt-1 DB pre-check before critic")
    critic = src.find("emit(PipelineStage.CRITIC")
    assert -1 not in {safety, sentinels, structural, db_pre, critic}
    assert safety < sentinels < structural < db_pre < critic
