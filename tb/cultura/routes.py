from tb.cultura.controllers.tb_cultura_controller_summary import (
    TBCulturaDiagnosticCascade,
    TBCulturaResultsByMonth,
    TBCulturaSummaryIndicators,
    TBCulturaTatAndBacklog,
)
from tb.cultura.controllers.tb_cultura_controller_facility import TBCulturaFacilityMetrics
from tb.cultura.controllers.tb_cultura_controller_laboratory import TBCulturaLaboratoryMetrics
from tb.cultura.controllers.tb_cultura_controller_resistance import TBCulturaResistanceMetrics


def tb_cultura_routes(api):
    api.add_resource(
        TBCulturaSummaryIndicators,
        "/tb/cultura/summary/summary_indicators/",
    )
    api.add_resource(
        TBCulturaResultsByMonth,
        "/tb/cultura/summary/results_by_month/",
    )
    api.add_resource(
        TBCulturaTatAndBacklog,
        "/tb/cultura/summary/tat_and_backlog/",
    )
    api.add_resource(
        TBCulturaDiagnosticCascade,
        "/tb/cultura/summary/diagnostic_cascade/",
    )

    api.add_resource(
        TBCulturaFacilityMetrics,
        "/tb/cultura/facilities/metrics/",
    )
    api.add_resource(
        TBCulturaLaboratoryMetrics,
        "/tb/cultura/laboratories/metrics/",
    )
    api.add_resource(
        TBCulturaResistanceMetrics,
        "/tb/cultura/resistance/metrics/",
    )