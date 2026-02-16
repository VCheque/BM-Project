"""Audience-oriented interpretation helpers."""

from __future__ import annotations


def audience_paragraph(
    lens: str,
    *,
    lang: str,
    accounts_per_capita: float,
    digital_share_pct: float,
    infra_per_100k: float,
) -> str:
    if lang == "PT":
        if lens == "Investidor":
            return (
                f"O indicador mostra penetração bancária de {accounts_per_capita:.2f} contas por pessoa elegível, "
                f"com peso digital de {digital_share_pct:.1f}% e densidade de infraestrutura de {infra_per_100k:.1f} "
                "pontos por 100 mil habitantes. A leitura conjunta apoia avaliação de escala, tração e capacidade."
            )
        if lens == "Investigador":
            return (
                f"A série revela {accounts_per_capita:.2f} contas por pessoa elegível, participação digital de "
                f"{digital_share_pct:.1f}% e infraestrutura de {infra_per_100k:.1f} pontos por 100 mil habitantes. "
                "Este conjunto permite comparar acesso, uso e capacidade com metodologia consistente."
            )
        if lens == "Empresa":
            return (
                f"A base de {accounts_per_capita:.2f} contas por pessoa elegível, combinada com {digital_share_pct:.1f}% "
                f"de peso digital e {infra_per_100k:.1f} pontos por 100 mil habitantes, oferece sinal para dimensionar "
                "cobertura comercial e priorização territorial."
            )
        return (
            f"Com {accounts_per_capita:.2f} contas por pessoa elegível e {digital_share_pct:.1f}% de peso digital, "
            f"a densidade de {infra_per_100k:.1f} pontos por 100 mil habitantes ajuda a perceber onde há maior espaço "
            "para oferta e parceria local."
        )

    if lens == "Investor":
        return (
            f"The market shows {accounts_per_capita:.2f} accounts per eligible person, "
            f"{digital_share_pct:.1f}% digital share, and {infra_per_100k:.1f} infrastructure points per 100k people. "
            "This combination supports sizing, traction, and capacity assessment."
        )
    if lens == "Researcher":
        return (
            f"The series indicates {accounts_per_capita:.2f} accounts per eligible person, "
            f"{digital_share_pct:.1f}% digital share, and {infra_per_100k:.1f} points per 100k people. "
            "This allows coherent comparison of access, usage, and capacity."
        )
    if lens == "Company":
        return (
            f"With {accounts_per_capita:.2f} accounts per eligible person, {digital_share_pct:.1f}% digital share, "
            f"and {infra_per_100k:.1f} points per 100k people, the data gives a practical signal for coverage planning "
            "and regional prioritization."
        )
    return (
        f"At {accounts_per_capita:.2f} accounts per eligible person and {digital_share_pct:.1f}% digital share, "
        f"the {infra_per_100k:.1f} points per 100k people indicate where local services and partnerships may scale faster."
    )


def audience_kpis(lens: str, *, lang: str) -> list[str]:
    if lang == "PT":
        mapping = {
            "Investidor": ["Escala de mercado", "Tração digital", "Capacidade instalada"],
            "Investigador": ["Inclusão financeira", "Adoção digital", "Infraestrutura per capita"],
            "Empresa": ["Base de clientes", "Canal digital", "Cobertura operacional"],
            "PME": ["Potencial local", "Uso digital", "Acesso a pontos"],
        }
        return mapping.get(lens, mapping["PME"])
    mapping = {
        "Investor": ["Market scale", "Digital traction", "Installed capacity"],
        "Researcher": ["Financial inclusion", "Digital adoption", "Infrastructure per capita"],
        "Company": ["Customer base", "Digital channel", "Operational coverage"],
        "SME": ["Local potential", "Digital usage", "Access points"],
    }
    return mapping.get(lens, mapping["SME"])
