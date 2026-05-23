from sqlalchemy import ForeignKey, Index, Integer, String, Text
from sqlalchemy.dialects.postgresql import TSVECTOR
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class RxnConcept(Base):
    __tablename__ = "rxn_concepts"

    rxcui: Mapped[int] = mapped_column(Integer, primary_key=True)
    tty: Mapped[str] = mapped_column(String(20), nullable=False, index=True)
    name: Mapped[str] = mapped_column(Text, nullable=False)
    suppress: Mapped[str] = mapped_column(String(1), default="N")
    search_vector: Mapped[str | None] = mapped_column(TSVECTOR)

    __table_args__ = (
        Index("idx_rxn_concepts_search", "search_vector", postgresql_using="gin"),
        Index("idx_rxn_concepts_rxcui_tty", "rxcui", "tty"),
    )


class RxnRelationship(Base):
    __tablename__ = "rxn_relationships"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    rxcui1: Mapped[int] = mapped_column(Integer, ForeignKey("rxn_concepts.rxcui"), nullable=False)
    rel: Mapped[str] = mapped_column(String(10), nullable=False)
    rela: Mapped[str | None] = mapped_column(String(60))
    rxcui2: Mapped[int] = mapped_column(Integer, ForeignKey("rxn_concepts.rxcui"), nullable=False)

    __table_args__ = (
        Index("idx_rxn_rel_rxcui1", "rxcui1"),
        Index("idx_rxn_rel_rxcui2", "rxcui2"),
        Index("idx_rxn_rel_rela", "rela"),
        Index("idx_rxn_rel_rxcui1_rela", "rxcui1", "rela"),
    )


class RxnAttribute(Base):
    __tablename__ = "rxn_attributes"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    rxcui: Mapped[int] = mapped_column(Integer, ForeignKey("rxn_concepts.rxcui"), nullable=False)
    atn: Mapped[str] = mapped_column(String(100), nullable=False)
    atv: Mapped[str | None] = mapped_column(Text)

    __table_args__ = (
        Index("idx_rxn_attr_rxcui", "rxcui"),
        Index("idx_rxn_attr_atn", "atn"),
        Index("idx_rxn_attr_atn_atv", "atn", "atv"),
    )
