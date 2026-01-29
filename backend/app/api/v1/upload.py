from fastapi import APIRouter, Depends, File, UploadFile, HTTPException, Form
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_db
from app.schemas.trip import TripRead
from app.services.csv_parser import CSVParser
from app.services.analytics import TripAnalytics, DrivingBehaviorAnalytics

router = APIRouter()


@router.post("/", response_model=TripRead)
async def upload_csv(
    file: UploadFile = File(...),
    name: str = Form(None),
    description: str = Form(None),
    db: AsyncSession = Depends(get_db),
):
    if not file.filename or not file.filename.endswith(".csv"):
        raise HTTPException(status_code=400, detail="File must be a CSV")

    content = await file.read()
    try:
        text = content.decode("utf-8-sig")
    except UnicodeDecodeError:
        text = content.decode("latin-1")

    parser = CSVParser(db)
    trip = await parser.parse_and_store(
        csv_text=text,
        filename=file.filename,
        name=name,
        description=description,
    )

    # Automatically run analytics
    trip_analytics = TripAnalytics(db)
    trip = await trip_analytics.calculate_all(trip.id)

    behavior_analytics = DrivingBehaviorAnalytics(db)
    await behavior_analytics.detect_events(trip.id)

    return trip
