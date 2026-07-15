import pytest

from py_semantic_taxonomy.domain.constants import RelationshipVerbs
from py_semantic_taxonomy.domain.entities import (
    HierarchicRelationshipAcrossConceptScheme,
    HierarchyConflict,
    Relationship,
    RelationshipsReferencesConceptScheme,
)


async def test_relationships_get(graph_service, relationships):
    mock_kos_graph = graph_service.graph
    mock_kos_graph.relationships_get.return_value = relationships

    result = await graph_service.relationships_get(iri=relationships[3].source)
    assert result == relationships
    mock_kos_graph.relationships_get.assert_called_with(
        iri=relationships[3].source, source=True, target=False, verb=None
    )

    result = await graph_service.relationships_get(
        iri=relationships[3].source, source=False, target=True, verb=None
    )
    assert result == relationships
    mock_kos_graph.relationships_get.assert_called_with(
        iri=relationships[3].source, source=False, target=True, verb=None
    )


async def test_relationship_create(graph_service, relationships):
    mock_kos_graph = graph_service.graph
    mock_kos_graph.relationships_create.return_value = relationships
    # No concepts fetched => nothing to conflict with, relationships pass through.
    mock_kos_graph.concepts_hierarchy_info.return_value = []

    result = await graph_service.relationships_create(relationships)
    assert result == relationships
    mock_kos_graph.relationships_create.assert_called_with(relationships)


async def test_relationship_create_source_is_top_concept(graph_service, relationships):
    mock_kos_graph = graph_service.graph
    broader = next(r for r in relationships if r.predicate == RelationshipVerbs.broader)
    mock_kos_graph.concepts_hierarchy_info.return_value = [(broader.source, {"scheme"}, True)]

    with pytest.raises(HierarchyConflict) as excinfo:
        await graph_service.relationships_create([broader])
    assert excinfo.match("is marked as `topConceptOf`")
    mock_kos_graph.relationships_create.assert_not_called()


async def test_relationship_create_source_concept_missing(graph_service, relationships):
    mock_kos_graph = graph_service.graph
    mock_kos_graph.relationships_create.return_value = relationships
    mock_kos_graph.concepts_hierarchy_info.return_value = []

    broader = next(r for r in relationships if r.predicate == RelationshipVerbs.broader)
    await graph_service.relationships_create([broader])
    mock_kos_graph.relationships_create.assert_called_with([broader])


async def test_relationship_create_cross_concept_scheme_hierarchical(graph_service, relationships):
    mock_kos_graph = graph_service.graph
    rel = relationships[3]
    mock_kos_graph.concepts_hierarchy_info.return_value = [
        (rel.source, {"a"}, False),
        (rel.target, {"b"}, False),
    ]

    with pytest.raises(HierarchicRelationshipAcrossConceptScheme) as excinfo:
        await graph_service.relationships_create([rel])

    assert excinfo.match(
        f"Hierarchical relationship between `{rel.source}` and `{rel.target}` crosses Concept Schemes. Use an associative relationship like `skos:broadMatch` instead."
    )


async def test_relationship_create_reference_concept_scheme(graph_service, relationships):
    mock_kos_graph = graph_service.graph
    mock_kos_graph.concept_scheme_get_all_iris.return_value = ["a"]

    rel = Relationship(source="a", target="b", predicate=RelationshipVerbs.broad_match)
    with pytest.raises(RelationshipsReferencesConceptScheme) as excinfo:
        await graph_service.relationships_create([rel])
    assert excinfo.match(r"source refers to concept scheme `a`")

    rel = Relationship(source="b", target="a", predicate=RelationshipVerbs.broad_match)
    with pytest.raises(RelationshipsReferencesConceptScheme) as excinfo:
        await graph_service.relationships_create([rel])
    assert excinfo.match(r"target refers to concept scheme `a`")


async def test_relationship_create_cross_concept_scheme_associative(graph_service, relationships):
    mock_kos_graph = graph_service.graph
    mock_kos_graph.concepts_hierarchy_info.return_value = []

    associative = Relationship(
        source=relationships[3].source,
        target=relationships[3].target,
        predicate=RelationshipVerbs.broad_match,
    )
    # Associative relationships are allowed to cross Concept Schemes.
    await graph_service.relationships_create([associative])
    mock_kos_graph.relationships_create.assert_called_with([associative])


async def test_relationship_delete(graph_service, relationships):
    mock_kos_graph = graph_service.graph
    mock_kos_graph.relationships_delete.return_value = 1

    result = await graph_service.relationships_delete(relationships)
    assert result == 1
    mock_kos_graph.relationships_delete.assert_called_with(relationships)
