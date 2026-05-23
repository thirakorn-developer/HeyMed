from sqlalchemy import Date, Index, Integer, String, Text
from sqlalchemy.dialects.postgresql import TSVECTOR
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class NdcProduct(Base):
    __tablename__ = "ndc_products"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    product_ndc: Mapped[str] = mapped_column(String(20), nullable=False, index=True)
    product_type: Mapped[str] = mapped_column(String(100))
    brand_name: Mapped[str | None] = mapped_column(String(500))
    brand_name_suffix: Mapped[str | None] = mapped_column(String(200))
    generic_name: Mapped[str | None] = mapped_column(Text)
    dosage_form: Mapped[str | None] = mapped_column(String(200))
    route: Mapped[str | None] = mapped_column(String(200))
    marketing_category: Mapped[str | None] = mapped_column(String(100))
    application_number: Mapped[str | None] = mapped_column(String(50))
    labeler_name: Mapped[str | None] = mapped_column(String(500))
    substance_name: Mapped[str | None] = mapped_column(Text)
    strength: Mapped[str | None] = mapped_column(Text)
    strength_unit: Mapped[str | None] = mapped_column(Text)
    pharm_classes: Mapped[str | None] = mapped_column(Text)
    dea_schedule: Mapped[str | None] = mapped_column(String(10))
    search_vector: Mapped[str | None] = mapped_column(TSVECTOR)

    __table_args__ = (
        Index("idx_ndc_product_search", "search_vector", postgresql_using="gin"),
        Index("idx_ndc_product_brand", "brand_name"),
        Index("idx_ndc_product_generic", "generic_name"),
    )


class NdcPackage(Base):
    __tablename__ = "ndc_packages"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    product_ndc: Mapped[str] = mapped_column(String(20), nullable=False, index=True)
    ndc_package_code: Mapped[str] = mapped_column(String(20), nullable=False, unique=True)
    package_description: Mapped[str | None] = mapped_column(Text)

    __table_args__ = (
        Index("idx_ndc_package_code", "ndc_package_code"),
    )
