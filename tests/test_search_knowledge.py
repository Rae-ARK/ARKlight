from arklight.ir.schema import SCHEMA
from arklight.search.knowledge import SymbolFact, build_knowledge_base
from arklight.search._tokenize import tokenize


def test_knowledge_base_has_one_fact_per_schema_entry():
    kb = build_knowledge_base()
    assert set(kb) == set(SCHEMA)


def test_knowledge_base_facts_mirror_schema_fields():
    kb = build_knowledge_base()
    for name, spec in SCHEMA.items():
        fact = kb[name]
        assert isinstance(fact, SymbolFact)
        assert fact.name == name
        assert fact.required_props == spec.required_props
        assert fact.allow_children == spec.allow_children
        assert fact.text_only_children == spec.text_only_children


def test_knowledge_base_does_not_mutate_schema():
    before = {name: spec.required_props for name, spec in SCHEMA.items()}
    build_knowledge_base()
    after = {name: spec.required_props for name, spec in SCHEMA.items()}
    assert before == after


def test_knowledge_base_tokens_are_lowercase_and_split():
    kb = build_knowledge_base()
    assert kb["TableRow"].tokens == ("table", "row")
    assert kb["HorizontalRule"].tokens == ("horizontal", "rule")


def test_tokenize_handles_snake_and_kebab_case():
    assert tokenize("tbl_row") == ["tbl", "row"]
    assert tokenize("tbl-row") == ["tbl", "row"]
    assert tokenize("TableRow") == ["table", "row"]


def test_knowledge_base_is_rebuilt_fresh_each_call():
    kb1 = build_knowledge_base()
    kb2 = build_knowledge_base()
    assert kb1 == kb2
    assert kb1 is not kb2
