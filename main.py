from __future__ import annotations

from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Optional

from fastapi import Depends, FastAPI, Form, HTTPException, Request
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from sqlalchemy import DateTime, Enum as SqlEnum, Float, Integer, String, create_engine, func
from sqlalchemy.orm import DeclarativeBase, Mapped, Session, mapped_column, sessionmaker


BASE_DIR = Path(__file__).resolve().parent
DB_PATH = BASE_DIR / "student_jobs.db"
DATABASE_URL = f"sqlite:///{DB_PATH}"

engine = create_engine(
    DATABASE_URL,
    connect_args={"check_same_thread": False},
    pool_pre_ping=True,
)
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)


class Base(DeclarativeBase):
    pass


class JobStatus(str, Enum):
    PENDING = "Pending"
    IN_PROGRESS = "In Progress"
    COMPLETED = "Completed"


class JobPriority(str, Enum):
    LOW = "Low"
    MEDIUM = "Medium"
    HIGH = "High"


STATUS_ORDER = [JobStatus.PENDING, JobStatus.IN_PROGRESS, JobStatus.COMPLETED]
PRIORITY_ORDER = [JobPriority.LOW, JobPriority.MEDIUM, JobPriority.HIGH]


class StudentJob(Base):
    __tablename__ = "student_jobs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    student_name: Mapped[str] = mapped_column(String(120), nullable=False)
    matric_number: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    course_code: Mapped[str] = mapped_column(String(30), nullable=False, index=True)
    status: Mapped[JobStatus] = mapped_column(
        SqlEnum(JobStatus, native_enum=False), nullable=False, default=JobStatus.PENDING
    )
    priority: Mapped[JobPriority] = mapped_column(
        SqlEnum(JobPriority, native_enum=False), nullable=False, default=JobPriority.MEDIUM
    )
    fee_total: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    fee_paid: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, server_default=func.now())

    @property
    def fee_outstanding(self) -> float:
        return max(0.0, round(self.fee_total - self.fee_paid, 2))


Base.metadata.create_all(bind=engine)

app = FastAPI(title="Student Job Tracker")

templates = Jinja2Templates(directory=str(BASE_DIR / "templates"))


if not (BASE_DIR / "static").exists():
    (BASE_DIR / "static").mkdir(parents=True, exist_ok=True)
app.mount("/static", StaticFiles(directory=str(BASE_DIR / "static")), name="static")


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def parse_non_negative_float(value: str, field_name: str) -> float:
    try:
        parsed = float(value)
    except (TypeError, ValueError) as exc:
        raise HTTPException(status_code=400, detail=f"{field_name} must be a valid number.") from exc

    if parsed < 0:
        raise HTTPException(status_code=400, detail=f"{field_name} cannot be negative.")
    return round(parsed, 2)


def get_job_or_404(db: Session, job_id: int) -> StudentJob:
    job = db.get(StudentJob, job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found.")
    return job


def get_metrics(db: Session) -> dict[str, float | int]:
    jobs = db.query(StudentJob).all()
    total_active_jobs = sum(1 for j in jobs if j.status != JobStatus.COMPLETED)
    total_cash_collected = round(sum(j.fee_paid for j in jobs), 2)
    total_debt_owed = round(sum(max(0.0, j.fee_total - j.fee_paid) for j in jobs), 2)
    return {
        "total_active_jobs": total_active_jobs,
        "total_cash_collected": total_cash_collected,
        "total_debt_owed": total_debt_owed,
    }


@app.get("/", response_class=HTMLResponse)
def index(request: Request, db: Session = Depends(get_db), error: Optional[str] = None):
    jobs = db.query(StudentJob).order_by(StudentJob.created_at.desc(), StudentJob.id.desc()).all()
    return templates.TemplateResponse(
        "index.html",
        {
            "request": request,
            "jobs": jobs,
            "metrics": get_metrics(db),
            "status_values": [status.value for status in STATUS_ORDER],
            "priority_values": [priority.value for priority in PRIORITY_ORDER],
            "error": error,
        },
    )


@app.get("/partials/metrics", response_class=HTMLResponse)
def metrics_partial(request: Request, db: Session = Depends(get_db)):
    return templates.TemplateResponse(
        "partials/metrics.html", {"request": request, "metrics": get_metrics(db)}
    )


@app.get("/partials/table", response_class=HTMLResponse)
def table_partial(request: Request, db: Session = Depends(get_db)):
    jobs = db.query(StudentJob).order_by(StudentJob.created_at.desc(), StudentJob.id.desc()).all()
    return templates.TemplateResponse(
        "partials/table.html",
        {
            "request": request,
            "jobs": jobs,
            "status_values": [status.value for status in STATUS_ORDER],
            "priority_values": [priority.value for priority in PRIORITY_ORDER],
        },
    )


@app.get("/partials/row/{job_id}", response_class=HTMLResponse)
def row_partial(job_id: int, request: Request, db: Session = Depends(get_db)):
    job = get_job_or_404(db, job_id)
    return templates.TemplateResponse(
        "partials/row.html",
        {
            "request": request,
            "job": job,
            "status_values": [status.value for status in STATUS_ORDER],
            "priority_values": [priority.value for priority in PRIORITY_ORDER],
        },
    )


@app.post("/jobs", response_class=HTMLResponse)
def add_job(
    request: Request,
    student_name: str = Form(...),
    matric_number: str = Form(...),
    course_code: str = Form(...),
    fee_total: str = Form("0"),
    fee_paid: str = Form("0"),
    status: JobStatus = Form(JobStatus.PENDING),
    priority: JobPriority = Form(JobPriority.MEDIUM),
    db: Session = Depends(get_db),
):
    if not student_name.strip() or not matric_number.strip() or not course_code.strip():
        raise HTTPException(status_code=400, detail="Name, matric number, and course code are required.")

    parsed_total = parse_non_negative_float(fee_total, "Fee total")
    parsed_paid = parse_non_negative_float(fee_paid, "Fee paid")

    if parsed_paid > parsed_total:
        raise HTTPException(status_code=400, detail="Fee paid cannot exceed fee total.")

    job = StudentJob(
        student_name=student_name.strip(),
        matric_number=matric_number.strip(),
        course_code=course_code.strip().upper(),
        fee_total=parsed_total,
        fee_paid=parsed_paid,
        status=status,
        priority=priority,
    )
    db.add(job)
    db.commit()

    jobs = db.query(StudentJob).order_by(StudentJob.created_at.desc(), StudentJob.id.desc()).all()
    return templates.TemplateResponse(
        "partials/table.html",
        {
            "request": request,
            "jobs": jobs,
            "status_values": [status.value for status in STATUS_ORDER],
            "priority_values": [priority.value for priority in PRIORITY_ORDER],
        },
        headers={"HX-Trigger": "refresh-metrics"},
    )


@app.post("/jobs/{job_id}/status", response_class=HTMLResponse)
def cycle_status(job_id: int, request: Request, db: Session = Depends(get_db)):
    job = get_job_or_404(db, job_id)
    current_index = STATUS_ORDER.index(job.status)
    job.status = STATUS_ORDER[(current_index + 1) % len(STATUS_ORDER)]
    db.commit()
    db.refresh(job)

    return templates.TemplateResponse(
        "partials/row.html",
        {
            "request": request,
            "job": job,
            "status_values": [status.value for status in STATUS_ORDER],
            "priority_values": [priority.value for priority in PRIORITY_ORDER],
        },
        headers={"HX-Trigger": "refresh-metrics"},
    )


@app.post("/jobs/{job_id}/priority", response_class=HTMLResponse)
def cycle_priority(job_id: int, request: Request, db: Session = Depends(get_db)):
    job = get_job_or_404(db, job_id)
    current_index = PRIORITY_ORDER.index(job.priority)
    job.priority = PRIORITY_ORDER[(current_index + 1) % len(PRIORITY_ORDER)]
    db.commit()
    db.refresh(job)

    return templates.TemplateResponse(
        "partials/row.html",
        {
            "request": request,
            "job": job,
            "status_values": [status.value for status in STATUS_ORDER],
            "priority_values": [priority.value for priority in PRIORITY_ORDER],
        },
    )


@app.post("/jobs/{job_id}/fee-paid", response_class=HTMLResponse)
def update_fee_paid(
    job_id: int,
    request: Request,
    fee_paid: str = Form(...),
    db: Session = Depends(get_db),
):
    job = get_job_or_404(db, job_id)
    parsed_paid = parse_non_negative_float(fee_paid, "Fee paid")

    if parsed_paid > job.fee_total:
        raise HTTPException(status_code=400, detail="Fee paid cannot exceed fee total.")

    job.fee_paid = parsed_paid
    db.commit()
    db.refresh(job)

    return templates.TemplateResponse(
        "partials/row.html",
        {
            "request": request,
            "job": job,
            "status_values": [status.value for status in STATUS_ORDER],
            "priority_values": [priority.value for priority in PRIORITY_ORDER],
        },
        headers={"HX-Trigger": "refresh-metrics"},
    )


@app.delete("/jobs/{job_id}", response_class=HTMLResponse)
def delete_job(job_id: int, request: Request, db: Session = Depends(get_db)):
    job = get_job_or_404(db, job_id)
    db.delete(job)
    db.commit()

    jobs = db.query(StudentJob).order_by(StudentJob.created_at.desc(), StudentJob.id.desc()).all()
    return templates.TemplateResponse(
        "partials/table.html",
        {
            "request": request,
            "jobs": jobs,
            "status_values": [status.value for status in STATUS_ORDER],
            "priority_values": [priority.value for priority in PRIORITY_ORDER],
        },
        headers={"HX-Trigger": "refresh-metrics"},
    )


@app.exception_handler(HTTPException)
async def http_exception_handler(request: Request, exc: HTTPException):
    if request.headers.get("HX-Request") == "true":
        response = templates.TemplateResponse(
            "partials/error.html", {"request": request, "error": exc.detail}, status_code=exc.status_code
        )
        response.headers["HX-Retarget"] = "#form-error"
        response.headers["HX-Reswap"] = "innerHTML"
        return response
    return templates.TemplateResponse(
        "index.html",
        {
            "request": request,
            "jobs": [],
            "metrics": {"total_active_jobs": 0, "total_cash_collected": 0.0, "total_debt_owed": 0.0},
            "status_values": [status.value for status in STATUS_ORDER],
            "priority_values": [priority.value for priority in PRIORITY_ORDER],
            "error": str(exc.detail),
        },
        status_code=exc.status_code,
    )


if __name__ == "__main__":
    import uvicorn

    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
