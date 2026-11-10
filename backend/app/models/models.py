from datetime import datetime, timezone
from uuid import uuid4

from sqlalchemy import JSON, Boolean, CheckConstraint, Column, DateTime, Float, ForeignKey, Index, Integer, String, Text
from sqlalchemy.orm import relationship

from app.core.db import Base


def utcnow():
    return datetime.now(timezone.utc)


def uuid() -> str:
    return str(uuid4())


class User(Base):
    __tablename__ = "users"

    user_id = Column(String(36), primary_key=True, default=uuid)
    full_name = Column(String(255), nullable=False)
    email = Column(String(255), unique=True, nullable=False, index=True)
    password_hash = Column(String(255), nullable=False)
    major_name = Column(String(100), nullable=False)
    campus_name = Column(String(255), nullable=False)
    # Data sampul skripsi (dipakai semua proyek). major_name = program studi.
    nim = Column(String(40), nullable=False, default="", server_default="")
    faculty = Column(String(150), nullable=False, default="", server_default="")
    city = Column(String(80), nullable=False, default="", server_default="")
    logo_data = Column(Text, nullable=True)  # data URL PNG, maks 300 KB
    notify_prefs = Column(JSON, nullable=True)
    last_reminder_at = Column(DateTime(timezone=True), nullable=True)
    daily_goal = Column(Integer, nullable=False, default=300, server_default="300")  # target kata per hari
    created_at = Column(DateTime(timezone=True), default=utcnow)

    theses = relationship("Thesis", back_populates="owner", cascade="all, delete-orphan")


class Thesis(Base):
    __tablename__ = "theses"
    __table_args__ = (
        CheckConstraint(
            "research_method IN ('KUANTITATIF','KUALITATIF','MIXED_METHODS','RND')",
            name="ck_theses_method",
        ),
        CheckConstraint(
            "domain_category IN ('INFORMATIKA','ENGLISH_EDUCATION','UMUM')",
            name="ck_theses_domain",
        ),
    )

    thesis_id = Column(String(36), primary_key=True, default=uuid)
    user_id = Column(String(36), ForeignKey("users.user_id", ondelete="CASCADE"), nullable=False, index=True)
    title = Column(Text, nullable=False)
    research_method = Column(String(50), nullable=False)
    domain_category = Column(String(100), nullable=False)
    degree_level = Column(String(2), default="S1")
    # Bahasa naskah skripsi: "id" = Bahasa Indonesia, "en" = English (isi, judul bab, dan ekspor).
    language = Column(String(2), nullable=False, default="id", server_default="id")
    campus_template_id = Column(String(100), nullable=False)

    variable_x = Column(String(255), default="")
    variable_y = Column(String(255), default="")
    subject = Column(String(255), default="")

    picked_title_id = Column(String(36), nullable=True)
    selected_ref_ids = Column(JSON, default=list)
    charts_json = Column(JSON, default=list)
    diagrams_json = Column(JSON, default=list)
    review_json = Column(JSON, default=dict)
    brief_json = Column(JSON, nullable=True)  # kerangka dari peneliti: topik, fenomena, masalah, teori, metode
    front_json = Column(JSON, nullable=True)  # abstrak id/en, kata kunci, kata pengantar
    appendix_json = Column(JSON, nullable=True)  # lampiran instrumen: [{id,title,intro,items}]
    share_token = Column(String(48), unique=True, nullable=True, index=True)
    cover_json = Column(JSON, nullable=True)  # opsi sampul per proyek (tahun, pembimbing, jenis dokumen)

    status = Column(String(50), default="IN_PROGRESS")
    # NEW = dibuat dari awal; EXISTING = melanjutkan judul/bab milik pengguna.
    source_mode = Column(String(10), nullable=False, default="NEW", server_default="NEW")
    created_at = Column(DateTime(timezone=True), default=utcnow)
    updated_at = Column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)

    owner = relationship("User", back_populates="theses")
    citations = relationship("Citation", back_populates="thesis", cascade="all, delete-orphan")
    sections = relationship("ThesisSection", back_populates="thesis", cascade="all, delete-orphan")
    title_options = relationship("TitleOption", back_populates="thesis", cascade="all, delete-orphan")
    versions = relationship("SectionVersion", cascade="all, delete-orphan")
    research_data = relationship("ResearchData", cascade="all, delete-orphan", order_by="ResearchData.created_at")
    tables = relationship(
        "ThesisTable", back_populates="thesis", cascade="all, delete-orphan", order_by="ThesisTable.created_at"
    )


class Citation(Base):
    __tablename__ = "citations"

    citation_id = Column(String(36), primary_key=True, default=uuid)
    thesis_id = Column(String(36), ForeignKey("theses.thesis_id", ondelete="CASCADE"), nullable=False, index=True)
    doi = Column(String(255), nullable=True)
    title = Column(Text, nullable=False)
    authors = Column(JSON, nullable=False, default=list)
    publication_year = Column(Integer, nullable=False)
    journal_name = Column(String(255), nullable=True)
    volume_issue = Column(String(100), nullable=True)
    page_range = Column(String(50), nullable=True)
    pdf_url = Column(Text, nullable=True)
    highlighted_snippet = Column(Text, nullable=False, default="")
    page_number = Column(Integer, default=1)
    source_database = Column(String(50), nullable=False)
    cited_by = Column(Integer, default=0)
    created_at = Column(DateTime(timezone=True), default=utcnow)

    thesis = relationship("Thesis", back_populates="citations")


class ThesisSection(Base):
    __tablename__ = "thesis_sections"
    # Satu subbab per kode pada satu proyek; permintaan build yang berbarengan tidak boleh menggandakannya.
    __table_args__ = (Index("uq_section_thesis_code", "thesis_id", "section_code", unique=True),)

    section_id = Column(String(36), primary_key=True, default=uuid)
    thesis_id = Column(String(36), ForeignKey("theses.thesis_id", ondelete="CASCADE"), nullable=False, index=True)
    chapter_code = Column(String(20), nullable=False)
    section_code = Column(String(20), nullable=False)
    section_title = Column(String(255), nullable=False)
    content_markdown = Column(Text, nullable=False, default="")
    citations_json = Column(JSON, default=list)
    word_count = Column(Integer, default=0)
    target_words = Column(Integer, default=0)
    version_number = Column(Integer, default=1)
    # IMPORTED = tulisan pengguna (tidak ditimpa AI tanpa konfirmasi); GENERATED = ditulis agen.
    origin = Column(String(12), nullable=False, default="GENERATED", server_default="GENERATED")
    created_at = Column(DateTime(timezone=True), default=utcnow)
    updated_at = Column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)

    thesis = relationship("Thesis", back_populates="sections")


class TitleOption(Base):
    __tablename__ = "title_options"

    title_id = Column(String(36), primary_key=True, default=uuid)
    thesis_id = Column(String(36), ForeignKey("theses.thesis_id", ondelete="CASCADE"), nullable=False, index=True)
    text = Column(Text, nullable=False)
    rationale = Column(Text, default="")
    gap = Column(Text, default="")
    score = Column(Float, nullable=True)

    thesis = relationship("Thesis", back_populates="title_options")


class PipelineJob(Base):
    __tablename__ = "pipeline_jobs"

    job_id = Column(String(36), primary_key=True, default=uuid)
    thesis_id = Column(String(36), ForeignKey("theses.thesis_id", ondelete="CASCADE"), nullable=False, index=True)
    status = Column(String(20), default="QUEUED")
    current_step = Column(String(60), default="")
    logs = Column(JSON, default=list)
    error = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), default=utcnow)
    finished_at = Column(DateTime(timezone=True), nullable=True)


class RagDocument(Base):
    __tablename__ = "rag_documents"

    doc_id = Column(String(64), primary_key=True)
    thesis_id = Column(String(36), ForeignKey("theses.thesis_id", ondelete="CASCADE"), nullable=False, index=True)
    source_type = Column(String(30), default="citation")
    content = Column(Text, nullable=False)
    meta_json = Column(JSON, default=dict)


class ThesisTable(Base):
    """Tabel hasil (mis. statistik deskriptif & uji beda) yang disisipkan ke Bab IV."""

    __tablename__ = "thesis_tables"

    table_id = Column(String(36), primary_key=True, default=uuid)
    thesis_id = Column(String(36), ForeignKey("theses.thesis_id", ondelete="CASCADE"), nullable=False, index=True)
    title = Column(String(255), nullable=False)
    caption = Column(Text, default="")
    columns_json = Column(JSON, default=list)
    rows_json = Column(JSON, default=list)
    note = Column(Text, default="")
    # Bab tempat tabel disisipkan (mis. 3 untuk profil partisipan, 4 untuk hasil uji).
    chapter_code = Column(String(4), nullable=False, default="4", server_default="4")
    created_at = Column(DateTime(timezone=True), default=utcnow)

    thesis = relationship("Thesis", back_populates="tables")


class CustomTemplate(Base):
    """Templat kampus hasil parsing PDF pedoman, milik satu pengguna."""

    __tablename__ = "custom_templates"

    template_id = Column(String(60), primary_key=True)
    user_id = Column(String(36), ForeignKey("users.user_id", ondelete="CASCADE"), nullable=False, index=True)
    name = Column(String(255), nullable=False)
    source_filename = Column(String(255), default="")
    spec_json = Column(JSON, nullable=False)
    report_json = Column(JSON, default=dict)
    created_at = Column(DateTime(timezone=True), default=utcnow)


class SectionVersion(Base):
    """Salinan subbab sebelum ditimpa (buat ulang atau perbaikan), agar perubahan bisa diurungkan."""

    __tablename__ = "section_versions"

    version_id = Column(String(36), primary_key=True, default=uuid)
    thesis_id = Column(String(36), ForeignKey("theses.thesis_id", ondelete="CASCADE"), nullable=False, index=True)
    section_id = Column(String(36), nullable=False, index=True)
    section_code = Column(String(20), nullable=False)
    content_markdown = Column(Text, nullable=False, default="")
    citations_json = Column(JSON, default=list)
    reason = Column(String(40), default="")
    created_at = Column(DateTime(timezone=True), default=utcnow)


class ShareComment(Base):
    """Komentar dosen pembimbing lewat tautan baca-saja."""

    __tablename__ = "share_comments"

    comment_id = Column(String(36), primary_key=True, default=uuid)
    thesis_id = Column(String(36), ForeignKey("theses.thesis_id", ondelete="CASCADE"), nullable=False, index=True)
    section_code = Column(String(20), nullable=False, default="")
    author = Column(String(80), nullable=False, default="Pembimbing")
    text = Column(Text, nullable=False)
    resolved = Column(Boolean, nullable=False, default=False, server_default="0")
    created_at = Column(DateTime(timezone=True), default=utcnow)


class WritingActivity(Base):
    """Jumlah kata yang ditulis/diubah per pengguna per hari (untuk target harian dan streak)."""

    __tablename__ = "writing_activity"
    __table_args__ = (Index("uq_activity_user_day", "user_id", "day", unique=True),)

    activity_id = Column(String(36), primary_key=True, default=uuid)
    user_id = Column(String(36), ForeignKey("users.user_id", ondelete="CASCADE"), nullable=False, index=True)
    day = Column(String(10), nullable=False)  # YYYY-MM-DD
    words = Column(Integer, nullable=False, default=0)


class ResearchData(Base):
    """Data penelitian milik pengguna (tabel CSV atau teks) untuk Bab IV, beserta hasil olah agen."""

    __tablename__ = "research_data"

    data_id = Column(String(36), primary_key=True, default=uuid)
    thesis_id = Column(String(36), ForeignKey("theses.thesis_id", ondelete="CASCADE"), nullable=False, index=True)
    title = Column(String(150), nullable=False)
    kind = Column(String(10), nullable=False)  # table | text
    content = Column(Text, nullable=False, default="")
    analysis_json = Column(JSON, nullable=True)
    created_at = Column(DateTime(timezone=True), default=utcnow)
