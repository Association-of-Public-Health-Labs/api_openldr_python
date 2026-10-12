from app import app
from tb.cultura.controllers.tb_cultura_controller_facility import (
    TBCulturaFacilityMetrics,
)
from tb.cultura.controllers.tb_cultura_controller_laboratory import (
    TBCulturaLaboratoryMetrics,
)
from tb.cultura.controllers.tb_cultura_controller_resistance import (
    TBCulturaResistanceMetrics,
)
from tb.cultura.controllers.tb_cultura_controller_summary import (
    TBCulturaDiagnosticCascade,
    TBCulturaResultsByMonth,
    TBCulturaSummaryIndicators,
    TBCulturaTatAndBacklog,
)


COMMON_SWAGGER_PARAMS = (
    "#/parameters/ProvinceParameter",
    "#/parameters/DistrictParameter",
    "#/parameters/HealthFacilityParameter",
    "#/parameters/FacilityType",
    "#/parameters/DisaggregationParameter",
    "#/parameters/TypeOfLaboratory",
    "#/parameters/IntervalDates",
)


def test_tb_cultura_controllers_are_importable():
    assert TBCulturaSummaryIndicators
    assert TBCulturaResultsByMonth
    assert TBCulturaTatAndBacklog
    assert TBCulturaDiagnosticCascade
    assert TBCulturaFacilityMetrics
    assert TBCulturaLaboratoryMetrics
    assert TBCulturaResistanceMetrics


def test_tb_cultura_routes_are_registered():
    rules = {rule.rule for rule in app.url_map.iter_rules()}

    assert "/tb/cultura/summary/summary_indicators/" in rules
    assert "/tb/cultura/summary/results_by_month/" in rules
    assert "/tb/cultura/summary/tat_and_backlog/" in rules
    assert "/tb/cultura/summary/diagnostic_cascade/" in rules
    assert "/tb/cultura/facilities/metrics/" in rules
    assert "/tb/cultura/laboratories/metrics/" in rules
    assert "/tb/cultura/resistance/metrics/" in rules


def test_tb_cultura_controller_docs_include_common_parameters():
    controllers = (
        TBCulturaSummaryIndicators,
        TBCulturaResultsByMonth,
        TBCulturaTatAndBacklog,
        TBCulturaDiagnosticCascade,
        TBCulturaFacilityMetrics,
        TBCulturaLaboratoryMetrics,
    )

    for controller in controllers:
        doc = controller.get.__doc__
        for parameter in COMMON_SWAGGER_PARAMS:
            assert parameter in doc


def test_tb_cultura_resistance_docs_include_drug_parameter():
    doc = TBCulturaResistanceMetrics.get.__doc__

    for parameter in COMMON_SWAGGER_PARAMS:
        assert parameter in doc
    assert "#/parameters/DrugTypeParameter" in doc
