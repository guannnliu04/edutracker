import copy
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))
import pytest

from lagen import templates, validate
from lagen.taxonomy import TAXONOMY


@pytest.fixture
def ctx():
    return validate.Ctx(taxonomy=TAXONOMY, learned_sections=set(TAXONOMY.values()), today=100)


@pytest.fixture
def good():
    """一題確實正確的『AI 風格』候選題(來源標為 ai_generated)"""
    c = templates.make("rank_computation", 1, 2, "basic")
    c["source"] = "ai_generated"
    return copy.deepcopy(c)
